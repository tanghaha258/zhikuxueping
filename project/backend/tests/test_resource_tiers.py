"""资源层级、阶段、审核状态与权限测试（计划 Task 3.1/3.5/3.7）。

覆盖计划 3.1 验收要点：
- 资源创建携带 tier/stage/review_status，按维度过滤查询。
- 审核状态流转（update review_status）。
- 三级递进覆盖检查（tier-coverage）：每层至少一项 PUBLISHED 资源才算覆盖。
- 学生仅可见 PUBLISHED/APPROVED 资源（列表与单点）；教师可见全部。
- 历史资源（未指定 tier/review_status）默认为未分层草稿，向后兼容。
- 无效枚举值在创建/更新时返回 400。
"""
import uuid


_counter = 0


def _setup(client):
    """构造 admin/teacher/student + 项目（关联学生班级）的测试上下文。"""
    global _counter
    _counter += 1
    tag = f"rt{_counter}"

    admin = _register(client, f"rta_{tag}", "admin")
    admin_token = _login(client, f"rta_{tag}")["access_token"]
    school = client.post(
        "/api/v1/schools",
        json={"name": f"RT School {tag}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]
    cls1 = client.post(
        f"/api/v1/schools/{school['id']}/classes",
        json={"school_id": school["id"], "grade": "七年级", "name": "1班"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]

    _register(client, f"rtt_{tag}", "teacher")
    teacher_token = _login(client, f"rtt_{tag}")["access_token"]
    _register(client, f"rts1_{tag}", "student", class_id=cls1["id"])
    student_token = _login(client, f"rts1_{tag}")["access_token"]

    project = client.post(
        "/api/v1/projects",
        json={"title": f"RT 项目 {tag}", "class_ids": [cls1["id"]]},
        headers={"Authorization": f"Bearer {teacher_token}"},
    ).json()["data"]
    return {
        "teacher_token": teacher_token,
        "student_token": student_token,
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


def _create_resource(client, token, project_id, title, **kwargs):
    payload = {"project_id": project_id, "title": title, "res_type": "document"}
    payload.update(kwargs)
    r = client.post("/api/v1/resources", json=payload, headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ── 层级与阶段 ─────────────────────────────────────────────
class TestResourceTierAndStage:
    def test_create_resource_with_tier_stage_review_status(self, client):
        ctx = _setup(client)
        r = _create_resource(
            client, ctx["teacher_token"], ctx["project_id"],
            "基础资源", tier="foundation", stage="pre_class", review_status="draft",
        )
        assert r["tier"] == "foundation"
        assert r["stage"] == "pre_class"
        assert r["review_status"] == "draft"

    def test_filter_resources_by_tier(self, client):
        ctx = _setup(client)
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "基础",
                         tier="foundation", review_status="published")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "提升",
                         tier="enhancement", review_status="published")
        r = client.get(
            f"/api/v1/resources?project_id={ctx['project_id']}&tier=foundation",
            headers=_headers(ctx["teacher_token"]),
        )
        titles = [x["title"] for x in r.json()["data"]]
        assert titles == ["基础"]

    def test_filter_resources_by_stage(self, client):
        ctx = _setup(client)
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "课前",
                         stage="pre_class", review_status="published")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "课中",
                         stage="in_class", review_status="published")
        r = client.get(
            f"/api/v1/resources?project_id={ctx['project_id']}&stage=in_class",
            headers=_headers(ctx["teacher_token"]),
        )
        titles = [x["title"] for x in r.json()["data"]]
        assert titles == ["课中"]

    def test_legacy_resource_without_tier_defaults_unassigned(self, client):
        """历史资源不指定 tier/review_status，默认未分层草稿，向后兼容。"""
        ctx = _setup(client)
        r = _create_resource(client, ctx["teacher_token"], ctx["project_id"], "历史资源")
        assert r["tier"] is None
        assert r["stage"] is None
        assert r["review_status"] == "draft"


# ── 审核状态 ───────────────────────────────────────────────
class TestResourceReviewStatus:
    def test_filter_resources_by_review_status(self, client):
        ctx = _setup(client)
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "草稿A",
                         review_status="draft")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "已发布B",
                         review_status="published")
        r = client.get(
            f"/api/v1/resources?project_id={ctx['project_id']}&review_status=published",
            headers=_headers(ctx["teacher_token"]),
        )
        titles = [x["title"] for x in r.json()["data"]]
        assert titles == ["已发布B"]

    def test_update_review_status_flow(self, client):
        """审核状态流转：draft → pending_review → approved → published。"""
        ctx = _setup(client)
        res = _create_resource(client, ctx["teacher_token"], ctx["project_id"],
                               "待审核", review_status="draft")
        for target in ("pending_review", "approved", "published"):
            r = client.put(
                f"/api/v1/resources/{res['id']}", json={"review_status": target},
                headers=_headers(ctx["teacher_token"]),
            )
            assert r.status_code == 200, r.text
            assert r.json()["data"]["review_status"] == target

    def test_invalid_tier_rejected(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/resources", json={
            "project_id": ctx["project_id"], "title": "坏层级",
            "res_type": "document", "tier": "invalid_tier",
        }, headers=_headers(ctx["teacher_token"]))
        assert r.status_code == 400

    def test_invalid_review_status_rejected(self, client):
        ctx = _setup(client)
        r = client.post("/api/v1/resources", json={
            "project_id": ctx["project_id"], "title": "坏状态",
            "res_type": "document", "review_status": "bogus",
        }, headers=_headers(ctx["teacher_token"]))
        assert r.status_code == 400


# ── 三级递进覆盖检查 ───────────────────────────────────────
class TestResourceTierCoverage:
    def test_all_layers_published(self, client):
        ctx = _setup(client)
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "基础",
                         tier="foundation", review_status="published")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "提升",
                         tier="enhancement", review_status="published")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "拓展",
                         tier="extension", review_status="published")
        r = client.get(
            f"/api/v1/resources/tier-coverage?project_id={ctx['project_id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        data = r.json()["data"]
        assert data["foundation"] is True
        assert data["enhancement"] is True
        assert data["extension"] is True
        assert data["missing"] == []
        assert data["total"] == 3
        assert data["counts"]["foundation"] == 1
        assert data["counts"]["enhancement"] == 1
        assert data["counts"]["extension"] == 1
        assert data["counts"]["unassigned"] == 0

    def test_missing_layer_when_only_draft(self, client):
        """某层只有草稿资源，不算覆盖（学生不可见）。"""
        ctx = _setup(client)
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "基础",
                         tier="foundation", review_status="published")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "提升草稿",
                         tier="enhancement", review_status="draft")
        r = client.get(
            f"/api/v1/resources/tier-coverage?project_id={ctx['project_id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        data = r.json()["data"]
        assert data["foundation"] is True
        assert data["enhancement"] is False
        assert data["extension"] is False
        assert "enhancement" in data["missing"]
        assert "extension" in data["missing"]
        # counts 仍统计草稿
        assert data["counts"]["enhancement"] == 1
        assert data["total"] == 2

    def test_empty_project_all_missing(self, client):
        ctx = _setup(client)
        r = client.get(
            f"/api/v1/resources/tier-coverage?project_id={ctx['project_id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        data = r.json()["data"]
        assert data["missing"] == ["foundation", "enhancement", "extension"]
        assert data["total"] == 0


# ── 学生权限（计划 3.7）────────────────────────────────────
class TestResourceStudentPermissions:
    def test_student_sees_only_published_and_approved(self, client):
        ctx = _setup(client)
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "已发布",
                         review_status="published", tier="foundation")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "草稿",
                         review_status="draft", tier="enhancement")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "已通过",
                         review_status="approved", tier="extension")
        _create_resource(client, ctx["teacher_token"], ctx["project_id"], "已退回",
                         review_status="returned", tier="foundation")
        r = client.get(
            f"/api/v1/resources?project_id={ctx['project_id']}",
            headers=_headers(ctx["student_token"]),
        )
        titles = sorted(x["title"] for x in r.json()["data"])
        assert titles == ["已发布", "已通过"]

    def test_student_cannot_read_draft_resource_directly(self, client):
        """学生即使知道草稿资源 ID 也不能单点读取（计划 3.7）。"""
        ctx = _setup(client)
        res = _create_resource(client, ctx["teacher_token"], ctx["project_id"],
                               "草稿机密", review_status="draft")
        r = client.get(
            f"/api/v1/resources/{res['id']}",
            headers=_headers(ctx["student_token"]),
        )
        assert r.status_code == 403

    def test_student_can_read_published_resource_directly(self, client):
        ctx = _setup(client)
        res = _create_resource(client, ctx["teacher_token"], ctx["project_id"],
                               "已发布资源", review_status="published")
        r = client.get(
            f"/api/v1/resources/{res['id']}",
            headers=_headers(ctx["student_token"]),
        )
        assert r.status_code == 200
        assert r.json()["data"]["title"] == "已发布资源"

    def test_student_cannot_manage_resource(self, client):
        """学生无权创建/更新/删除资源。"""
        ctx = _setup(client)
        # 创建
        r = client.post("/api/v1/resources", json={
            "project_id": ctx["project_id"], "title": "学生偷建", "res_type": "document",
        }, headers=_headers(ctx["student_token"]))
        assert r.status_code == 403
