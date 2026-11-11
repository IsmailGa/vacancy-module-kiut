# Валидация данных

Данные проверяются на двух уровнях. Pydantic-схема (`app/schemas/`) ловит ошибку первой и возвращает
понятное сообщение на русском. Ограничения в БД (CHECK / UNIQUE / FK, `app/models/`) страхуют от
обхода API. Правила, для которых нужна БД или текущий объект, проверяет сервис (`app/services/`).

Все входные схемы наследуются от `InputModel` (`app/schemas/common.py`):
`extra="forbid"` (лишнее поле даёт ошибку «Лишнее поле») и `str_strip_whitespace=True`.

Стандартные сообщения Pydantic переводятся на русский в `app/core/exceptions.py` (`_MESSAGES`):

| Правило | Сообщение |
|---|---|
| поле не передано | Обязательное поле |
| лишнее поле | Лишнее поле |
| строка короче минимума | Минимальная длина: N симв. |
| строка длиннее максимума | Максимальная длина: N симв. |
| число меньше / больше границы | Значение должно быть не меньше N / не больше N |
| не число | Ожидается целое число |
| значение не из enum | Допустимые значения: ... |
| не дата | Ожидается дата в формате ГГГГ-ММ-ДД |
| невалидный email | Некорректный email |

Ниже в колонке «Сообщение» для таких правил написано «стандартное».

## Пользователь (`UserCreate`, `UserUpdate` в `app/schemas/users.py`)

| Поле | Правило | Сообщение об ошибке | Где проверяется |
|---|---|---|---|
| `email` | валидный email, приводится к нижнему регистру | Некорректный email | Pydantic (`EmailStr`, `lower_email`); БД: `ck_users_email_lowercase` |
| `email` | не занят | Пользователь с таким email уже зарегистрирован (409 `email_taken`) | сервис `register_user`; БД: уникальный индекс `ix_users_email` |
| `full_name` | пробелы схлопываются, 2–100 символов | ФИО должно быть длиной от 2 до 100 символов | Pydantic (`clean_full_name`); БД: `varchar(100)` |
| `full_name` | только буквы, пробел, дефис, апостроф | ФИО может содержать только буквы, пробел, дефис и апостроф | Pydantic (`clean_full_name`) |
| `phone` | необязательно; без пробелов и дефисов `^\+?\d{9,15}$` | Телефон: от 9 до 15 цифр, можно с + в начале | Pydantic (`clean_phone`); БД: `varchar(20)` |
| `password` | 8–64 символа | стандартное (длина) | Pydantic (`Field`) |
| `password` | минимум одна буква и одна цифра | Пароль должен содержать минимум одну букву и одну цифру | Pydantic (`check_password`) |
| `role` | `student` или `employer` | Зарегистрироваться можно только как student или employer | Pydantic (`forbid_admin`); БД: `ck_users_role` |
| `course` | 1–6 | стандартное (границы) | Pydantic (`Field`); БД: `ck_users_course_range` |
| `course` | обязателен для студента | Для студента нужно указать курс (1–6) | Pydantic (`check_role_fields`); в `PATCH /users/me` сервис `update_profile` |
| `course` | отсутствует у остальных ролей | Курс указывается только студентом | Pydantic (`check_role_fields`); сервис `update_profile` |
| `organization` | 2–150 символов | стандартное (длина) | Pydantic (`Field`); БД: `varchar(150)` |
| `organization` | обязательна для работодателя | Для работодателя нужно указать организацию | Pydantic (`check_role_fields`); сервис `update_profile` |
| `organization` | отсутствует у студента | Организация указывается только работодателем | Pydantic (`check_role_fields`); сервис `update_profile` |
| `student_id` | необязательно; ровно 7 цифр | ID студента должен состоять ровно из 7 цифр | Pydantic (`check_student_id`); БД: `ck_users_student_id_format` |
| `student_id` | только у студента | ID студента указывается только студентом | Pydantic (`check_role_fields`) |
| `student_id` | не занят | Этот ID студента уже зарегистрирован (409 `student_id_taken`) | сервис `register_user`; БД: `uq_users_student_id` |
| `full_name` в `UserUpdate` | нельзя передать `null` | ФИО не может быть пустым | Pydantic (`check_name`) |

## Вход (`POST /auth/login`)

| Поле | Правило | Сообщение об ошибке | Где проверяется |
|---|---|---|---|
| `username`, `password` | обязательны | стандартное | FastAPI (`OAuth2PasswordRequestForm`) |
| `username` + `password` | пользователь найден по email или ID студента, пароль верный | Неверный логин или пароль (401 `invalid_credentials`), одинаково для обоих случаев | сервис `authenticate` |
| учётная запись | активна | Учётная запись отключена (403 `user_inactive`) | сервис `authenticate`, `deps.get_current_user` |

## Категория (`CategoryCreate`, `CategoryUpdate` в `app/schemas/categories.py`)

| Поле | Правило | Сообщение об ошибке | Где проверяется |
|---|---|---|---|
| `name` | 2–100 символов | стандартное (длина) | Pydantic; БД: `varchar(100)` |
| `slug` | 2–100, `^[a-z0-9]+(?:-[a-z0-9]+)*$` | Недопустимый формат | Pydantic (`Slug`) |
| `name`, `slug` | уникальны | Категория с таким названием или slug уже есть (409 `category_exists`) | сервис `_ensure_unique`; БД: `uq_categories_name`, `uq_categories_slug` |
| `name`, `slug` в `CategoryUpdate` | нельзя передать `null` | Поле не может быть пустым | Pydantic (`not_null`) |
| удаление | категория не используется вакансиями | Категория используется в вакансиях (409 `category_in_use`) | сервис `delete_category`; БД: FK `RESTRICT` |

## Вакансия (`VacancyCreate`, `VacancyUpdate` в `app/schemas/vacancies.py`)

| Поле | Правило | Сообщение об ошибке | Где проверяется |
|---|---|---|---|
| `title` | 5–150 символов | стандартное (длина) | Pydantic; БД: `varchar(150)` |
| `description` | 30–5000 символов | стандартное (длина) | Pydantic |
| `requirements` | необязательно, до 3000 | стандартное (длина) | Pydantic |
| `category_id` | категория существует | Категория не найдена (422 `category_not_found`, поле `body.category_id`) | сервис `_ensure_category_exists`; БД: FK `fk_vacancies_category_id_categories` |
| `employment_type` | `full_time` / `part_time` / `internship` / `project` | стандартное (enum) | Pydantic; БД: `ck_vacancies_employment_type` |
| `location` | 2–100 символов | стандартное (длина) | Pydantic; БД: `varchar(100)` |
| `salary_min`, `salary_max` | необязательно, 0…1 000 000 000 | стандартное (границы) | Pydantic; БД: `ck_vacancies_salary_non_negative` |
| `salary_max` | `salary_min <= salary_max` | Максимальная зарплата не может быть меньше минимальной | Pydantic (`check_salary_order`); при `PATCH` с одним полем сервис `update_vacancy`; БД: `ck_vacancies_salary_range` |
| `currency` | `UZS` / `USD`, по умолчанию `UZS` | стандартное (enum) | Pydantic; БД: `ck_vacancies_currency` |
| `target_course` | необязательно, 1–6 | стандартное (границы) | Pydantic; БД: `ck_vacancies_target_course_range` |
| `contact_email` | валидный email | Некорректный email | Pydantic (`EmailStr`) |
| `deadline` | строго в будущем | Дедлайн должен быть в будущем | Pydantic (`check_deadline`) |
| `deadline` | не позже чем через 365 дней | Дедлайн не может быть позже чем через 365 дней | Pydantic (`check_deadline`) |
| обязательные поля в `VacancyUpdate` | нельзя передать `null` | Поле не может быть пустым | Pydantic (`forbid_null_for_required`) |
| правка | статус `draft` или `rejected` | Редактировать можно только черновик или отклонённую вакансию (409 `vacancy_not_editable`) | сервис `update_vacancy` |
| удаление | статус `draft` | Удалить можно только черновик (409 `vacancy_not_deletable`) | сервис `delete_vacancy` |
| смена статуса | переход есть в `ALLOWED_TRANSITIONS` | Нельзя перевести вакансию из статуса «X» в «Y» (409 `invalid_status_transition`) | сервис `_change_status`; БД: `ck_vacancies_status` |
| отправка на модерацию | дедлайн ещё не прошёл | Дедлайн вакансии уже прошёл, обновите его перед отправкой (409 `vacancy_deadline_passed`) | сервис `submit_vacancy` |
| владелец | вакансия принадлежит текущему работодателю | Вакансия не найдена (404 `vacancy_not_found`) | сервис `get_owned` |

## Модерация (`VacancyReject`)

| Поле | Правило | Сообщение об ошибке | Где проверяется |
|---|---|---|---|
| `comment` | обязателен, 10–500 символов | стандартное (обязательность, длина) | Pydantic; БД: `varchar(500)` |

## Фильтр ленты (`VacancyFilter`, query-параметры `GET /vacancies`)

| Поле | Правило | Сообщение об ошибке | Где проверяется |
|---|---|---|---|
| `q` | до 100 символов | стандартное (длина) | Pydantic |
| `category_id` | целое ≥ 1 | стандартное | Pydantic |
| `employment_type` | значение enum | стандартное (enum) | Pydantic |
| `is_remote` | boolean | Ожидается true или false | Pydantic |
| `salary_from` | 0…1 000 000 000 | стандартное (границы) | Pydantic |
| `course` | 1–6 | стандартное (границы) | Pydantic |
| `sort` | `newest` / `deadline` / `salary` | стандартное (enum) | Pydantic |
| `limit` | 1–50, по умолчанию 20 | стандартное (границы) | Pydantic |
| `offset` | ≥ 0 | стандартное (границы) | Pydantic |
| неизвестный параметр | запрещён | Лишнее поле | Pydantic (`extra="forbid"`) |

Списки `GET /vacancies/my` и `GET /admin/vacancies` используют `VacancyStatusFilter`: `status` (enum), `limit`, `offset` с теми же правилами.

## Отклик (`multipart/form-data`, `ApplicationCreate` + `app/services/applications.py`)

| Поле | Правило | Сообщение об ошибке | Где проверяется |
|---|---|---|---|
| `cover_letter` | необязательно; если есть, 20–2000 символов | Сопроводительное письмо: от 20 до 2000 символов | Pydantic (`check_cover_letter`) |
| `resume` | `content_type` равен `application/pdf` | Резюме должно быть файлом PDF (415 `resume_not_pdf`) | сервис `_save_resume` |
| `resume` | файл начинается с сигнатуры `%PDF-` | Резюме должно быть файлом PDF (415 `resume_not_pdf`) | сервис `_save_resume` |
| `resume` | размер ≤ `MAX_RESUME_SIZE_MB` | Размер резюме не должен превышать N МБ (413 `resume_too_large`) | сервис `_save_resume` (считает по чанкам) |
| `resume` | имя на диске `uuid4().pdf`; имя от клиента очищается и хранится только для показа | — | сервис `_save_resume`, `clean_filename` |
| вакансия | существует и в статусе `published` | Вакансия не найдена (404 `vacancy_not_found`) | сервис `create_application`; БД: FK |
| вакансия | дедлайн не прошёл | Срок подачи откликов на вакансию истёк (409 `vacancy_expired`) | сервис `create_application` |
| отклик | один на пару студент–вакансия | Вы уже откликнулись на эту вакансию (409 `already_applied`) | сервис `create_application`; БД: `uq_applications_vacancy_student` |

## Статус отклика (`ApplicationStatusUpdate`)

| Поле | Правило | Сообщение об ошибке | Где проверяется |
|---|---|---|---|
| `status` | только `viewed`, `accepted`, `rejected` | Допустимые статусы: viewed, accepted, rejected | Pydantic (`forbid_sent`); БД: `ck_applications_status` |
| переход | из `sent` или `viewed`; `accepted` и `rejected` конечные | Нельзя перевести отклик из статуса «X» в «Y» (409 `invalid_status_transition`) | сервис `change_status` (`ALLOWED_TRANSITIONS`) |
| владелец | отклик на вакансию текущего работодателя | Отклик не найден (404 `application_not_found`) | сервис `change_status` |

## Формат ответа 422

```json
{
  "detail": "Ошибка валидации",
  "code": "validation_error",
  "errors": [
    {"field": "body.salary_max", "message": "Максимальная зарплата не может быть меньше минимальной"}
  ]
}
```

`field` состоит из источника (`body`, `query`, `path`) и имени поля. Ошибки, зависящие от нескольких
полей (`check_role_fields`), тоже привязываются к конкретному полю через `FieldError`.
