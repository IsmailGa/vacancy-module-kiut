# ER-диаграмма

Диаграмма построена по реальным моделям из `app/models/` (схема создаётся миграциями Alembic).

```mermaid
erDiagram
    users ||--o{ vacancies : "публикует (employer_id)"
    categories ||--o{ vacancies : "содержит (category_id)"
    vacancies ||--o{ applications : "получает (vacancy_id)"
    users ||--o{ applications : "отправляет (student_id)"

    users {
        int id PK
        varchar(255) email UK "нижний регистр, индекс"
        varchar(7) student_id UK "nullable, 7 цифр"
        varchar(100) full_name
        varchar(20) phone "nullable"
        varchar(255) hashed_password "Argon2"
        varchar(20) role "student | employer | admin"
        smallint course "nullable, 1-6"
        varchar(150) organization "nullable"
        boolean is_active "default true"
        timestamptz created_at "default now()"
    }

    categories {
        int id PK
        varchar(100) name UK
        varchar(100) slug UK
    }

    vacancies {
        int id PK
        int employer_id FK "users.id, RESTRICT"
        int category_id FK "categories.id, RESTRICT"
        varchar(150) title
        text description
        text requirements "nullable"
        varchar(20) employment_type "full_time | part_time | internship | project"
        varchar(100) location
        boolean is_remote "default false"
        int salary_min "nullable"
        int salary_max "nullable"
        varchar(20) currency "UZS | USD, default UZS"
        smallint target_course "nullable, 1-6"
        varchar(255) contact_email
        date deadline "индекс"
        varchar(20) status "draft | pending | published | rejected | closed"
        varchar(500) moderation_comment "nullable"
        timestamptz created_at
        timestamptz updated_at
        timestamptz published_at "nullable"
    }

    applications {
        int id PK
        int vacancy_id FK "vacancies.id, CASCADE"
        int student_id FK "users.id, CASCADE"
        text cover_letter "nullable"
        varchar(64) resume_path "nullable, uuid4.pdf"
        varchar(255) resume_original_name "nullable"
        varchar(20) status "sent | viewed | accepted | rejected"
        timestamptz created_at
    }
```

## Таблицы

### users (`app/models/users.py`)
Все учётные записи: студенты, работодатели (сотрудники университета) и администраторы. Роль хранится
в `role`. `course` заполняется только у студентов, `organization` только у работодателей.
`student_id` — необязательный 7-значный ID студента в университете, по нему можно входить вместо email.
Пароль хранится только как Argon2-хеш в `hashed_password`.

Ограничения: `uq_users_student_id`, уникальный индекс `ix_users_email`,
`ck_users_course_range` (1–6), `ck_users_email_lowercase`, `ck_users_student_id_format` (7 цифр),
`ck_users_role`.

### categories (`app/models/categories.py`)
Справочник категорий вакансий. `name` и `slug` уникальны.

### vacancies (`app/models/vacancies.py`)
Вакансия принадлежит работодателю (`employer_id`) и категории (`category_id`). Оба внешних ключа
`RESTRICT`: нельзя удалить пользователя или категорию, пока есть их вакансии. Жизненный цикл
задаётся полем `status`, комментарий модератора при отклонении лежит в `moderation_comment`.

Индексы: `ix_vacancies_status_category_id (status, category_id)` для публичной ленты,
`ix_vacancies_deadline`, `ix_vacancies_employer_id`.
CHECK: `ck_vacancies_salary_range` (`salary_min <= salary_max`, если оба заданы),
`ck_vacancies_salary_non_negative`, `ck_vacancies_target_course_range` (1–6),
`ck_vacancies_employment_type`, `ck_vacancies_currency`, `ck_vacancies_status`.

### applications (`app/models/applications.py`)
Отклик студента на вакансию. Внешние ключи `CASCADE`: отклики удаляются вместе с вакансией или
студентом. `uq_applications_vacancy_student (vacancy_id, student_id)` запрещает повторный отклик.
`resume_path` хранит только имя файла на диске (`<uuid4>.pdf` в `UPLOAD_DIR`), исходное имя файла
от клиента лежит отдельно в `resume_original_name` и на диск не попадает.

Индекс: `ix_applications_student_id`. CHECK: `ck_applications_status`.

## Общие правила

- Время хранится как `timestamptz` в UTC, `created_at` проставляет сервер БД (`now()`).
- Enum'ы хранятся как `varchar` + CHECK (`native_enum=False`), а не как типы PostgreSQL: так проще мигрировать.
- Имена индексов и ограничений задаёт `naming_convention` в `app/core/db.py`.
