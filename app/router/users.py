from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.schemas.common import error_responses
from app.schemas.users import UserRead, UserUpdate
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Профиль текущего пользователя",
    responses=error_responses(401, 403),
)
async def read_me(user: CurrentUser):
    """Любой авторизованный. Данные берутся из users по id из токена."""
    return user


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Изменить свой профиль",
    responses=error_responses(401, 403, 422),
)
async def update_me(data: UserUpdate, user: CurrentUser, db: DbSession):
    """Любой авторизованный. Меняются full_name, phone и course/organization по роли."""
    return await user_service.update_profile(db, user, data)
