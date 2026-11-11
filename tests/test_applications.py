from pathlib import Path

from app.core.config import settings
from tests.utils import (
    API,
    PDF_BYTES,
    create_admin,
    create_category,
    create_vacancy,
    employer_payload,
    field_errors,
    publish_vacancy,
    register,
    student_payload,
)

COVER_LETTER = "Здравствуйте! Хочу пройти стажировку в вашей команде."


async def setup(client, db):
    """Админ, работодатель, студент и опубликованная вакансия."""
    admin = await create_admin(client, db)
    employer = await register(client, employer_payload())
    student = await register(client, student_payload())
    category_id = await create_category(client, admin)
    vacancy = await publish_vacancy(client, employer, admin, category_id)
    return admin, employer, student, vacancy


def pdf(
    name: str = "resume.pdf", content: bytes = PDF_BYTES, content_type: str = "application/pdf"
):
    return {"resume": (name, content, content_type)}


async def apply(client, student, vacancy_id, files=None, cover_letter=COVER_LETTER):
    data = {"cover_letter": cover_letter} if cover_letter is not None else None
    return await client.post(
        f"{API}/vacancies/{vacancy_id}/applications", data=data, files=files, headers=student
    )


async def test_apply_success_with_resume(client, db):
    _, _, student, vacancy = await setup(client, db)
    response = await apply(client, student, vacancy["id"], pdf("../../Моё резюме.pdf"))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "sent"
    assert body["has_resume"] is True
    assert body["resume_original_name"] == "Моё резюме.pdf"
    assert "resume_path" not in body

    # на диске файл лежит под uuid-именем, а не под именем от клиента
    stored = list(Path(settings.UPLOAD_DIR).iterdir())
    assert len(stored) == 1
    assert stored[0].suffix == ".pdf"
    assert len(stored[0].stem) == 32
    assert stored[0].read_bytes() == PDF_BYTES

    mine = await client.get(f"{API}/applications/my", headers=student)
    assert mine.status_code == 200
    assert mine.json()[0]["vacancy"]["title"] == vacancy["title"]


async def test_apply_without_resume_and_letter(client, db):
    _, _, student, vacancy = await setup(client, db)
    response = await client.post(f"{API}/vacancies/{vacancy['id']}/applications", headers=student)
    assert response.status_code == 201, response.text
    assert response.json()["has_resume"] is False
    assert response.json()["cover_letter"] is None


async def test_apply_twice_conflict(client, db):
    _, _, student, vacancy = await setup(client, db)
    assert (await apply(client, student, vacancy["id"])).status_code == 201
    response = await apply(client, student, vacancy["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "already_applied"


async def test_apply_to_unpublished_vacancy(client, db):
    admin, employer, student, vacancy = await setup(client, db)
    draft = await create_vacancy(
        client, employer, vacancy["category_id"], title="Черновик вакансии"
    )
    assert (await apply(client, student, draft["id"])).status_code == 404

    await client.post(f"{API}/vacancies/{vacancy['id']}/close", headers=employer)
    response = await apply(client, student, vacancy["id"])
    assert response.status_code == 404
    assert response.json()["code"] == "vacancy_not_found"


async def test_apply_requires_student_role(client, db):
    _, employer, _, vacancy = await setup(client, db)
    assert (await apply(client, employer, vacancy["id"])).status_code == 403


async def test_apply_short_cover_letter(client, db):
    _, _, student, vacancy = await setup(client, db)
    response = await apply(client, student, vacancy["id"], cover_letter="Привет")
    assert response.status_code == 422
    assert "body.cover_letter" in field_errors(response)


async def test_apply_non_pdf_file(client, db):
    _, _, student, vacancy = await setup(client, db)
    # неверный content-type
    response = await apply(client, student, vacancy["id"], pdf("cv.txt", b"hello", "text/plain"))
    assert response.status_code == 415
    assert response.json()["code"] == "resume_not_pdf"
    # content-type подделан, но сигнатура не %PDF-
    response = await apply(client, student, vacancy["id"], pdf("cv.pdf", b"MZ\x90\x00 not a pdf"))
    assert response.status_code == 415
    assert not Path(settings.UPLOAD_DIR).exists() or not list(Path(settings.UPLOAD_DIR).iterdir())
    # неудачная загрузка не создаёт отклик
    assert (await client.get(f"{API}/applications/my", headers=student)).json() == []


async def test_apply_too_large_file(client, db, monkeypatch):
    _, _, student, vacancy = await setup(client, db)
    monkeypatch.setattr(settings, "MAX_RESUME_SIZE_MB", 1)
    big = PDF_BYTES + b"0" * (1024 * 1024)
    response = await apply(client, student, vacancy["id"], pdf(content=big))
    assert response.status_code == 413
    assert response.json()["code"] == "resume_too_large"
    assert list(Path(settings.UPLOAD_DIR).iterdir()) == []


async def test_resume_access(client, db):
    _, employer, student, vacancy = await setup(client, db)
    application = (await apply(client, student, vacancy["id"], pdf())).json()
    url = f"{API}/applications/{application['id']}/resume"

    for allowed in (student, employer):
        response = await client.get(url, headers=allowed)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == PDF_BYTES

    other_student = await register(client, student_payload(email="other@example.com"))
    other_employer = await register(client, employer_payload(email="other-hr@example.com"))
    assert (await client.get(url, headers=other_student)).status_code == 404
    assert (await client.get(url, headers=other_employer)).status_code == 404
    assert (await client.get(url)).status_code == 401


async def test_employer_sees_and_updates_applications(client, db):
    _, employer, student, vacancy = await setup(client, db)
    application = (await apply(client, student, vacancy["id"])).json()
    list_url = f"{API}/vacancies/{vacancy['id']}/applications"
    status_url = f"{API}/applications/{application['id']}/status"

    response = await client.get(list_url, headers=employer)
    assert response.status_code == 200
    assert response.json()[0]["student"]["email"] == "student@example.com"

    other = await register(client, employer_payload(email="other-hr@example.com"))
    assert (await client.get(list_url, headers=other)).status_code == 404
    assert (
        await client.patch(status_url, json={"status": "viewed"}, headers=other)
    ).status_code == 404
    assert (
        await client.patch(status_url, json={"status": "viewed"}, headers=student)
    ).status_code == 403

    assert (
        await client.patch(status_url, json={"status": "sent"}, headers=employer)
    ).status_code == 422
    response = await client.patch(status_url, json={"status": "viewed"}, headers=employer)
    assert response.status_code == 200
    assert response.json()["status"] == "viewed"
    response = await client.patch(status_url, json={"status": "accepted"}, headers=employer)
    assert response.json()["status"] == "accepted"
    # accepted — конечный статус
    response = await client.patch(status_url, json={"status": "rejected"}, headers=employer)
    assert response.status_code == 409


async def test_admin_stats(client, db):
    admin, _, student, vacancy = await setup(client, db)
    await apply(client, student, vacancy["id"])
    response = await client.get(f"{API}/admin/stats", headers=admin)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["vacancies_by_status"]["published"] == 1
    assert body["vacancies_by_status"]["draft"] == 0
    assert body["applications_total"] == 1
    assert body["top_categories"] == [
        {"category_id": vacancy["category_id"], "name": "IT", "applications": 1}
    ]
    assert len(body["applications_by_day"]) == 14
    assert body["applications_by_day"][-1]["applications"] == 1
    assert sum(day["applications"] for day in body["applications_by_day"]) == 1
