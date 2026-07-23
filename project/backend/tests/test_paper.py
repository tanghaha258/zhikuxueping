"""
试卷批改扩展 (Phase C) 测试
"""

_counter = 0


def _setup(client):
    global _counter
    _counter += 1
    tag = f"p{_counter}"

    # admin creates school & classes
    admin = _register(client, f"pa_{tag}", "admin")
    admin_token = _login(client, f"pa_{tag}")["access_token"]
    school = client.post("/api/v1/schools", json={"name": f"Paper School {tag}"},
                         headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]
    cls1 = client.post(f"/api/v1/schools/{school['id']}/classes", json={
        "school_id": school["id"], "grade": "七年级", "name": "1班",
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]
    cls2 = client.post(f"/api/v1/schools/{school['id']}/classes", json={
        "school_id": school["id"], "grade": "七年级", "name": "2班",
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]

    # teacher
    teacher = _register(client, f"pt_{tag}", "teacher")
    teacher_token = _login(client, f"pt_{tag}")["access_token"]
    teacher_id = teacher["id"]

    # students
    s1 = _register(client, f"ps1_{tag}", "student", class_id=cls1["id"])
    s1_token = _login(client, f"ps1_{tag}")["access_token"]
    s2 = _register(client, f"ps2_{tag}", "student", class_id=cls2["id"])
    s2_token = _login(client, f"ps2_{tag}")["access_token"]

    return {
        "admin_token": admin_token,
        "teacher_token": teacher_token,
        "teacher_id": teacher_id,
        "s1_token": s1_token,
        "s1_id": s1["id"],
        "s2_token": s2_token,
        "s2_id": s2["id"],
        "cls1": cls1,
        "cls2": cls2,
    }


def _register(client, username, role, class_id=None):
    data = {
        "username": username, "password": "12345678",
        "email": f"{username}@test.com", "display_name": username.title(),
        "role": role,
    }
    if class_id:
        data["class_id"] = class_id
    client.post("/api/v1/auth/register", json=data)
    return client.post("/api/v1/auth/login", json={"username": username, "password": "12345678"}).json()["data"]["user"]


def _login(client, username):
    return client.post("/api/v1/auth/login", json={"username": username, "password": "12345678"}).json()["data"]


class TestPaperCRUD:
    def test_create_paper(self, client):
        ctx = _setup(client)
        resp = client.post("/api/v1/papers", json={
            "title": "期中测试卷", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "期中测试卷"
        assert data["class_ids"] == [ctx["cls1"]["id"]]
        assert data["status"] == "draft"

    def test_get_paper(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={"title": "单元测试"},
                        headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        resp = client.get(f"/api/v1/papers/{pid}", headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "单元测试"

    def test_list_papers(self, client):
        ctx = _setup(client)
        client.post("/api/v1/papers", json={"title": "试卷A"},
                    headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        resp = client.get("/api/v1/papers",
                          headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        titles = [p["title"] for p in items]
        assert "试卷A" in titles

    def test_update_paper(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={"title": "原标题"},
                        headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        resp = client.put(f"/api/v1/papers/{pid}", json={"title": "新标题"},
                          headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "新标题"

    def test_delete_paper(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={"title": "待删除"},
                        headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        resp = client.delete(f"/api/v1/papers/{pid}",
                             headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        resp = client.get(f"/api/v1/papers/{pid}", headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 404


class TestPaperAnswerKey:
    def test_set_answer_key(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={"title": "带答案的试卷"},
                        headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        resp = client.post(f"/api/v1/papers/{pid}/answer-key", json={
            "questions": [{"index": 0, "type": "essay", "score": 10, "answer": "答案略", "rubric": "言之有理即可"}],
            "total_score": 100,
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_score"] == 100
        assert len(data["questions"]) == 1

    def test_get_answer_key(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={"title": "答案试卷"},
                        headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        client.post(f"/api/v1/papers/{pid}/answer-key", json={
            "questions": [{"index": 0, "type": "essay", "score": 20, "answer": "略"}],
            "total_score": 20,
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        resp = client.get(f"/api/v1/papers/{pid}/answer-key", headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total_score"] == 20


class TestPaperDistribute:
    def test_distribute_to_class(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={
            "title": "分发测试", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        resp = client.post(f"/api/v1/papers/{pid}/distribute",
                           headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["distributed"] >= 1

    def test_list_submissions(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={
            "title": "提交测试", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        client.post(f"/api/v1/papers/{pid}/distribute",
                    headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        resp = client.get(f"/api/v1/papers/{pid}/submissions", headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["status"] == "pending"

    def test_get_stats(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={
            "title": "统计测试", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        client.post(f"/api/v1/papers/{pid}/distribute",
                    headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        client.post(f"/api/v1/papers/{pid}/answer-key", json={
            "questions": [{"index": 0, "type": "essay", "score": 100, "answer": "略"}],
            "total_score": 100,
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        resp = client.get(f"/api/v1/papers/{pid}/stats", headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert stats["total"] >= 1
        assert stats["pending"] >= 1


class TestPaperEvaluate:
    def test_ai_evaluate_submissions(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/papers", json={
            "title": "AI批改测试", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        client.post(f"/api/v1/papers/{pid}/distribute",
                    headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        client.post(f"/api/v1/papers/{pid}/answer-key", json={
            "questions": [{"index": 0, "type": "essay", "score": 100, "answer": "略"}],
            "total_score": 100,
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        resp = client.post(f"/api/v1/papers/{pid}/evaluate",
                           headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        # 无可用 Provider 时不产生伪造批改，completed 为 0。
        assert data["completed"] == 0


class TestPaperAuthorization:
    def _paper_id(self, client, ctx):
        response = client.post(
            "/api/v1/papers",
            json={"title": "Protected paper", "class_ids": [ctx["cls1"]["id"]]},
            headers={"Authorization": f"Bearer {ctx['teacher_token']}"},
        )
        return response.json()["data"]["id"]

    def test_anonymous_user_cannot_read_paper_detail(self, client):
        ctx = _setup(client)
        paper_id = self._paper_id(client, ctx)

        response = client.get(f"/api/v1/papers/{paper_id}")

        assert response.status_code == 401

    def test_other_teacher_cannot_access_or_manage_paper(self, client):
        ctx = _setup(client)
        paper_id = self._paper_id(client, ctx)
        client.post(
            f"/api/v1/papers/{paper_id}/answer-key",
            json={"questions": [], "total_score": 0},
            headers={"Authorization": f"Bearer {ctx['teacher_token']}"},
        )
        _register(client, f"other_teacher_{_counter}", "teacher")
        other_token = _login(client, f"other_teacher_{_counter}")["access_token"]
        headers = {"Authorization": f"Bearer {other_token}"}

        responses = [
            client.get(f"/api/v1/papers/{paper_id}", headers=headers),
            client.put(f"/api/v1/papers/{paper_id}", json={"title": "changed"}, headers=headers),
            client.delete(f"/api/v1/papers/{paper_id}", headers=headers),
            client.post(f"/api/v1/papers/{paper_id}/answer-key", json={"questions": []}, headers=headers),
            client.get(f"/api/v1/papers/{paper_id}/answer-key", headers=headers),
            client.post(f"/api/v1/papers/{paper_id}/distribute", headers=headers),
            client.get(f"/api/v1/papers/{paper_id}/submissions", headers=headers),
            client.get(f"/api/v1/papers/{paper_id}/stats", headers=headers),
            client.post(f"/api/v1/papers/{paper_id}/evaluate", headers=headers),
            client.post(f"/api/v1/papers/{paper_id}/process-feedback", headers=headers),
        ]

        assert [response.status_code for response in responses] == [403] * len(responses)
