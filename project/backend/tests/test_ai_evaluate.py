def _setup(client):
    for u in [("eval_admin", "admin"), ("eval_teacher", "teacher"), ("eval_student", "student")]:
        client.post("/api/v1/auth/register", json={
            "username": u[0], "password": "test1234",
            "email": f"{u[0]}@test.com", "display_name": u[0], "role": u[1],
        })
    def login(u): return client.post("/api/v1/auth/login", json={"username": u, "password": "test1234"}).json()["data"]["access_token"]

    t_token = login("eval_teacher")
    s_token = login("eval_student")

    p = client.post("/api/v1/projects", json={"title": "Eval Project"},
                    headers={"Authorization": f"Bearer {t_token}"}).json()["data"]
    task = client.post("/api/v1/tasks", json={
        "project_id": p["id"], "title": "Eval Task", "description": "请完成实验报告",
        "max_score": 100, "rubric": '[{"name":"内容","max_score":50},{"name":"格式","max_score":50}]',
    }, headers={"Authorization": f"Bearer {t_token}"}).json()["data"]
    sub = client.post("/api/v1/submissions", json={
        "task_id": task["id"], "content": "这是我的实验报告，数据详实...",
    }, headers={"Authorization": f"Bearer {s_token}"}).json()["data"]
    return t_token, task, sub


class TestAiEvaluate:
    def test_teacher_can_evaluate(self, client):
        t_token, task, sub = _setup(client)
        resp = client.post(f"/api/v1/ai/evaluate/{sub['id']}",
                           headers={"Authorization": f"Bearer {t_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 无可用 Provider 时返回明确不可用状态，不写入 AI 分数。
        assert data["status"] == "unavailable"
        assert data["error_code"] == "provider_unavailable"
        assert "total_score" not in data

    def test_student_cannot_evaluate(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "eval_s2", "password": "test1234",
            "email": "eval_s2@test.com", "display_name": "S2", "role": "student",
        })
        s_token = client.post("/api/v1/auth/login", json={"username": "eval_s2", "password": "test1234"}).json()["data"]["access_token"]
        resp = client.post("/api/v1/ai/evaluate/nonexistent",
                           headers={"Authorization": f"Bearer {s_token}"})
        assert resp.status_code == 403

    def test_batch_evaluate(self, client):
        t_token, task, sub = _setup(client)
        resp = client.post(f"/api/v1/ai/evaluate/batch?task_id={task['id']}",
                           headers={"Authorization": f"Bearer {t_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1

    def test_other_teacher_cannot_evaluate_another_teachers_task(self, client):
        _, task, sub = _setup(client)
        client.post("/api/v1/auth/register", json={
            "username": "eval_other_teacher", "password": "test1234",
            "email": "eval_other_teacher@test.com", "display_name": "Other", "role": "teacher",
        })
        token = client.post("/api/v1/auth/login", json={
            "username": "eval_other_teacher", "password": "test1234",
        }).json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        responses = [
            client.post(f"/api/v1/ai/evaluate/{sub['id']}", headers=headers),
            client.post(f"/api/v1/ai/evaluate/batch?task_id={task['id']}", headers=headers),
        ]

        assert [response.status_code for response in responses] == [403, 403]
