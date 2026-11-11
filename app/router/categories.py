from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.schemas.categories import CategoryCreate, CategoryRead, CategoryUpdate
from app.schemas.common import error_responses
from app.services import categories as category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead], summary="Список категорий")
async def list_categories(db: DbSession):
    """Публичный. Справочник для фильтра вакансий и формы создания."""
    return await category_service.list_categories(db)


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать категорию",
    responses=error_responses(401, 403, 409, 422),
)
async def create_category(data: CategoryCreate, _: AdminUser, db: DbSession):
    """Только admin."""
    return await category_service.create_category(db, data)


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Изменить категорию",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def update_category(category_id: int, data: CategoryUpdate, _: AdminUser, db: DbSession):
    """Только admin."""
    return await category_service.update_category(db, category_id, data)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить категорию",
    responses=error_responses(401, 403, 404, 409),
)
async def delete_category(category_id: int, _: AdminUser, db: DbSession) -> None:
    """Только admin. Категорию, в которой есть вакансии, удалить нельзя (409)."""
    await category_service.delete_category(db, category_id)
