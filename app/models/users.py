import enum

from sqlalchemy import Boolean, CheckConstraint, SmallInteger, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAt, enum_type


class UserRole(str, enum.Enum):
    STUDENT = "student"
    EMPLOYER = "employer"
    ADMIN = "admin"


class User(Base):
    """Пользователь: студент, работодатель (сотрудник университета) или администратор."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("course BETWEEN 1 AND 6", name="course_range"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("student_id ~ '^[0-9]{7}$'", name="student_id_format"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    student_id: Mapped[str | None] = mapped_column(String(7), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole, "role"))
    course: Mapped[int | None] = mapped_column(SmallInteger)
    organization: Mapped[str | None] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[CreatedAt]
