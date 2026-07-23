"""
项目-班级关联 (A3) + 班级任务过滤 (A4) 测试
"""
import uuid


_counter = 0


def _setup(client):
    global _counter
    _counter += 1
    tag = f"t{_counter}"

    admin = _register(client, f"pca_{tag}", "admin")
    admin_token = _login(client, f"pca_{tag}")["access_token"]

    school = client.post("/api/v1/schools", json={"name": f"PC School {tag}"},
                         headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]
    cls1 = client.post(f"/api/v1/schools/{school['id']}/classes", json={
        "school_id": school["id"], "grade": "七年级", "name": "1班",
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]
    cls2 = client.post(f"/api/v1/schools/{school['id']}/classes", json={
        "school_id": school["id"], "grade": "七年级", "name": "2班",
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]

    teacher = _register(client, f"pct_{tag}", "teacher")
    teacher_token = _login(client, f"pct_{tag}")["access_token"]
    teacher_id = teacher["id"]

    student1 = _register(client, f"pcs1_{tag}", "student", class_id=cls1["id"])
    student1_token = _login(client, f"pcs1_{tag}")["access_token"]
    student1_id = student1["id"]

    student2 = _register(client, f"pcs2_{tag}", "student", class_id=cls2["id"])
    student2_token = _login(client, f"pcs2_{tag}")["access_token"]
    student2_id = student2["id"]

    return {
        "admin_token": admin_token,
        "teacher_token": teacher_token,
        "teacher_id": teacher_id,
        "student1_token": student1_token,
        "student1_id": student1_id,
        "student2_token": student2_token,
        "student2_id": student2_id,
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


class TestProjectClass:
    def test_create_project_with_class_ids(self, client):
        ctx = _setup(client)
        resp = client.post("/api/v1/projects", json={
            "title": "班级项目A", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["class_ids"] == [ctx["cls1"]["id"]]

    def test_get_project_returns_class_ids(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/projects", json={
            "title": "班级项目B", "class_ids": [ctx["cls2"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        resp = client.get(
            f"/api/v1/projects/{pid}",
            headers={"Authorization": f"Bearer {ctx['teacher_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["class_ids"] == [ctx["cls2"]["id"]]

    def test_list_projects_returns_class_ids(self, client):
        ctx = _setup(client)
        client.post("/api/v1/projects", json={
            "title": "班级项目C", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        resp = client.get("/api/v1/projects",
                          headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        match = [p for p in items if p["title"] == "班级项目C"]
        assert len(match) == 1
        assert match[0]["class_ids"] == [ctx["cls1"]["id"]]

    def test_create_project_without_class_ids(self, client):
        ctx = _setup(client)
        resp = client.post("/api/v1/projects", json={
            "title": "无班级项目",
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["class_ids"] == []

    def test_delete_project_cascades_class(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/projects", json={
            "title": "待删除班级项目", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        resp = client.delete(f"/api/v1/projects/{pid}",
                             headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert resp.status_code == 200
        # Verify project no longer exists
        resp = client.get(
            f"/api/v1/projects/{pid}",
            headers={"Authorization": f"Bearer {ctx['teacher_token']}"},
        )
        assert resp.status_code == 404


class TestClassTaskFilter:
    def test_student_sees_tasks_from_own_class_project(self, client):
        ctx = _setup(client)
        # teacher creates a project linked to cls1
        r = client.post("/api/v1/projects", json={
            "title": "Cls1 项目", "class_ids": [ctx["cls1"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        # create a task in that project
        r = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "Cls1 任务",
            "student_ids": [ctx["student1_id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert r.status_code == 200
        task_id = r.json()["data"]["id"]
        # 新任务默认 publish_status=DRAFT，学生不可见；需经状态机发布后学生才能看到（计划 3.7）
        r = client.post(
            f"/api/v1/tasks/{task_id}/transition",
            json={"target": "published"},
            headers={"Authorization": f"Bearer {ctx['teacher_token']}"},
        )
        assert r.status_code == 200
        # student1 (in cls1) should see the published task
        resp = client.get("/api/v1/tasks/my",
                          headers={"Authorization": f"Bearer {ctx['student1_token']}"})
        assert resp.status_code == 200
        titles = [t["title"] for t in resp.json()["data"]]
        assert "Cls1 任务" in titles

    def test_student_does_not_see_tasks_from_other_class_project(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/projects", json={
            "title": "Cls2 项目", "class_ids": [ctx["cls2"]["id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        pid = r.json()["data"]["id"]
        # Task 1：分配 cls2 的学生（student2），student1 在 cls1 不应看到
        r = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "Cls2 任务",
            "student_ids": [ctx["student2_id"]],
        }, headers={"Authorization": f"Bearer {ctx['teacher_token']}"})
        assert r.status_code == 200
        task_id = r.json()["data"]["id"]
        # 发布任务，确保学生看不到是因为跨班级而非草稿状态（计划 3.7）
        r = client.post(
            f"/api/v1/tasks/{task_id}/transition",
            json={"target": "published"},
            headers={"Authorization": f"Bearer {ctx['teacher_token']}"},
        )
        assert r.status_code == 200
        # student1 (in cls1) should NOT see cls2's task
        resp = client.get("/api/v1/tasks/my",
                          headers={"Authorization": f"Bearer {ctx['student1_token']}"})
        titles = [t["title"] for t in resp.json()["data"]]
        assert "Cls2 任务" not in titles
