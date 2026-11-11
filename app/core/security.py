from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Argon2-хеш пароля. Блокирует поток: вызывать через run_in_threadpool."""
    return password_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Проверка пароля. Блокирует поток: вызывать через run_in_threadpool."""
    return password_hash.verify(plain, hashed)


# Хеш, против которого проверяется пароль несуществующего пользователя:
# время ответа логина не выдаёт, зарегистрирован ли email.
DUMMY_HASH = hash_password("dummy-password-for-timing")


def create_access_token(user_id: int) -> str:
    """JWT c sub = id пользователя и сроком жизни из настроек."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Возвращает id пользователя из токена или None, если токен невалиден/просрочен."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
