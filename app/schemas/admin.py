from pydantic import BaseModel, ConfigDict, Field

from app.models.applications import ApplicationStatus
from app.models.users import UserRole
from app.schemas.applications import ApplicationRead, StudentBrief
from app.schemas.common import InputModel
from app.schemas.users import UserRead
from app.schemas.vacancies import VacancyBrief


class AdminUserFilter(BaseModel):
    """Query-параметры списка пользователей в админке."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: str | None = Field(default=None, max_length=100, description="ФИО, email или ID студента")
    role: UserRole | None = None
    is_active: bool | None = None
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class UserPage(BaseModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int


class UserActiveUpdate(InputModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"is_active": False}]})

    is_active: bool


class AdminApplicationFilter(BaseModel):
    """Query-параметры списка всех откликов в админке."""

    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus | None = None
    vacancy_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class ApplicationAdminRead(ApplicationRead):
    """Отклик глазами администратора: и вакансия, и студент."""

    vacancy: VacancyBrief
    student: StudentBrief


class ApplicationPage(BaseModel):
    items: list[ApplicationAdminRead]
    total: int
    limit: int
    offset: int
