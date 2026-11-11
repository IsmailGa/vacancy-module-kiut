from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.deps import DbSession
from app.schemas.common import error_responses
from app.schemas.users import Token, UserCreate, UserRead
from app.services import users as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация студента или работодателя",
    responses=error_responses(409, 422),
)
async def register(data: UserCreate, db: DbSession):
    """Публичный. Данные формы регистрации -> UserCreate -> таблица users."""
    return await user_service.register_user(db, data)


@router.post(
    "/login",
    response_model=Token,
    summary="Вход: получение JWT (username = email или ID студента)",
    responses=error_responses(401, 403, 422),
)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """Публичный. Форма x-www-form-urlencoded: username (email или 7-значный ID студента) и password."""
    token = await user_service.authenticate(db, form.username, form.password)
    return Token(access_token=token)
