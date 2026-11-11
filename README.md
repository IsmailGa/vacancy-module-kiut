# University Jobs — backend

REST API модуля вакансий университета: студенты ищут вакансии и откликаются, работодатели
публикуют вакансии, администратор модерирует. Frontend (Vue 3) пишется отдельно.

Стек: Python 3.13, FastAPI, SQLAlchemy 2.0 async + asyncpg, PostgreSQL 17, Alembic, Pydantic v2,
pwdlib (Argon2), PyJWT, pytest, ruff, Docker.

## Быстрый старт в Docker

```bash
cp .env.example .env
```

Заполните в `.env` пароль БД и `SECRET_KEY`, затем:

```bash
docker compose up --build
```

Миграции применяются автоматически перед стартом сервера. Тестовые данные:

```bash
docker compose exec backend python -m scripts.seed
```

- Swagger: http://localhost:8000/docs
- Проверка: http://localhost:8000/api/v1/health

Если порты 5432 или 8000 на хосте заняты, поменяйте `DB_HOST_PORT` / `BACKEND_HOST_PORT` в `.env`.

## Локальная разработка

Нужны `uv` и Docker. Все команды выполняются из папки `back`.

```bash
docker compose up -d db
```

```bash
uv sync
```

```bash
uv run alembic upgrade head
```

```bash
uv run python -m scripts.seed
```

```bash
uv run fastapi dev
```

Если `DB_HOST_PORT` в `.env` отличается от 5432, укажите там же такой же `POSTGRES_PORT`:
локальное приложение подключается к `POSTGRES_HOST:POSTGRES_PORT`.

## Тесты и качество

```bash
uv run pytest
```

```bash
uv run ruff check .
```

```bash
uv run ruff format .
```

Тесты используют отдельную базу `<POSTGRES_DB>_test` на том же сервере PostgreSQL (создаётся автоматически),
поэтому контейнер `db` должен быть запущен.

## Миграции

```bash
uv run alembic revision --autogenerate -m "описание"
```

```bash
uv run alembic upgrade head
```

## Тестовые аккаунты (после seed)

Пароль у всех: `Password123`.

| Роль | Email | ID студента |
|---|---|---|
| admin | admin@kiut.uz | |
| employer | career@kiut.uz | |
| employer | hr@techpark.uz | |
| student | student1@kiut.uz | 2300013 |
| student | student2@kiut.uz | 2300024 |
| student | student3@kiut.uz | 2300035 |
| student | student4@kiut.uz | 2300046 |
| student | student5@kiut.uz | 2300047 |

Студент может войти по email или по ID студента. В Swagger нажмите **Authorize** и введите логин и пароль.

## Структура

```
app/
  main.py        приложение, CORS, обработчики ошибок, lifespan
  deps.py        DbSession, CurrentUser, require_roles
  core/          настройки, БД, безопасность, ошибки
  models/        таблицы SQLAlchemy
  schemas/       Pydantic: валидация и ответы
  services/      бизнес-логика
  router/        эндпоинты /api/v1
alembic/         миграции
scripts/seed.py  тестовые данные
tests/           pytest
docs/            документация для отчёта
```

## Документация

- [ER-диаграмма](docs/ER_DIAGRAM.md)
- [Архитектура](docs/ARCHITECTURE.md)
- [Сценарии использования](docs/USE_CASES.md)
- [Валидация](docs/VALIDATION.md)
- [Потоки данных](docs/DATA_FLOW.md)
- [Решения и следующие шаги](docs/DECISIONS.md)
