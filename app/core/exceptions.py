import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app")


class AppError(Exception):
    """Базовая ошибка бизнес-логики. Сервисы бросают её, а не HTTPException."""

    status_code: int = 400
    code: str = "app_error"
    detail: str = "Ошибка запроса"

    def __init__(
        self,
        detail: str | None = None,
        code: str | None = None,
        *,
        status_code: int | None = None,
        errors: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.detail = detail or self.detail
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.errors = errors
        self.headers = headers
        super().__init__(self.detail)


class UnauthorizedError(AppError):
    status_code = 401
    code = "not_authenticated"
    detail = "Требуется авторизация"

    def __init__(self, detail: str | None = None, code: str | None = None) -> None:
        super().__init__(detail, code, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    detail = "Недостаточно прав"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    detail = "Объект не найден"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    detail = "Конфликт данных"


class InvalidStateError(ConflictError):
    code = "invalid_state"
    detail = "Действие недоступно в текущем статусе"


class UnprocessableError(AppError):
    """422 из сервиса: правило, которое не проверить одной схемой (нужна БД или текущий объект)."""

    status_code = 422
    code = "validation_error"
    detail = "Ошибка валидации"

    def __init__(self, field: str, message: str, code: str | None = None) -> None:
        super().__init__(code=code, errors=[{"field": field, "message": message}])


class FieldError(ValueError):
    """ValueError из model_validator с именем поля, чтобы фронт подсветил нужный input."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(message)


# Перевод стандартных сообщений Pydantic на русский (по типу ошибки).
_MESSAGES: dict[str, str] = {
    "missing": "Обязательное поле",
    "extra_forbidden": "Лишнее поле",
    "string_too_short": "Минимальная длина: {min_length} симв.",
    "string_too_long": "Максимальная длина: {max_length} симв.",
    "string_type": "Ожидается строка",
    "string_pattern_mismatch": "Недопустимый формат",
    "greater_than_equal": "Значение должно быть не меньше {ge}",
    "less_than_equal": "Значение должно быть не больше {le}",
    "greater_than": "Значение должно быть больше {gt}",
    "less_than": "Значение должно быть меньше {lt}",
    "int_type": "Ожидается целое число",
    "int_parsing": "Ожидается целое число",
    "int_from_float": "Ожидается целое число",
    "bool_type": "Ожидается true или false",
    "bool_parsing": "Ожидается true или false",
    "enum": "Допустимые значения: {expected}",
    "literal_error": "Допустимые значения: {expected}",
    "date_type": "Ожидается дата в формате ГГГГ-ММ-ДД",
    "date_parsing": "Ожидается дата в формате ГГГГ-ММ-ДД",
    "date_from_datetime_parsing": "Ожидается дата в формате ГГГГ-ММ-ДД",
    "date_from_datetime_inexact": "Ожидается дата в формате ГГГГ-ММ-ДД",
    "json_invalid": "Некорректный JSON",
    "model_attributes_type": "Ожидается объект",
    "dict_type": "Ожидается объект",
}


def format_validation_error(err: dict) -> dict[str, str]:
    """Одна ошибка Pydantic -> {"field": "body.salary_max", "message": "..."}."""
    loc = [str(part) for part in err.get("loc", ())]
    ctx = err.get("ctx") or {}
    err_type = err.get("type", "")
    message = err.get("msg", "Некорректное значение")

    if err_type == "value_error":
        original = ctx.get("error")
        if isinstance(original, FieldError):
            loc.append(original.field)
        message = message.removeprefix("Value error, ")
        if message.startswith("value is not a valid email address"):
            message = "Некорректный email"
    elif err_type in _MESSAGES:
        try:
            message = _MESSAGES[err_type].format(**ctx)
        except (KeyError, IndexError):
            message = _MESSAGES[err_type]
    return {"field": ".".join(loc), "message": message}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    content: dict = {"detail": exc.detail, "code": exc.code}
    if exc.errors:
        content["errors"] = exc.errors
    return JSONResponse(content, status_code=exc.status_code, headers=exc.headers)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        {
            "detail": "Ошибка валидации",
            "code": "validation_error",
            "errors": [format_validation_error(err) for err in exc.errors()],
        },
        status_code=422,
    )


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Ошибки самого фреймворка (неизвестный путь, метод) в едином формате."""
    return JSONResponse(
        {"detail": str(exc.detail), "code": _HTTP_CODES.get(exc.status_code, "http_error")},
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Трассировка уходит только в лог, наружу отдаётся безликий 500."""
    logger.error("Необработанная ошибка: %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        {"detail": "Внутренняя ошибка сервера", "code": "internal_error"},
        status_code=500,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
