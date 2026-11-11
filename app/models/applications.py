import enum

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import CreatedAt, enum_type
from app.models.users import User
from app.models.vacancies import Vacancy


class ApplicationStatus(str, enum.Enum):
    SENT = "sent"
    VIEWED = "viewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Application(Base):
    """Отклик студента на вакансию. Один студент — один отклик на вакансию."""

    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "student_id", name="uq_applications_vacancy_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cover_letter: Mapped[str | None] = mapped_column(Text)
    resume_path: Mapped[str | None] = mapped_column(String(64))
    resume_original_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus, "status"),
        default=ApplicationStatus.SENT,
        server_default=ApplicationStatus.SENT.value,
    )
    created_at: Mapped[CreatedAt]

    vacancy: Mapped[Vacancy] = relationship(lazy="raise")
    student: Mapped[User] = relationship(lazy="raise")

    @property
    def has_resume(self) -> bool:
        return self.resume_path is not None
