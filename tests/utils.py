"""Помощники тестов: создание пользователей, вакансий и откликов через API."""

from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.users import User, UserRole

API = "/api/v1"
PASSWORD = "Password123"
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def student_payload(email: str = "student@example.com", **overrides) -> dict:
    payload = {
        "email": email,
        "full_name": "Алишер Каримов",
        "password": PASSWORD,
        "role": "student",
        "course": 3,
    }
    return payload | overrides


def employer_payload(email: str = "employer@example.com", **overrides) -> dict:
    payload = {
        "email": email,
        "full_name": "Дилноза Юсупова",
        "password": PASSWORD,
        "role": "employer",
        "organization": "Отдел карьеры",
    }
    return payload | overrides


def vacancy_payload(category_id: int, **overrides) -> dict:
    payload = {
        "title": "Стажёр Python-разработчик",
        "description": "Разработка внутренних сервисов университета на FastAPI и PostgreSQL.",
        "category_id": category_id,
        "employment_type": "internship",
        "location": "Ташкент",
        "salary_min": 3_000_000,
        "salary_max": 5_000_000,
        "contact_email": "hr@example.com",
        "deadline": (date.today() + timedelta(days=30)).isoformat(),
    }
    return payload | overrides


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    """Логинится и возвращает заголовок Authorization."""
    response = await client.post(
        f"{API}/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def register(client: AsyncClient, payload: dict) -> dict[str, str]:
    """Регистрирует пользователя и возвращает его заголовок Authorization."""
    response = await client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return await login(client, payload["email"])


async def create_admin(
    client: AsyncClient, db: AsyncSession, email: str = "admin@example.com"
) -> dict[str, str]:
    """Админа нельзя создать через API, поэтому пишем его прямо в БД."""
    db.add(
        User(
            email=email,
            full_name="Админ",
            hashed_password=hash_password(PASSWORD),
            role=UserRole.ADMIN,
        )
    )
    await db.commit()
    return await login(client, email)


async def create_category(
    client: AsyncClient, admin: dict[str, str], name: str = "IT", slug: str = "it"
) -> int:
    response = await client.post(
        f"{API}/categories", json={"name": name, "slug": slug}, headers=admin
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def create_vacancy(
    client: AsyncClient, employer: dict[str, str], category_id: int, **overrides
) -> dict:
    response = await client.post(
        f"{API}/vacancies", json=vacancy_payload(category_id, **overrides), headers=employer
    )
    assert response.status_code == 201, response.text
    return response.json()


async def publish_vacancy(
    client: AsyncClient,
    employer: dict[str, str],
    admin: dict[str, str],
    category_id: int,
    **overrides,
) -> dict:
    """Проводит вакансию по пути draft -> pending -> published."""
    vacancy = await create_vacancy(client, employer, category_id, **overrides)
    response = await client.post(f"{API}/vacancies/{vacancy['id']}/submit", headers=employer)
    assert response.status_code == 200, response.text
    response = await client.post(f"{API}/admin/vacancies/{vacancy['id']}/approve", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


def field_errors(response) -> dict[str, str]:
    """{"body.course": "сообщение"} из ответа 422."""
    body = response.json()
    assert body["code"] == "validation_error", body
    return {item["field"]: item["message"] for item in body["errors"]}
