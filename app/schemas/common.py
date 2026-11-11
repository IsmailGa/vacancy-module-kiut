from pydantic import BaseModel, ConfigDict


class InputModel(BaseModel):
    """База всех входных схем: лишние поля запрещены, пробелы по краям строк обрезаются."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReadModel(BaseModel):
    """База выходных схем: собираются прямо из ORM-объектов."""

    model_config = ConfigDict(from_attributes=True)


class FieldErrorItem(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    """Единый формат ошибки API."""

    detail: str
    code: str
    errors: list[FieldErrorItem] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"detail": "Вакансия не найдена", "code": "vacancy_not_found"}]
        }
    )


_DESCRIPTIONS = {
    401: "Не авторизован",
    403: "Недостаточно прав",
    404: "Не найдено",
    409: "Конфликт или недопустимый переход статуса",
    413: "Файл слишком большой",
    415: "Файл не PDF",
    422: "Ошибка валидации",
    503: "База данных недоступна",
}


def error_responses(*codes: int) -> dict:
    """Описание ошибок эндпоинта для Swagger: error_responses(401, 404)."""
    return {
        code: {"model": ErrorResponse, "description": _DESCRIPTIONS.get(code, "Ошибка")}
        for code in codes
    }
