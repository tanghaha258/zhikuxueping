"""工具上下文链接服务测试（Task 8）。

覆盖计划 Task 8 验收项与 spec 第 7 节测试边界：
- 项目模式必须提供 project_id 和 placement；独立模式不得伪造项目 ID。
- 跨校项目关联必须拒绝（403）；同校管理员可关联。
- 保存时创建一次业务资产和一条项目引用；取消关联只删引用，不删资产/文件。
- 同一资产在同一项目同一位置不可重复挂载（409）。
- 资源创建带 project_id 时自动建立一条默认引用（placement=resource）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.resource import Resource
from app.models.saved_lesson_plan import SavedLessonPlan
from app.models.tool_context import ToolContextLink
from app.models.user import User


# ── 测试辅助 ──────────────────────────────────────────────────
def _register(client, username: str, role: str = "teacher", school_id: str | None = None):
    payload = {
        "username": username,
        "password": "12345678",
        "email": f"{username}@test.com",
        "display_name": username,
        "role": role,
    }
    if school_id:
        payload["school_id"] = school_id
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _login(client, username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "12345678"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_project(client, token: str, title: str = "上下文项目") -> str:
    resp = client.post("/api/v1/projects", json={"title": title}, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _create_resource(client, token: str, project_id: str | None = None) -> str:
    payload = {
        "title": "上下文测试资源",
        "res_type": "link",
        "url": "https://example.com/test",
    }
    if project_id:
        payload["project_id"] = project_id
    resp = client.post("/api/v1/resources", json=payload, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _create_lesson_plan(client, token: str) -> str:
    resp = client.post(
        "/api/v1/ai/lesson-plans",
        json={
            "title": "上下文教案",
            "content": "<h1>内容</h1>",
            "subject": "science",
            "grade": "七年级",
            "topic": "主题",
            "duration": 45,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _user_id(db_session, username: str) -> str:
    return db_session.execute(select(User).where(User.username == username)).scalar_one().id


# ============================================================
# 1. 上下文校验：项目模式必须 project_id + placement；独立模式不得伪造
# ============================================================
class TestContextValidation:
    def test_project_mode_requires_project_id(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        resource_id = _create_resource(client, token)

        # 缺 project_id → 400
        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "placement": "resource",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_project_mode_requires_placement(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token)

        # 缺 placement → 400
        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "project_id": project_id,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_independent_mode_does_not_fake_project_id(self, client):
        """独立模式不通过 context-links 端点伪造项目关联。

        context-links 端点只接受项目模式（必须 project_id+placement）。
        试图用空 project_id 关联必须被拒绝。
        """
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        resource_id = _create_resource(client, token)

        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "project_id": "",
                "placement": "resource",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_invalid_artifact_type_rejected(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token)

        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "unknown_type",
                "artifact_id": resource_id,
                "project_id": project_id,
                "placement": "resource",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_invalid_placement_rejected(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token)

        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "project_id": project_id,
                "placement": "bad_placement",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_invalid_phase_rejected(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token)

        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "project_id": project_id,
                "placement": "resource",
                "phase": "not_a_phase",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400


# ============================================================
# 2. 跨校项目关联必须拒绝
# ============================================================
class TestCrossSchoolLinkRejection:
    def _setup_two_schools(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sysadmin_{tag}", "admin")
        sys_token = _login(client, f"sysadmin_{tag}")
        school_a = client.post(
            "/api/v1/schools", json={"name": f"A校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        school_b = client.post(
            "/api/v1/schools", json={"name": f"B校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        _register(client, f"ta_{tag}", "teacher", school_id=school_a["id"])
        _register(client, f"tb_{tag}", "teacher", school_id=school_b["id"])
        _register(client, f"sb_{tag}", "school_admin", school_id=school_b["id"])
        ta_token = _login(client, f"ta_{tag}")
        tb_token = _login(client, f"tb_{tag}")
        sb_token = _login(client, f"sb_{tag}")
        return ta_token, tb_token, sb_token, tag

    def test_cross_school_teacher_cannot_link_resource(self, client):
        ta_token, tb_token, _, tag = self._setup_two_schools(client)
        project_id = _create_project(client, ta_token, title=f"A校项目 {tag}")
        # tb 在 B 校创建独立资源
        tb_resource = _create_resource(client, tb_token)

        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": tb_resource,
                "project_id": project_id,
                "placement": "resource",
            },
            headers=_auth(tb_token),
        )
        assert resp.status_code == 403

    def test_cross_school_admin_cannot_link(self, client):
        ta_token, _, sb_token, tag = self._setup_two_schools(client)
        project_id = _create_project(client, ta_token, title=f"A校项目 {tag}")
        # B 校管理员试图关联任意资产到 A 校项目
        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": "any-asset-id",
                "project_id": project_id,
                "placement": "resource",
            },
            headers=_auth(sb_token),
        )
        assert resp.status_code == 403

    def test_same_school_admin_can_link(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sysadmin_{tag}", "admin")
        sys_token = _login(client, f"sysadmin_{tag}")
        school = client.post(
            "/api/v1/schools", json={"name": f"同校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        _register(client, f"t_{tag}", "teacher", school_id=school["id"])
        _register(client, f"sa_{tag}", "school_admin", school_id=school["id"])
        t_token = _login(client, f"t_{tag}")
        sa_token = _login(client, f"sa_{tag}")
        project_id = _create_project(client, t_token, title=f"同校项目 {tag}")
        resource_id = _create_resource(client, t_token)

        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "project_id": project_id,
                "placement": "resource",
            },
            headers=_auth(sa_token),
        )
        assert resp.status_code == 200, resp.text


# ============================================================
# 3. 保存创建一次资产 + 一条项目引用；取消关联只删引用
# ============================================================
class TestLinkUnlinkAssetPreservation:
    def test_link_creates_one_reference(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token)

        resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "project_id": project_id,
                "placement": "resource",
                "phase": "preparation",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        link_id = resp.json()["data"]["id"]

        # 数据库仅一条引用
        links = list(
            db_session.execute(
                select(ToolContextLink).where(ToolContextLink.artifact_id == resource_id)
            ).scalars().all()
        )
        assert len(links) == 1
        assert links[0].id == link_id
        assert links[0].artifact_type == "resource"
        assert links[0].project_id == project_id
        assert links[0].placement == "resource"
        assert links[0].phase == "preparation"

    def test_duplicate_link_rejected(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token)
        payload = {
            "artifact_type": "resource",
            "artifact_id": resource_id,
            "project_id": project_id,
            "placement": "resource",
        }
        first = client.post("/api/v1/resources/context-links", json=payload, headers=_auth(token))
        assert first.status_code == 200

        second = client.post("/api/v1/resources/context-links", json=payload, headers=_auth(token))
        assert second.status_code == 409

    def test_same_asset_different_placement_allowed(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token)

        r1 = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "project_id": project_id,
                "placement": "resource",
            },
            headers=_auth(token),
        )
        r2 = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": resource_id,
                "project_id": project_id,
                "placement": "pre_test",
            },
            headers=_auth(token),
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_unlink_deletes_reference_keeps_asset(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token, project_id=project_id)

        # 资源创建时已带 project_id，应自动建立一条默认引用
        links_before = list(
            db_session.execute(
                select(ToolContextLink).where(ToolContextLink.artifact_id == resource_id)
            ).scalars().all()
        )
        assert len(links_before) == 1
        link_id = links_before[0].id

        # 取消关联：只删引用
        resp = client.delete(
            f"/api/v1/resources/context-links/{link_id}", headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["preserved"] is True

        # 引用已删除
        link_after = db_session.get(ToolContextLink, link_id)
        assert link_after is None

        # 资产（资源）仍存在，文件 URL 保留
        resource_after = db_session.get(Resource, resource_id)
        assert resource_after is not None
        assert resource_after.title == "上下文测试资源"
        assert resource_after.url == "https://example.com/test"
        # 资源的 project_id 也被清空（解耦项目关联）
        assert resource_after.project_id is None

    def test_unlink_nonexistent_link_returns_404(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")

        resp = client.delete(
            "/api/v1/resources/context-links/nonexistent-id", headers=_auth(token)
        )
        assert resp.status_code == 404

    def test_unlink_cross_school_rejected(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sysadmin_{tag}", "admin")
        sys_token = _login(client, f"sysadmin_{tag}")
        school_a = client.post(
            "/api/v1/schools", json={"name": f"A校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        school_b = client.post(
            "/api/v1/schools", json={"name": f"B校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        _register(client, f"ta_{tag}", "teacher", school_id=school_a["id"])
        _register(client, f"tb_{tag}", "teacher", school_id=school_b["id"])
        ta_token = _login(client, f"ta_{tag}")
        tb_token = _login(client, f"tb_{tag}")
        project_id = _create_project(client, ta_token, title=f"A校项目 {tag}")
        ta_resource = _create_resource(client, ta_token)

        link_resp = client.post(
            "/api/v1/resources/context-links",
            json={
                "artifact_type": "resource",
                "artifact_id": ta_resource,
                "project_id": project_id,
                "placement": "resource",
            },
            headers=_auth(ta_token),
        )
        link_id = link_resp.json()["data"]["id"]

        # B 校教师试图解关联
        resp = client.delete(
            f"/api/v1/resources/context-links/{link_id}", headers=_auth(tb_token)
        )
        assert resp.status_code == 403


# ============================================================
# 4. 资源创建带 project_id 时自动建立一条默认引用
# ============================================================
class TestResourceAutoLinkOnCreate:
    def test_create_resource_with_project_auto_links(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)

        resource_id = _create_resource(client, token, project_id=project_id)

        links = list(
            db_session.execute(
                select(ToolContextLink).where(ToolContextLink.artifact_id == resource_id)
            ).scalars().all()
        )
        assert len(links) == 1
        assert links[0].artifact_type == "resource"
        assert links[0].project_id == project_id
        assert links[0].placement == "resource"

    def test_create_resource_without_project_no_link(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        resource_id = _create_resource(client, token)

        links = list(
            db_session.execute(
                select(ToolContextLink).where(ToolContextLink.artifact_id == resource_id)
            ).scalars().all()
        )
        assert len(links) == 0


# ============================================================
# 5. 列表查询
# ============================================================
class TestListLinks:
    def test_list_project_links(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        r1 = _create_resource(client, token)
        r2 = _create_resource(client, token)

        client.post(
            "/api/v1/resources/context-links",
            json={"artifact_type": "resource", "artifact_id": r1, "project_id": project_id, "placement": "resource"},
            headers=_auth(token),
        )
        client.post(
            "/api/v1/resources/context-links",
            json={"artifact_type": "resource", "artifact_id": r2, "project_id": project_id, "placement": "pre_test"},
            headers=_auth(token),
        )

        resp = client.get(
            f"/api/v1/resources/context-links?project_id={project_id}",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2

    def test_list_project_links_filter_by_artifact_type(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        project_id = _create_project(client, token)
        resource_id = _create_resource(client, token)
        plan_id = _create_lesson_plan(client, token)

        client.post(
            "/api/v1/resources/context-links",
            json={"artifact_type": "resource", "artifact_id": resource_id, "project_id": project_id, "placement": "resource"},
            headers=_auth(token),
        )
        client.post(
            "/api/v1/resources/context-links",
            json={"artifact_type": "lesson_plan", "artifact_id": plan_id, "project_id": project_id, "placement": "lesson_plan"},
            headers=_auth(token),
        )

        resp = client.get(
            f"/api/v1/resources/context-links?project_id={project_id}&artifact_type=lesson_plan",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["artifact_type"] == "lesson_plan"

    def test_list_links_cross_school_rejected(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sysadmin_{tag}", "admin")
        sys_token = _login(client, f"sysadmin_{tag}")
        school_a = client.post(
            "/api/v1/schools", json={"name": f"A校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        school_b = client.post(
            "/api/v1/schools", json={"name": f"B校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        _register(client, f"ta_{tag}", "teacher", school_id=school_a["id"])
        _register(client, f"tb_{tag}", "teacher", school_id=school_b["id"])
        ta_token = _login(client, f"ta_{tag}")
        tb_token = _login(client, f"tb_{tag}")
        project_id = _create_project(client, ta_token, title=f"A校项目 {tag}")

        resp = client.get(
            f"/api/v1/resources/context-links?project_id={project_id}",
            headers=_auth(tb_token),
        )
        assert resp.status_code == 403

    def test_list_links_require_auth(self, client):
        resp = client.get("/api/v1/resources/context-links?project_id=any")
        assert resp.status_code == 401


# ============================================================
# 6. 教案服务层关联（无独立路由，验证服务可直接调用）
# ============================================================
class TestLessonPlanServiceLink:
    def test_lesson_plan_link_unlink_preserves_plan(self, client, db_session):
        from app.modules.lesson_plans.service import (
            link_lesson_plan_to_project,
            list_lesson_plan_links,
            unlink_lesson_plan_from_project,
        )
        from app.modules.projects.repository import ProjectRepository

        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        username = f"t_{tag}"
        plan_id = _create_lesson_plan(client, token)
        project_id = _create_project(client, token)

        actor = db_session.execute(
            select(User).where(User.username == username)
        ).scalar_one()
        project = ProjectRepository(db_session).get(project_id)

        link = link_lesson_plan_to_project(
            db_session,
            actor=actor,
            plan_id=plan_id,
            project_id=project_id,
            placement="lesson_plan",
            phase="preparation",
        )
        assert link.artifact_type == "lesson_plan"
        assert link.artifact_id == plan_id
        assert link.project_id == project_id

        links = list_lesson_plan_links(db_session, actor=actor, plan_id=plan_id)
        assert len(links) == 1

        result = unlink_lesson_plan_from_project(db_session, actor=actor, link_id=link.id)
        assert result["preserved"] is True
        assert result["artifact_type"] == "lesson_plan"
        assert result["artifact_id"] == plan_id

        # 教案资产仍存在
        plan_after = db_session.get(SavedLessonPlan, plan_id)
        assert plan_after is not None
        assert plan_after.title == "上下文教案"

        # 引用已删除
        links_after = list_lesson_plan_links(db_session, actor=actor, plan_id=plan_id)
        assert len(links_after) == 0

    def test_lesson_plan_cross_school_rejected(self, client, db_session):
        from app.modules.lesson_plans.service import link_lesson_plan_to_project

        tag = uuid.uuid4().hex[:8]
        _register(client, f"sysadmin_{tag}", "admin")
        sys_token = _login(client, f"sysadmin_{tag}")
        school_a = client.post(
            "/api/v1/schools", json={"name": f"A校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        school_b = client.post(
            "/api/v1/schools", json={"name": f"B校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        _register(client, f"ta_{tag}", "teacher", school_id=school_a["id"])
        _register(client, f"tb_{tag}", "teacher", school_id=school_b["id"])
        ta_token = _login(client, f"ta_{tag}")
        tb_token = _login(client, f"tb_{tag}")
        plan_id = _create_lesson_plan(client, tb_token)
        project_id = _create_project(client, ta_token, title=f"A校项目 {tag}")

        tb_user = db_session.execute(
            select(User).where(User.username == f"tb_{tag}")
        ).scalar_one()

        from app.core.exceptions import AppException
        with pytest.raises(AppException) as exc:
            link_lesson_plan_to_project(
                db_session,
                actor=tb_user,
                plan_id=plan_id,
                project_id=project_id,
                placement="lesson_plan",
            )
        assert exc.value.status_code == 403
