from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.applications import Application
from app.models.categories import Category
from app.models.vacancies import Vacancy, VacancyStatus
from app.schemas.stats import AdminStats, CategoryStat, DayStat

STATS_DAYS = 14

_BY_DAY_SQL = text(
    """
    SELECT CAST(d.day AS date) AS day, count(a.id) AS applications
    FROM generate_series(
        CAST(timezone('UTC', now()) AS date) - (:days - 1),
        CAST(timezone('UTC', now()) AS date),
        interval '1 day'
    ) AS d(day)
    LEFT JOIN applications AS a
        ON CAST(timezone('UTC', a.created_at) AS date) = CAST(d.day AS date)
    GROUP BY d.day
    ORDER BY d.day
    """
)


async def get_admin_stats(db: AsyncSession) -> AdminStats:
    """Сводка для админ-панели. Все агрегаты считает PostgreSQL (GROUP BY), а не Python."""
    status_rows = await db.execute(select(Vacancy.status, func.count()).group_by(Vacancy.status))
    by_status = {status.value: 0 for status in VacancyStatus}
    by_status.update({status.value: count for status, count in status_rows})

    applications_total = await db.scalar(select(func.count()).select_from(Application)) or 0

    applications_count = func.count(Application.id)
    top_rows = await db.execute(
        select(Category.id, Category.name, applications_count)
        .join(Vacancy, Vacancy.category_id == Category.id)
        .join(Application, Application.vacancy_id == Vacancy.id)
        .group_by(Category.id, Category.name)
        .order_by(applications_count.desc(), Category.name)
        .limit(5)
    )
    day_rows = await db.execute(_BY_DAY_SQL, {"days": STATS_DAYS})

    return AdminStats(
        vacancies_by_status=by_status,
        vacancies_total=sum(by_status.values()),
        applications_total=applications_total,
        top_categories=[
            CategoryStat(category_id=cid, name=name, applications=count)
            for cid, name, count in top_rows
        ],
        applications_by_day=[DayStat(day=day, applications=count) for day, count in day_rows],
    )
