from tests.utils import (
    API,
    PASSWORD,
    PDF_BYTES,
    create_admin,
    create_category,
    employer_payload,
    publish_vacancy,
    register,
    student_payload,
)


async def test_admin_lists_and_filters_users(client, db):
    admin = await create_admin(client, db)
    await register(client, student_payload(student_id="2300001"))
    employer = await register(client, employer_payload())

    response = await client.get(f"{API}/admin/users", headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert "hashed_password" not in body["items"][0]

    students = await client.get(f"{API}/admin/users", params={"role": "student"}, headers=admin)
    assert [user["email"] for user in students.json()["items"]] == ["student@example.com"]

    by_id = await client.get(f"{API}/admin/users", params={"q": "2300001"}, headers=admin)
    assert by_id.json()["total"] == 1

    assert (await client.get(f"{API}/admin/users", headers=employer)).status_code == 403


async def test_admin_blocks_and_unblocks_user(client, db):
    admin = await create_admin(client, db)
    student = await register(client, student_payload())
    student_id = (await client.get(f"{API}/users/me", headers=student)).json()["id"]
    admin_id = (await client.get(f"{API}/users/me", headers=admin)).json()["id"]
    url = f"{API}/admin/users/{student_id}/active"

    response = await client.patch(url, json={"is_active": False}, headers=admin)
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert (await client.get(f"{API}/users/me", headers=student)).status_code == 403
    login = await client.post(
        f"{API}/auth/login", data={"username": "student@example.com", "password": PASSWORD}
    )
    assert login.status_code == 403

    response = await client.patch(url, json={"is_active": True}, headers=admin)
    assert response.json()["is_active"] is True
    assert (await client.get(f"{API}/users/me", headers=student)).status_code == 200

    own = await client.patch(
        f"{API}/admin/users/{admin_id}/active", json={"is_active": False}, headers=admin
    )
    assert own.status_code == 409
    assert own.json()["code"] == "cannot_deactivate_self"
    missing = await client.patch(
        f"{API}/admin/users/9999/active", json={"is_active": False}, headers=admin
    )
    assert missing.status_code == 404


async def test_admin_sees_all_applications_and_resumes(client, db):
    admin = await create_admin(client, db)
    employer = await register(client, employer_payload())
    student = await register(client, student_payload())
    category_id = await create_category(client, admin)
    vacancy = await publish_vacancy(client, employer, admin, category_id)
    created = await client.post(
        f"{API}/vacancies/{vacancy['id']}/applications",
        files={"resume": ("cv.pdf", PDF_BYTES, "application/pdf")},
        headers=student,
    )
    assert created.status_code == 201

    response = await client.get(f"{API}/admin/applications", headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["vacancy"]["title"] == vacancy["title"]
    assert body["items"][0]["student"]["email"] == "student@example.com"

    empty = await client.get(
        f"{API}/admin/applications", params={"status": "accepted"}, headers=admin
    )
    assert empty.json()["total"] == 0
    assert (await client.get(f"{API}/admin/applications", headers=student)).status_code == 403

    resume = await client.get(f"{API}/applications/{created.json()['id']}/resume", headers=admin)
    assert resume.status_code == 200
    assert resume.content == PDF_BYTES

    stats = (await client.get(f"{API}/admin/stats", headers=admin)).json()
    assert stats["users_by_role"] == {"student": 1, "employer": 1, "admin": 1}
    assert stats["users_total"] == 3
