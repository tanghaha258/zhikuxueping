import uuid


def _register(client, username: str) -> None:
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


def _login(client, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "12345678"},
    )
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_resource_in_project(client):
    suffix = uuid.uuid4().hex[:8]
    owner_name = f"resource_owner_{suffix}"
    other_name = f"resource_other_{suffix}"
    _register(client, owner_name)
    _register(client, other_name)
    owner_token = _login(client, owner_name)
    other_token = _login(client, other_name)
    project_response = client.post(
        "/api/v1/projects",
        json={"title": "Protected resource project"},
        headers=_headers(owner_token),
    )
    project_id = project_response.json()["data"]["id"]
    resource_response = client.post(
        "/api/v1/resources",
        json={
            "project_id": project_id,
            "title": "Protected resource",
            "res_type": "link",
            "url": "https://example.com/private",
        },
        headers=_headers(owner_token),
    )
    return project_id, resource_response.json()["data"]["id"], other_token


def test_resource_endpoints_require_authentication(client):
    project_id, resource_id, _ = _create_resource_in_project(client)

    list_response = client.get(f"/api/v1/resources?project_id={project_id}")
    detail_response = client.get(f"/api/v1/resources/{resource_id}")

    assert list_response.status_code == 401
    assert detail_response.status_code == 401


def test_teacher_cannot_access_another_teachers_project_resource(client):
    project_id, resource_id, other_token = _create_resource_in_project(client)
    headers = _headers(other_token)

    responses = [
        client.get(f"/api/v1/resources?project_id={project_id}", headers=headers),
        client.get(f"/api/v1/resources/{resource_id}", headers=headers),
        client.put(f"/api/v1/resources/{resource_id}", json={"title": "changed"}, headers=headers),
        client.delete(f"/api/v1/resources/{resource_id}", headers=headers),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403]
