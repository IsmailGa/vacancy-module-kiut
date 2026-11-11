from tests.utils import (
    API,
    PASSWORD,
    employer_payload,
    field_errors,
    login,
    register,
    student_payload,
)


async def test_health(client):
    response = await client.get(f"{API}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_register_student_success(client):
    payload = student_payload(email="  Student@Example.COM ", full_name="  Алишер   Каримов ")
    response = await client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "student@example.com"
    assert body["full_name"] == "Алишер Каримов"
    assert body["role"] == "student"
    assert body["course"] == 3
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_employer_success(client):
    response = await client.post(
        f"{API}/auth/register", json=employer_payload(phone="+998 90 123-45-67")
    )
    assert response.status_code == 201
    assert response.json()["phone"] == "+998901234567"
    assert response.json()["organization"] == "Отдел карьеры"


async def test_register_duplicate_email(client):
    await register(client, student_payload())
    response = await client.post(
        f"{API}/auth/register", json=student_payload(email="STUDENT@example.com")
    )
    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


async def test_register_weak_password(client):
    response = await client.post(
        f"{API}/auth/register", json=student_payload(password="onlyletters")
    )
    assert response.status_code == 422
    assert "body.password" in field_errors(response)

    response = await client.post(f"{API}/auth/register", json=student_payload(password="a1"))
    assert response.status_code == 422
    assert "body.password" in field_errors(response)


async def test_register_admin_role_forbidden(client):
    payload = student_payload(role="admin")
    payload.pop("course")
    response = await client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 422
    assert "body.role" in field_errors(response)


async def test_register_student_without_course(client):
    payload = student_payload()
    payload.pop("course")
    response = await client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 422
    assert "body.course" in field_errors(response)


async def test_register_employer_without_organization(client):
    payload = employer_payload()
    payload.pop("organization")
    response = await client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 422
    assert "body.organization" in field_errors(response)


async def test_register_rejects_bad_fields(client):
    payload = student_payload(
        email="not-an-email", full_name="R2-D2", phone="12345", unknown_field="x"
    )
    response = await client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 422
    errors = field_errors(response)
    assert {"body.email", "body.full_name", "body.phone", "body.unknown_field"} <= set(errors)
    assert errors["body.email"] == "Некорректный email"


async def test_login_success_and_me(client):
    headers = await register(client, student_payload())
    response = await client.get(f"{API}/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "student@example.com"


async def test_login_wrong_password_and_unknown_user_look_the_same(client):
    await register(client, student_payload())
    wrong_password = await client.post(
        f"{API}/auth/login", data={"username": "student@example.com", "password": "Wrong12345"}
    )
    unknown_user = await client.post(
        f"{API}/auth/login", data={"username": "nobody@example.com", "password": PASSWORD}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.json()["detail"] == "Неверный логин или пароль"
    assert wrong_password.headers["www-authenticate"] == "Bearer"


async def test_me_requires_valid_token(client):
    response = await client.get(f"{API}/users/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    response = await client.get(f"{API}/users/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


async def test_update_profile_respects_role(client):
    headers = await register(client, student_payload())
    response = await client.patch(
        f"{API}/users/me", json={"full_name": "Алишер Валиев", "course": 4}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Алишер Валиев"
    assert response.json()["course"] == 4

    response = await client.patch(
        f"{API}/users/me", json={"organization": "Компания"}, headers=headers
    )
    assert response.status_code == 422
    assert "body.organization" in field_errors(response)

    assert await login(client, "student@example.com")


async def test_login_by_student_id(client):
    response = await client.post(f"{API}/auth/register", json=student_payload(student_id="2300001"))
    assert response.status_code == 201
    assert response.json()["student_id"] == "2300001"

    headers = await login(client, "2300001")
    me = await client.get(f"{API}/users/me", headers=headers)
    assert me.json()["email"] == "student@example.com"

    response = await client.post(
        f"{API}/auth/login", data={"username": "2300001", "password": "Wrong12345"}
    )
    assert response.status_code == 401


async def test_student_id_validation(client):
    await register(client, student_payload(student_id="2300001"))
    duplicate = await client.post(
        f"{API}/auth/register",
        json=student_payload(email="second@example.com", student_id="2300001"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "student_id_taken"

    bad_format = await client.post(
        f"{API}/auth/register",
        json=student_payload(email="third@example.com", student_id="23A0001"),
    )
    assert bad_format.status_code == 422
    assert "body.student_id" in field_errors(bad_format)

    employer = await client.post(
        f"{API}/auth/register", json=employer_payload(student_id="2300002")
    )
    assert employer.status_code == 422
    assert "body.student_id" in field_errors(employer)
