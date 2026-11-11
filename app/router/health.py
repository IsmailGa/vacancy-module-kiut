import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.deps import DbSession
from app.schemas.stats import HealthRead

logger = logging.getLogger("app")

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthRead,
    summary="Проверка живости сервиса и соединения с БД",
    responses={503: {"model": HealthRead, "description": "База данных недоступна"}},
)
async def health(db: DbSession):
    """Выполняет SELECT 1; используется мониторингом и для ручной проверки запуска."""
    try:
        await db.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        logger.exception("Health-check: база данных недоступна")
        return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)
    return HealthRead(status="ok", database="ok")
