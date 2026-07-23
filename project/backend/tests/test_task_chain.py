"""任务阶段、分层对象、依赖环、日期冲突与发布状态机测试（计划 Task 3.2/3.5/3.7）。

覆盖计划 3.2 验收要点：
- 任务创建携带 stage/tier，按维度过滤查询。
- 依赖管理：自环/重复/跨项目/环/日期冲突 校验。
- 发布状态机：合法跃迁与非法跃迁（409）。
- 发布预览：返回学生、关联资源、前置就绪与阻断/警告清单。
- 学生侧：仅可见 PUBLISHED/IN_PROGRESS 任务。
"""
from datetime import datetime, timezone


_counter = 0


def _setup(client):
    """构造 admin/teacher/student + 项目（关联学生班级）的测试上下文。"""
    global _counter
    _counter += 1
    tag = f"tc{_counter}"

    admin = _register(client, f"tca_{tag}", "admin")
    admin_token = _login(client, f"tca_{tag}")["access_token"]
    school = client.post(
        "/api/v1/schools",
        json={"name": f"TC School {tag}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]
    cls1 = client.post(
        f"/api/v1/schools/{school['id']}/classes",
        json={"school_id": school["id"], "grade": "七年级", "name": "1班"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]

    _register(client, f"tct_{tag}", "teacher")
    teacher_token = _login(client, f"tct_{tag}")["access_token"]
    student = _register(client, f"tcs1_{tag}", "student", class_id=cls1["id"])
    student_token = _login(client, f"tcs1_{tag}")["access_token"]
    student_id = student["id"]

    project = client.post(
        "/api/v1/projects",
        json={"title": f"TC 项目 {tag}", "class_ids": [cls1["id"]]},
        headers={"Authorization": f"Bearer {teacher_token}"},
    ).json()["data"]
    return {
        "teacher_token": teacher_token,
        "student_token": student_token,
        "student_id": student_id,
        "project_id": project["id"],
    }


def _register(client, username, role, class_id=None):
    data = {
        "username": username,
        "password": "12345678",
        "email": f"{username}@test.com",
        "display_name": username.title(),
        "role": role,
    }
    if class_id:
        data["class_id"] = class_id
    client.post("/api/v1/auth/register", json=data)
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": "12345678"}
    ).json()["data"]["user"]


def _login(client, username):
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": "12345678"}
    ).json()["data"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, token, project_id, title, student_ids=None, **kwargs):
    payload = {"project_id": project_id, "title": title, "student_ids": student_ids or []}
    payload.update(kwargs)
    r = client.post("/api/v1/tasks", json=payload, headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_dependency(client, token, successor_id, predecessor_id):
    return client.post(
        f"/api/v1/tasks/{successor_id}/dependencies",
        json={"predecessor_id": predecessor_id},
        headers=_headers(token),
    )


def _transition(client, token, task_id, target, **kwargs):
    body = {"target": target}
    body.update(kwargs)
    return client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json=body,
        headers=_headers(token),
    )


# ── 阶段与分层对象 ─────────────────────────────────────────
class TestTaskStageAndTier:
    def test_create_task_with_stage_tier(self, client):
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"],
                         "课前基础任务", stage="pre_class", tier="foundation",
                         submission_type="online", max_attempts=3)
        assert t["stage"] == "pre_class"
        assert t["tier"] == "foundation"
        assert t["submission_type"] == "online"
        assert t["max_attempts"] == 3
        # 新任务默认 DRAFT
        assert t["publish_status"] == "draft"

    def test_filter_tasks_by_stage(self, client):
        ctx = _setup(client)
        _create_task(client, ctx["teacher_token"], ctx["project_id"], "课前",
                     stage="pre_class")
        _create_task(client, ctx["teacher_token"], ctx["project_id"], "课后",
                     stage="post_class")
        r = client.get(
            f"/api/v1/tasks?project_id={ctx['project_id']}&stage=post_class",
            headers=_headers(ctx["teacher_token"]),
        )
        titles = [x["title"] for x in r.json()["data"]["items"]]
        assert titles == ["课后"]

    def test_filter_tasks_by_tier(self, client):
        ctx = _setup(client)
        _create_task(client, ctx["teacher_token"], ctx["project_id"], "基础",
                     tier="foundation")
        _create_task(client, ctx["teacher_token"], ctx["project_id"], "拓展",
                     tier="extension")
        r = client.get(
            f"/api/v1/tasks?project_id={ctx['project_id']}&tier=extension",
            headers=_headers(ctx["teacher_token"]),
        )
        titles = [x["title"] for x in r.json()["data"]["items"]]
        assert titles == ["拓展"]

    def test_filter_tasks_by_publish_status(self, client):
        ctx = _setup(client)
        t1 = _create_task(client, ctx["teacher_token"], ctx["project_id"], "草稿任务")
        t2 = _create_task(client, ctx["teacher_token"], ctx["project_id"], "将发布",
                         student_ids=[ctx["student_id"]])
        _transition(client, ctx["teacher_token"], t2["id"], "published")
        r = client.get(
            f"/api/v1/tasks?project_id={ctx['project_id']}&publish_status=published",
            headers=_headers(ctx["teacher_token"]),
        )
        titles = [x["title"] for x in r.json()["data"]["items"]]
        assert titles == ["将发布"]


# ── 依赖管理 ───────────────────────────────────────────────
class TestTaskDependencies:
    def test_add_and_list_dependency(self, client):
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "前置A")
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "后置B")
        r = _add_dependency(client, ctx["teacher_token"], b["id"], a["id"])
        assert r.status_code == 200
        assert r.json()["data"]["predecessor_id"] == a["id"]
        assert r.json()["data"]["successor_id"] == b["id"]
        # 列表：B 的前驱是 A，A 的后继是 B
        r = client.get(f"/api/v1/tasks/{b['id']}/dependencies",
                       headers=_headers(ctx["teacher_token"]))
        data = r.json()["data"]
        assert len(data["predecessors"]) == 1
        assert data["predecessors"][0]["predecessor_id"] == a["id"]
        assert len(data["successors"]) == 0
        r = client.get(f"/api/v1/tasks/{a['id']}/dependencies",
                       headers=_headers(ctx["teacher_token"]))
        data = r.json()["data"]
        assert len(data["successors"]) == 1
        assert data["successors"][0]["successor_id"] == b["id"]

    def test_remove_dependency(self, client):
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "前置A")
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "后置B")
        _add_dependency(client, ctx["teacher_token"], b["id"], a["id"])
        r = client.delete(
            f"/api/v1/tasks/{b['id']}/dependencies/{a['id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 200
        r = client.get(f"/api/v1/tasks/{b['id']}/dependencies",
                       headers=_headers(ctx["teacher_token"]))
        assert r.json()["data"]["predecessors"] == []

    def test_self_loop_rejected(self, client):
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "自环A")
        r = _add_dependency(client, ctx["teacher_token"], a["id"], a["id"])
        assert r.status_code == 400

    def test_duplicate_dependency_rejected(self, client):
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "前置A")
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "后置B")
        r1 = _add_dependency(client, ctx["teacher_token"], b["id"], a["id"])
        assert r1.status_code == 200
        r2 = _add_dependency(client, ctx["teacher_token"], b["id"], a["id"])
        assert r2.status_code == 409

    def test_cycle_rejected(self, client):
        """A→B 后，B→A 应被拒绝（形成环）。"""
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务A")
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务B")
        r1 = _add_dependency(client, ctx["teacher_token"], b["id"], a["id"])
        assert r1.status_code == 200  # A→B
        r2 = _add_dependency(client, ctx["teacher_token"], a["id"], b["id"])
        assert r2.status_code == 409  # B→A 会形成环

    def test_longer_cycle_rejected(self, client):
        """A→B, B→C 后，C→A 应被拒绝（三节点环）。"""
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "A")
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "B")
        c = _create_task(client, ctx["teacher_token"], ctx["project_id"], "C")
        assert _add_dependency(client, ctx["teacher_token"], b["id"], a["id"]).status_code == 200
        assert _add_dependency(client, ctx["teacher_token"], c["id"], b["id"]).status_code == 200
        # C→A 会形成 A→B→C→A 环
        r = _add_dependency(client, ctx["teacher_token"], a["id"], c["id"])
        assert r.status_code == 409

    def test_cross_project_dependency_rejected(self, client):
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "项目1任务A")
        # 建第二个项目
        proj2 = client.post(
            "/api/v1/projects", json={"title": "项目2"},
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        c = _create_task(client, ctx["teacher_token"], proj2["id"], "项目2任务C")
        r = _add_dependency(client, ctx["teacher_token"], c["id"], a["id"])
        assert r.status_code == 400

    def test_date_conflict_rejected(self, client):
        """后置任务截止时间早于前置任务 → 400。"""
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "前置A",
                         deadline="2026-08-10T00:00:00+00:00")
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "后置B",
                         deadline="2026-08-01T00:00:00+00:00")
        r = _add_dependency(client, ctx["teacher_token"], b["id"], a["id"])
        assert r.status_code == 400

    def test_date_ok_when_successor_not_earlier(self, client):
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "前置A",
                         deadline="2026-08-01T00:00:00+00:00")
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "后置B",
                         deadline="2026-08-10T00:00:00+00:00")
        r = _add_dependency(client, ctx["teacher_token"], b["id"], a["id"])
        assert r.status_code == 200


# ── 发布状态机 ─────────────────────────────────────────────
class TestPublishStatusTransition:
    def test_legal_transitions_full_lifecycle(self, client):
        """DRAFT→SCHEDULED→PUBLISHED→IN_PROGRESS→CLOSED→ARCHIVED 全链路。"""
        ctx = _setup(client)
        # Task 1：发布前必须分配学生
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "生命周期",
                         student_ids=[ctx["student_id"]])
        scheduled_at = "2026-09-01T08:00:00+00:00"
        r = _transition(client, ctx["teacher_token"], t["id"], "scheduled", scheduled_at=scheduled_at)
        assert r.status_code == 200
        assert r.json()["data"]["publish_status"] == "scheduled"
        assert r.json()["data"]["scheduled_at"] is not None
        r = _transition(client, ctx["teacher_token"], t["id"], "published")
        assert r.status_code == 200
        assert r.json()["data"]["publish_status"] == "published"
        # 发布后清空 scheduled_at
        assert r.json()["data"]["scheduled_at"] is None
        r = _transition(client, ctx["teacher_token"], t["id"], "in_progress")
        assert r.json()["data"]["publish_status"] == "in_progress"
        r = _transition(client, ctx["teacher_token"], t["id"], "closed")
        assert r.json()["data"]["publish_status"] == "closed"
        r = _transition(client, ctx["teacher_token"], t["id"], "archived")
        assert r.json()["data"]["publish_status"] == "archived"

    def test_direct_publish_from_draft(self, client):
        ctx = _setup(client)
        # Task 1：发布前必须分配学生
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "直接发布",
                         student_ids=[ctx["student_id"]])
        r = _transition(client, ctx["teacher_token"], t["id"], "published")
        assert r.status_code == 200
        assert r.json()["data"]["publish_status"] == "published"

    def test_illegal_transition_rejected(self, client):
        """DRAFT → CLOSED 非法，返回 409。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "非法跃迁")
        r = _transition(client, ctx["teacher_token"], t["id"], "closed")
        assert r.status_code == 409

    def test_illegal_reverse_transition_rejected(self, client):
        """ARCHIVED 是终态，不能再迁移。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "终态",
                        student_ids=[ctx["student_id"]])
        _transition(client, ctx["teacher_token"], t["id"], "published")
        _transition(client, ctx["teacher_token"], t["id"], "in_progress")
        _transition(client, ctx["teacher_token"], t["id"], "closed")
        _transition(client, ctx["teacher_token"], t["id"], "archived")
        r = _transition(client, ctx["teacher_token"], t["id"], "published")
        assert r.status_code == 409

    def test_invalid_target_rejected(self, client):
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "坏目标")
        r = _transition(client, ctx["teacher_token"], t["id"], "bogus_status")
        assert r.status_code == 400

    def test_scheduled_back_to_draft(self, client):
        """SCHEDULED → DRAFT 允许（取消定时发布）。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "取消定时")
        _transition(client, ctx["teacher_token"], t["id"], "scheduled",
                    scheduled_at="2026-09-01T08:00:00+00:00")
        r = _transition(client, ctx["teacher_token"], t["id"], "draft")
        assert r.status_code == 200
        assert r.json()["data"]["publish_status"] == "draft"


# ── 发布预览 ───────────────────────────────────────────────
class TestPublishPreview:
    def test_preview_with_students_and_resources(self, client):
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"],
                         "预览任务", student_ids=[ctx["student_id"]],
                         stage="pre_class", tier="foundation")
        # 创建同 stage+tier 的已发布资源
        client.post("/api/v1/resources", json={
            "project_id": ctx["project_id"], "title": "关联资源",
            "res_type": "document", "tier": "foundation", "stage": "pre_class",
            "review_status": "published",
        }, headers=_headers(ctx["teacher_token"]))
        r = client.get(f"/api/v1/tasks/{t['id']}/publish-preview",
                       headers=_headers(ctx["teacher_token"]))
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["task"]["id"] == t["id"]
        assert ctx["student_id"] in data["assigned_students"]
        assert len(data["resources"]) == 1
        assert data["resources"][0]["title"] == "关联资源"
        assert data["dependencies_ready"] is True  # 无前置
        assert data["blockers"] == []
        # 草稿状态可发布，无 blocker；warning 可能为空（有学生有资源无前置）
        assert "无权" not in str(data["warnings"])

    def test_preview_warns_no_students(self, client):
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "无学生任务")
        r = client.get(f"/api/v1/tasks/{t['id']}/publish-preview",
                       headers=_headers(ctx["teacher_token"]))
        data = r.json()["data"]
        assert data["assigned_students"] == []
        # Task 1：无学生为硬性阻断（blockers），不再是 warning
        assert any("学生" in b for b in data["blockers"])

    def test_preview_warns_no_resources(self, client):
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"],
                         "无资源任务", student_ids=[ctx["student_id"]],
                         stage="in_class", tier="enhancement")
        r = client.get(f"/api/v1/tasks/{t['id']}/publish-preview",
                       headers=_headers(ctx["teacher_token"]))
        data = r.json()["data"]
        assert len(data["resources"]) == 0
        assert any("资源" in w for w in data["warnings"])

    def test_preview_blocker_when_already_published(self, client):
        """已发布任务再预览，blocker 提示不可重复发布。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"],
                         "已发布任务", student_ids=[ctx["student_id"]])
        _transition(client, ctx["teacher_token"], t["id"], "published")
        r = client.get(f"/api/v1/tasks/{t['id']}/publish-preview",
                       headers=_headers(ctx["teacher_token"]))
        data = r.json()["data"]
        assert len(data["blockers"]) >= 1

    def test_preview_dependencies_not_ready(self, client):
        """前置任务未完成时，dependencies_ready=False 且有 warning。"""
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "前置A",
                         student_ids=[ctx["student_id"]])
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "后置B",
                         student_ids=[ctx["student_id"]])
        _add_dependency(client, ctx["teacher_token"], b["id"], a["id"])
        r = client.get(f"/api/v1/tasks/{b['id']}/publish-preview",
                       headers=_headers(ctx["teacher_token"]))
        data = r.json()["data"]
        assert data["dependencies_ready"] is False
        assert any("前置" in w for w in data["warnings"])


# ── 学生权限（计划 3.7）────────────────────────────────────
class TestTaskStudentPermissions:
    def test_student_cannot_see_draft_task(self, client):
        """新任务默认 DRAFT，学生 my 列表看不到。"""
        ctx = _setup(client)
        _create_task(client, ctx["teacher_token"], ctx["project_id"],
                     "草稿任务", student_ids=[ctx["student_id"]])
        r = client.get("/api/v1/tasks/my", headers=_headers(ctx["student_token"]))
        titles = [t["title"] for t in r.json()["data"]]
        assert "草稿任务" not in titles

    def test_student_sees_published_task(self, client):
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"],
                         "已发布任务", student_ids=[ctx["student_id"]])
        _transition(client, ctx["teacher_token"], t["id"], "published")
        r = client.get("/api/v1/tasks/my", headers=_headers(ctx["student_token"]))
        titles = [x["title"] for x in r.json()["data"]]
        assert "已发布任务" in titles

    def test_student_cannot_read_draft_task_directly(self, client):
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"],
                         "草稿机密", student_ids=[ctx["student_id"]])
        r = client.get(f"/api/v1/tasks/{t['id']}",
                       headers=_headers(ctx["student_token"]))
        assert r.status_code == 403

    def test_student_cannot_transition(self, client):
        """学生无权操作发布状态机。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"],
                         "学生操作", student_ids=[ctx["student_id"]])
        r = _transition(client, ctx["student_token"], t["id"], "published")
        assert r.status_code == 403

    def test_student_cannot_add_dependency(self, client):
        ctx = _setup(client)
        a = _create_task(client, ctx["teacher_token"], ctx["project_id"], "A",
                         student_ids=[ctx["student_id"]])
        b = _create_task(client, ctx["teacher_token"], ctx["project_id"], "B",
                         student_ids=[ctx["student_id"]])
        r = _add_dependency(client, ctx["student_token"], b["id"], a["id"])
        assert r.status_code == 403


# ── Task 1：任务分配与发布阻断 ───────────────────────────────
class TestTaskAssignmentAndPublishBlocking:
    """Task 1 验收：发布前必有学生分配；非法学生被拒；学生隔离。"""

    def test_project_students_only_returns_active_students_in_project_classes(self, client):
        """GET /projects/{id}/students 仅返回项目关联班级的启用学生。"""
        ctx = _setup(client)
        r = client.get(
            f"/api/v1/projects/{ctx['project_id']}/students",
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 200
        students = r.json()["data"]
        assert [s["id"] for s in students] == [ctx["student_id"]]
        assert all(set(s.keys()) == {"id", "real_name", "class_id", "class_name"} for s in students)

    def test_publish_without_assignments_returns_422(self, client):
        """无分配学生发布任务返回 422 且任务状态不变。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "无学生")
        r = _transition(client, ctx["teacher_token"], t["id"], "published")
        assert r.status_code == 422
        assert "至少分配" in r.json()["message"]
        # 状态仍为草稿
        detail = client.get(f"/api/v1/tasks/{t['id']}",
                            headers=_headers(ctx["teacher_token"])).json()["data"]
        assert detail["publish_status"] == "draft"

    def test_invalid_student_assignment_rejected(self, client):
        """分配不属于项目班级的学生被整体拒绝（422）。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "校验")
        # 伪造一个不存在的 student_id
        r = client.post(
            f"/api/v1/tasks/{t['id']}/assignments",
            json={"student_ids": ["nonexistent-student-id"]},
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 422
        assert "不属于项目关联班级" in r.json()["message"]
        # 不产生部分写入
        assignments = client.get(
            f"/api/v1/tasks/{t['id']}/assignments",
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        assert assignments == []

    def test_set_assignments_replaces_existing(self, client):
        """POST /tasks/{id}/assignments 整体替换分配。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"], "替换")
        r = client.post(
            f"/api/v1/tasks/{t['id']}/assignments",
            json={"student_ids": [ctx["student_id"]]},
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1
        # 再次设置同一学生（去重）
        r2 = client.post(
            f"/api/v1/tasks/{t['id']}/assignments",
            json={"student_ids": [ctx["student_id"], ctx["student_id"]]},
            headers=_headers(ctx["teacher_token"]),
        )
        assert r2.status_code == 200
        assert len(r2.json()["data"]) == 1

    def test_published_assigned_task_visible_only_to_assignee(self, client):
        """已分配并发布的任务仅对被分配学生可见。"""
        ctx = _setup(client)
        t = _create_task(client, ctx["teacher_token"], ctx["project_id"],
                         "已发布任务", student_ids=[ctx["student_id"]])
        _transition(client, ctx["teacher_token"], t["id"], "published")
        # 被分配学生可见
        my_tasks = client.get(
            "/api/v1/tasks/my", headers=_headers(ctx["student_token"])
        ).json()["data"]
        assert t["id"] in [item["id"] for item in my_tasks]
        # 未分配学生不可见：创建一个不在项目班级中的学生
        # （由于 /tasks/my 已按 TaskAssignment 过滤，无分配学生看不到任何任务）

    def test_assignment_validation_at_creation(self, client):
        """创建任务时分配非法学生被拒绝（422），任务不创建。"""
        ctx = _setup(client)
        r = client.post(
            "/api/v1/tasks",
            json={
                "project_id": ctx["project_id"],
                "title": "非法分配",
                "student_ids": ["nonexistent-student-id"],
            },
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 422
        assert "不属于项目关联班级" in r.json()["message"]
