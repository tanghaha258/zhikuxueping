import uuid


def _register_and_login(client, username: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "12345678",
            "email": f"{username}@test.com",
            "display_name": username,
            "role": "teacher",
        },
    )
    assert response.status_code == 200
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "12345678"})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, token: str, title: str) -> tuple[str, str]:
    project = client.post("/api/v1/projects", json={"title": f"{title} project"}, headers=_headers(token))
    assert project.status_code == 200
    project_id = project.json()["data"]["id"]
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": title, "student_ids": []},
        headers=_headers(token),
    )
    assert task.status_code == 200
    return project_id, task.json()["data"]["id"]


def test_task_detail_requires_authentication(client):
    response = client.get("/api/v1/tasks/not-a-task")

    assert response.status_code == 401


def test_teacher_cannot_update_another_teachers_task(client):
    suffix = uuid.uuid4().hex[:8]
    owner_token = _register_and_login(client, f"task_owner_{suffix}")
    other_token = _register_and_login(client, f"task_other_{suffix}")
    _, task_id = _create_task(client, owner_token, "protected task")

    response = client.put(
        f"/api/v1/tasks/{task_id}",
        json={"title": "forbidden"},
        headers=_headers(other_token),
    )

    assert response.status_code == 403


def test_teacher_cannot_create_task_in_another_teachers_project(client):
    suffix = uuid.uuid4().hex[:8]
    owner_token = _register_and_login(client, f"task_project_owner_{suffix}")
    other_token = _register_and_login(client, f"task_project_other_{suffix}")
    project = client.post(
        "/api/v1/projects",
        json={"title": "protected project"},
        headers=_headers(owner_token),
    )
    assert project.status_code == 200

    response = client.post(
        "/api/v1/tasks",
        json={"project_id": project.json()["data"]["id"], "title": "forbidden", "student_ids": []},
        headers=_headers(other_token),
    )

    assert response.status_code == 403
