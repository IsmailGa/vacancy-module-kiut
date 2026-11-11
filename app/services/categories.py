from collections.abc import Sequence

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.categories import Category
from app.models.vacancies import Vacancy
from app.schemas.categories import CategoryCreate, CategoryUpdate


async def list_categories(db: AsyncSession) -> Sequence[Category]:
    """Все категории по алфавиту. Публичный справочник для фильтра и формы вакансии."""
    return (await db.scalars(select(Category).order_by(Category.name))).all()


async def get_category(db: AsyncSession, category_id: int) -> Category:
    category = await db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Категория не найдена", "category_not_found")
    return category


async def _ensure_unique(
    db: AsyncSession, name: str | None, slug: str | None, exclude_id: int | None = None
) -> None:
    conditions = []
    if name is not None:
        conditions.append(Category.name == name)
    if slug is not None:
        conditions.append(Category.slug == slug)
    if not conditions:
        return
    query = select(Category.id).where(or_(*conditions))
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if await db.scalar(query.limit(1)) is not None:
        raise ConflictError("Категория с таким названием или slug уже есть", "category_exists")


async def create_category(db: AsyncSession, data: CategoryCreate) -> Category:
    """Создаёт категорию (admin). Уникальность name/slug: проверка здесь + UNIQUE в БД."""
    await _ensure_unique(db, data.name, data.slug)
    category = Category(name=data.name, slug=data.slug)
    db.add(category)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(
            "Категория с таким названием или slug уже есть", "category_exists"
        ) from None
    return category


async def update_category(db: AsyncSession, category_id: int, data: CategoryUpdate) -> Category:
    """Переименовывает категорию (admin)."""
    category = await get_category(db, category_id)
    changes = data.model_dump(exclude_unset=True)
    await _ensure_unique(db, changes.get("name"), changes.get("slug"), exclude_id=category.id)
    for field, value in changes.items():
        setattr(category, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(
            "Категория с таким названием или slug уже есть", "category_exists"
        ) from None
    return category


async def delete_category(db: AsyncSession, category_id: int) -> None:
    """Удаляет категорию (admin). Используемую вакансиями удалить нельзя (409, FK RESTRICT)."""
    category = await get_category(db, category_id)
    in_use = await db.scalar(select(exists().where(Vacancy.category_id == category.id)))
    if in_use:
        raise ConflictError("Категория используется в вакансиях", "category_in_use")
    await db.delete(category)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Категория используется в вакансиях", "category_in_use") from None
