"""Тестовые данные для демонстрации. Запуск из папки back: uv run python -m scripts.seed"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.core.security import hash_password
from app.models import (
    Application,
    ApplicationStatus,
    Category,
    Currency,
    EmploymentType,
    User,
    UserRole,
    Vacancy,
    VacancyStatus,
)

SEED_PASSWORD = "Password123"

CATEGORIES = [
    ("IT и разработка", "it"),
    ("Маркетинг и SMM", "marketing"),
    ("Дизайн", "design"),
    ("Образование и репетиторство", "education"),
    ("Администрирование", "administration"),
    ("Финансы и бухгалтерия", "finance"),
    ("Наука и исследования", "research"),
]

USERS = [
    ("admin@kiut.uz", "Администратор Системы", UserRole.ADMIN, None, None),
    ("career@kiut.uz", "Дилноза Юсупова", UserRole.EMPLOYER, None, "Центр карьеры KIUT"),
    ("hr@techpark.uz", "Тимур Рахимов", UserRole.EMPLOYER, None, "IT Park Tashkent"),
    ("student1@kiut.uz", "Алишер Каримов", UserRole.STUDENT, 1, None),
    ("student2@kiut.uz", "Мадина Абдуллаева", UserRole.STUDENT, 2, None),
    ("student3@kiut.uz", "Жасур Турсунов", UserRole.STUDENT, 3, None),
    ("student4@kiut.uz", "Севара Исмаилова", UserRole.STUDENT, 4, None),
    ("student5@kiut.uz", "Бобур Назаров", UserRole.STUDENT, 4, None),
]

# (название, slug категории, тип, удалённо, зарплата от/до, валюта, курс, статус)
VACANCIES = [
    (
        "Стажёр Python-разработчик",
        "it",
        "internship",
        False,
        3_000_000,
        5_000_000,
        "UZS",
        3,
        "published",
    ),
    ("Frontend-разработчик (Vue 3)", "it", "part_time", True, 500, 900, "USD", 4, "published"),
    (
        "Лаборант кафедры информатики",
        "research",
        "part_time",
        False,
        2_000_000,
        None,
        "UZS",
        None,
        "published",
    ),
    (
        "SMM-менеджер университета",
        "marketing",
        "part_time",
        True,
        2_500_000,
        4_000_000,
        "UZS",
        None,
        "published",
    ),
    (
        "Графический дизайнер афиш",
        "design",
        "project",
        True,
        None,
        3_000_000,
        "UZS",
        2,
        "published",
    ),
    (
        "Репетитор по математике для абитуриентов",
        "education",
        "part_time",
        False,
        80_000,
        120_000,
        "UZS",
        3,
        "published",
    ),
    (
        "Помощник в приёмную комиссию",
        "administration",
        "full_time",
        False,
        3_500_000,
        4_500_000,
        "UZS",
        None,
        "published",
    ),
    (
        "Младший бухгалтер",
        "finance",
        "full_time",
        False,
        4_000_000,
        6_000_000,
        "UZS",
        4,
        "published",
    ),
    ("QA-инженер (стажировка)", "it", "internship", True, None, None, "UZS", 2, "published"),
    (
        "Ассистент исследователя в лаборатории ИИ",
        "research",
        "project",
        False,
        300,
        600,
        "USD",
        4,
        "published",
    ),
    (
        "Контент-менеджер сайта университета",
        "marketing",
        "part_time",
        True,
        2_000_000,
        3_000_000,
        "UZS",
        1,
        "published",
    ),
    (
        "Тьютор по английскому языку",
        "education",
        "part_time",
        False,
        100_000,
        150_000,
        "UZS",
        None,
        "published",
    ),
    ("DevOps-стажёр", "it", "internship", False, 4_000_000, 6_000_000, "UZS", 4, "pending"),
    (
        "UX-исследователь студенческого портала",
        "design",
        "project",
        True,
        400,
        700,
        "USD",
        3,
        "pending",
    ),
    (
        "Оператор колл-центра приёмной кампании",
        "administration",
        "part_time",
        False,
        2_000_000,
        2_500_000,
        "UZS",
        None,
        "pending",
    ),
    ("Аналитик данных (Junior)", "it", "full_time", False, 6_000_000, 9_000_000, "UZS", 4, "draft"),
    ("Фотограф мероприятий", "design", "project", False, None, 1_500_000, "UZS", None, "draft"),
    (
        "Промоутер на день открытых дверей",
        "marketing",
        "project",
        False,
        300_000,
        300_000,
        "UZS",
        None,
        "rejected",
    ),
    (
        "Финансовый аналитик (стажировка)",
        "finance",
        "internship",
        False,
        3_000_000,
        4_000_000,
        "UZS",
        3,
        "closed",
    ),
    ("Мобильный разработчик (Flutter)", "it", "part_time", True, 600, 1_000, "USD", 3, "closed"),
]

DESCRIPTION = (
    "{title}. Работа в дружной команде, гибкий график, который можно совмещать с учёбой. "
    "Наставник поможет войти в задачи, по итогам возможна рекомендация и продолжение сотрудничества."
)


async def seed() -> None:
    """Наполняет пустую БД; при повторном запуске ничего не дублирует."""
    async with SessionLocal() as db:
        if await db.scalar(select(User.id).limit(1)) is not None:
            print("В базе уже есть данные, seed пропущен.")
            return

        hashed = hash_password(SEED_PASSWORD)
        users = [
            User(
                email=email,
                full_name=name,
                hashed_password=hashed,
                role=role,
                course=course,
                organization=organization,
                phone="+998901234567" if role is not UserRole.ADMIN else None,
                student_id=f"23000{course}{index}" if role is UserRole.STUDENT else None,
            )
            for index, (email, name, role, course, organization) in enumerate(USERS)
        ]
        categories = {slug: Category(name=name, slug=slug) for name, slug in CATEGORIES}
        db.add_all([*users, *categories.values()])
        await db.flush()

        employers = [user for user in users if user.role is UserRole.EMPLOYER]
        students = [user for user in users if user.role is UserRole.STUDENT]
        now = datetime.now(UTC)
        today = now.date()

        vacancies = []
        for index, row in enumerate(VACANCIES):
            title, slug, kind, remote, salary_min, salary_max, currency, course, status = row
            status = VacancyStatus(status)
            was_published = status in (VacancyStatus.PUBLISHED, VacancyStatus.CLOSED)
            employer = employers[index % len(employers)]
            vacancies.append(
                Vacancy(
                    employer_id=employer.id,
                    category_id=categories[slug].id,
                    title=title,
                    description=DESCRIPTION.format(title=title),
                    requirements="Ответственность, грамотная речь, желание учиться.",
                    employment_type=EmploymentType(kind),
                    location="Ташкент",
                    is_remote=remote,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=Currency(currency),
                    target_course=course,
                    contact_email=employer.email,
                    deadline=today + timedelta(days=14 + index * 3),
                    status=status,
                    moderation_comment=(
                        "Укажите подробнее обязанности и условия оплаты."
                        if status is VacancyStatus.REJECTED
                        else None
                    ),
                    published_at=now - timedelta(days=index, hours=index)
                    if was_published
                    else None,
                )
            )
        db.add_all(vacancies)
        await db.flush()

        published = [v for v in vacancies if v.status is VacancyStatus.PUBLISHED]
        statuses = list(ApplicationStatus)
        applications = []
        for s_index, student in enumerate(students):
            for v_index, vacancy in enumerate(published):
                if (s_index + v_index) % 3 == 0:
                    number = len(applications)
                    applications.append(
                        Application(
                            vacancy_id=vacancy.id,
                            student_id=student.id,
                            cover_letter="Здравствуйте! Меня заинтересовала вакансия, готов пройти собеседование.",
                            status=statuses[number % len(statuses)],
                            created_at=now - timedelta(days=number % 12, hours=number),
                        )
                    )
        db.add_all(applications)
        await db.commit()

        print(
            f"Создано: пользователей {len(users)}, категорий {len(categories)}, "
            f"вакансий {len(vacancies)}, откликов {len(applications)}."
        )
        print(f"\nТестовые аккаунты (пароль у всех: {SEED_PASSWORD}):")
        for user in users:
            extra = f"  (ID студента: {user.student_id})" if user.student_id else ""
            print(f"  {user.role.value:<9} {user.email}{extra}")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
