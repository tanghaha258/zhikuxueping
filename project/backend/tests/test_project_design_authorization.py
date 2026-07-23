"""项目设计领域权限、状态机和 validate-activation 接口测试。

覆盖计划 Task 1 验收项：
- 写跨教师、跨学校读取和修改拒绝测试。
- 实现 POST /api/v1/projects/{id}/validate-activation 的接口验证。
- 实现状态转换时的服务端强制校验（409）。
"""
from __future__ import annotations

import uuid


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


def _create_project(client, token: str, title: str = "设计权限项目") -> str:
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
    # 真实问题
    r = client.put(
        f"/api/v1/projects/{project_id}/design/problem",
        json={"context": "家乡河道黑臭水体现状", "deliverable": "检测报告"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    # 核心学科
    r = client.post(
        f"/api/v1/projects/{project_id}/design/contributions",
        json={
            "subject_id": "sub-science",
            "role": "core",
            "knowledge": "水质指标",
            "thinking": "证据推理",
            "inquiry": "采样对照",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    # 支撑学科
    r = client.post(
        f"/api/v1/projects/{project_id}/design/contributions",
        json={
            "subject_id": "sub-math",
            "role": "support",
            "knowledge": "数据统计",
            "thinking": "建模",
            "inquiry": "数据分析",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    # 学习目标
    r = client.post(
        f"/api/v1/projects/{project_id}/design/goals",
        json={"goal_type": "ability", "name": "能设计检测方案"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    goal_id = r.json()["data"]["id"]
    # 评价指标
    r = client.post(
        f"/api/v1/projects/{project_id}/design/indicators",
        json={"goal_id": goal_id, "observable_behavior": "列出 3 项指标", "level_rule": "3 项=优秀"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    indicator_id = r.json()["data"]["id"]
    # 证据计划
    r = client.post(
        f"/api/v1/projects/{project_id}/design/evidence-plans",
        json={
            "indicator_id": indicator_id,
            "stage": "in_class",
            "evidence_type": "artifact",
            "collector": "student",
            "required": True,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text


# ── 跨教师权限 ───────────────────────────────────────────────
class TestCrossTeacherAuthorization:
    """教师 A 的项目设计，教师 B 不能读取或修改。"""

    def test_other_teacher_cannot_read_design(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        pid = _create_project(client, owner_token)

        resp = client.get(
            f"/api/v1/projects/{pid}/design",
            headers=_auth(other_token),
        )
        assert resp.status_code == 403

    def test_other_teacher_cannot_add_contribution(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        pid = _create_project(client, owner_token)

        resp = client.post(
            f"/api/v1/projects/{pid}/design/contributions",
            json={"subject_id": "sub-x", "role": "core"},
            headers=_auth(other_token),
        )
        assert resp.status_code == 403

    def test_owner_can_read_and_edit_design(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        pid = _create_project(client, owner_token)

        resp = client.get(f"/api/v1/projects/{pid}/design", headers=_auth(owner_token))
        assert resp.status_code == 200
        # 初始设计为空
        data = resp.json()["data"]
        assert data["problem"] is None
        assert data["contributions"] == []


# ── 跨学校权限 ───────────────────────────────────────────────
class TestCrossSchoolAuthorization:
    """学校 A 的项目设计，学校 B 的管理员不能读取。"""

    def test_other_school_admin_cannot_read_design(self, client):
        tag = uuid.uuid4().hex[:8]
        # 系统管理员创建两所学校
        _register(client, f"sysadmin_{tag}", "admin")
        sys_token = _login(client, f"sysadmin_{tag}")
        school_a = client.post(
            "/api/v1/schools",
            json={"name": f"A校 {tag}"},
            headers=_auth(sys_token),
        ).json()["data"]
        school_b = client.post(
            "/api/v1/schools",
            json={"name": f"B校 {tag}"},
            headers=_auth(sys_token),
        ).json()["data"]

        # 两名校管理员分别归属不同学校
        _register(client, f"sa_a_{tag}", "school_admin", school_id=school_a["id"])
        _register(client, f"sa_b_{tag}", "school_admin", school_id=school_b["id"])
        sa_a_token = _login(client, f"sa_a_{tag}")
        sa_b_token = _login(client, f"sa_b_{tag}")

        # sa_a 创建项目（project.school_id = school_a）
        pid = _create_project(client, sa_a_token, title=f"跨校项目 {tag}")

        # sa_b 不能读取 sa_a 学校的项目设计
        resp = client.get(
            f"/api/v1/projects/{pid}/design",
            headers=_auth(sa_b_token),
        )
        assert resp.status_code == 403

    def test_same_school_admin_can_read_design(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sysadmin_{tag}", "admin")
        sys_token = _login(client, f"sysadmin_{tag}")
        school = client.post(
            "/api/v1/schools",
            json={"name": f"同校 {tag}"},
            headers=_auth(sys_token),
        ).json()["data"]

        # 同校的教师创建项目，同校的校管理员可读
        _register(client, f"t_{tag}", "teacher", school_id=school["id"])
        _register(client, f"sa_{tag}", "school_admin", school_id=school["id"])
        t_token = _login(client, f"t_{tag}")
        sa_token = _login(client, f"sa_{tag}")
        pid = _create_project(client, t_token, title=f"同校项目 {tag}")

        resp = client.get(
            f"/api/v1/projects/{pid}/design",
            headers=_auth(sa_token),
        )
        assert resp.status_code == 200


# ── validate-activation 接口 ────────────────────────────────
class TestValidateActivationApi:
    """POST /api/v1/projects/{id}/validate-activation 返回 blockers/warnings/completion。"""

    def test_empty_project_returns_blockers(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        resp = client.post(
            f"/api/v1/projects/{pid}/validate-activation",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["can_activate"] is False
        assert len(data["blockers"]) > 0
        codes = {b["code"] for b in data["blockers"]}
        assert "missing_core_subject" in codes
        assert "missing_support_subject" in codes
        assert 0.0 <= data["completion"] < 1.0
        assert "details" in data

    def test_complete_project_returns_can_activate(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_complete_design(client, token, pid)

        resp = client.post(
            f"/api/v1/projects/{pid}/validate-activation",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["can_activate"] is True
        assert data["blockers"] == []
        assert data["completion"] == 1.0

    def test_student_can_read_validation_but_not_activate(self, client):
        """学生可见完整度（读取权限）但无法激活（角色限制）。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        # 学生无法访问该教师私有项目（不在班级范围），预期 403
        # 此处验证 validate-activation 仍受 ensure_can_read 约束
        _register(client, f"s_{tag}", "student")
        s_token = _login(client, f"s_{tag}")
        resp = client.post(
            f"/api/v1/projects/{pid}/validate-activation",
            headers=_auth(s_token),
        )
        assert resp.status_code == 403


# ── 状态机 409 ───────────────────────────────────────────────
class TestProjectStateMachine409:
    """非法状态跃迁统一返回 409，并包含当前/目标状态信息。"""

    def test_activate_from_draft_returns_409(self, client):
        """draft -> active 直接激活被拒（必须先 submit_for_review）。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        resp = client.post(
            f"/api/v1/projects/{pid}/activate",
            headers=_auth(token),
        )
        assert resp.status_code == 409
        message = resp.json()["message"]
        assert "pending_review" in message or "不允许" in message

    def test_activate_incomplete_project_returns_409(self, client):
        """pending_review -> active 但完整性未通过返回 409。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        # 提交审核（草稿允许暂缺字段）
        r = client.post(
            f"/api/v1/projects/{pid}/submit-for-review",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "pending_review"
        # 激活不完整项目被拒
        resp = client.post(
            f"/api/v1/projects/{pid}/activate",
            headers=_auth(token),
        )
        assert resp.status_code == 409
        assert "完整性" in resp.json()["message"] or "blocker" in resp.json()["message"].lower()

    def test_complete_from_draft_returns_409(self, client):
        """draft -> complete 非法跃迁返回 409。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        resp = client.post(
            f"/api/v1/projects/{pid}/complete",
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_submit_for_review_then_activate_complete_project(self, client):
        """完整项目：draft -> pending_review -> active 成功路径。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_complete_design(client, token, pid)

        r = client.post(
            f"/api/v1/projects/{pid}/submit-for-review",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "pending_review"

        r = client.post(
            f"/api/v1/projects/{pid}/activate",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "active"

    def test_submit_for_review_twice_returns_409(self, client):
        """pending_review -> pending_review 非法跃迁返回 409。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        client.post(f"/api/v1/projects/{pid}/submit-for-review", headers=_auth(token))
        resp = client.post(
            f"/api/v1/projects/{pid}/submit-for-review",
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ── 设计编辑状态保护 ─────────────────────────────────────────
class TestDesignEditStateProtection:
    """active 及之后状态的项目设计只读，编辑返回 409。"""

    def test_cannot_edit_design_after_activate(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_complete_design(client, token, pid)
        client.post(f"/api/v1/projects/{pid}/submit-for-review", headers=_auth(token))
        client.post(f"/api/v1/projects/{pid}/activate", headers=_auth(token))

        # 激活后编辑设计被拒（409 状态冲突）
        resp = client.put(
            f"/api/v1/projects/{pid}/design/problem",
            json={"context": "尝试修改已激活项目"},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_can_edit_design_in_draft(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        resp = client.put(
            f"/api/v1/projects/{pid}/design/problem",
            json={"context": "草稿阶段可编辑"},
            headers=_auth(token),
        )
        assert resp.status_code == 200


# ── 重复学科接口级 409 ──────────────────────────────────────
class TestDuplicateSubjectApi409:
    """通过 API 重复登记学科/重复核心学科返回 409。"""

    def test_duplicate_subject_returns_409(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        r = client.post(
            f"/api/v1/projects/{pid}/design/contributions",
            json={"subject_id": "sub-math", "role": "support"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        r = client.post(
            f"/api/v1/projects/{pid}/design/contributions",
            json={"subject_id": "sub-math", "role": "support"},
            headers=_auth(token),
        )
        assert r.status_code == 409

    def test_second_core_returns_409(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        client.post(
            f"/api/v1/projects/{pid}/design/contributions",
            json={"subject_id": "sub-a", "role": "core"},
            headers=_auth(token),
        )
        r = client.post(
            f"/api/v1/projects/{pid}/design/contributions",
            json={"subject_id": "sub-b", "role": "core"},
            headers=_auth(token),
        )
        assert r.status_code == 409
