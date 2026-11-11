import enum
from datetime import UTC, date, datetime, timedelta
from typing import ClassVar, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.core.exceptions import FieldError
from app.models.vacancies import Currency, EmploymentType, VacancyStatus
from app.schemas.categories import CategoryRead
from app.schemas.common import InputModel, ReadModel

MAX_SALARY = 1_000_000_000
MAX_DEADLINE_DAYS = 365
SALARY_ORDER_MESSAGE = "Максимальная зарплата не может быть меньше минимальной"


def today_utc() -> date:
    """«Сегодня» для всех правил про deadline (сервер и БД живут в UTC)."""
    return datetime.now(UTC).date()


def check_deadline(value: date) -> date:
    today = today_utc()
    if value <= today:
        raise ValueError("Дедлайн должен быть в будущем")
    if value > today + timedelta(days=MAX_DEADLINE_DAYS):
        raise ValueError("Дедлайн не может быть позже чем через 365 дней")
    return value


def check_salary_order(value: int | None, info: ValidationInfo) -> int | None:
    """Валидатор salary_max: сравнивает с уже проверенным salary_min."""
    salary_min = info.data.get("salary_min")
    if value is not None and salary_min is not None and salary_min > value:
        raise ValueError(SALARY_ORDER_MESSAGE)
    return value


_VACANCY_EXAMPLE = {
    "title": "Стажёр Python-разработчик",
    "description": "Разработка внутренних сервисов университета на FastAPI и PostgreSQL в команде IT-отдела.",
    "requirements": "Базовые знания Python и SQL, желание учиться.",
    "category_id": 1,
    "employment_type": "internship",
    "location": "Ташкент",
    "is_remote": False,
    "salary_min": 3000000,
    "salary_max": 5000000,
    "currency": "UZS",
    "target_course": 3,
    "contact_email": "hr@example.com",
    "deadline": "2027-01-31",
}


class VacancyCreate(InputModel):
    model_config = ConfigDict(json_schema_extra={"examples": [_VACANCY_EXAMPLE]})

    title: str = Field(min_length=5, max_length=150)
    description: str = Field(min_length=30, max_length=5000)
    requirements: str | None = Field(default=None, max_length=3000)
    category_id: int = Field(ge=1)
    employment_type: EmploymentType
    location: str = Field(min_length=2, max_length=100)
    is_remote: bool = False
    salary_min: int | None = Field(default=None, ge=0, le=MAX_SALARY)
    salary_max: int | None = Field(default=None, ge=0, le=MAX_SALARY)
    currency: Currency = Currency.UZS
    target_course: int | None = Field(default=None, ge=1, le=6)
    contact_email: EmailStr
    deadline: date

    _deadline = field_validator("deadline")(check_deadline)
    _salary = field_validator("salary_max")(check_salary_order)


class VacancyUpdate(InputModel):
    """Все поля необязательные; к переданным применяются те же правила, что при создании."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"title": "Стажёр backend-разработчик", "salary_max": 6000000}]
        }
    )

    # Поля, которые можно сбросить в null.
    NULLABLE: ClassVar[frozenset[str]] = frozenset(
        {"requirements", "salary_min", "salary_max", "target_course"}
    )

    title: str | None = Field(default=None, min_length=5, max_length=150)
    description: str | None = Field(default=None, min_length=30, max_length=5000)
    requirements: str | None = Field(default=None, max_length=3000)
    category_id: int | None = Field(default=None, ge=1)
    employment_type: EmploymentType | None = None
    location: str | None = Field(default=None, min_length=2, max_length=100)
    is_remote: bool | None = None
    salary_min: int | None = Field(default=None, ge=0, le=MAX_SALARY)
    salary_max: int | None = Field(default=None, ge=0, le=MAX_SALARY)
    currency: Currency | None = None
    target_course: int | None = Field(default=None, ge=1, le=6)
    contact_email: EmailStr | None = None
    deadline: date | None = None

    @field_validator("deadline")
    @classmethod
    def _deadline(cls, v: date | None) -> date | None:
        return check_deadline(v) if v is not None else v

    _salary = field_validator("salary_max")(check_salary_order)

    @model_validator(mode="after")
    def forbid_null_for_required(self) -> Self:
        for name in self.model_fields_set - self.NULLABLE:
            if getattr(self, name) is None:
                raise FieldError(name, "Поле не может быть пустым")
        return self


class VacancyReject(InputModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"comment": "Уточните условия оплаты и график работы."}]}
    )

    comment: str = Field(min_length=10, max_length=500)


class VacancySort(str, enum.Enum):
    NEWEST = "newest"
    DEADLINE = "deadline"
    SALARY = "salary"


class VacancyFilter(BaseModel):
    """Query-параметры публичного списка вакансий."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: str | None = Field(default=None, max_length=100, description="Поиск по названию и описанию")
    category_id: int | None = Field(default=None, ge=1)
    employment_type: EmploymentType | None = None
    is_remote: bool | None = None
    salary_from: int | None = Field(default=None, ge=0, le=MAX_SALARY)
    course: int | None = Field(default=None, ge=1, le=6, description="Курс студента")
    sort: VacancySort = VacancySort.NEWEST
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class VacancyStatusFilter(BaseModel):
    """Query-параметры списков «мои вакансии» и очереди модерации."""

    model_config = ConfigDict(extra="forbid")

    status: VacancyStatus | None = None
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class EmployerBrief(ReadModel):
    id: int
    full_name: str
    organization: str | None


class VacancyRead(ReadModel):
    id: int
    employer_id: int
    category_id: int
    title: str
    description: str
    requirements: str | None
    employment_type: EmploymentType
    location: str
    is_remote: bool
    salary_min: int | None
    salary_max: int | None
    currency: Currency
    target_course: int | None
    contact_email: EmailStr
    deadline: date
    status: VacancyStatus
    moderation_comment: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    category: CategoryRead
    employer: EmployerBrief


class VacancyBrief(ReadModel):
    """Краткая карточка вакансии внутри отклика."""

    id: int
    title: str
    employment_type: EmploymentType
    location: str
    deadline: date
    status: VacancyStatus


class VacancyPage(BaseModel):
    items: list[VacancyRead]
    total: int
    limit: int
    offset: int
