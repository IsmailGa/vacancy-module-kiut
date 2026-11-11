from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import AdminUser, DbSession
from app.schemas.common import error_responses
from app.schemas.stats import AdminStats
from app.schemas.vacancies import VacancyPage, VacancyRead, VacancyReject, VacancyStatusFilter
from app.services import stats as stats_service
from app.services import vacancies as vacancy_service

router = APIRouter(prefix="/admin", tags=["admin"], responses=error_responses(401, 403))


@router.get(
    "/vacancies",
    response_model=VacancyPage,
    summary="Очередь модерации (?status=pending)",
    responses=error_responses(422),
)
async def list_vacancies_for_moderation(
    params: Annotated[VacancyStatusFilter, Query()], _: AdminUser, db: DbSession
):
    """Только admin. Вакансии всех работодателей с фильтром по статусу."""
    items, total = await vacancy_service.list_for_admin(
        db, params.status, params.limit, params.offset
    )
    return VacancyPage(items=items, total=total, limit=params.limit, offset=params.offset)


@router.post(
    "/vacancies/{vacancy_id}/approve",
    response_model=VacancyRead,
    summary="Одобрить вакансию",
    responses=error_responses(404, 409),
)
async def approve_vacancy(vacancy_id: int, _: AdminUser, db: DbSession):
    """Только admin. pending -> published, проставляется published_at."""
    return await vacancy_service.approve_vacancy(db, vacancy_id)


@router.post(
    "/vacancies/{vacancy_id}/reject",
    response_model=VacancyRead,
    summary="Отклонить вакансию с комментарием",
    responses=error_responses(404, 409, 422),
)
async def reject_vacancy(vacancy_id: int, data: VacancyReject, _: AdminUser, db: DbSession):
    """Только admin. pending -> rejected, комментарий сохраняется в moderation_comment."""
    return await vacancy_service.reject_vacancy(db, vacancy_id, data.comment)


@router.get("/stats", response_model=AdminStats, summary="Статистика для админ-панели")
async def read_stats(_: AdminUser, db: DbSession):
    """Только admin. Агрегаты считаются SQL-запросами по vacancies и applications."""
    return await stats_service.get_admin_stats(db)
