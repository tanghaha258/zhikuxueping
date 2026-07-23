"""评价权限与统一来源测试（计划 Task 2）。

覆盖：
- 旧 `/evaluations` 只读接口仍要求鉴权与跨教师隔离（数据通过 DB 直接播种，绕过已弃用写入入口）。
- 旧 `/evaluations` 写入入口已弃用（POST/PUT 返回 410）。
- 新 `EvaluationRecord` 流：AI 草稿对学生不可见；教师发布后学生在反馈视图与评价列表看到同一已发布分数/评语。
- 跨学生、跨项目访问被拒绝（403/404）。
"""
import uuid

from app.models.evaluation import Evaluation


def _register_and_login(client, username: str, role: str = "teacher") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "12345678",
            "email": f"{username}@test.com",
            "display_name": username,
            "role": role,
        },
    )
    assert response.status_code == 200
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "12345678"}
    )
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_legacy_evaluation(db_session, task_id, student_id, evaluator_id, score=90):
    """直接构造旧版评价记录（绕过已弃用的 POST /evaluations）。"""
    evaluation = Evaluation(
        task_id=task_id,
        student_id=student_id,
        evaluator_id=evaluator_id,
        score=score,
        comment="legacy comment",
        eval_type="teacher",
        is_legacy=True,
    )
    db_session.add(evaluation)
    db_session.commit()
    db_session.refresh(evaluation)
    return evaluation


# ── 旧接口只读权限 ───────────────────────────────────────────
class TestLegacyEvaluationReadOnlyPermissions:
    def test_evaluation_detail_requires_authentication(self, client, db_session):
        suffix = uuid.uuid4().hex[:8]
        owner_token = _register_and_login(client, f"evaluation_owner_{suffix}")
        project_response = client.post(
            "/api/v1/projects",
            json={"title": "Protected evaluation project"},
            headers=_headers(owner_token),
        )
        project_id = project_response.json()["data"]["id"]
        task_response = client.post(
            "/api/v1/tasks",
            json={
                "project_id": project_id,
                "title": "Protected evaluation task",
                "student_ids": [],
            },
            headers=_headers(owner_token),
        )
        task_id = task_response.json()["data"]["id"]
        _seed_legacy_evaluation(db_session, task_id, "student-1", "legacy-teacher")

        # 未鉴权访问详情 → 401
        response = client.get("/api/v1/evaluations/does-not-exist")
        assert response.status_code == 401

    def test_teacher_cannot_access_another_teachers_legacy_evaluation(
        self, client, db_session
    ):
        suffix = uuid.uuid4().hex[:8]
        owner_token = _register_and_login(client, f"evaluation_owner_{suffix}")
        other_token = _register_and_login(client, f"evaluation_other_{suffix}")
        project_response = client.post(
            "/api/v1/projects",
            json={"title": "Protected evaluation project"},
            headers=_headers(owner_token),
        )
        project_id = project_response.json()["data"]["id"]
        task_response = client.post(
            "/api/v1/tasks",
            json={
                "project_id": project_id,
                "title": "Protected evaluation task",
                "student_ids": [],
            },
            headers=_headers(owner_token),
        )
        task_id = task_response.json()["data"]["id"]
        owner_user = client.get(
            "/api/v1/auth/me", headers=_headers(owner_token)
        ).json()["data"]
        evaluation = _seed_legacy_evaluation(
            db_session, task_id, "student-1", owner_user["id"]
        )

        headers = _headers(other_token)
        responses = [
            client.get(f"/api/v1/evaluations/task/{task_id}", headers=headers),
            client.get(f"/api/v1/evaluations/{evaluation.id}", headers=headers),
        ]
        # 跨教师读取旧版评价 → 403
        assert [r.status_code for r in responses] == [403, 403]


# ── 旧接口写入弃用 ───────────────────────────────────────────
class TestLegacyWriteDeprecated:
    def test_post_evaluations_returns_410(self, client, db_session):
        suffix = uuid.uuid4().hex[:8]
        owner_token = _register_and_login(client, f"dep_owner_{suffix}")
        project_response = client.post(
            "/api/v1/projects",
            json={"title": "Dep project"},
            headers=_headers(owner_token),
        )
        project_id = project_response.json()["data"]["id"]
        task_response = client.post(
            "/api/v1/tasks",
            json={
                "project_id": project_id,
                "title": "Dep task",
                "student_ids": [],
            },
            headers=_headers(owner_token),
        )
        task_id = task_response.json()["data"]["id"]
        response = client.post(
            "/api/v1/evaluations",
            json={
                "task_id": task_id,
                "student_id": "student-1",
                "score": 90,
                "eval_type": "teacher",
            },
            headers=_headers(owner_token),
        )
        assert response.status_code == 410
        # 未写入旧表
        assert (
            db_session.query(Evaluation).filter_by(task_id=task_id).count() == 0
        )

    def test_put_evaluations_returns_410(self, client, db_session):
        suffix = uuid.uuid4().hex[:8]
        owner_token = _register_and_login(client, f"put_owner_{suffix}")
        project_response = client.post(
            "/api/v1/projects",
            json={"title": "Put project"},
            headers=_headers(owner_token),
        )
        project_id = project_response.json()["data"]["id"]
        task_response = client.post(
            "/api/v1/tasks",
            json={
                "project_id": project_id,
                "title": "Put task",
                "student_ids": [],
            },
            headers=_headers(owner_token),
        )
        task_id = task_response.json()["data"]["id"]
        owner_user = client.get(
            "/api/v1/auth/me", headers=_headers(owner_token)
        ).json()["data"]
        evaluation = _seed_legacy_evaluation(
            db_session, task_id, "student-1", owner_user["id"], score=80
        )
        response = client.put(
            f"/api/v1/evaluations/{evaluation.id}",
            json={"score": 100},
            headers=_headers(owner_token),
        )
        assert response.status_code == 410
        # 原记录未被修改
        db_session.refresh(evaluation)
        assert evaluation.score == 80


# ── 新 EvaluationRecord 统一来源 ──────────────────────────────
def _setup_project_with_student(client):
    """构造 admin/teacher/student + 项目（关联学生班级）+ 任务 的上下文。"""
    suffix = uuid.uuid4().hex[:8]
    admin_token = _register_and_login(client, f"epa_{suffix}", "admin")
    school = client.post(
        "/api/v1/schools",
        json={"name": f"EP School {suffix}"},
        headers=_headers(admin_token),
    ).json()["data"]
    cls = client.post(
        f"/api/v1/schools/{school['id']}/classes",
        json={"school_id": school["id"], "grade": "七年级", "name": "1班"},
        headers=_headers(admin_token),
    ).json()["data"]
    teacher_token = _register_and_login(client, f"ept_{suffix}", "teacher")
    teacher_user = client.get(
        "/api/v1/auth/me", headers=_headers(teacher_token)
    ).json()["data"]
    client.post(
        "/api/v1/auth/register",
        json={
            "username": f"eps_{suffix}",
            "password": "12345678",
            "email": f"eps_{suffix}@test.com",
            "display_name": f"eps_{suffix}",
            "role": "student",
            "class_id": cls["id"],
        },
    )
    student_token = client.post(
        "/api/v1/auth/login",
        json={"username": f"eps_{suffix}", "password": "12345678"},
    ).json()["data"]["access_token"]
    student_user = client.get(
        "/api/v1/auth/me", headers=_headers(student_token)
    ).json()["data"]
    project = client.post(
        "/api/v1/projects",
        json={"title": f"EP 项目 {suffix}", "class_ids": [cls["id"]]},
        headers=_headers(teacher_token),
    ).json()["data"]
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"EP 任务 {suffix}",
            "student_ids": [student_user["id"]],
        },
        headers=_headers(teacher_token),
    ).json()["data"]
    # 学生提交
    submission = client.post(
        "/api/v1/submissions",
        json={"task_id": task["id"], "content": "我的作答"},
        headers=_headers(student_token),
    ).json()["data"]
    return {
        "teacher_token": teacher_token,
        "teacher_id": teacher_user["id"],
        "student_token": student_token,
        "student_id": student_user["id"],
        "project_id": project["id"],
        "task_id": task["id"],
        "submission_id": submission["id"],
    }


def _transition_record(client, token, record_id, target):
    return client.post(
        f"/api/v1/evaluation-plans/records/{record_id}/transition",
        json={"target": target},
        headers=_headers(token),
    )


class TestEvaluationRecordUnifiedFlow:
    def test_student_cannot_read_unpublished_record_via_feedback(self, client):
        """AI 草稿/未发布评价对学生不可见：反馈视图 evaluations 为空。"""
        ctx = _setup_project_with_student(client)
        # 教师创建一条 DRAFT 评价记录（模拟 AI 草稿）
        record = client.post(
            "/api/v1/evaluation-plans/records",
            json={
                "project_id": ctx["project_id"],
                "task_id": ctx["task_id"],
                "student_id": ctx["student_id"],
                "evaluator_id": ctx["teacher_id"],
                "subject_type": "task",
                "subject_id": ctx["task_id"],
                "source": "ai",
            },
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        assert record["status"] == "draft"

        # 学生反馈视图：未发布记录不返回
        r = client.get(
            f"/api/v1/student/submissions/{ctx['submission_id']}/feedback",
            headers=_headers(ctx["student_token"]),
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["evaluations"] == []

    def test_published_record_visible_in_feedback_and_list(self, client):
        """教师发布后学生在反馈视图与评价列表看到同一已发布分数/评语。"""
        ctx = _setup_project_with_student(client)
        record = client.post(
            "/api/v1/evaluation-plans/records",
            json={
                "project_id": ctx["project_id"],
                "task_id": ctx["task_id"],
                "student_id": ctx["student_id"],
                "evaluator_id": ctx["teacher_id"],
                "subject_type": "task",
                "subject_id": ctx["task_id"],
                "source": "teacher",
                "comment": "论证完整",
            },
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        # 迁移到 published
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_record(client, ctx["teacher_token"], record["id"], "confirmed")
        _transition_record(client, ctx["teacher_token"], record["id"], "published")

        # 学生反馈视图
        r = client.get(
            f"/api/v1/student/submissions/{ctx['submission_id']}/feedback",
            headers=_headers(ctx["student_token"]),
        )
        assert r.status_code == 200
        evals = r.json()["data"]["evaluations"]
        assert len(evals) == 1
        assert evals[0]["status"] == "published"
        assert evals[0]["comment"] == "论证完整"

        # 学生评价列表（同一项目）
        r = client.get(
            f"/api/v1/evaluation-plans/records?project_id={ctx['project_id']}",
            headers=_headers(ctx["student_token"]),
        )
        assert r.status_code == 200
        items = r.json()["data"]
        assert len(items) == 1
        assert items[0]["id"] == record["id"]
        assert items[0]["status"] == "published"

    def test_student_cannot_read_other_student_record(self, client):
        """跨学生访问评价记录 → 403。"""
        ctx = _setup_project_with_student(client)
        record = client.post(
            "/api/v1/evaluation-plans/records",
            json={
                "project_id": ctx["project_id"],
                "task_id": ctx["task_id"],
                "student_id": ctx["student_id"],
                "evaluator_id": ctx["teacher_id"],
                "subject_type": "task",
                "subject_id": ctx["task_id"],
                "source": "teacher",
            },
            headers=_headers(ctx["teacher_token"]),
        ).json()["data"]
        _transition_record(client, ctx["teacher_token"], record["id"], "collecting_evidence")
        _transition_record(client, ctx["teacher_token"], record["id"], "pending_teacher_confirmation")
        _transition_record(client, ctx["teacher_token"], record["id"], "confirmed")
        _transition_record(client, ctx["teacher_token"], record["id"], "published")

        # 注册另一个不属于该班级的学生
        suffix = uuid.uuid4().hex[:8]
        outsider_token = _register_and_login(client, f"out_{suffix}", "student")
        # 试图读取他人评价详情 → 403/404
        r = client.get(
            f"/api/v1/evaluation-plans/records/{record['id']}",
            headers=_headers(outsider_token),
        )
        assert r.status_code in (403, 404)
