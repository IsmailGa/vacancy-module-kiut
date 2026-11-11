import re
from datetime import datetime
from typing import Self

from pydantic import ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.exceptions import FieldError
from app.models.users import UserRole
from app.schemas.common import InputModel, ReadModel

PHONE_RE = re.compile(r"^\+?\d{9,15}$")
# Буквы любого алфавита; между словами пробел, дефис или апостроф.
STUDENT_ID_RE = re.compile(r"^\d{7}$")
FULL_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ \-'’][^\W\d_]+)*$")


def clean_full_name(value: str) -> str:
    value = " ".join(value.split())
    if not 2 <= len(value) <= 100:
        raise ValueError("ФИО должно быть длиной от 2 до 100 символов")
    if not FULL_NAME_RE.match(value):
        raise ValueError("ФИО может содержать только буквы, пробел, дефис и апостроф")
    return value


def clean_phone(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    value = value.replace(" ", "").replace("-", "")
    if not PHONE_RE.match(value):
        raise ValueError("Телефон: от 9 до 15 цифр, можно с + в начале")
    return value


class UserCreate(InputModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "student@example.com",
                    "full_name": "Алишер Каримов",
                    "phone": "+998 90 123-45-67",
                    "password": "Password123",
                    "role": "student",
                    "course": 3,
                    "student_id": "2300001",
                },
                {
                    "email": "hr@example.com",
                    "full_name": "Дилноза Юсупова",
                    "password": "Password123",
                    "role": "employer",
                    "organization": "Отдел карьеры KIUT",
                },
            ]
        }
    )

    email: EmailStr
    full_name: str
    phone: str | None = None
    password: str = Field(min_length=8, max_length=64)
    role: UserRole
    course: int | None = Field(default=None, ge=1, le=6)
    organization: str | None = Field(default=None, min_length=2, max_length=150)
    student_id: str | None = Field(
        default=None, description="ID студента в университете: ровно 7 цифр, им можно входить"
    )

    @field_validator("student_id")
    @classmethod
    def check_student_id(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not STUDENT_ID_RE.match(v):
            raise ValueError("ID студента должен состоять ровно из 7 цифр")
        return v

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    _clean_name = field_validator("full_name")(clean_full_name)
    _clean_phone = field_validator("phone")(clean_phone)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if not (re.search(r"[^\W\d_]", v) and re.search(r"\d", v)):
            raise ValueError("Пароль должен содержать минимум одну букву и одну цифру")
        return v

    @field_validator("role")
    @classmethod
    def forbid_admin(cls, v: UserRole) -> UserRole:
        if v is UserRole.ADMIN:
            raise ValueError("Зарегистрироваться можно только как student или employer")
        return v

    @model_validator(mode="after")
    def check_role_fields(self) -> Self:
        """course нужен только студенту, organization только работодателю."""
        if self.role is UserRole.STUDENT:
            if self.course is None:
                raise FieldError("course", "Для студента нужно указать курс (1–6)")
            if self.organization is not None:
                raise FieldError("organization", "Организация указывается только работодателем")
        else:
            if self.organization is None:
                raise FieldError("organization", "Для работодателя нужно указать организацию")
            if self.course is not None:
                raise FieldError("course", "Курс указывается только студентом")
            if self.student_id is not None:
                raise FieldError("student_id", "ID студента указывается только студентом")
        return self


class UserUpdate(InputModel):
    """Частичное обновление профиля. Соответствие полей роли проверяет сервис."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"full_name": "Алишер Каримов", "course": 4}]}
    )

    full_name: str | None = None
    phone: str | None = None
    course: int | None = Field(default=None, ge=1, le=6)
    organization: str | None = Field(default=None, min_length=2, max_length=150)

    @field_validator("full_name")
    @classmethod
    def check_name(cls, v: str | None) -> str:
        if v is None:
            raise ValueError("ФИО не может быть пустым")
        return clean_full_name(v)

    _clean_phone = field_validator("phone")(clean_phone)


class UserRead(ReadModel):
    id: int
    email: EmailStr
    student_id: str | None
    full_name: str
    phone: str | None
    role: UserRole
    course: int | None
    organization: str | None
    is_active: bool
    created_at: datetime


class Token(ReadModel):
    access_token: str
    token_type: str = "bearer"
