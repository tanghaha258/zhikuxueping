"""
AI 端点（备课 + Provider CRUD）测试
"""


def _admin_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "ai_admin", "password": "ai1234",
        "email": "ai_admin@test.com", "display_name": "AI管理员", "role": "admin",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "ai_admin", "password": "ai1234",
    })
    return resp.json()["data"]["access_token"]


def _teacher_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "ai_teacher", "password": "ai1234",
        "email": "ai_teacher@test.com", "display_name": "AI教师", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "ai_teacher", "password": "ai1234",
    })
    return resp.json()["data"]["access_token"]


def _student_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "ai_student", "password": "ai1234",
        "email": "ai_student@test.com", "display_name": "AI学生", "role": "student",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "ai_student", "password": "ai1234",
    })
    return resp.json()["data"]["access_token"]


class TestLessonPlan:
    def test_generate_lesson_plan(self, client):
        token = _teacher_token(client)
        resp = client.post("/api/v1/ai/lesson-plan", json={
            "subject": "yuwen", "grade": "qinianji", "topic": "chun", "duration": 45,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "content" in data
        assert "title" in data
        assert "chun" in data["title"]

    def test_student_cannot_generate(self, client):
        token = _student_token(client)
        resp = client.post("/api/v1/ai/lesson-plan", json={
            "subject": "math", "grade": "b", "topic": "t", "duration": 45,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestAiProviders:
    def _create_provider(self, client, token):
        resp = client.post("/api/v1/ai/providers", json={
            "name": "TestAI", "api_url": "https://test.api.com/v1",
            "model": "gpt-4", "api_key": "sk-test12345",
        }, headers={"Authorization": f"Bearer {token}"})
        return resp.json()["data"]["id"]

    def test_create_provider(self, client):
        token = _admin_token(client)
        resp = client.post("/api/v1/ai/providers", json={
            "name": "OpenAI", "api_url": "https://api.openai.com/v1",
            "model": "gpt-4o", "api_key": "sk-demo12345",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "OpenAI"
        assert data["model"] == "gpt-4o"

    def test_list_providers(self, client):
        token = _admin_token(client)
        self._create_provider(client, token)
        resp = client.get("/api/v1/ai/providers",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_update_provider(self, client):
        token = _admin_token(client)
        pid = self._create_provider(client, token)
        resp = client.put(f"/api/v1/ai/providers/{pid}", json={"name": "UpdatedAI"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "UpdatedAI"

    def test_delete_provider(self, client):
        token = _admin_token(client)
        pid = self._create_provider(client, token)
        resp = client.delete(f"/api/v1/ai/providers/{pid}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_teacher_cannot_create(self, client):
        token = _teacher_token(client)
        resp = client.post("/api/v1/ai/providers", json={
            "name": "X", "api_url": "http://x.com", "model": "x", "api_key": "x",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_unauthorized_cannot_list(self, client):
        resp = client.get("/api/v1/ai/providers")
        assert resp.status_code == 401


class TestTaskRubric:
    def _teacher_token(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "rubric_t", "password": "test1234",
            "email": "rubric_t@test.com", "display_name": "RubricT", "role": "teacher",
        })
        resp = client.post("/api/v1/auth/login", json={"username": "rubric_t", "password": "test1234"})
        return resp.json()["data"]["access_token"]

    def _admin_token(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "rubric_a", "password": "test1234",
            "email": "rubric_a@test.com", "display_name": "RubricA", "role": "admin",
        })
        resp = client.post("/api/v1/auth/login", json={"username": "rubric_a", "password": "test1234"})
        return resp.json()["data"]["access_token"]

    def _project_id(self, client, token):
        resp = client.post("/api/v1/projects", json={
            "title": "Rubric Project", "description": "test",
        }, headers={"Authorization": f"Bearer {token}"})
        return resp.json()["data"]["id"]

    def test_create_task_with_rubric(self, client):
        token = self._teacher_token(client)
        pid = self._project_id(client, token)
        rubric_json = '[{"name":"内容","max_score":50,"description":"内容完整性"},{"name":"格式","max_score":50,"description":"格式规范性"}]'
        resp = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "Rubric Task", "description": "test",
            "max_score": 100, "rubric": rubric_json,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["rubric"] == rubric_json

    def test_update_task_rubric(self, client):
        token = self._teacher_token(client)
        pid = self._project_id(client, token)
        resp = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "Update Rubric", "description": "test",
        }, headers={"Authorization": f"Bearer {token}"})
        task_id = resp.json()["data"]["id"]
        new_rubric = '[{"name":"创新","max_score":100,"description":"创新性"}]'
        resp2 = client.put(f"/api/v1/tasks/{task_id}", json={"rubric": new_rubric},
                           headers={"Authorization": f"Bearer {token}"})
        assert resp2.status_code == 200
        assert resp2.json()["data"]["rubric"] == new_rubric
