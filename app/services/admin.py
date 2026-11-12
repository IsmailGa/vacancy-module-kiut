from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.models.applications import Application
from app.models.users import User
from app.schemas.admin import AdminApplicationFilter, AdminUserFilter


async def list_users(db: AsyncSession, filters: AdminUserFilter) -> tuple[Sequence[User], int]:
    """Все пользователи с поиском по ФИО, email и ID студента. Только для админки."""
    query = select(User)
    if filters.q:
        escaped = filters.q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped}%"
        query = query.where(
            or_(
                User.full_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
                User.student_id.ilike(pattern, escape="\\"),
                User.organization.ilike(pattern, escape="\\"),
            )
        )
    if filters.role is not None:
        query = query.where(User.role == filters.role)
    if filters.is_active is not None:
        query = query.where(User.is_active == filters.is_active)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    items = await db.scalars(
        query.order_by(User.created_at.desc(), User.id.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    )
    return items.all(), total or 0


async def set_user_active(db: AsyncSession, user_id: int, admin: User, is_active: bool) -> User:
    """Блокирует или разблокирует учётную запись. Самого себя отключить нельзя."""
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("Пользователь не найден", "user_not_found")
    if user.id == admin.id and not is_active:
        raise ConflictError("Нельзя отключить собственную учётную запись", "cannot_deactivate_self")
    user.is_active = is_active
    await db.commit()
    return user


async def list_applications(
    db: AsyncSession, filters: AdminApplicationFilter
) -> tuple[Sequence[Application], int]:
    """Все отклики портала с вакансией и студентом, новые сверху. Только для админки."""
    query = select(Application)
    if filters.status is not None:
        query = query.where(Application.status == filters.status)
    if filters.vacancy_id is not None:
        query = query.where(Application.vacancy_id == filters.vacancy_id)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    items = await db.scalars(
        query.options(selectinload(Application.vacancy), selectinload(Application.student))
        .order_by(Application.created_at.desc(), Application.id.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    )
    return items.all(), total or 0
