"""教师复核工作台测试（计划 Task 4.5 / 验收标准 2/5/6）。

覆盖：
- 验收 2：AI 建议、教师最终结论、人机差异、修改原因。
- 验收 5：复核队列规则和教师确认接口。
- 验收 6：评价状态机和提交状态机（后端部分）。

阶段验收：每条正式评价均可追溯到评价主体、指标、证据、时间和确认教师。
"""
from datetime import datetime, timezone


_counter = 0


def _setup(client):
    """构造 admin/teacher/student + 项目（关联学生班级）的测试上下文。"""
    global _counter
    _counter += 1
    tag = f"tr{_counter}"

    admin = _register(client, f"tra_{tag}", "admin")
    admin_token = _login(client, f"tra_{tag}")["access_token"]
    school = client.post(
        "/api/v1/schools",
        json={"name": f"TR School {tag}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]
    cls1 = client.post(
        f"/api/v1/schools/{school['id']}/classes",
        json={"school_id": school["id"], "grade": "七年级", "name": "1班"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]

    teacher = _register(client, f"trt_{tag}", "teacher")
    teacher_token = _login(client, f"trt_{tag}")["access_token"]
    teacher_id = teacher["id"]
    student = _register(client, f"trs1_{tag}", "student", class_id=cls1["id"])
    student_token = _login(client, f"trs1_{tag}")["access_token"]
    student_id = student["id"]

    project = client.post(
        "/api/v1/projects",
        json={"title": f"TR 项目 {tag}", "class_ids": [cls1["id"]]},
        headers={"Authorization": f"Bearer {teacher_token}"},
    ).json()["data"]
    return {
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


def _create_task(client, token, project_id, title, student_ids=None):
    payload = {"project_id": project_id, "title": title, "student_ids": student_ids or []}
    r = client.post("/api/v1/tasks", json=payload, headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _create_submission(client, student_token, task_id, content="学生提交内容"):
    r = client.post(
        "/api/v1/submissions",
        json={"task_id": task_id, "content": content},
        headers=_headers(student_token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _create_record(client, token, project_id, student_id, evaluator_id, task_id,
                   rubric_id=None, source="teacher"):
    body = {
        "project_id": project_id,
        "student_id": student_id,
        "evaluator_id": evaluator_id,
        "task_id": task_id,
        "subject_type": "task",
        "subject_id": task_id,
        "source": source,
    }
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


def _transition_submission(client, token, submission_id, target):
    return client.post(
        f"/api/v1/evaluation-plans/submissions/{submission_id}/transition",
        json={"target": target},
        headers=_headers(token),
    )


def _add_score(client, token, record_id, criterion_id, suggested_score=None,
               final_score=None, ai_confidence=None, difference_reason=None,
               evidence_ref=None):
    body = {
        "record_id": record_id,
        "criterion_id": criterion_id,
    }
    if suggested_score is not None:
        body["suggested_score"] = suggested_score
    if final_score is not None:
        body["final_score"] = final_score
    if ai_confidence is not None:
        body["ai_confidence"] = ai_confidence
    if difference_reason:
        body["difference_reason"] = difference_reason
    if evidence_ref:
        body["evidence_ref"] = evidence_ref
    return client.post(
        "/api/v1/evaluation-plans/scores",
        json=body,
        headers=_headers(token),
    )


def _update_score(client, token, score_id, final_score=None, difference_reason=None):
    body = {}
    if final_score is not None:
        body["final_score"] = final_score
    if difference_reason:
        body["difference_reason"] = difference_reason
    return client.put(
        f"/api/v1/evaluation-plans/scores/{score_id}",
        json=body,
        headers=_headers(token),
    )


def _get_review_queue(client, token, project_id, task_id=None):
    qs = f"project_id={project_id}"
    if task_id:
        qs += f"&task_id={task_id}"
    return client.get(
        f"/api/v1/evaluation-plans/review-queue?{qs}",
        headers=_headers(token),
    )


def _confirm_review(client, token, submission_id, scores, total_score=None,
                    comment=None, difference_reason=None):
    body = {"scores": scores}
    if total_score is not None:
        body["total_score"] = total_score
    if comment:
        body["comment"] = comment
    if difference_reason:
        body["difference_reason"] = difference_reason
    return client.post(
        f"/api/v1/evaluation-plans/review-queue/{submission_id}/confirm",
        json=body,
        headers=_headers(token),
    )


def _create_rubric(client, token, project_id, created_by):
    r = client.post(
        "/api/v1/evaluation-plans/rubrics",
        json={"project_id": project_id, "created_by": created_by},
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _add_criterion(client, token, rubric_id, dimension="维度", weight=1.0, levels=None):
    body = {"rubric_id": rubric_id, "dimension": dimension, "weight": weight, "ai_weight": 0.0}
    if levels:
        body["levels"] = levels
    r = client.post(
        "/api/v1/evaluation-plans/criteria",
        json=body,
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _publish_record(client, token, record_id):
    """辅助：将记录从 draft 迁移到 published。"""
    _transition_record(client, token, record_id, "collecting_evidence")
    _transition_record(client, token, record_id, "pending_teacher_confirmation")
    _transition_record(client, token, record_id, "confirmed")
    return _transition_record(client, token, record_id, "published")


# ── 评价状态机 ───────────────────────────────────────────────
class TestEvaluationStateMachine:
    def test_legal_transitions_full_lifecycle(self, client):
        """draft -> collecting_evidence -> pending_teacher_confirmation
        -> confirmed -> published -> finalized 全链路。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"])

        r = _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "collecting_evidence"

        r = _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "pending_teacher_confirmation"

        r = _transition_record(client, ctx["teacher_token"], record["id"], "confirmed")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "confirmed"

        r = _transition_record(client, ctx["teacher_token"], record["id"], "published")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "published"

        r = _transition_record(client, ctx["teacher_token"], record["id"], "finalized")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "finalized"

    def test_appeal_and_recheck_path(self, client):
        """published -> appealed -> rechecked -> finalized 申诉复核路径。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"])
        _publish_record(client, ctx["teacher_token"], record["id"])

        r = _transition_record(client, ctx["teacher_token"], record["id"], "appealed")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "appealed"

        r = _transition_record(client, ctx["teacher_token"], record["id"], "rechecked")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "rechecked"

        r = _transition_record(client, ctx["teacher_token"], record["id"], "finalized")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "finalized"

    def test_illegal_transition_rejected(self, client):
        """draft -> published 非法跃迁返回 409。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"])
        r = _transition_record(client, ctx["teacher_token"], record["id"], "published")
        assert r.status_code == 409

    def test_finalized_is_terminal(self, client):
        """finalized 是终态，不可再迁移。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"])
        _publish_record(client, ctx["teacher_token"], record["id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "finalized")
        r = _transition_record(client, ctx["teacher_token"], record["id"], "published")
        assert r.status_code == 409

    def test_invalid_target_rejected(self, client):
        """无效状态值返回 400。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"])
        r = _transition_record(client, ctx["teacher_token"], record["id"], "bogus_status")
        assert r.status_code == 400

    def test_confirmed_sets_confirmed_by_and_at(self, client):
        """确认时记录 confirmed_by 和 confirmed_at。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        r = _transition_record(client, ctx["teacher_token"], record["id"], "confirmed")
        data = r.json()["data"]
        assert data["confirmed_by"] == ctx["teacher_id"]
        assert data["confirmed_at"] is not None

    def test_published_sets_published_at(self, client):
        """发布时记录 published_at。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_record(client, ctx["teacher_token"], record["id"], "confirmed")
        r = _transition_record(client, ctx["teacher_token"], record["id"], "published")
        assert r.json()["data"]["published_at"] is not None

    def test_pending_can_back_to_collecting(self, client):
        """pending_teacher_confirmation -> collecting_evidence 允许（补充证据）。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        r = _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "collecting_evidence"


# ── 提交状态机 ───────────────────────────────────────────────
class TestSubmissionStateMachine:
    def test_legal_transitions_full_lifecycle(self, client):
        """submitted -> ai_reviewed -> teacher_reviewed -> finalized 全链路。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        assert sub["status"] == "submitted"

        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        assert r.status_code == 200
        assert r.json()["data"]["review_status"] == "ai_reviewed"

        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")
        assert r.status_code == 200
        assert r.json()["data"]["review_status"] == "teacher_reviewed"

        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "finalized")
        assert r.status_code == 200
        assert r.json()["data"]["review_status"] == "finalized"

    def test_return_and_resubmit_path(self, client):
        """teacher_reviewed -> returned -> resubmitted -> ai_reviewed 退回重提路径。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")

        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "returned")
        assert r.status_code == 200
        assert r.json()["data"]["review_status"] == "returned"

        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "resubmitted")
        assert r.status_code == 200
        assert r.json()["data"]["review_status"] == "resubmitted"

        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        assert r.status_code == 200

    def test_illegal_transition_rejected(self, client):
        """submitted -> finalized 非法跃迁返回 409。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "finalized")
        assert r.status_code == 409

    def test_finalized_is_terminal(self, client):
        """finalized 是终态。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "finalized")
        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")
        assert r.status_code == 409

    def test_invalid_target_rejected(self, client):
        """无效状态值返回 400。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "bogus")
        assert r.status_code == 400

    def test_transition_mirrors_to_status_field(self, client):
        """迁移后旧 status 字段镜像 review_status。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        r = _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        data = r.json()["data"]
        assert data["review_status"] == "ai_reviewed"
        assert data["status"] == "ai_reviewed"


# ── 分维度评分：AI 建议 / 教师最终 / 人机差异 ─────────────────
class TestEvaluationScore:
    def test_add_score_with_ai_suggestion_same_as_final(self, client):
        """验收 2：AI 建议分数与教师最终一致，无需差异原因。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        r = _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                       suggested_score=80, final_score=80, ai_confidence=0.9)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["suggested_score"] == 80
        assert data["final_score"] == 80
        assert data["ai_confidence"] == 0.9

    def test_add_score_difference_requires_reason(self, client):
        """验收 2：教师修改 AI 建议分数必须填写差异原因（400）。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        r = _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                       suggested_score=80, final_score=70)
        assert r.status_code == 400
        assert "差异原因" in r.json()["message"]

    def test_add_score_difference_with_reason(self, client):
        """验收 2：填写差异原因后可保存。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        r = _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                       suggested_score=80, final_score=70,
                       difference_reason="学生引用了额外证据，应加分")
        assert r.status_code == 200
        assert r.json()["data"]["difference_reason"] == "学生引用了额外证据，应加分"

    def test_update_score_difference_requires_reason(self, client):
        """更新评分时，若 final 与已有 suggested 差异 > 0.01，必须填差异原因。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        # 先创建 AI 建议分数（suggested=80, final=80）
        score = _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                           suggested_score=80, final_score=80).json()["data"]
        # 更新 final=60 且无差异原因 → 400
        r = _update_score(client, ctx["teacher_token"], score["id"], final_score=60)
        assert r.status_code == 400
        assert "差异原因" in r.json()["message"]

    def test_update_score_difference_with_reason(self, client):
        """更新评分时，填写差异原因可保存。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        score = _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                           suggested_score=80, final_score=80).json()["data"]
        r = _update_score(client, ctx["teacher_token"], score["id"], final_score=60,
                          difference_reason="教师复核后发现抄袭")
        assert r.status_code == 200
        assert r.json()["data"]["final_score"] == 60
        assert r.json()["data"]["difference_reason"] == "教师复核后发现抄袭"

    def test_list_scores_by_record(self, client):
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务")
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        c1 = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度1")
        c2 = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度2")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _add_score(client, ctx["teacher_token"], record["id"], c1["id"],
                   suggested_score=80, final_score=80)
        _add_score(client, ctx["teacher_token"], record["id"], c2["id"],
                   suggested_score=70, final_score=70)
        r = client.get(
            f"/api/v1/evaluation-plans/scores?record_id={record['id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2


# ── 复核队列 ─────────────────────────────────────────────────
class TestReviewQueue:
    def test_low_confidence_in_queue(self, client):
        """验收 5：低置信度（ai_confidence < 0.6）入队。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                   suggested_score=80, final_score=80, ai_confidence=0.3)
        r = _get_review_queue(client, ctx["teacher_token"], ctx["project_id"])
        items = r.json()["data"]
        assert len(items) == 1
        assert "低置信度" in items[0]["reasons"]
        assert items[0]["ai_confidence"] == 0.3

    def test_boundary_score_in_queue(self, client):
        """验收 5：边界分（60±5）入队。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                   suggested_score=60, final_score=60, ai_confidence=0.9)
        # 设置总分到边界范围
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_record(client, ctx["teacher_token"], record["id"], "confirmed")
        # 通过 confirm 设置 total_score
        _confirm_review(client, ctx["teacher_token"], sub["id"],
                        scores=[{"criterion_id": criterion["id"], "final_score": 60,
                                 "difference_reason": "边界分确认"}],
                        total_score=62)
        r = _get_review_queue(client, ctx["teacher_token"], ctx["project_id"])
        items = r.json()["data"]
        assert len(items) == 1
        assert "边界分" in items[0]["reasons"]
        assert items[0]["total_score"] == 62

    def test_rule_conflict_in_queue(self, client):
        """验收 5：规则冲突（suggested vs final 差异 > 10）入队。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        # suggested=80, final=60, diff=20 > 10
        _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                   suggested_score=80, final_score=60, ai_confidence=0.9,
                   difference_reason="差异原因")
        r = _get_review_queue(client, ctx["teacher_token"], ctx["project_id"])
        items = r.json()["data"]
        assert len(items) == 1
        assert "规则冲突" in items[0]["reasons"]

    def test_appealed_in_queue(self, client):
        """验收 5：学生申诉（record.status == APPEALED）入队。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                   suggested_score=80, final_score=80, ai_confidence=0.9)
        # 迁移到 published 再到 appealed
        _publish_record(client, ctx["teacher_token"], record["id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "appealed")
        r = _get_review_queue(client, ctx["teacher_token"], ctx["project_id"])
        items = r.json()["data"]
        assert len(items) == 1
        assert "学生申诉" in items[0]["reasons"]

    def test_finalized_submission_not_in_queue(self, client):
        """已 finalized 的提交不入队。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                   suggested_score=80, final_score=80, ai_confidence=0.3)
        # 将提交迁移到 finalized
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "finalized")
        r = _get_review_queue(client, ctx["teacher_token"], ctx["project_id"])
        items = r.json()["data"]
        assert len(items) == 0

    def test_empty_queue_when_no_issues(self, client):
        """无问题时队列为空。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        r = _get_review_queue(client, ctx["teacher_token"], ctx["project_id"])
        assert r.status_code == 200
        assert r.json()["data"] == []


# ── 教师确认复核 ─────────────────────────────────────────────
class TestReviewConfirm:
    def test_confirm_writes_final_scores(self, client):
        """验收 5：教师确认写入分维度最终分数。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        c1 = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度1")
        c2 = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度2")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        # 迁移记录到 pending_teacher_confirmation
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        # 将提交迁移到 teacher_reviewed
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")

        r = _confirm_review(client, ctx["teacher_token"], sub["id"],
                            scores=[
                                {"criterion_id": c1["id"], "final_score": 85, "evidence_ref": "证据1"},
                                {"criterion_id": c2["id"], "final_score": 75, "evidence_ref": "证据2"},
                            ],
                            total_score=80, comment="教师确认")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["record"]["total_score"] == 80
        assert data["record"]["comment"] == "教师确认"
        # 验证分维度分数已写入
        scores = client.get(
            f"/api/v1/evaluation-plans/scores?record_id={record['id']}",
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        assert len(scores) == 2

    def test_confirm_requires_difference_reason(self, client):
        """验收 2/5：教师修改 AI 分数时必须填差异原因（400）。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        # 先添加 AI 建议分数（suggested=80）
        _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                   suggested_score=80, final_score=None, ai_confidence=0.9)
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")
        # 教师确认时 final=60，差异 > 0.01，无差异原因 → 400
        r = _confirm_review(client, ctx["teacher_token"], sub["id"],
                            scores=[{"criterion_id": criterion["id"], "final_score": 60}],
                            total_score=60)
        assert r.status_code == 400
        assert "差异原因" in r.json()["message"]

    def test_confirm_transitions_submission_to_finalized(self, client):
        """验收 5：教师确认后提交转为 finalized。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")

        r = _confirm_review(client, ctx["teacher_token"], sub["id"],
                            scores=[{"criterion_id": criterion["id"], "final_score": 80}],
                            total_score=80)
        assert r.status_code == 200
        assert r.json()["data"]["review_status"] == "finalized"

    def test_confirm_transitions_record_to_confirmed(self, client):
        """验收 5：教师确认后评价记录转为 confirmed。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")

        r = _confirm_review(client, ctx["teacher_token"], sub["id"],
                            scores=[{"criterion_id": criterion["id"], "final_score": 80}],
                            total_score=80)
        data = r.json()["data"]
        assert data["record"]["status"] == "confirmed"
        assert data["record"]["confirmed_by"] == ctx["teacher_id"]
        assert data["record"]["confirmed_at"] is not None

    def test_confirm_with_difference_reason(self, client):
        """验收 2：教师确认时填写差异原因，可成功修改 AI 分数。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _add_score(client, ctx["teacher_token"], record["id"], criterion["id"],
                   suggested_score=80, final_score=None, ai_confidence=0.9)
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")

        r = _confirm_review(client, ctx["teacher_token"], sub["id"],
                            scores=[{"criterion_id": criterion["id"], "final_score": 65,
                                     "difference_reason": "学生补充了证据"}],
                            total_score=65)
        assert r.status_code == 200
        # 验证差异原因已记录
        scores = client.get(
            f"/api/v1/evaluation-plans/scores?record_id={record['id']}",
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        assert any(s["difference_reason"] == "学生补充了证据" for s in scores)

    def test_traceability_confirmed_by_and_at(self, client):
        """阶段验收：每条正式评价可追溯到确认教师和时间。"""
        ctx = _setup(client)
        task = _create_task(client, ctx["teacher_token"], ctx["project_id"], "任务",
                            student_ids=[ctx["student_id"]])
        sub = _create_submission(client, ctx["student_token"], task["id"])
        rubric = _create_rubric(client, ctx["teacher_token"], ctx["project_id"], ctx["teacher_id"])
        criterion = _add_criterion(client, ctx["teacher_token"], rubric["id"], "维度")
        record = _create_record(client, ctx["teacher_token"], ctx["project_id"],
                                ctx["student_id"], ctx["teacher_id"], task["id"],
                                rubric_id=rubric["id"])
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "ai_reviewed")
        _transition_submission(client, ctx["teacher_token"], sub["id"], "teacher_reviewed")
        _confirm_review(client, ctx["teacher_token"], sub["id"],
                        scores=[{"criterion_id": criterion["id"], "final_score": 85}],
                        total_score=85, comment="可追溯")
        # 获取记录详情，验证追溯信息
        r = client.get(
            f"/api/v1/evaluation-plans/records/{record['id']}",
            headers=_headers(ctx["teacher_token"]),
        )
        data = r.json()["data"]
        assert data["evaluator_id"] == ctx["teacher_id"]
        assert data["confirmed_by"] == ctx["teacher_id"]
        assert data["confirmed_at"] is not None
        assert data["task_id"] == task["id"]
        assert data["student_id"] == ctx["student_id"]
        assert data["rubric_id"] == rubric["id"]
        assert data["total_score"] == 85
