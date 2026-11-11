from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import InvalidStateError, NotFoundError, UnprocessableError
from app.models.categories import Category
from app.models.users import User, UserRole
from app.models.vacancies import Vacancy, VacancyStatus
from app.schemas.vacancies import (
    SALARY_ORDER_MESSAGE,
    VacancyCreate,
    VacancyFilter,
    VacancySort,
    VacancyUpdate,
    today_utc,
)

# Таблица разрешённых переходов статуса. Всё, чего здесь нет, даёт 409.
ALLOWED_TRANSITIONS: dict[VacancyStatus, frozenset[VacancyStatus]] = {
    VacancyStatus.DRAFT: frozenset({VacancyStatus.PENDING}),
    VacancyStatus.PENDING: frozenset({VacancyStatus.PUBLISHED, VacancyStatus.REJECTED}),
    VacancyStatus.REJECTED: frozenset({VacancyStatus.PENDING}),
    VacancyStatus.PUBLISHED: frozenset({VacancyStatus.CLOSED}),
    VacancyStatus.CLOSED: frozenset(),
}
EDITABLE_STATUSES = frozenset({VacancyStatus.DRAFT, VacancyStatus.REJECTED})

_WITH_RELATIONS = (selectinload(Vacancy.category), selectinload(Vacancy.employer))
_NOT_FOUND = ("Вакансия не найдена", "vacancy_not_found")


def _change_status(vacancy: Vacancy, new_status: VacancyStatus) -> None:
    """Единственное место, где меняется статус вакансии."""
    if new_status not in ALLOWED_TRANSITIONS[vacancy.status]:
        raise InvalidStateError(
            f"Нельзя перевести вакансию из статуса «{vacancy.status.value}» в «{new_status.value}»",
            "invalid_status_transition",
        )
    vacancy.status = new_status


async def _load(db: AsyncSession, vacancy_id: int) -> Vacancy | None:
    """Вакансия вместе с категорией и работодателем (свежие данные из БД)."""
    query = (
        select(Vacancy)
        .where(Vacancy.id == vacancy_id)
        .options(*_WITH_RELATIONS)
        .execution_options(populate_existing=True)
    )
    return await db.scalar(query)


async def _page(
    db: AsyncSession, query: Select, order_by: tuple, limit: int, offset: int
) -> tuple[Sequence[Vacancy], int]:
    """Страница результата + общее количество (COUNT по тому же фильтру)."""
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    items = await db.scalars(
        query.options(*_WITH_RELATIONS).order_by(*order_by).limit(limit).offset(offset)
    )
    return items.all(), total or 0


async def _ensure_category_exists(db: AsyncSession, category_id: int) -> None:
    if await db.get(Category, category_id) is None:
        raise UnprocessableError(
            "body.category_id", "Категория не найдена", code="category_not_found"
        )


async def list_published(db: AsyncSession, filters: VacancyFilter) -> tuple[Sequence[Vacancy], int]:
    """Публичная лента: только published и не просроченные, с фильтрами из query-параметров."""
    query = select(Vacancy).where(
        Vacancy.status == VacancyStatus.PUBLISHED, Vacancy.deadline >= today_utc()
    )
    if filters.q:
        pattern = (
            "%" + filters.q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
        )
        query = query.where(
            or_(
                Vacancy.title.ilike(pattern, escape="\\"),
                Vacancy.description.ilike(pattern, escape="\\"),
            )
        )
    if filters.category_id is not None:
        query = query.where(Vacancy.category_id == filters.category_id)
    if filters.employment_type is not None:
        query = query.where(Vacancy.employment_type == filters.employment_type)
    if filters.is_remote is not None:
        query = query.where(Vacancy.is_remote == filters.is_remote)
    top_salary = func.coalesce(Vacancy.salary_max, Vacancy.salary_min)
    if filters.salary_from is not None:
        query = query.where(top_salary >= filters.salary_from)
    if filters.course is not None:
        # target_course — подсказка: вакансии «для всех курсов» тоже подходят.
        query = query.where(
            or_(Vacancy.target_course.is_(None), Vacancy.target_course == filters.course)
        )

    order_by = {
        VacancySort.NEWEST: (Vacancy.published_at.desc(), Vacancy.id.desc()),
        VacancySort.DEADLINE: (Vacancy.deadline.asc(), Vacancy.id.desc()),
        VacancySort.SALARY: (top_salary.desc().nulls_last(), Vacancy.id.desc()),
    }[filters.sort]
    return await _page(db, query, order_by, filters.limit, filters.offset)


async def get_visible(db: AsyncSession, vacancy_id: int, user: User | None) -> Vacancy:
    """Одна вакансия: опубликованную видят все, остальные только владелец и admin."""
    vacancy = await _load(db, vacancy_id)
    if vacancy is None:
        raise NotFoundError(*_NOT_FOUND)
    if vacancy.status is VacancyStatus.PUBLISHED:
        return vacancy
    is_owner = user is not None and vacancy.employer_id == user.id
    is_admin = user is not None and user.role is UserRole.ADMIN
    if not (is_owner or is_admin):
        raise NotFoundError(*_NOT_FOUND)
    return vacancy


async def get_owned(db: AsyncSession, vacancy_id: int, employer: User) -> Vacancy:
    """Вакансия текущего работодателя. Чужая отдаётся как 404, чтобы не раскрывать её."""
    vacancy = await _load(db, vacancy_id)
    if vacancy is None or vacancy.employer_id != employer.id:
        raise NotFoundError(*_NOT_FOUND)
    return vacancy


async def list_my(
    db: AsyncSession, employer: User, status: VacancyStatus | None, limit: int, offset: int
) -> tuple[Sequence[Vacancy], int]:
    """Вакансии текущего работодателя в любом статусе."""
    query = select(Vacancy).where(Vacancy.employer_id == employer.id)
    if status is not None:
        query = query.where(Vacancy.status == status)
    return await _page(db, query, (Vacancy.created_at.desc(), Vacancy.id.desc()), limit, offset)


async def list_for_admin(
    db: AsyncSession, status: VacancyStatus | None, limit: int, offset: int
) -> tuple[Sequence[Vacancy], int]:
    """Очередь модерации: вакансии всех работодателей, старые сверху."""
    query = select(Vacancy)
    if status is not None:
        query = query.where(Vacancy.status == status)
    return await _page(db, query, (Vacancy.updated_at.asc(), Vacancy.id.asc()), limit, offset)


async def create_vacancy(db: AsyncSession, employer: User, data: VacancyCreate) -> Vacancy:
    """Создаёт черновик вакансии от имени работодателя."""
    await _ensure_category_exists(db, data.category_id)
    vacancy = Vacancy(**data.model_dump(), employer_id=employer.id, status=VacancyStatus.DRAFT)
    db.add(vacancy)
    await db.commit()
    return await _load(db, vacancy.id)


async def update_vacancy(
    db: AsyncSession, vacancy_id: int, employer: User, data: VacancyUpdate
) -> Vacancy:
    """Правит свою вакансию. Разрешено только в статусах draft и rejected."""
    vacancy = await get_owned(db, vacancy_id, employer)
    if vacancy.status not in EDITABLE_STATUSES:
        raise InvalidStateError(
            "Редактировать можно только черновик или отклонённую вакансию",
            "vacancy_not_editable",
        )
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        await _ensure_category_exists(db, changes["category_id"])

    # Схема сравнивает зарплаты, только если переданы обе; здесь сверяем с сохранённым значением.
    salary_min = changes.get("salary_min", vacancy.salary_min)
    salary_max = changes.get("salary_max", vacancy.salary_max)
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        field = "body.salary_max" if "salary_max" in changes else "body.salary_min"
        raise UnprocessableError(field, SALARY_ORDER_MESSAGE)

    for field, value in changes.items():
        setattr(vacancy, field, value)
    await db.commit()
    return await _load(db, vacancy.id)


async def delete_vacancy(db: AsyncSession, vacancy_id: int, employer: User) -> None:
    """Удаляет свою вакансию. Разрешено только для черновика."""
    vacancy = await get_owned(db, vacancy_id, employer)
    if vacancy.status is not VacancyStatus.DRAFT:
        raise InvalidStateError("Удалить можно только черновик", "vacancy_not_deletable")
    await db.delete(vacancy)
    await db.commit()


async def submit_vacancy(db: AsyncSession, vacancy_id: int, employer: User) -> Vacancy:
    """Отправляет на модерацию: draft/rejected -> pending."""
    vacancy = await get_owned(db, vacancy_id, employer)
    _change_status(vacancy, VacancyStatus.PENDING)
    if vacancy.deadline <= today_utc():
        raise InvalidStateError(
            "Дедлайн вакансии уже прошёл, обновите его перед отправкой", "vacancy_deadline_passed"
        )
    await db.commit()
    return await _load(db, vacancy.id)


async def close_vacancy(db: AsyncSession, vacancy_id: int, employer: User) -> Vacancy:
    """Снимает с публикации: published -> closed."""
    vacancy = await get_owned(db, vacancy_id, employer)
    _change_status(vacancy, VacancyStatus.CLOSED)
    await db.commit()
    return await _load(db, vacancy.id)


async def _get_for_moderation(db: AsyncSession, vacancy_id: int) -> Vacancy:
    vacancy = await _load(db, vacancy_id)
    if vacancy is None:
        raise NotFoundError(*_NOT_FOUND)
    return vacancy


async def approve_vacancy(db: AsyncSession, vacancy_id: int) -> Vacancy:
    """Одобрение админом: pending -> published, фиксируется время публикации."""
    vacancy = await _get_for_moderation(db, vacancy_id)
    _change_status(vacancy, VacancyStatus.PUBLISHED)
    vacancy.published_at = datetime.now(UTC)
    vacancy.moderation_comment = None
    await db.commit()
    return await _load(db, vacancy.id)


async def reject_vacancy(db: AsyncSession, vacancy_id: int, comment: str) -> Vacancy:
    """Отклонение админом: pending -> rejected, комментарий виден работодателю."""
    vacancy = await _get_for_moderation(db, vacancy_id)
    _change_status(vacancy, VacancyStatus.REJECTED)
    vacancy.moderation_comment = comment
    await db.commit()
    return await _load(db, vacancy.id)
