from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.deps import CurrentUser, DbSession, EmployerUser, StudentUser
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationStatusUpdate,
    ApplicationWithStudent,
    ApplicationWithVacancy,
)
from app.schemas.common import error_responses
from app.services import applications as application_service

router = APIRouter(tags=["applications"])


@router.post(
    "/vacancies/{vacancy_id}/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Откликнуться на вакансию (multipart/form-data)",
    responses=error_responses(401, 403, 404, 409, 413, 415, 422),
)
async def apply(
    vacancy_id: int,
    student: StudentUser,
    db: DbSession,
    cover_letter: Annotated[
        str | None, Form(description="Сопроводительное письмо, 20–2000 символов")
    ] = None,
    resume: Annotated[UploadFile | None, File(description="Резюме, только PDF")] = None,
):
    """Только student. Поля формы отклика -> ApplicationCreate + проверка PDF -> applications."""
    try:
        data = ApplicationCreate(cover_letter=cover_letter)
    except ValidationError as exc:
        errors = [{**err, "loc": ("body", *err["loc"])} for err in exc.errors()]
        raise RequestValidationError(errors) from exc
    return await application_service.create_application(
        db, student, vacancy_id, data.cover_letter, resume
    )


@router.get(
    "/applications/my",
    response_model=list[ApplicationWithVacancy],
    summary="Мои отклики",
    responses=error_responses(401, 403),
)
async def list_my_applications(student: StudentUser, db: DbSession):
    """Только student. Свои отклики с краткой карточкой вакансии."""
    return await application_service.list_my(db, student)


@router.get(
    "/vacancies/{vacancy_id}/applications",
    response_model=list[ApplicationWithStudent],
    summary="Отклики на мою вакансию",
    responses=error_responses(401, 403, 404),
)
async def list_vacancy_applications(vacancy_id: int, employer: EmployerUser, db: DbSession):
    """Только владелец вакансии. Отклики с контактами студентов."""
    return await application_service.list_for_vacancy(db, vacancy_id, employer)


@router.patch(
    "/applications/{application_id}/status",
    response_model=ApplicationRead,
    summary="Изменить статус отклика",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def change_application_status(
    application_id: int, data: ApplicationStatusUpdate, employer: EmployerUser, db: DbSession
):
    """Только владелец вакансии. sent/viewed -> viewed/accepted/rejected."""
    return await application_service.change_status(db, application_id, employer, data.status)


@router.get(
    "/applications/{application_id}/resume",
    response_class=FileResponse,
    summary="Скачать резюме из отклика (PDF)",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Файл резюме"},
        **error_responses(401, 403, 404),
    },
)
async def download_resume(application_id: int, user: CurrentUser, db: DbSession):
    """Студент-автор отклика или владелец вакансии. Файл читается из UPLOAD_DIR."""
    path, filename = await application_service.get_resume(db, application_id, user)
    return FileResponse(path, media_type="application/pdf", filename=filename)
