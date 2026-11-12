from datetime import date

from pydantic import BaseModel


class CategoryStat(BaseModel):
    category_id: int
    name: str
    applications: int


class DayStat(BaseModel):
    day: date
    applications: int


class AdminStats(BaseModel):
    vacancies_by_status: dict[str, int]
    vacancies_total: int
    applications_total: int
    users_by_role: dict[str, int]
    users_total: int
    top_categories: list[CategoryStat]
    applications_by_day: list[DayStat]


class HealthRead(BaseModel):
    status: str
    database: str
