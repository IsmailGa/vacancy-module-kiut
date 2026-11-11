from datetime import datetime

from pydantic import ConfigDict, EmailStr, field_validator

from app.models.applications import ApplicationStatus
from app.schemas.common import InputModel, ReadModel
from app.schemas.vacancies import VacancyBrief


class ApplicationCreate(InputModel):
    """Текстовая часть multipart-отклика (файл резюме проверяется в сервисе)."""

    cover_letter: str | None = None

    @field_validator("cover_letter")
    @classmethod
    def check_cover_letter(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not 20 <= len(v) <= 2000:
            raise ValueError("Сопроводительное письмо: от 20 до 2000 символов")
        return v


class ApplicationStatusUpdate(InputModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "viewed"}]})

    status: ApplicationStatus

    @field_validator("status")
    @classmethod
    def forbid_sent(cls, v: ApplicationStatus) -> ApplicationStatus:
        if v is ApplicationStatus.SENT:
            raise ValueError("Допустимые статусы: viewed, accepted, rejected")
        return v


class StudentBrief(ReadModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str | None
    course: int | None


class ApplicationRead(ReadModel):
    id: int
    vacancy_id: int
    student_id: int
    cover_letter: str | None
    has_resume: bool
    resume_original_name: str | None
    status: ApplicationStatus
    created_at: datetime


class ApplicationWithVacancy(ApplicationRead):
    """Отклик глазами студента."""

    vacancy: VacancyBrief


class ApplicationWithStudent(ApplicationRead):
    """Отклик глазами работодателя."""

    student: StudentBrief
