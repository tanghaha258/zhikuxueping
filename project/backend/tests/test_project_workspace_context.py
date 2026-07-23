"""统一项目上下文与阶段服务测试（Task 3）。

覆盖计划 Task 3 验收项与 7 节测试边界：
- GET /api/v1/project-workspace/{project_id}/context 返回真实项目、阶段、权限、
  blockers、warnings、counts 与 actions；阶段固定七阶段顺序；actions 全局至多一个 primary。
- 权限失败、跨学校访问、跨教师访问均返回 403；未认证返回 401。
- POST .../phases/{phase}/complete 与 .../phases/{phase}/reopen 复用项目读写授权；
  归档项目只读（409）；非法阶段 400。
- timeline 返回真实事件（阶段完成/重开/项目创建），不伪造。
- next_action 基于真实数据计算，不用假数据掩盖缺失。
"""
from __future__ import annotations

import uuid

from sqlalchemy import update as sa_update

from app.models.project import Project, ProjectStatus


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


def _create_project(client, token: str, title: str = "工作区上下文项目") -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"title": title},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _add_complete_design(client, token: str, project_id: str) -> None:
    """通过 API 构造一个通过完整性检查的完整项目设计。"""
    headers = _auth(token)
    client.put(
        f"/api/v1/projects/{project_id}/design/problem",
        json={"context": "家乡河道黑臭水体现状", "deliverable": "检测报告"},
        headers=headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/design/contributions",
        json={"subject_id": "sub-science", "role": "core",
              "knowledge": "水质指标", "thinking": "证据推理", "inquiry": "采样对照"},
        headers=headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/design/contributions",
        json={"subject_id": "sub-math", "role": "support",
              "knowledge": "数据统计", "thinking": "建模", "inquiry": "数据分析"},
        headers=headers,
    )
    r = client.post(
        f"/api/v1/projects/{project_id}/design/goals",
        json={"goal_type": "ability", "name": "能设计检测方案"},
        headers=headers,
    )
    goal_id = r.json()["data"]["id"]
    r = client.post(
        f"/api/v1/projects/{project_id}/design/indicators",
        json={"goal_id": goal_id, "observable_behavior": "列出 3 项指标",
              "level_rule": "3 项=优秀"},
        headers=headers,
    )
    indicator_id = r.json()["data"]["id"]
    client.post(
        f"/api/v1/projects/{project_id}/design/evidence-plans",
        json={"indicator_id": indicator_id, "stage": "in_class",
              "evidence_type": "artifact", "collector": "student", "required": True},
        headers=headers,
    )


def _set_project_status(db_session, project_id: str, status: ProjectStatus) -> None:
    """直接设置项目状态，绕过状态机用于归档只读测试。"""
    db_session.execute(
        sa_update(Project).where(Project.id == project_id).values(status=status)
    )
    db_session.commit()


# ============================================================
# 认证与权限
# ============================================================
class TestWorkspaceAuthentication:
    def test_context_requires_authentication(self, client):
        resp = client.get("/api/v1/project-workspace/any/context")
        assert resp.status_code == 401

    def test_timeline_requires_authentication(self, client):
        resp = client.get("/api/v1/project-workspace/any/timeline")
        assert resp.status_code == 401


class TestWorkspaceReadAuthorization:
    """跨教师、跨学校读取 context/timeline 受项目读权限约束。"""

    def test_other_teacher_cannot_read_context(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        pid = _create_project(client, owner_token)

        assert client.get(
            f"/api/v1/project-workspace/{pid}/context",
            headers=_auth(other_token),
        ).status_code == 403
        assert client.get(
            f"/api/v1/project-workspace/{pid}/timeline",
            headers=_auth(other_token),
        ).status_code == 403

    def test_other_school_admin_cannot_read_context(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sysadmin_{tag}", "admin")
        sys_token = _login(client, f"sysadmin_{tag}")
        school_a = client.post(
            "/api/v1/schools", json={"name": f"A校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        school_b = client.post(
            "/api/v1/schools", json={"name": f"B校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]

        _register(client, f"sa_a_{tag}", "school_admin", school_id=school_a["id"])
        _register(client, f"sa_b_{tag}", "school_admin", school_id=school_b["id"])
        sa_a_token = _login(client, f"sa_a_{tag}")
        sa_b_token = _login(client, f"sa_b_{tag}")
        pid = _create_project(client, sa_a_token, title=f"跨校项目 {tag}")

        assert client.get(
            f"/api/v1/project-workspace/{pid}/context",
            headers=_auth(sa_b_token),
        ).status_code == 403

    def test_same_school_admin_can_read_context(self, client):
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
        pid = _create_project(client, t_token, title=f"同校项目 {tag}")

        assert client.get(
            f"/api/v1/project-workspace/{pid}/context",
            headers=_auth(sa_token),
        ).status_code == 200

    def test_context_nonexistent_project_returns_404(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        resp = client.get(
            f"/api/v1/project-workspace/not-a-project/context",
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ============================================================
# context 合同：阶段顺序、唯一主操作、字段完整
# ============================================================
class TestWorkspaceContextContract:
    EXPECTED_PHASES = [
        "diagnosis", "design", "preparation", "implementation",
        "evaluation", "improvement", "closure",
    ]

    def test_context_returns_phases_in_fixed_order_and_single_primary_action(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        data = client.get(
            f"/api/v1/project-workspace/{pid}/context", headers=_auth(token)
        ).json()["data"]

        assert data["project"]["id"] == pid
        assert [p["phase"] for p in data["phases"]] == self.EXPECTED_PHASES
        # 每个阶段都有状态字段，初始为 not_started
        for phase in data["phases"]:
            assert phase["status"] in ("not_started", "in_progress", "completed", "blocked")
        # 至多一个 primary
        primaries = [a for a in data["actions"] if a["primary"]]
        assert len(primaries) == 1
        # next_action 与 primary 一致
        assert data["next_action"] is not None
        assert data["next_action"]["id"] == primaries[0]["id"]

    def test_context_contains_all_required_fields(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        data = client.get(
            f"/api/v1/project-workspace/{pid}/context", headers=_auth(token)
        ).json()["data"]

        # 统一返回真实项目、阶段、权限、blockers、warnings、counts 与 actions
        assert "project" in data and data["project"]["id"] == pid
        assert "phases" in data and len(data["phases"]) == 7
        assert "permissions" in data
        assert "can_view" in data["permissions"]
        assert "can_manage" in data["permissions"]
        assert "is_archived" in data["permissions"]
        assert "blockers" in data and isinstance(data["blockers"], list)
        assert "warnings" in data and isinstance(data["warnings"], list)
        assert "counts" in data and isinstance(data["counts"], dict)
        assert "actions" in data and isinstance(data["actions"], list)

    def test_context_counts_reflect_real_data(self, client):
        """counts 来自真实数据；新项目无任务/提交/评价时计为 0，不伪造。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        counts = client.get(
            f"/api/v1/project-workspace/{pid}/context", headers=_auth(token)
        ).json()["data"]["counts"]

        assert counts["tasks"] == 0
        assert counts["submissions"] == 0
        assert counts["evaluations"] == 0
        assert counts["students"] == 0

    def test_context_next_action_for_draft_points_to_design(self, client):
        """草稿项目缺设计 → next_action 指向设计页，基于真实阻断。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        data = client.get(
            f"/api/v1/project-workspace/{pid}/context", headers=_auth(token)
        ).json()["data"]
        assert data["next_action"]["id"] == "complete_design"
        assert "design" in data["next_action"]["route"]
        # 存在设计阻断
        assert any(b["code"].startswith("missing_") for b in data["blockers"])

    def test_context_next_action_for_active_points_to_first_open_phase(self, client):
        """激活项目 → next_action 指向首个未完成阶段。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_complete_design(client, token, pid)
        client.post(f"/api/v1/projects/{pid}/submit-for-review", headers=_auth(token))
        client.post(f"/api/v1/projects/{pid}/activate", headers=_auth(token))

        data = client.get(
            f"/api/v1/project-workspace/{pid}/context", headers=_auth(token)
        ).json()["data"]
        assert data["project"]["status"] == "active"
        assert data["next_action"]["id"] == "work_diagnosis"
        assert "diagnosis" in data["next_action"]["route"]


# ============================================================
# 阶段完成 / 重开
# ============================================================
class TestPhaseCompleteReopen:
    def test_complete_phase_requires_manage_permission(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        pid = _create_project(client, owner_token)

        resp = client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/complete",
            headers=_auth(other_token),
        )
        assert resp.status_code == 403

    def test_complete_phase_invalid_phase_returns_400(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        resp = client.post(
            f"/api/v1/project-workspace/{pid}/phases/not-a-phase/complete",
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_complete_phase_archived_project_returns_409(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _set_project_status(db_session, pid, ProjectStatus.ARCHIVED)

        resp = client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/complete",
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_owner_can_complete_phase(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        resp = client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/complete",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        phase = resp.json()["data"]
        assert phase["phase"] == "diagnosis"
        assert phase["status"] == "completed"
        assert phase["completed_at"] is not None

        # context 反映完成
        data = client.get(
            f"/api/v1/project-workspace/{pid}/context", headers=_auth(token)
        ).json()["data"]
        diagnosis = next(p for p in data["phases"] if p["phase"] == "diagnosis")
        assert diagnosis["status"] == "completed"

    def test_reopen_phase_restores_in_progress(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/complete",
            headers=_auth(token),
        )

        resp = client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/reopen",
            json={"reason": "需要补充诊断"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        phase = resp.json()["data"]
        assert phase["status"] == "in_progress"
        assert phase["reopened_at"] is not None
        assert phase["reopened_by"] is not None
        assert phase["reopen_reason"] == "需要补充诊断"

    def test_reopen_phase_not_completed_returns_409(self, client):
        """重开未完成的阶段无意义，返回 409。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        resp = client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/reopen",
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_reopen_phase_archived_project_returns_409(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/complete",
            headers=_auth(token),
        )
        _set_project_status(db_session, pid, ProjectStatus.ARCHIVED)

        resp = client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/reopen",
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ============================================================
# 归档只读
# ============================================================
class TestArchivedReadOnly:
    def test_archived_context_has_no_write_primary_action(self, client, db_session):
        """归档项目 context 不含写操作主操作（next_action 不可操作或为空）。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _set_project_status(db_session, pid, ProjectStatus.ARCHIVED)

        data = client.get(
            f"/api/v1/project-workspace/{pid}/context", headers=_auth(token)
        ).json()["data"]
        assert data["permissions"]["is_archived"] is True
        # 归档后无写操作 primary
        write_types = {"transition", "phase_complete", "phase_reopen"}
        primaries = [a for a in data["actions"] if a["primary"] and a["type"] in write_types]
        assert primaries == []


# ============================================================
# timeline 真实事件
# ============================================================
class TestWorkspaceTimeline:
    def test_timeline_returns_project_created_and_phase_events(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        client.post(
            f"/api/v1/project-workspace/{pid}/phases/diagnosis/complete",
            headers=_auth(token),
        )

        events = client.get(
            f"/api/v1/project-workspace/{pid}/timeline", headers=_auth(token)
        ).json()["data"]
        types = {e["type"] for e in events}
        assert "project_created" in types
        assert "phase_completed" in types
        # 每个事件都有时间戳
        for e in events:
            assert e["timestamp"]
            assert e["label"]

    def test_timeline_includes_phase_reopened_event(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        client.post(
            f"/api/v1/project-workspace/{pid}/phases/design/complete",
            headers=_auth(token),
        )
        client.post(
            f"/api/v1/project-workspace/{pid}/phases/design/reopen",
            json={"reason": "调整设计"},
            headers=_auth(token),
        )

        events = client.get(
            f"/api/v1/project-workspace/{pid}/timeline", headers=_auth(token)
        ).json()["data"]
        types = {e["type"] for e in events}
        assert "phase_reopened" in types
        reopened = next(e for e in events if e["type"] == "phase_reopened")
        assert reopened["phase"] == "design"
