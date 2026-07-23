def _setup(client):
    client.post("/api/v1/auth/register", json={
        "username": "import_t", "password": "test1234",
        "email": "import_t@test.com", "display_name": "ImportT", "role": "teacher",
    })
    client.post("/api/v1/auth/register", json={
        "username": "import_s", "password": "test1234",
        "email": "import_s@test.com", "display_name": "ImportS", "role": "student",
    })
    t_token = client.post("/api/v1/auth/login", json={"username": "import_t", "password": "test1234"}).json()["data"]["access_token"]
    p = client.post("/api/v1/projects", json={"title": "Import Project"},
                    headers={"Authorization": f"Bearer {t_token}"}).json()["data"]
    task = client.post("/api/v1/tasks", json={"project_id": p["id"], "title": "Import Task"},
                       headers={"Authorization": f"Bearer {t_token}"}).json()["data"]
    return t_token, task


class TestSubmissionImport:
    def test_import_submissions(self, client):
        t_token, task = _setup(client)
        resp = client.post("/api/v1/submissions/import", json={
            "task_id": task["id"],
            "items": [
                {"student_id": "import_s_id", "file_url": "/uploads/test.docx", "content": "作业内容"},
            ],
        }, headers={"Authorization": f"Bearer {t_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["imported"] == 1

    def test_student_cannot_import(self, client):
        s_token = client.post("/api/v1/auth/login", json={"username": "import_s", "password": "test1234"}).json()["data"]["access_token"]
        resp = client.post("/api/v1/submissions/import", json={
            "task_id": "x", "items": [],
        }, headers={"Authorization": f"Bearer {s_token}"})
        assert resp.status_code == 403
