from datetime import date, timedelta

from tests.utils import (
    API,
    create_admin,
    create_category,
    create_vacancy,
    employer_payload,
    field_errors,
    publish_vacancy,
    register,
    student_payload,
    vacancy_payload,
)


async def setup(client, db):
    """Админ, работодатель и одна категория."""
    admin = await create_admin(client, db)
    employer = await register(client, employer_payload())
    category_id = await create_category(client, admin)
    return admin, employer, category_id


async def test_create_vacancy_success(client, db):
    _, employer, category_id = await setup(client, db)
    vacancy = await create_vacancy(client, employer, category_id)
    assert vacancy["status"] == "draft"
    assert vacancy["currency"] == "UZS"
    assert vacancy["category"]["slug"] == "it"
    assert vacancy["employer"]["organization"] == "Отдел карьеры"
    assert vacancy["published_at"] is None


async def test_create_vacancy_requires_employer_role(client, db):
    _, _, category_id = await setup(client, db)
    student = await register(client, student_payload())
    response = await client.post(
        f"{API}/vacancies", json=vacancy_payload(category_id), headers=student
    )
    assert response.status_code == 403
    response = await client.post(f"{API}/vacancies", json=vacancy_payload(category_id))
    assert response.status_code == 401


async def test_create_vacancy_deadline_in_past(client, db):
    _, employer, category_id = await setup(client, db)
    for bad_deadline in (date.today() - timedelta(days=1), date.today() + timedelta(days=400)):
        response = await client.post(
            f"{API}/vacancies",
            json=vacancy_payload(category_id, deadline=bad_deadline.isoformat()),
            headers=employer,
        )
        assert response.status_code == 422
        assert "body.deadline" in field_errors(response)


async def test_create_vacancy_salary_min_greater_than_max(client, db):
    _, employer, category_id = await setup(client, db)
    response = await client.post(
        f"{API}/vacancies",
        json=vacancy_payload(category_id, salary_min=500, salary_max=100),
        headers=employer,
    )
    assert response.status_code == 422
    assert field_errors(response) == {
        "body.salary_max": "Максимальная зарплата не может быть меньше минимальной"
    }


async def test_create_vacancy_short_title_and_unknown_category(client, db):
    _, employer, category_id = await setup(client, db)
    response = await client.post(
        f"{API}/vacancies", json=vacancy_payload(category_id, title="Dev"), headers=employer
    )
    assert response.status_code == 422
    assert "body.title" in field_errors(response)

    response = await client.post(
        f"{API}/vacancies", json=vacancy_payload(category_id + 100), headers=employer
    )
    assert response.status_code == 422
    assert response.json()["code"] == "category_not_found"


async def test_foreign_vacancy_is_hidden(client, db):
    _, employer, category_id = await setup(client, db)
    other = await register(client, employer_payload(email="other@example.com"))
    vacancy = await create_vacancy(client, employer, category_id)
    url = f"{API}/vacancies/{vacancy['id']}"

    assert (
        await client.patch(url, json={"title": "Чужая правка"}, headers=other)
    ).status_code == 404
    assert (await client.delete(url, headers=other)).status_code == 404
    assert (await client.post(f"{url}/submit", headers=other)).status_code == 404
    assert (await client.get(url, headers=other)).status_code == 404
    assert (await client.get(url)).status_code == 404
    assert (await client.get(url, headers=employer)).status_code == 200


async def test_update_vacancy_checks_salary_against_saved_value(client, db):
    _, employer, category_id = await setup(client, db)
    vacancy = await create_vacancy(client, employer, category_id)
    url = f"{API}/vacancies/{vacancy['id']}"

    response = await client.patch(url, json={"salary_min": 9_000_000}, headers=employer)
    assert response.status_code == 422
    assert "body.salary_min" in field_errors(response)

    response = await client.patch(
        url, json={"title": "Junior Python-разработчик", "salary_max": None}, headers=employer
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Junior Python-разработчик"
    assert response.json()["salary_max"] is None

    response = await client.patch(url, json={"title": None}, headers=employer)
    assert response.status_code == 422
    assert "body.title" in field_errors(response)


async def test_forbidden_status_transitions(client, db):
    admin, employer, category_id = await setup(client, db)
    vacancy = await create_vacancy(client, employer, category_id)
    url = f"{API}/vacancies/{vacancy['id']}"
    admin_url = f"{API}/admin/vacancies/{vacancy['id']}"

    # draft нельзя закрыть или одобрить
    assert (await client.post(f"{url}/close", headers=employer)).status_code == 409
    response = await client.post(f"{admin_url}/approve", headers=admin)
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_status_transition"

    assert (await client.post(f"{url}/submit", headers=employer)).status_code == 200
    # pending нельзя отправить повторно, править и удалить
    assert (await client.post(f"{url}/submit", headers=employer)).status_code == 409
    assert (
        await client.patch(url, json={"location": "Самарканд"}, headers=employer)
    ).status_code == 409
    assert (await client.delete(url, headers=employer)).status_code == 409


async def test_delete_draft(client, db):
    _, employer, category_id = await setup(client, db)
    vacancy = await create_vacancy(client, employer, category_id)
    url = f"{API}/vacancies/{vacancy['id']}"
    assert (await client.delete(url, headers=employer)).status_code == 204
    assert (await client.get(url, headers=employer)).status_code == 404


async def test_moderation_approve_and_close(client, db):
    admin, employer, category_id = await setup(client, db)
    vacancy = await create_vacancy(client, employer, category_id)
    await client.post(f"{API}/vacancies/{vacancy['id']}/submit", headers=employer)

    queue = await client.get(f"{API}/admin/vacancies", params={"status": "pending"}, headers=admin)
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()["items"]] == [vacancy["id"]]

    response = await client.post(f"{API}/admin/vacancies/{vacancy['id']}/approve", headers=admin)
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["published_at"] is not None

    # опубликованная видна всем
    assert (await client.get(f"{API}/vacancies/{vacancy['id']}")).status_code == 200

    response = await client.post(f"{API}/vacancies/{vacancy['id']}/close", headers=employer)
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


async def test_moderation_reject_requires_comment_then_resubmit(client, db):
    admin, employer, category_id = await setup(client, db)
    vacancy = await create_vacancy(client, employer, category_id)
    url = f"{API}/vacancies/{vacancy['id']}"
    reject_url = f"{API}/admin/vacancies/{vacancy['id']}/reject"
    await client.post(f"{url}/submit", headers=employer)

    assert (await client.post(reject_url, json={}, headers=admin)).status_code == 422
    response = await client.post(reject_url, json={"comment": "мало"}, headers=admin)
    assert response.status_code == 422
    assert "body.comment" in field_errors(response)

    response = await client.post(
        reject_url, json={"comment": "Уточните условия оплаты и график."}, headers=admin
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["moderation_comment"] == "Уточните условия оплаты и график."

    # после правок отклонённую можно отправить снова
    assert (
        await client.patch(url, json={"location": "Самарканд"}, headers=employer)
    ).status_code == 200
    response = await client.post(f"{url}/submit", headers=employer)
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_admin_endpoints_require_admin(client, db):
    _, employer, _ = await setup(client, db)
    assert (await client.get(f"{API}/admin/vacancies", headers=employer)).status_code == 403
    assert (await client.get(f"{API}/admin/stats", headers=employer)).status_code == 403
    response = await client.post(
        f"{API}/categories", json={"name": "Дизайн", "slug": "design"}, headers=employer
    )
    assert response.status_code == 403


async def test_list_shows_only_published(client, db):
    admin, employer, category_id = await setup(client, db)
    published = await publish_vacancy(client, employer, admin, category_id)
    await create_vacancy(client, employer, category_id, title="Черновик вакансии")
    pending = await create_vacancy(client, employer, category_id, title="На модерации")
    await client.post(f"{API}/vacancies/{pending['id']}/submit", headers=employer)
    closed = await publish_vacancy(client, employer, admin, category_id, title="Закрытая вакансия")
    await client.post(f"{API}/vacancies/{closed['id']}/close", headers=employer)

    response = await client.get(f"{API}/vacancies")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [published["id"]]

    mine = await client.get(f"{API}/vacancies/my", headers=employer)
    assert mine.json()["total"] == 4


async def test_list_filters(client, db):
    admin, employer, it_id = await setup(client, db)
    design_id = await create_category(client, admin, "Дизайн", "design")
    await publish_vacancy(client, employer, admin, it_id, title="Backend-разработчик")
    await publish_vacancy(
        client,
        employer,
        admin,
        design_id,
        title="UI-дизайнер интерфейсов",
        is_remote=True,
        employment_type="part_time",
        salary_min=8_000_000,
        salary_max=9_000_000,
        target_course=4,
    )

    async def titles(**params) -> list[str]:
        response = await client.get(f"{API}/vacancies", params=params)
        assert response.status_code == 200, response.text
        return [item["title"] for item in response.json()["items"]]

    assert await titles(category_id=design_id) == ["UI-дизайнер интерфейсов"]
    assert await titles(q="backend") == ["Backend-разработчик"]
    assert await titles(is_remote="true") == ["UI-дизайнер интерфейсов"]
    assert await titles(employment_type="internship") == ["Backend-разработчик"]
    assert await titles(salary_from=6_000_000) == ["UI-дизайнер интерфейсов"]
    assert await titles(course=2) == ["Backend-разработчик"]
    assert await titles(sort="salary") == ["UI-дизайнер интерфейсов", "Backend-разработчик"]

    response = await client.get(f"{API}/vacancies", params={"limit": 100})
    assert response.status_code == 422
    assert "query.limit" in field_errors(response)
    response = await client.get(f"{API}/vacancies", params={"unknown": 1})
    assert response.status_code == 422


async def test_list_pagination(client, db):
    admin, employer, category_id = await setup(client, db)
    for number in range(1, 6):
        await publish_vacancy(
            client, employer, admin, category_id, title=f"Вакансия номер {number}"
        )

    first = (await client.get(f"{API}/vacancies", params={"limit": 2})).json()
    assert first["total"] == 5
    assert first["limit"] == 2
    assert first["offset"] == 0
    assert [item["title"] for item in first["items"]] == ["Вакансия номер 5", "Вакансия номер 4"]

    last = (await client.get(f"{API}/vacancies", params={"limit": 2, "offset": 4})).json()
    assert [item["title"] for item in last["items"]] == ["Вакансия номер 1"]


async def test_category_in_use_cannot_be_deleted(client, db):
    admin, employer, category_id = await setup(client, db)
    await create_vacancy(client, employer, category_id)
    response = await client.delete(f"{API}/categories/{category_id}", headers=admin)
    assert response.status_code == 409
    assert response.json()["code"] == "category_in_use"

    response = await client.post(
        f"{API}/categories", json={"name": "IT", "slug": "it2"}, headers=admin
    )
    assert response.status_code == 409

    free_id = await create_category(client, admin, "Маркетинг", "marketing")
    assert (await client.delete(f"{API}/categories/{free_id}", headers=admin)).status_code == 204
    assert len((await client.get(f"{API}/categories")).json()) == 1
