"""评价计划领域测试（计划 Task 4.5 / 验收标准 1/3/4/7）。

覆盖：
- 验收 1：量规版本、权重、缺失证据、AI 默认零权重。
- 验收 3：学生不可见未发布评价、不可见他人评价。
- 验收 4：模型实现（量规、证据计划、评价记录、维度分数）。
- 验收 7：历史简单评价仍可读取，并显示为"旧版评价记录"。
"""
from datetime import datetime, timezone


_counter = 0


def _setup(client):
    """构造 admin/teacher/student + 项目（关联学生班级）的测试上下文。"""
    global _counter
    _counter += 1
    tag = f"ep{_counter}"

    admin = _register(client, f"epa_{tag}", "admin")
    admin_token = _login(client, f"epa_{tag}")["access_token"]
    school = client.post(
        "/api/v1/schools",
        json={"name": f"EP School {tag}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]
    cls1 = client.post(
        f"/api/v1/schools/{school['id']}/classes",
        json={"school_id": school["id"], "grade": "七年级", "name": "1班"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]

    teacher = _register(client, f"ept_{tag}", "teacher")
    teacher_token = _login(client, f"ept_{tag}")["access_token"]
    teacher_id = teacher["id"]
    student = _register(client, f"eps1_{tag}", "student", class_id=cls1["id"])
    student_token = _login(client, f"eps1_{tag}")["access_token"]
    student_id = student["id"]

    project = client.post(
        "/api/v1/projects",
        json={"title": f"EP 项目 {tag}", "class_ids": [cls1["id"]]},
        headers={"Authorization": f"Bearer {teacher_token}"},
    ).json()["data"]
    return {
        "admin_token": admin_token,
        "teacher_token": teacher_token,
        "teacher_id": teacher_id,
        "student_token": student_token,
        "student_id": student_id,
        "class_id": cls1["id"],
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


# ── 项目设计辅助：创建目标/指标/证据计划 ──────────────────────
def _add_goal(client, token, project_id, name="目标", goal_type="ability"):
    r = client.post(
        f"/api/v1/projects/{project_id}/design/goals",
        json={"goal_type": goal_type, "name": name},
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_indicator(client, token, project_id, goal_id, behavior="可观察行为"):
    r = client.post(
        f"/api/v1/projects/{project_id}/design/indicators",
        json={"goal_id": goal_id, "observable_behavior": behavior},
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_evidence_plan(client, token, project_id, indicator_id, required=True,
                       stage="in_class", evidence_type="artifact", collector="student"):
    r = client.post(
        f"/api/v1/projects/{project_id}/design/evidence-plans",
        json={
            "indicator_id": indicator_id,
            "stage": stage,
            "evidence_type": evidence_type,
            "collector": collector,
            "required": required,
        },
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ── 评价计划辅助 ──────────────────────────────────────────────
def _create_rubric(client, token, project_id, created_by):
    r = client.post(
        "/api/v1/evaluation-plans/rubrics",
        json={"project_id": project_id, "created_by": created_by},
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_criterion(client, token, rubric_id, dimension="维度", weight=0.5,
                   ai_weight=0.0, indicator_id=None, levels=None):
    body = {
        "rubric_id": rubric_id,
        "dimension": dimension,
        "weight": weight,
        "ai_weight": ai_weight,
    }
    if indicator_id:
        body["indicator_id"] = indicator_id
    if levels is not None:
        body["levels"] = levels
    r = client.post(
        "/api/v1/evaluation-plans/criteria",
        json=body,
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _publish_rubric(client, token, rubric_id):
    return client.post(
        f"/api/v1/evaluation-plans/rubrics/{rubric_id}/publish",
        headers=_headers(token),
    )


def _archive_rubric(client, token, rubric_id):
    return client.post(
        f"/api/v1/evaluation-plans/rubrics/{rubric_id}/archive",
        headers=_headers(token),
    )


def _add_artifact(client, token, project_id, indicator_id, collected_by,
                  source_type="observation", content_ref="观察记录",
                  submission_id=None, plan_id=None):
    body = {
        "project_id": project_id,
        "indicator_id": indicator_id,
        "source_type": source_type,
        "content_ref": content_ref,
        "collected_by": collected_by,
    }
    if submission_id:
        body["submission_id"] = submission_id
    if plan_id:
        body["plan_id"] = plan_id
    r = client.post(
        "/api/v1/evaluation-plans/artifacts",
        json=body,
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _create_record(client, token, project_id, student_id, evaluator_id,
                   task_id=None, subject_type="project", subject_id=None,
                   source="teacher", rubric_id=None):
    body = {
        "project_id": project_id,
        "student_id": student_id,
        "evaluator_id": evaluator_id,
        "subject_type": subject_type,
        "subject_id": subject_id or project_id,
        "source": source,
    }
    if task_id:
        body["task_id"] = task_id
    if rubric_id:
        body["rubric_id"] = rubric_id
    r = client.post(
        "/api/v1/evaluation-plans/records",
        json=body,
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _transition_record(client, token, record_id, target):
    return client.post(
        f"/api/v1/evaluation-plans/records/{record_id}/transition",
        json={"target": target},
        headers=_headers(token),
    )


def _validate(client, token, project_id):
    return client.get(
        f"/api/v1/evaluation-plans/validate?project_id={project_id}",
        headers=_headers(token),
    )


def _get_snapshot(client, token, project_id):
    return client.get(
        f"/api/v1/evaluation-plans/snapshot?project_id={project_id}",
        headers=_headers(token),
    )


def _list_records(client, token, project_id, **kwargs):
    qs = f"project_id={project_id}"
    for k, v in kwargs.items():
        if v:
            qs += f"&{k}={v}"
    return client.get(
        f"/api/v1/evaluation-plans/records?{qs}",
        headers=_headers(token),
    )


def _get_record(client, token, record_id):
    return client.get(
        f"/api/v1/evaluation-plans/records/{record_id}",
        headers=_headers(token),
    )


# ── 量规版本管理 ─────────────────────────────────────────────
class TestRubricVersionManagement:
    def test_create_first_rubric(self, client):
        ctx = _setup(client)
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        assert rubric["version"] == 1
        assert rubric["is_current"] is True
        assert rubric["status"] == "draft"

    def test_create_second_version_marks_old_non_current(self, client):
        ctx = _setup(client)
        r1 = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                            ctx["teacher_id"])
        r2 = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                            ctx["teacher_id"])
        assert r2["version"] == 2
        assert r2["is_current"] is True
        # 旧版本被标记为非当前（通过快照查询）
        snap = _get_snapshot(client, ctx["teacher_token"], ctx["project_id"])
        assert snap.json()["data"]["rubric"]["id"] == r2["id"]

    def test_publish_rubric_blocked_without_indicators(self, client):
        """无指标时发布被阻断，返回 blockers。"""
        ctx = _setup(client)
        # 创建目标但不创建指标
        _add_goal(client, ctx["teacher_token"], ctx["project_id"], "无指标目标")
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        r = _publish_rubric(client, ctx["teacher_token"], rubric["id"])
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data["blockers"]) > 0
        assert any("未拆解" in b for b in data["blockers"])
        # 状态保持 draft
        assert data["rubric"]["status"] == "draft"

    def test_publish_rubric_success(self, client):
        """完整设计时发布成功。"""
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度1",
                       weight=1.0, ai_weight=0.0,
                       levels=[{"level": "优秀", "score": 90, "description": "描述清晰"}])
        r = _publish_rubric(client, ctx["teacher_token"], rubric["id"])
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["blockers"] == []
        assert data["rubric"]["status"] == "published"

    def test_archive_rubric_only_published(self, client):
        """draft 状态归档返回 409。"""
        ctx = _setup(client)
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        r = _archive_rubric(client, ctx["teacher_token"], rubric["id"])
        assert r.status_code == 409

    def test_archive_rubric_success(self, client):
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        _publish_rubric(client, ctx["teacher_token"], rubric["id"])
        r = _archive_rubric(client, ctx["teacher_token"], rubric["id"])
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "archived"


# ── 量规维度 CRUD ────────────────────────────────────────────
class TestRubricCriterionCRUD:
    def test_add_criterion_default_ai_weight_zero(self, client):
        """验收 1：AI 默认权重为零。"""
        ctx = _setup(client)
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        c = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度",
                           weight=0.5)
        assert c["ai_weight"] == 0.0
        assert c["weight"] == 0.5

    def test_add_criterion_with_levels(self, client):
        ctx = _setup(client)
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        levels = [
            {"level": "优秀", "score": 90, "description": "超出预期"},
            {"level": "合格", "score": 60, "description": "达到基本要求"},
        ]
        c = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度",
                           levels=levels)
        assert len(c["levels"]) == 2
        assert c["levels"][0]["description"] == "超出预期"

    def test_update_criterion(self, client):
        ctx = _setup(client)
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        c = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度",
                           weight=0.5)
        r = client.put(
            f"/api/v1/evaluation-plans/criteria/{c['id']}",
            json={"weight": 0.8},
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 200
        assert r.json()["data"]["weight"] == 0.8

    def test_remove_criterion(self, client):
        ctx = _setup(client)
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        c = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        r = client.delete(
            f"/api/v1/evaluation-plans/criteria/{c['id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 200
        # 列表为空
        r = client.get(
            f"/api/v1/evaluation-plans/criteria?rubric_id={rubric['id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.json()["data"] == []

    def test_modify_criterion_after_publish_returns_409(self, client):
        """验收：发布后不可修改维度，需新建版本。"""
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        c = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度",
                           weight=1.0,
                           levels=[{"level": "合格", "score": 60, "description": "达到要求"}])
        _publish_rubric(client, ctx["teacher_token"], rubric["id"])
        # 发布后修改 → 409
        r = client.put(
            f"/api/v1/evaluation-plans/criteria/{c['id']}",
            json={"weight": 0.5},
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 409
        # 发布后删除 → 409
        r = client.delete(
            f"/api/v1/evaluation-plans/criteria/{c['id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 409
        # 发布后新增 → 409
        r = client.post(
            "/api/v1/evaluation-plans/criteria",
            json={"rubric_id": rubric["id"], "dimension": "新维度", "weight": 0.5},
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 409

    def test_new_version_allows_modification(self, client):
        """新建版本后可修改维度。"""
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        r1 = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                            ctx["teacher_id"])
        _add_criterion(client, ctx["teacher_token"], r1["id"], "维度1", weight=1.0,
                       levels=[{"level": "合格", "score": 60, "description": "达到要求"}])
        _publish_rubric(client, ctx["teacher_token"], r1["id"])
        # 新建版本
        r2 = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                            ctx["teacher_id"])
        assert r2["version"] == 2
        # 新版本可添加维度
        c = _add_criterion(client, ctx["teacher_token"], r2["id"], "新维度", weight=1.0)
        assert c["dimension"] == "新维度"


# ── 评价计划完整性校验 ───────────────────────────────────────
class TestEvaluationPlanValidation:
    def test_ai_weight_nonzero_blocks_publish(self, client):
        """验收 1：AI 权重非零阻断发布。"""
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        indicator = _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度", weight=1.0,
                       ai_weight=0.3, indicator_id=indicator["id"],
                       levels=[{"level": "合格", "score": 60, "description": "达到要求"}])
        r = _validate(client, ctx["teacher_token"], ctx["project_id"])
        data = r.json()["data"]
        assert data["ai_weight_nonzero"] is True
        assert data["ready"] is False
        assert any("AI 权重" in b for b in data["blockers"])

    def test_goal_without_indicator_blocks_publish(self, client):
        """验收 1：抽象目标未拆成可观察指标时禁止发布。"""
        ctx = _setup(client)
        _add_goal(client, ctx["teacher_token"], ctx["project_id"], "无指标目标")
        r = _validate(client, ctx["teacher_token"], ctx["project_id"])
        data = r.json()["data"]
        assert len(data["goals_without_indicators"]) > 0
        assert data["ready"] is False
        assert any("未拆解" in b for b in data["blockers"])

    def test_criterion_level_empty_description_blocks(self, client):
        """验收 1：量规等级必须有可观察描述。"""
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度", weight=1.0,
                       levels=[{"level": "合格", "score": 60, "description": ""}])
        r = _validate(client, ctx["teacher_token"], ctx["project_id"])
        data = r.json()["data"]
        assert len(data["criteria_without_level_description"]) > 0
        assert data["ready"] is False
        assert any("等级描述" in b for b in data["blockers"])

    def test_missing_required_evidence_returns_warning(self, client):
        """验收 1：缺失证据显示"未采集"（warning，不阻断）。"""
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        indicator = _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        _add_evidence_plan(client, ctx["teacher_token"], ctx["project_id"],
                           indicator["id"], required=True)
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度", weight=1.0,
                       indicator_id=indicator["id"],
                       levels=[{"level": "合格", "score": 60, "description": "达到要求"}])
        r = _validate(client, ctx["teacher_token"], ctx["project_id"])
        data = r.json()["data"]
        # 缺失证据是 warning，不阻断
        assert data["ready"] is True
        assert len(data["missing_required_evidence"]) > 0
        assert any("未采集" in w for w in data["warnings"])

    def test_validation_ready_when_all_complete(self, client):
        """全部满足时 ready=True。"""
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        indicator = _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        _add_evidence_plan(client, ctx["teacher_token"], ctx["project_id"],
                           indicator["id"], required=True)
        # 采集证据
        _add_artifact(client, ctx["teacher_token"], ctx["project_id"],
                      indicator["id"], ctx["teacher_id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度", weight=1.0,
                       ai_weight=0.0, indicator_id=indicator["id"],
                       levels=[{"level": "合格", "score": 60, "description": "达到要求"}])
        r = _validate(client, ctx["teacher_token"], ctx["project_id"])
        data = r.json()["data"]
        assert data["ready"] is True
        assert data["blockers"] == []
        assert data["ai_weight_nonzero"] is False
        assert data["goals_without_indicators"] == []
        assert data["criteria_without_level_description"] == []

    def test_snapshot_aggregates_all_data(self, client):
        """验收 4：快照聚合量规/维度/目标/指标/证据计划/证据/校验结果。"""
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        indicator = _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        _add_evidence_plan(client, ctx["teacher_token"], ctx["project_id"],
                           indicator["id"], required=True)
        _add_artifact(client, ctx["teacher_token"], ctx["project_id"],
                      indicator["id"], ctx["teacher_id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["teacher_id"])
        _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度", weight=1.0,
                       indicator_id=indicator["id"])
        r = _get_snapshot(client, ctx["teacher_token"], ctx["project_id"])
        data = r.json()["data"]
        assert data["rubric"]["id"] == rubric["id"]
        assert len(data["criteria"]) == 1
        assert len(data["goals"]) == 1
        assert len(data["indicators"]) == 1
        assert len(data["evidence_plans"]) == 1
        assert len(data["evidence_artifacts"]) == 1
        assert "validation" in data


# ── 证据 ─────────────────────────────────────────────────────
class TestEvidenceArtifact:
    def test_add_artifact(self, client):
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        indicator = _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"])
        a = _add_artifact(client, ctx["teacher_token"], ctx["project_id"],
                          indicator["id"], ctx["teacher_id"],
                          source_type="observation", content_ref="课堂观察记录")
        assert a["source_type"] == "observation"
        assert a["content_ref"] == "课堂观察记录"
        assert a["collected_by"] == ctx["teacher_id"]

    def test_list_artifacts(self, client):
        ctx = _setup(client)
        goal = _add_goal(client, ctx["teacher_token"], ctx["project_id"], "目标1")
        i1 = _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"], "行为1")
        i2 = _add_indicator(client, ctx["teacher_token"], ctx["project_id"], goal["id"], "行为2")
        _add_artifact(client, ctx["teacher_token"], ctx["project_id"],
                      i1["id"], ctx["teacher_id"], content_ref="证据1")
        _add_artifact(client, ctx["teacher_token"], ctx["project_id"],
                      i2["id"], ctx["teacher_id"], content_ref="证据2")
        r = client.get(
            f"/api/v1/evaluation-plans/artifacts?project_id={ctx['project_id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 200
        items = r.json()["data"]
        assert len(items) == 2


# ── 旧版评价兼容 ─────────────────────────────────────────────
class TestLegacyEvaluation:
    def test_legacy_evaluation_is_legacy_flag(self, client, db_session):
        """验收 7：旧版评价标记 is_legacy=True（数据通过 DB 直接播种，绕过已弃用写入入口）。"""
        from app.models.evaluation import Evaluation
        ctx = _setup(client)
        # 创建任务
        task = client.post(
            "/api/v1/tasks",
            json={"project_id": ctx["project_id"], "title": "旧版任务",
                  "student_ids": [ctx["student_id"]]},
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        # 直接构造旧版评价记录（POST /evaluations 已弃用为只读）
        db_session.add(Evaluation(
            task_id=task["id"],
            student_id=ctx["student_id"],
            evaluator_id=ctx["teacher_id"],
            score=85,
            comment="旧版评价",
            eval_type="teacher",
            is_legacy=True,
        ))
        db_session.commit()
        # 通过旧版评价列表接口读取，标记 is_legacy
        r = client.get(
            f"/api/v1/evaluation-plans/legacy?task_id={task['id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 200
        items = r.json()["data"]
        assert len(items) == 1
        assert items[0]["is_legacy"] is True
        assert items[0]["score"] == 85
        assert items[0]["eval_type"] == "teacher"

    def test_legacy_evaluation_student_can_read_own(self, client, db_session):
        """验收 7：学生可读取自己的旧版评价（数据通过 DB 直接播种）。"""
        from app.models.evaluation import Evaluation
        ctx = _setup(client)
        task = client.post(
            "/api/v1/tasks",
            json={"project_id": ctx["project_id"], "title": "旧版任务",
                  "student_ids": [ctx["student_id"]]},
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        db_session.add(Evaluation(
            task_id=task["id"],
            student_id=ctx["student_id"],
            evaluator_id=ctx["teacher_id"],
            score=90,
            eval_type="teacher",
            is_legacy=True,
        ))
        db_session.commit()
        # 学生通过旧版评价列表接口读取
        r = client.get(
            f"/api/v1/evaluation-plans/legacy?task_id={task['id']}",
            headers=_headers(ctx["student_token"]),
        )
        assert r.status_code == 200
        items = r.json()["data"]
        assert len(items) == 1
        assert items[0]["is_legacy"] is True


# ── 学生评价权限 ─────────────────────────────────────────────
class TestStudentEvaluationPermissions:
    def test_student_cannot_see_unpublished_record(self, client):
        """验收 3：学生不可见未发布评价。"""
        ctx = _setup(client)
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"])
        # 状态为 draft，学生不可见
        r = _get_record(client, ctx["student_token"], record["id"])
        assert r.status_code == 403

    def test_student_can_see_published_record(self, client):
        """学生可见已发布评价。"""
        ctx = _setup(client)
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"])
        # 迁移到 published
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_record(client, ctx["teacher_token"], record["id"], "confirmed")
        _transition_record(client, ctx["teacher_token"], record["id"], "published")
        r = _get_record(client, ctx["student_token"], record["id"])
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "published"

    def test_student_cannot_see_others_record(self, client):
        """验收 3：学生不可见他人评价。"""
        ctx = _setup(client)
        # 创建第二个学生（同班级）
        student2 = _register(client, f"eps2_{_counter}", "student", class_id=ctx["class_id"])
        # 为 student2 创建并发布评价
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                student2["id"], ctx["teacher_id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_record(client, ctx["teacher_token"], record["id"], "confirmed")
        _transition_record(client, ctx["teacher_token"], record["id"], "published")
        # student1 试图读取 student2 的评价 → 403
        r = _get_record(client, ctx["student_token"], record["id"])
        assert r.status_code == 403

    def test_student_list_only_own_published(self, client):
        """验收 3：学生列表仅返回自己的已发布评价。"""
        ctx = _setup(client)
        student2 = _register(client, f"eps2_{_counter}", "student", class_id=ctx["class_id"])

        # student1 的草稿评价（不可见）
        r1 = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                            ctx["student_id"], ctx["teacher_id"])
        # student1 的已发布评价（可见）
        r2 = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                            ctx["student_id"], ctx["teacher_id"])
        _transition_record(client, ctx["teacher_token"], r2["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], r2["id"], "pending_teacher_confirmation")
        _transition_record(client, ctx["teacher_token"], r2["id"], "confirmed")
        _transition_record(client, ctx["teacher_token"], r2["id"], "published")

        # student2 的已发布评价（对 student1 不可见）
        r3 = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                            student2["id"], ctx["teacher_id"])
        _transition_record(client, ctx["teacher_token"], r3["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], r3["id"], "pending_teacher_confirmation")
        _transition_record(client, ctx["teacher_token"], r3["id"], "confirmed")
        _transition_record(client, ctx["teacher_token"], r3["id"], "published")

        # student1 列表：仅看到 r2
        r = _list_records(client, ctx["student_token"], ctx["project_id"])
        assert r.status_code == 200
        items = r.json()["data"]
        assert len(items) == 1
        assert items[0]["id"] == r2["id"]
        assert items[0]["student_id"] == ctx["student_id"]

    def test_teacher_list_all_records(self, client):
        """教师/管理员可列出全部状态的评价记录。"""
        ctx = _setup(client)
        _create_record(client, ctx["teacher_token"], ctx["project_id"],
                       ctx["student_id"], ctx["teacher_id"])
        r = _list_records(client, ctx["teacher_token"], ctx["project_id"])
        items = r.json()["data"]
        assert len(items) >= 1
        # 包含 draft 状态
        assert any(item["status"] == "draft" for item in items)
