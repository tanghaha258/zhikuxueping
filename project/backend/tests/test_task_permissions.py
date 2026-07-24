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


# ── Task 9：任务中心与进度接口权限 ───────────────────────────
def test_task_center_requires_authentication(client):
    response = client.get("/api/v1/tasks/center")
    assert response.status_code == 401


def test_task_center_rejects_student(client):
    suffix = uuid.uuid4().hex[:8]
    student = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"task_center_student_{suffix}",
            "password": "12345678",
            "email": f"task_center_student_{suffix}@test.com",
            "display_name": "student",
            "role": "student",
        },
    )
    assert student.status_code == 200
    token = client.post(
        "/api/v1/auth/login",
        json={"username": f"task_center_student_{suffix}", "password": "12345678"},
    ).json()["data"]["access_token"]
    response = client.get("/api/v1/tasks/center", headers=_headers(token))
    assert response.status_code == 403


def test_task_progress_requires_manage_permission(client):
    """学生无权读取任务执行进度汇总（教师管理视图）。"""
    suffix = uuid.uuid4().hex[:8]
    owner_token = _register_and_login(client, f"task_progress_owner_{suffix}")
    project = client.post(
        "/api/v1/projects", json={"title": "progress project"},
        headers=_headers(owner_token),
    ).json()["data"]
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "progress task", "student_ids": []},
        headers=_headers(owner_token),
    ).json()["data"]

    # 学生无权读取教师进度汇总
    client.post(
        "/api/v1/auth/register",
        json={
            "username": f"task_progress_student_{suffix}",
            "password": "12345678",
            "email": f"task_progress_student_{suffix}@test.com",
            "display_name": "student",
            "role": "student",
        },
    )
    student_token = client.post(
        "/api/v1/auth/login",
        json={"username": f"task_progress_student_{suffix}", "password": "12345678"},
    ).json()["data"]["access_token"]

    response = client.get(
        f"/api/v1/tasks/{task['id']}/progress", headers=_headers(student_token)
    )
    assert response.status_code == 403


def test_cross_project_student_assignment_rejected(client):
    """分配不属于项目班级的学生被拒（422），且不产生部分写入。"""
    suffix = uuid.uuid4().hex[:8]
    teacher_token = _register_and_login(client, f"task_xproj_teacher_{suffix}")
    # 项目1（无班级）
    project = client.post(
        "/api/v1/projects", json={"title": "xproj project"},
        headers=_headers(teacher_token),
    ).json()["data"]
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "xproj task", "student_ids": []},
        headers=_headers(teacher_token),
    ).json()["data"]
    # 创建一个不属于任何项目班级的学生
    student = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"task_xproj_outsider_{suffix}",
            "password": "12345678",
            "email": f"task_xproj_outsider_{suffix}@test.com",
            "display_name": "outsider",
            "role": "student",
        },
    )
    outsider_id = client.post(
        "/api/v1/auth/login",
        json={"username": f"task_xproj_outsider_{suffix}", "password": "12345678"},
    ).json()["data"]["user"]["id"]

    response = client.post(
        f"/api/v1/tasks/{task['id']}/assignments",
        json={"student_ids": [outsider_id]},
        headers=_headers(teacher_token),
    )
    assert response.status_code == 422
    assert "不属于项目关联班级" in response.json()["message"]
    # 不产生部分写入
    assignments = client.get(
        f"/api/v1/tasks/{task['id']}/assignments", headers=_headers(teacher_token)
    ).json()["data"]
    assert assignments == []
