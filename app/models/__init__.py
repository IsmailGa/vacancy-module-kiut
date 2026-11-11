"""Все модели импортируются здесь, чтобы Alembic видел полную metadata."""

from app.models.applications import Application, ApplicationStatus
from app.models.categories import Category
from app.models.users import User, UserRole
from app.models.vacancies import Currency, EmploymentType, Vacancy, VacancyStatus

__all__ = [
    "Application",
    "ApplicationStatus",
    "Category",
    "Currency",
    "EmploymentType",
    "User",
    "UserRole",
    "Vacancy",
    "VacancyStatus",
]
