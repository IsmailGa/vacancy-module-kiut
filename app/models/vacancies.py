import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import CreatedAt, enum_type
from app.models.categories import Category
from app.models.users import User


class EmploymentType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    INTERNSHIP = "internship"
    PROJECT = "project"


class Currency(str, enum.Enum):
    UZS = "UZS"
    USD = "USD"


class VacancyStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
    CLOSED = "closed"


class Vacancy(Base):
    """Вакансия работодателя. Жизненный цикл задаётся полем status."""

    __tablename__ = "vacancies"
    __table_args__ = (
        Index("ix_vacancies_status_category_id", "status", "category_id"),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="salary_range",
        ),
        CheckConstraint("salary_min >= 0 AND salary_max >= 0", name="salary_non_negative"),
        CheckConstraint("target_course BETWEEN 1 AND 6", name="target_course_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    employment_type: Mapped[EmploymentType] = mapped_column(
        enum_type(EmploymentType, "employment_type")
    )
    location: Mapped[str] = mapped_column(String(100))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[Currency] = mapped_column(
        enum_type(Currency, "currency"), default=Currency.UZS, server_default=Currency.UZS.value
    )
    target_course: Mapped[int | None] = mapped_column(SmallInteger)
    contact_email: Mapped[str] = mapped_column(String(255))
    deadline: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[VacancyStatus] = mapped_column(
        enum_type(VacancyStatus, "status"),
        default=VacancyStatus.DRAFT,
        server_default=VacancyStatus.DRAFT.value,
    )
    moderation_comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employer: Mapped[User] = relationship(lazy="raise")
    category: Mapped[Category] = relationship(lazy="raise")
