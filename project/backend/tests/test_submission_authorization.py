from sqlalchemy import select

from app.models.project import ProjectClass
from app.models.school import Class
from app.models.submission import Submission
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


def _owner_task(client, owner_token: str) -> dict:
    headers = {"Authorization": f"Bearer {owner_token}"}
    project = client.post(
        "/api/v1/projects",
        json={"title": "Submission authorization project"},
        headers=headers,
    ).json()["data"]
    return client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Submission authorization task"},
        headers=headers,
    ).json()["data"]


def _submission_for_owner_task(client, db_session):
    owner_token = _token(client, "submission_auth_owner", "teacher")
    task = _owner_task(client, owner_token)
    submission = Submission(
        task_id=task["id"],
        student_id="submission_auth_student",
        content="Private submission",
        status="submitted",
    )
    db_session.add(submission)
    db_session.commit()
    db_session.refresh(submission)
    return submission


def _task_and_unassigned_student(client, db_session):
    owner_token = _token(client, "submission_visibility_owner", "teacher")
    task = _owner_task(client, owner_token)
    target_class = Class(
        id="submission-target-class",
        school_id="submission-school",
        grade="grade-7",
        name="Target class",
    )
    other_class = Class(
        id="submission-other-class",
        school_id="submission-school",
        grade="grade-7",
        name="Other class",
    )
    db_session.add_all([
        target_class,
        other_class,
        ProjectClass(project_id=task["project_id"], class_id=target_class.id),
    ])
    student_token = _token(client, "submission_unassigned_student", "student")
    student = db_session.execute(
        select(User).where(User.username == "submission_unassigned_student")
    ).scalar_one()
    student.class_id = other_class.id
    db_session.commit()
    return task, {"Authorization": f"Bearer {student_token}"}


def _visible_task_and_student(client, db_session):
    owner_token = _token(client, "submission_visible_owner", "teacher")
    task = _owner_task(client, owner_token)
    target_class = Class(
        id="submission-visible-class",
        school_id="submission-visible-school",
        grade="grade-7",
        name="Visible class",
    )
    db_session.add_all([
        target_class,
        ProjectClass(project_id=task["project_id"], class_id=target_class.id),
    ])
    student_token = _token(client, "submission_visible_student", "student")
    student = db_session.execute(
        select(User).where(User.username == "submission_visible_student")
    ).scalar_one()
    student.class_id = target_class.id
    db_session.commit()
    return task, {"Authorization": f"Bearer {student_token}"}


def test_submission_detail_requires_authentication(client, db_session):
    submission = _submission_for_owner_task(client, db_session)

    response = client.get(f"/api/v1/submissions/{submission.id}")

    assert response.status_code == 401


def test_cross_teacher_cannot_read_or_manage_task_submissions(client, db_session):
    submission = _submission_for_owner_task(client, db_session)
    other_token = _token(client, "submission_auth_other", "teacher")
    headers = {"Authorization": f"Bearer {other_token}"}

    detail_response = client.get(f"/api/v1/submissions/{submission.id}", headers=headers)
    task_response = client.get(f"/api/v1/submissions/task/{submission.task_id}", headers=headers)
    update_response = client.patch(
        f"/api/v1/submissions/{submission.id}",
        json={"score": 80},
        headers=headers,
    )
    import_response = client.post(
        "/api/v1/submissions/import",
        json={"task_id": submission.task_id, "items": []},
        headers=headers,
    )

    assert detail_response.status_code == 403
    assert task_response.status_code == 403
    assert update_response.status_code == 403
    assert import_response.status_code == 403


def test_student_cannot_submit_to_task_outside_their_class(client, db_session):
    task, headers = _task_and_unassigned_student(client, db_session)

    response = client.post(
        "/api/v1/submissions",
        json={"task_id": task["id"], "content": "Unauthorized answer"},
        headers=headers,
    )

    assert response.status_code == 403


def test_student_can_create_and_read_own_submission_for_visible_task(client, db_session):
    task, headers = _visible_task_and_student(client, db_session)

    created = client.post(
        "/api/v1/submissions",
        json={"task_id": task["id"], "content": "Visible answer"},
        headers=headers,
    )
    submission_id = created.json()["data"]["id"]
    detail = client.get(f"/api/v1/submissions/{submission_id}", headers=headers)

    assert created.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["data"]["student_id"] == created.json()["data"]["student_id"]
