from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models.learning_profile import ClassLearningReport
from app.models.school import Class
from app.models.user import User


def _token(client, username: str, role: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "test1234",
            "email": f"{username}@test.com",
            "display_name": username,
            "role": role,
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "test1234"},
    )
    return response.json()["data"]["access_token"]


def _class_context(client, db_session, suffix: str):
    owner_username = f"profile_owner_{suffix}"
    owner_token = _token(client, owner_username, "teacher")
    other_token = _token(client, f"profile_other_{suffix}", "teacher")
    student_token = _token(client, f"profile_student_{suffix}", "student")
    owner = db_session.execute(
        select(User).where(User.username == owner_username)
    ).scalar_one()
    class_id = f"profile-class-{suffix}"
    db_session.add(
        Class(
            id=class_id,
            school_id=f"profile-school-{suffix}",
            grade="grade-7",
            name=f"Profile class {suffix}",
            head_teacher_id=owner.id,
        )
    )
    db_session.commit()
    return (
        class_id,
        {"Authorization": f"Bearer {owner_token}"},
        {"Authorization": f"Bearer {other_token}"},
        {"Authorization": f"Bearer {student_token}"},
    )


def test_student_cannot_access_class_learning_profile_routes(client, db_session):
    class_id, _, _, student_headers = _class_context(client, db_session, "student")

    responses = [
        client.get(f"/api/v1/learning-profile/classes/{class_id}", headers=student_headers),
        client.post(f"/api/v1/learning-profile/classes/{class_id}/report", headers=student_headers),
        client.get(f"/api/v1/learning-profile/classes/{class_id}/reports", headers=student_headers),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403]


def test_unassigned_teacher_cannot_access_class_learning_profile_routes(client, db_session):
    class_id, _, other_headers, _ = _class_context(client, db_session, "other")

    responses = [
        client.get(f"/api/v1/learning-profile/classes/{class_id}", headers=other_headers),
        client.post(f"/api/v1/learning-profile/classes/{class_id}/report", headers=other_headers),
        client.get(f"/api/v1/learning-profile/classes/{class_id}/reports", headers=other_headers),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403]


def test_head_teacher_can_read_class_learning_profile(client, db_session):
    class_id, owner_headers, _, _ = _class_context(client, db_session, "owner")

    response = client.get(
        f"/api/v1/learning-profile/classes/{class_id}",
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["class_id"] == class_id


def test_generated_report_is_persisted_after_request(client, db_session, test_engine):
    class_id, owner_headers, _, _ = _class_context(client, db_session, "persisted")

    response = client.post(
        f"/api/v1/learning-profile/classes/{class_id}/report",
        headers=owner_headers,
    )
    report_id = response.json()["data"]["id"]
    other_session = sessionmaker(bind=test_engine)()
    try:
        report = other_session.get(ClassLearningReport, report_id)
    finally:
        other_session.close()

    assert response.status_code == 200
    assert report is not None
    assert report.class_id == class_id
