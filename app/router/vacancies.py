from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import DbSession, EmployerUser, OptionalUser
from app.schemas.common import error_responses
from app.schemas.vacancies import (
    VacancyCreate,
    VacancyFilter,
    VacancyPage,
    VacancyRead,
    VacancyStatusFilter,
    VacancyUpdate,
)
from app.services import vacancies as vacancy_service

router = APIRouter(prefix="/vacancies", tags=["vacancies"])

_OWNER_ERRORS = error_responses(401, 403, 404, 409)


@router.get(
    "",
    response_model=VacancyPage,
    summary="Лента опубликованных вакансий с фильтрами",
    responses=error_responses(422),
)
async def list_vacancies(filters: Annotated[VacancyFilter, Query()], db: DbSession):
    """Публичный. Только published и не просроченные; фильтры и пагинация из query."""
    items, total = await vacancy_service.list_published(db, filters)
    return VacancyPage(items=items, total=total, limit=filters.limit, offset=filters.offset)


@router.get(
    "/my",
    response_model=VacancyPage,
    summary="Мои вакансии (любой статус)",
    responses=error_responses(401, 403, 422),
)
async def list_my_vacancies(
    params: Annotated[VacancyStatusFilter, Query()], employer: EmployerUser, db: DbSession
):
    """Только employer. Свои вакансии, опционально с фильтром по статусу."""
    items, total = await vacancy_service.list_my(
        db, employer, params.status, params.limit, params.offset
    )
    return VacancyPage(items=items, total=total, limit=params.limit, offset=params.offset)


@router.post(
    "",
    response_model=VacancyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать вакансию (черновик)",
    responses=error_responses(401, 403, 422),
)
async def create_vacancy(data: VacancyCreate, employer: EmployerUser, db: DbSession):
    """Только employer. Форма вакансии -> VacancyCreate -> vacancies в статусе draft."""
    return await vacancy_service.create_vacancy(db, employer, data)


@router.get(
    "/{vacancy_id}",
    response_model=VacancyRead,
    summary="Одна вакансия",
    responses=error_responses(401, 404),
)
async def read_vacancy(vacancy_id: int, user: OptionalUser, db: DbSession):
    """Публичный для published; владелец и admin (с токеном) видят любую."""
    return await vacancy_service.get_visible(db, vacancy_id, user)


@router.patch(
    "/{vacancy_id}",
    response_model=VacancyRead,
    summary="Изменить свою вакансию",
    responses={**_OWNER_ERRORS, **error_responses(422)},
)
async def update_vacancy(
    vacancy_id: int, data: VacancyUpdate, employer: EmployerUser, db: DbSession
):
    """Только владелец. Доступно в статусах draft и rejected, иначе 409."""
    return await vacancy_service.update_vacancy(db, vacancy_id, employer, data)


@router.delete(
    "/{vacancy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить свой черновик",
    responses=_OWNER_ERRORS,
)
async def delete_vacancy(vacancy_id: int, employer: EmployerUser, db: DbSession) -> None:
    """Только владелец и только в статусе draft."""
    await vacancy_service.delete_vacancy(db, vacancy_id, employer)


@router.post(
    "/{vacancy_id}/submit",
    response_model=VacancyRead,
    summary="Отправить вакансию на модерацию",
    responses=_OWNER_ERRORS,
)
async def submit_vacancy(vacancy_id: int, employer: EmployerUser, db: DbSession):
    """Только владелец. draft/rejected -> pending."""
    return await vacancy_service.submit_vacancy(db, vacancy_id, employer)


@router.post(
    "/{vacancy_id}/close",
    response_model=VacancyRead,
    summary="Закрыть опубликованную вакансию",
    responses=_OWNER_ERRORS,
)
async def close_vacancy(vacancy_id: int, employer: EmployerUser, db: DbSession):
    """Только владелец. published -> closed."""
    return await vacancy_service.close_vacancy(db, vacancy_id, employer)
