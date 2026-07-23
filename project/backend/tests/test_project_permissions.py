import uuid


def register(client, username: str):
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


def login(client, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "12345678"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_project_detail_requires_authentication(client):
    response = client.get("/api/v1/projects/not-a-project")

    assert response.status_code == 401


def test_teacher_cannot_update_another_teachers_project(client):
    suffix = uuid.uuid4().hex[:8]
    owner_name = f"project_owner_{suffix}"
    other_name = f"project_other_{suffix}"
    register(client, owner_name)
    register(client, other_name)

    owner_token = login(client, owner_name)
    other_token = login(client, other_name)
    create_response = client.post(
        "/api/v1/projects",
        json={"title": "受保护项目"},
        headers=authorization(owner_token),
    )
    assert create_response.status_code == 200
    project_id = create_response.json()["data"]["id"]

    response = client.put(
        f"/api/v1/projects/{project_id}",
        json={"title": "越权修改"},
        headers=authorization(other_token),
    )

    assert response.status_code == 403
