from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.users import User, UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
TokenDep = Annotated[str | None, Depends(oauth2_scheme)]


async def get_current_user(db: DbSession, token: TokenDep) -> User:
    """Пользователь по Bearer-токену: 401 без токена/с плохим токеном, 403 если отключён."""
    if token is None:
        raise UnauthorizedError()
    user_id = decode_access_token(token)
    if user_id is None:
        raise UnauthorizedError("Токен недействителен или просрочен", "invalid_token")
    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Токен недействителен или просрочен", "invalid_token")
    if not user.is_active:
        raise ForbiddenError("Учётная запись отключена", "user_inactive")
    return user


async def get_optional_user(db: DbSession, token: TokenDep) -> User | None:
    """Для публичных эндпоинтов: None без токена, иначе обычная проверка токена."""
    if token is None:
        return None
    return await get_current_user(db, token)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    """Фабрика зависимости: пропускает только указанные роли, иначе 403."""

    async def check_role(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("Действие недоступно для вашей роли", "role_forbidden")
        return user

    return check_role


StudentUser = Annotated[User, Depends(require_roles(UserRole.STUDENT))]
EmployerUser = Annotated[User, Depends(require_roles(UserRole.EMPLOYER))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
