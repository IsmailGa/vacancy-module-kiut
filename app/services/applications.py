import re
import uuid
from collections.abc import Sequence
from pathlib import PurePath

import aiofiles
import anyio
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.config import settings
from app.core.exceptions import AppError, ConflictError, InvalidStateError, NotFoundError
from app.models.applications import Application, ApplicationStatus
from app.models.users import User
from app.models.vacancies import Vacancy, VacancyStatus
from app.schemas.vacancies import today_utc
from app.services import vacancies as vacancy_service

PDF_SIGNATURE = b"%PDF-"
PDF_CONTENT_TYPE = "application/pdf"
CHUNK_SIZE = 64 * 1024

ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.SENT: frozenset(
        {ApplicationStatus.VIEWED, ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.VIEWED: frozenset(
        {ApplicationStatus.VIEWED, ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.ACCEPTED: frozenset(),
    ApplicationStatus.REJECTED: frozenset(),
}

_NOT_FOUND = ("Отклик не найден", "application_not_found")


def _not_pdf() -> AppError:
    return AppError("Резюме должно быть файлом PDF", "resume_not_pdf", status_code=415)


def clean_filename(name: str | None) -> str:
    """Имя файла от клиента -> безопасная строка только для показа (на диск не идёт)."""
    name = PurePath((name or "").replace("\\", "/")).name
    name = re.sub(r"[^\w .()\-]", "_", name).strip(" .")[:255]
    return name or "resume.pdf"


async def _save_resume(resume: UploadFile) -> str:
    """Проверяет, что файл — PDF допустимого размера, и пишет его чанками под именем uuid4.pdf."""
    if resume.content_type != PDF_CONTENT_TYPE:
        raise _not_pdf()
    head = await resume.read(CHUNK_SIZE)
    if not head.startswith(PDF_SIGNATURE):
        raise _not_pdf()

    max_bytes = settings.MAX_RESUME_SIZE_MB * 1024 * 1024
    upload_dir = anyio.Path(settings.UPLOAD_DIR)
    await upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.pdf"
    path = upload_dir / stored_name

    size = 0
    too_large = False
    async with aiofiles.open(path, "wb") as out:
        chunk = head
        while chunk:
            size += len(chunk)
            if size > max_bytes:
                too_large = True
                break
            await out.write(chunk)
            chunk = await resume.read(CHUNK_SIZE)
    if too_large:
        await path.unlink(missing_ok=True)
        raise AppError(
            f"Размер резюме не должен превышать {settings.MAX_RESUME_SIZE_MB} МБ",
            "resume_too_large",
            status_code=413,
        )
    return stored_name


async def _delete_resume(stored_name: str | None) -> None:
    if stored_name:
        await (anyio.Path(settings.UPLOAD_DIR) / stored_name).unlink(missing_ok=True)


async def create_application(
    db: AsyncSession,
    student: User,
    vacancy_id: int,
    cover_letter: str | None,
    resume: UploadFile | None,
) -> Application:
    """Отклик студента. Вакансия должна быть опубликована и не просрочена; дубль даёт 409."""
    vacancy = await db.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.status is not VacancyStatus.PUBLISHED:
        raise NotFoundError("Вакансия не найдена", "vacancy_not_found")
    if vacancy.deadline < today_utc():
        raise ConflictError("Срок подачи откликов на вакансию истёк", "vacancy_expired")

    already_applied = await db.scalar(
        select(Application.id).where(
            Application.vacancy_id == vacancy_id, Application.student_id == student.id
        )
    )
    if already_applied is not None:
        raise ConflictError("Вы уже откликнулись на эту вакансию", "already_applied")

    # Swagger и браузеры присылают пустую файловую часть, если файл не выбран.
    has_file = resume is not None and bool(resume.filename)
    stored_name = await _save_resume(resume) if has_file else None

    application = Application(
        vacancy_id=vacancy_id,
        student_id=student.id,
        cover_letter=cover_letter,
        resume_path=stored_name,
        resume_original_name=clean_filename(resume.filename) if has_file else None,
    )
    db.add(application)
    try:
        await db.commit()
    except IntegrityError:
        # Два одновременных отклика: страхует UNIQUE(vacancy_id, student_id).
        await db.rollback()
        await _delete_resume(stored_name)
        raise ConflictError("Вы уже откликнулись на эту вакансию", "already_applied") from None
    return application


async def list_my(db: AsyncSession, student: User) -> Sequence[Application]:
    """Отклики текущего студента с краткой карточкой вакансии, новые сверху."""
    query = (
        select(Application)
        .where(Application.student_id == student.id)
        .options(selectinload(Application.vacancy))
        .order_by(Application.created_at.desc(), Application.id.desc())
    )
    return (await db.scalars(query)).all()


async def list_for_vacancy(
    db: AsyncSession, vacancy_id: int, employer: User
) -> Sequence[Application]:
    """Отклики на вакансию текущего работодателя с данными студента."""
    await vacancy_service.get_owned(db, vacancy_id, employer)
    query = (
        select(Application)
        .where(Application.vacancy_id == vacancy_id)
        .options(selectinload(Application.student))
        .order_by(Application.created_at.desc(), Application.id.desc())
    )
    return (await db.scalars(query)).all()


async def _get_with_vacancy(db: AsyncSession, application_id: int) -> Application:
    application = await db.scalar(
        select(Application)
        .where(Application.id == application_id)
        .options(joinedload(Application.vacancy), joinedload(Application.student))
    )
    if application is None:
        raise NotFoundError(*_NOT_FOUND)
    return application


async def change_status(
    db: AsyncSession, application_id: int, employer: User, new_status: ApplicationStatus
) -> Application:
    """Работодатель меняет статус отклика на свою вакансию по таблице переходов."""
    application = await _get_with_vacancy(db, application_id)
    if application.vacancy.employer_id != employer.id:
        raise NotFoundError(*_NOT_FOUND)
    if new_status not in ALLOWED_TRANSITIONS[application.status]:
        raise InvalidStateError(
            f"Нельзя перевести отклик из статуса «{application.status.value}» "
            f"в «{new_status.value}»",
            "invalid_status_transition",
        )
    application.status = new_status
    await db.commit()
    return application


async def get_resume(db: AsyncSession, application_id: int, user: User) -> tuple[str, str]:
    """Путь к PDF и имя для скачивания. Доступ: студент-автор или владелец вакансии."""
    application = await _get_with_vacancy(db, application_id)
    is_author = application.student_id == user.id
    is_vacancy_owner = application.vacancy.employer_id == user.id
    if not (is_author or is_vacancy_owner):
        raise NotFoundError(*_NOT_FOUND)
    if application.resume_path is None:
        raise NotFoundError("К отклику не приложено резюме", "resume_not_found")
    path = anyio.Path(settings.UPLOAD_DIR) / application.resume_path
    if not await path.is_file():
        raise NotFoundError("Файл резюме не найден", "resume_not_found")
    return str(path), application.resume_original_name or "resume.pdf"
