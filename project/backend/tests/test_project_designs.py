"""跨学科设计与完整性校验测试（Task 7）。

覆盖计划 Task 7 验收点：
- 完整性校验：核心学科、支持学科、每个学科贡献说明、真实问题最终成果、目标-指标-证据可追踪。
- 缺项必须返回具体 field 与修复路由（fix_route）。
- 原地编辑已有贡献/目标/指标/证据计划，不删除重建（ID 保持不变）。
- 关联删除必须返回引用影响并要求显式确认（confirm=true）。

通过 API 端到端验证，使用真实数据库会话，不模拟业务结果。
"""
from __future__ import annotations

import uuid

import pytest


# ── 测试辅助 ────────────────────────────────────────────────────
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


def _create_project(client, token: str, title: str = "跨学科设计项目") -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"title": title},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _add_problem(client, token, pid, *, context="河道水质现状", deliverable="检测报告"):
    r = client.put(
        f"/api/v1/projects/{pid}/design/problem",
        json={"context": context, "deliverable": deliverable},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_contribution(
    client,
    token,
    pid,
    subject_id,
    role,
    *,
    knowledge="知识贡献",
    thinking="思维方式",
    inquiry="探究方法",
):
    r = client.post(
        f"/api/v1/projects/{pid}/design/contributions",
        json={
            "subject_id": subject_id,
            "role": role,
            "knowledge": knowledge,
            "thinking": thinking,
            "inquiry": inquiry,
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_goal(client, token, pid, *, name="能设计检测方案", goal_type="ability"):
    r = client.post(
        f"/api/v1/projects/{pid}/design/goals",
        json={"goal_type": goal_type, "name": name},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_indicator(client, token, pid, goal_id, *, behavior="列出3项指标"):
    r = client.post(
        f"/api/v1/projects/{pid}/design/indicators",
        json={"goal_id": goal_id, "observable_behavior": behavior, "level_rule": "3项优秀"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_evidence(client, token, pid, indicator_id, *, required=True):
    r = client.post(
        f"/api/v1/projects/{pid}/design/evidence-plans",
        json={
            "indicator_id": indicator_id,
            "stage": "in_class",
            "evidence_type": "artifact",
            "collector": "student",
            "required": required,
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _validate(client, token, pid) -> dict:
    r = client.post(
        f"/api/v1/projects/{pid}/validate-activation",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _unique_tag() -> str:
    return uuid.uuid4().hex[:8]


# ============================================================
# 1. 完整性校验：每个学科必须有贡献说明
# ============================================================
class TestContributionDescriptionValidation:
    """每个学科贡献说明（knowledge/thinking/inquiry 至少一项非空）为阻断项。"""

    def test_validation_rejects_subject_without_contribution(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_problem(client, token, pid)
        # 核心学科：贡献说明全部为空
        _add_contribution(
            client, token, pid, "sub-core", "core",
            knowledge="", thinking="", inquiry="",
        )
        _add_contribution(
            client, token, pid, "sub-support", "support",
        )

        data = _validate(client, token, pid)

        codes = [b["code"] for b in data["blockers"]]
        assert "SUBJECT_CONTRIBUTION_MISSING" in codes, (
            f"贡献说明为空时应返回 SUBJECT_CONTRIBUTION_MISSING，实际 blockers={codes}"
        )
        # 能定位到具体学科
        target = [b for b in data["blockers"] if b["code"] == "SUBJECT_CONTRIBUTION_MISSING"][0]
        assert "sub-core" in target["field"]

    def test_validation_accepts_partial_contribution(self, client):
        """至少一项非空即可通过此项校验。"""
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_problem(client, token, pid)
        _add_contribution(
            client, token, pid, "sub-core", "core",
            knowledge="水质指标", thinking="", inquiry="",
        )
        _add_contribution(
            client, token, pid, "sub-support", "support",
            knowledge="数据统计",
        )
        _add_goal(client, token, pid)
        goal = _add_goal(client, token, pid, name="目标2")
        ind = _add_indicator(client, token, pid, goal["id"])
        _add_evidence(client, token, pid, ind["id"])

        data = _validate(client, token, pid)
        codes = [b["code"] for b in data["blockers"]]
        assert "SUBJECT_CONTRIBUTION_MISSING" not in codes


# ============================================================
# 2. 完整性校验：真实问题必须有最终成果
# ============================================================
class TestProblemDeliverableValidation:
    """真实问题的 deliverable（最终成果）不能为空。"""

    def test_validation_rejects_problem_without_deliverable(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        # deliverable 为空
        _add_problem(client, token, pid, deliverable="")
        _add_contribution(client, token, pid, "sub-c", "core")
        _add_contribution(client, token, pid, "sub-s", "support")

        data = _validate(client, token, pid)

        codes = [b["code"] for b in data["blockers"]]
        assert "PROBLEM_DELIVERABLE_MISSING" in codes, (
            f"deliverable 为空时应返回 PROBLEM_DELIVERABLE_MISSING，实际 blockers={codes}"
        )
        target = [b for b in data["blockers"] if b["code"] == "PROBLEM_DELIVERABLE_MISSING"][0]
        assert target["field"] == "problem.deliverable"

    def test_validation_accepts_problem_with_deliverable(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_problem(client, token, pid, deliverable="检测报告")
        _add_contribution(client, token, pid, "sub-c", "core")
        _add_contribution(client, token, pid, "sub-s", "support")
        goal = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, goal["id"])
        _add_evidence(client, token, pid, ind["id"])

        data = _validate(client, token, pid)
        codes = [b["code"] for b in data["blockers"]]
        assert "PROBLEM_DELIVERABLE_MISSING" not in codes


# ============================================================
# 3. 每个阻断/警告必须携带 fix_route 修复路由
# ============================================================
class TestValidationFixRoute:
    """缺项必须返回具体 field 与修复路由，前端可据此定位编辑区。"""

    def test_blockers_carry_fix_route(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        # 空设计，必然有多个 blocker
        data = _validate(client, token, pid)

        assert len(data["blockers"]) > 0
        for b in data["blockers"]:
            assert "fix_route" in b, f"blocker {b['code']} 缺少 fix_route"
            assert b["fix_route"], f"blocker {b['code']} 的 fix_route 为空"
            # fix_route 应指向项目设计页的某个锚点
            assert pid in b["fix_route"] or "/design" in b["fix_route"], (
                f"blocker {b['code']} 的 fix_route={b['fix_route']} 未指向设计页"
            )

    def test_missing_core_subject_fix_route_points_to_contributions(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        data = _validate(client, token, pid)
        target = [b for b in data["blockers"] if b["code"] == "missing_core_subject"][0]
        assert "contributions" in target["fix_route"]

    def test_missing_problem_fix_route_points_to_problem(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)

        data = _validate(client, token, pid)
        target = [b for b in data["blockers"] if b["code"] == "missing_problem"][0]
        assert "problem" in target["fix_route"]


# ============================================================
# 4. 原地编辑：已有贡献/目标/指标/证据计划 ID 保持不变
# ============================================================
class TestInPlaceEdit:
    """通过 PATCH 原地更新，不删除重建；ID 必须保持不变。"""

    def test_patch_contribution_preserves_id(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        c = _add_contribution(client, token, pid, "sub-c", "core")
        original_id = c["id"]

        r = client.patch(
            f"/api/v1/projects/{pid}/design/contributions/{original_id}",
            json={"knowledge": "更新后的知识贡献"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        updated = r.json()["data"]
        assert updated["id"] == original_id, "原地编辑后 ID 必须保持不变"
        assert updated["knowledge"] == "更新后的知识贡献"
        # 其他字段保持原值
        assert updated["thinking"] == c["thinking"]
        assert updated["inquiry"] == c["inquiry"]

    def test_patch_goal_preserves_id(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        g = _add_goal(client, token, pid, name="原始目标")
        original_id = g["id"]

        r = client.patch(
            f"/api/v1/projects/{pid}/design/goals/{original_id}",
            json={"name": "更新后的目标", "description": "新增描述"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        updated = r.json()["data"]
        assert updated["id"] == original_id
        assert updated["name"] == "更新后的目标"
        assert updated["description"] == "新增描述"

    def test_patch_indicator_preserves_id(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        g = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, g["id"])
        original_id = ind["id"]

        r = client.patch(
            f"/api/v1/projects/{pid}/design/indicators/{original_id}",
            json={"observable_behavior": "更新后的可观察行为"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        updated = r.json()["data"]
        assert updated["id"] == original_id
        assert updated["observable_behavior"] == "更新后的可观察行为"

    def test_patch_evidence_plan_preserves_id(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        g = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, g["id"])
        plan = _add_evidence(client, token, pid, ind["id"])
        original_id = plan["id"]

        r = client.patch(
            f"/api/v1/projects/{pid}/design/evidence-plans/{original_id}",
            json={"description": "更新后的描述", "required": False},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        updated = r.json()["data"]
        assert updated["id"] == original_id
        assert updated["description"] == "更新后的描述"
        assert updated["required"] is False

    def test_patch_problem_preserves_version_chain(self, client):
        """PATCH 真实问题原地更新当前版本，不新增版本（PUT 才版本化）。"""
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        p = _add_problem(client, token, pid, context="原始情境")
        original_version = p["version"]

        r = client.patch(
            f"/api/v1/projects/{pid}/design/problem",
            json={"context": "更新后的情境"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        updated = r.json()["data"]
        assert updated["id"] == p["id"], "PATCH 原地更新不新增记录"
        assert updated["version"] == original_version, "PATCH 不应新增版本"
        assert updated["context"] == "更新后的情境"


# ============================================================
# 5. 关联删除：返回引用影响并要求显式确认
# ============================================================
class TestDeletionWithConfirmation:
    """删除被引用的实体必须返回引用影响，confirm=true 才执行。"""

    def test_delete_goal_without_confirm_returns_impact(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        g = _add_goal(client, token, pid)
        _add_indicator(client, token, pid, g["id"])

        r = client.delete(
            f"/api/v1/projects/{pid}/design/goals/{g['id']}",
            headers=_auth(token),
        )
        assert r.status_code == 409, r.text
        body = r.json()
        # 返回引用影响
        assert "data" in body
        impact = body["data"]
        assert impact["requires_confirmation"] is True
        assert impact["referenced_by"]["indicators"] >= 1
        # 目标仍然存在
        snap = client.get(
            f"/api/v1/projects/{pid}/design", headers=_auth(token)
        ).json()["data"]
        assert any(go["id"] == g["id"] for go in snap["goals"])

    def test_delete_goal_with_confirm_cascades(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        g = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, g["id"])
        _add_evidence(client, token, pid, ind["id"])

        r = client.delete(
            f"/api/v1/projects/{pid}/design/goals/{g['id']}?confirm=true",
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        # 级联删除：目标、指标、证据计划全部消失
        snap = client.get(
            f"/api/v1/projects/{pid}/design", headers=_auth(token)
        ).json()["data"]
        assert snap["goals"] == []
        assert snap["indicators"] == []
        assert snap["evidence_plans"] == []

    def test_delete_indicator_without_confirm_returns_impact(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        g = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, g["id"])
        _add_evidence(client, token, pid, ind["id"])

        r = client.delete(
            f"/api/v1/projects/{pid}/design/indicators/{ind['id']}",
            headers=_auth(token),
        )
        assert r.status_code == 409, r.text
        impact = r.json()["data"]
        assert impact["requires_confirmation"] is True
        assert impact["referenced_by"]["evidence_plans"] >= 1

    def test_delete_indicator_with_confirm_cascades(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        g = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, g["id"])
        _add_evidence(client, token, pid, ind["id"])

        r = client.delete(
            f"/api/v1/projects/{pid}/design/indicators/{ind['id']}?confirm=true",
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        snap = client.get(
            f"/api/v1/projects/{pid}/design", headers=_auth(token)
        ).json()["data"]
        assert snap["indicators"] == []
        assert snap["evidence_plans"] == []

    def test_delete_core_contribution_without_confirm_returns_impact(self, client):
        """移除核心学科会影响项目主表 core_subject_id，需显式确认。"""
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        c = _add_contribution(client, token, pid, "sub-core", "core")

        r = client.delete(
            f"/api/v1/projects/{pid}/design/contributions/{c['id']}",
            headers=_auth(token),
        )
        assert r.status_code == 409, r.text
        impact = r.json()["data"]
        assert impact["requires_confirmation"] is True
        assert impact["will_clear_core_subject"] is True
        # 贡献仍在
        snap = client.get(
            f"/api/v1/projects/{pid}/design", headers=_auth(token)
        ).json()["data"]
        assert any(cc["id"] == c["id"] for cc in snap["contributions"])

    def test_delete_core_contribution_with_confirm_proceeds(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        c = _add_contribution(client, token, pid, "sub-core", "core")

        r = client.delete(
            f"/api/v1/projects/{pid}/design/contributions/{c['id']}?confirm=true",
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        snap = client.get(
            f"/api/v1/projects/{pid}/design", headers=_auth(token)
        ).json()["data"]
        assert all(cc["id"] != c["id"] for cc in snap["contributions"])

    def test_delete_support_contribution_without_references_proceeds(self, client):
        """无引用的支撑学科可直接删除，无需确认。"""
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        c = _add_contribution(client, token, pid, "sub-support", "support")

        r = client.delete(
            f"/api/v1/projects/{pid}/design/contributions/{c['id']}",
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text

    def test_delete_evidence_plan_without_references_proceeds(self, client):
        """证据计划无下游引用，可直接删除。"""
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        g = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, g["id"])
        plan = _add_evidence(client, token, pid, ind["id"])

        r = client.delete(
            f"/api/v1/projects/{pid}/design/evidence-plans/{plan['id']}",
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text


# ============================================================
# 6. 已有设计记录不丢失
# ============================================================
class TestDesignRecordPreservation:
    """完整设计记录在多次编辑后不丢失；聚合快照返回全部五段。"""

    def test_snapshot_returns_all_five_sections(self, client):
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_problem(client, token, pid)
        _add_contribution(client, token, pid, "sub-c", "core")
        _add_contribution(client, token, pid, "sub-s", "support")
        g = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, g["id"])
        _add_evidence(client, token, pid, ind["id"])

        snap = client.get(
            f"/api/v1/projects/{pid}/design", headers=_auth(token)
        ).json()["data"]

        # 五段固定字段全部存在
        assert snap["problem"] is not None
        assert len(snap["contributions"]) == 2
        assert len(snap["goals"]) == 1
        assert len(snap["indicators"]) == 1
        assert len(snap["evidence_plans"]) == 1

    def test_existing_design_preserved_after_unrelated_edit(self, client):
        """编辑某学科贡献不影响其他学科、目标、指标与证据计划。"""
        tag = _unique_tag()
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token)
        _add_problem(client, token, pid)
        c1 = _add_contribution(client, token, pid, "sub-c", "core")
        c2 = _add_contribution(client, token, pid, "sub-s", "support")
        g = _add_goal(client, token, pid)
        ind = _add_indicator(client, token, pid, g["id"])
        plan = _add_evidence(client, token, pid, ind["id"])

        # 编辑 c1
        client.patch(
            f"/api/v1/projects/{pid}/design/contributions/{c1['id']}",
            json={"knowledge": "新的核心知识"},
            headers=_auth(token),
        )

        snap = client.get(
            f"/api/v1/projects/{pid}/design", headers=_auth(token)
        ).json()["data"]
        # 其他记录原样保留
        assert len(snap["contributions"]) == 2
        assert any(c["id"] == c2["id"] and c["knowledge"] == c2["knowledge"] for c in snap["contributions"])
        assert any(c["id"] == c1["id"] and c["knowledge"] == "新的核心知识" for c in snap["contributions"])
        assert snap["problem"]["id"] is not None
        assert any(go["id"] == g["id"] for go in snap["goals"])
        assert any(i["id"] == ind["id"] for i in snap["indicators"])
        assert any(p["id"] == plan["id"] for p in snap["evidence_plans"])
