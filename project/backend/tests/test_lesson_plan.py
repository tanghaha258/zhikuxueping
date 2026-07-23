def _teacher_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "lp_teacher", "password": "test1234",
        "email": "lp_t@test.com", "display_name": "LPTeacher", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={"username": "lp_teacher", "password": "test1234"})
    return resp.json()["data"]["access_token"]


def _named_teacher_token(client, suffix: str):
    username = f"lp-security-{suffix}"
    client.post("/api/v1/auth/register", json={
        "username": username,
        "password": "test1234",
        "email": f"{username}@test.com",
        "display_name": username,
        "role": "teacher",
    })
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "test1234"},
    )
    return response.json()["data"]["access_token"]


def _create_plan(client, token: str) -> str:
    response = client.post(
        "/api/v1/ai/lesson-plans",
        json={
            "title": "Private plan",
            "content": "Private content",
            "subject": "science",
            "grade": "grade-7",
            "topic": "private-topic",
            "duration": 45,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["data"]["id"]


class TestSavedLessonPlan:
    def test_create_plan(self, client):
        token = _teacher_token(client)
        resp = client.post("/api/v1/ai/lesson-plans", json={
            "title": "《光合作用》教案", "content": "<h1>光合作用</h1>",
            "subject": "biology", "grade": "七年级", "topic": "光合作用", "duration": 45,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "《光合作用》教案"
        assert data["content"] == "<h1>光合作用</h1>"

    def test_list_plans(self, client):
        token = _teacher_token(client)
        resp = client.get("/api/v1/ai/lesson-plans", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)

    def test_update_plan(self, client):
        token = _teacher_token(client)
        resp = client.post("/api/v1/ai/lesson-plans", json={
            "title": "T", "content": "C", "subject": "s", "grade": "g", "topic": "t", "duration": 45,
        }, headers={"Authorization": f"Bearer {token}"})
        pid = resp.json()["data"]["id"]
        resp2 = client.put(f"/api/v1/ai/lesson-plans/{pid}", json={"title": "Updated"},
                           headers={"Authorization": f"Bearer {token}"})
        assert resp2.json()["data"]["title"] == "Updated"

    def test_delete_plan(self, client):
        token = _teacher_token(client)
        resp = client.post("/api/v1/ai/lesson-plans", json={
            "title": "D", "content": "C", "subject": "s", "grade": "g", "topic": "t", "duration": 45,
        }, headers={"Authorization": f"Bearer {token}"})
        pid = resp.json()["data"]["id"]
        resp2 = client.delete(f"/api/v1/ai/lesson-plans/{pid}",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp2.status_code == 200


class TestSavedLessonPlanAuthorization:
    def test_anonymous_user_cannot_read_a_saved_plan(self, client):
        owner_token = _named_teacher_token(client, "anonymous-owner")
        plan_id = _create_plan(client, owner_token)

        response = client.get(f"/api/v1/ai/lesson-plans/{plan_id}")

        assert response.status_code == 401

    def test_cross_teacher_cannot_access_a_saved_plan(self, client):
        owner_token = _named_teacher_token(client, "owner")
        other_token = _named_teacher_token(client, "other")
        plan_id = _create_plan(client, owner_token)
        headers = {"Authorization": f"Bearer {other_token}"}

        read_response = client.get(f"/api/v1/ai/lesson-plans/{plan_id}", headers=headers)
        update_response = client.put(
            f"/api/v1/ai/lesson-plans/{plan_id}",
            json={"title": "Unauthorized update"},
            headers=headers,
        )
        delete_response = client.delete(f"/api/v1/ai/lesson-plans/{plan_id}", headers=headers)

        assert read_response.status_code == 403
        assert update_response.status_code == 403
        assert delete_response.status_code == 403
