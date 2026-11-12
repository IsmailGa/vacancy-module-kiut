from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import AdminUser, DbSession
from app.schemas.admin import (
    AdminApplicationFilter,
    AdminUserFilter,
    ApplicationPage,
    UserActiveUpdate,
    UserPage,
)
from app.schemas.common import error_responses
from app.schemas.stats import AdminStats
from app.schemas.users import UserRead
from app.schemas.vacancies import VacancyPage, VacancyRead, VacancyReject, VacancyStatusFilter
from app.services import admin as admin_service
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


@router.get(
    "/users",
    response_model=UserPage,
    summary="Все пользователи с поиском и фильтрами",
    responses=error_responses(422),
)
async def list_users(filters: Annotated[AdminUserFilter, Query()], _: AdminUser, db: DbSession):
    """Только admin. Поиск по ФИО, email, организации и ID студента; фильтр по роли и активности."""
    items, total = await admin_service.list_users(db, filters)
    return UserPage(items=items, total=total, limit=filters.limit, offset=filters.offset)


@router.patch(
    "/users/{user_id}/active",
    response_model=UserRead,
    summary="Заблокировать или разблокировать пользователя",
    responses=error_responses(404, 409, 422),
)
async def set_user_active(user_id: int, data: UserActiveUpdate, admin: AdminUser, db: DbSession):
    """Только admin. Меняет users.is_active; отключить самого себя нельзя (409)."""
    return await admin_service.set_user_active(db, user_id, admin, data.is_active)


@router.get(
    "/applications",
    response_model=ApplicationPage,
    summary="Все отклики портала",
    responses=error_responses(422),
)
async def list_applications(
    filters: Annotated[AdminApplicationFilter, Query()], _: AdminUser, db: DbSession
):
    """Только admin. Отклики с вакансией и студентом, фильтр по статусу и вакансии."""
    items, total = await admin_service.list_applications(db, filters)
    return ApplicationPage(items=items, total=total, limit=filters.limit, offset=filters.offset)
