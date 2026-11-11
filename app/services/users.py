from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError, UnprocessableError
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.models.users import User, UserRole
from app.schemas.users import STUDENT_ID_RE, UserCreate, UserUpdate


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Поиск пользователя по email (в БД хранится в нижнем регистре)."""
    return await db.scalar(select(User).where(User.email == email.lower()))


async def get_user_by_login(db: AsyncSession, login: str) -> User | None:
    """Логин — это email или 7-значный ID студента."""
    login = login.strip()
    if STUDENT_ID_RE.match(login):
        return await db.scalar(select(User).where(User.student_id == login))
    return await get_user_by_email(db, login)


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    """Создаёт студента или работодателя. Вызывается из POST /auth/register."""
    if await get_user_by_email(db, data.email):
        raise ConflictError("Пользователь с таким email уже зарегистрирован", "email_taken")

    if data.student_id is not None and await db.scalar(
        select(User.id).where(User.student_id == data.student_id)
    ):
        raise ConflictError("Этот ID студента уже зарегистрирован", "student_id_taken")

    user = User(
        email=data.email,
        student_id=data.student_id,
        full_name=data.full_name,
        phone=data.phone,
        hashed_password=await run_in_threadpool(hash_password, data.password),
        role=data.role,
        course=data.course,
        organization=data.organization,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(
            "Пользователь с таким email уже зарегистрирован", "email_taken"
        ) from None
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> str:
    """Проверяет логин (email или ID студента) и пароль, возвращает JWT. Вызывается из POST /auth/login."""
    user = await get_user_by_login(db, email)
    hashed = user.hashed_password if user else DUMMY_HASH
    password_ok = await run_in_threadpool(verify_password, password, hashed)
    if user is None or not password_ok:
        raise UnauthorizedError("Неверный логин или пароль", "invalid_credentials")
    if not user.is_active:
        raise ForbiddenError("Учётная запись отключена", "user_inactive")
    return create_access_token(user.id)


async def update_profile(db: AsyncSession, user: User, data: UserUpdate) -> User:
    """Меняет профиль текущего пользователя. course доступен студенту, organization работодателю."""
    changes = data.model_dump(exclude_unset=True)

    if "course" in changes:
        if user.role is not UserRole.STUDENT:
            raise UnprocessableError("body.course", "Курс указывается только студентом")
        if changes["course"] is None:
            raise UnprocessableError("body.course", "Для студента нужно указать курс (1–6)")
    if "organization" in changes:
        if user.role is not UserRole.EMPLOYER:
            raise UnprocessableError(
                "body.organization", "Организация указывается только работодателем"
            )
        if changes["organization"] is None:
            raise UnprocessableError(
                "body.organization", "Для работодателя нужно указать организацию"
            )

    for field, value in changes.items():
        setattr(user, field, value)
    await db.commit()
    return user
