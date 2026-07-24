"""项目学情诊断服务测试（Task 6）。

覆盖计划 Task 6 验收项与 7 节测试边界：
- POST /api/v1/projects/{project_id}/insights/generate：无学习证据时返回
  ``insufficient_evidence`` 与空 segments；绝不为随机画像或伪成功。
- 数据来源只包含项目班级、前测、提交、已发布评价与题目作答；保存
  evidence_cutoff 与 source_counts。
- GET .../insights/latest：返回当前正式快照，历史快照只读保留。
- POST .../insights/{insight_id}/confirm：教师确认诊断；复用项目读写授权与学校作用域。
- 归档项目只读（409）；跨教师/跨学校访问 403；未认证 401。
- 诊断基于真实数据计算，不引入随机分层或模拟 AI 分数。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.enums import (
    EvaluationSource,
    EvaluationStatus,
    EvaluationSubjectType,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.paper import Paper, PaperSubmission
from app.models.project import Project, ProjectClass, ProjectStatus
from app.models.submission import Submission
from app.models.task import Task, TaskStatus, TaskType
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


def _create_project_api(client, token: str, title: str = "学情诊断项目") -> str:
    resp = client.post("/api/v1/projects", json={"title": title}, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _user_id(db_session, username: str) -> str:
    return db_session.execute(select(User).where(User.username == username)).scalar_one().id


def _make_project(
    db_session, creator_id: str, status: ProjectStatus = ProjectStatus.ACTIVE, title: str = "诊断DB项目"
) -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        title=title,
        status=status,
        creator_id=creator_id,
        is_template=False,
    )
    db_session.add(project)
    db_session.flush()
    return project


def _make_task(db_session, project_id: str, created_by: str, title: str = "诊断任务") -> Task:
    task = Task(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=title,
        task_type=TaskType.INDIVIDUAL,
        status=TaskStatus.PENDING,
        max_score=100,
        created_by=created_by,
    )
    db_session.add(task)
    db_session.flush()
    return task


def _make_submission(db_session, task_id: str, student_id: str, score: int | None = None) -> Submission:
    sub = Submission(
        id=str(uuid.uuid4()),
        task_id=task_id,
        student_id=student_id,
        content="学生提交内容",
        status="submitted",
        score=score,
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(sub)
    db_session.flush()
    return sub


def _make_published_eval(
    db_session,
    project_id: str,
    task_id: str,
    student_id: str,
    evaluator_id: str,
    total_score: float,
    status: EvaluationStatus = EvaluationStatus.PUBLISHED,
) -> EvaluationRecord:
    record = EvaluationRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        task_id=task_id,
        student_id=student_id,
        evaluator_id=evaluator_id,
        subject_type=EvaluationSubjectType.TASK,
        subject_id=task_id,
        source=EvaluationSource.TEACHER,
        status=status,
        total_score=total_score,
        comment="教师评价反馈",
    )
    db_session.add(record)
    db_session.flush()
    return record


def _register_student(db_session, username: str, class_id: str | None = None) -> User:
    # 学生通过 API 注册以获得合法密码哈希；此处仅返回记录用于关联
    student = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@test.com",
        hashed_password="$2b$12$placeholderhashforstudentonlyusedindbxxxxx",
        display_name=username,
        role="student",
        class_id=class_id,
        is_active=True,
    )
    db_session.add(student)
    db_session.flush()
    return student


def _link_pre_test_paper(db_session, project_id: str, paper_id: str, created_by: str) -> ToolContextLink:
    link = ToolContextLink(
        id=str(uuid.uuid4()),
        artifact_type="paper",
        artifact_id=paper_id,
        project_id=project_id,
        placement="pre_test",
        phase="diagnosis",
        created_by=created_by,
    )
    db_session.add(link)
    db_session.flush()
    return link


def _make_paper(db_session, teacher_id: str, title: str = "前测试卷") -> Paper:
    paper = Paper(
        id=str(uuid.uuid4()),
        title=title,
        teacher_id=teacher_id,
        class_ids=[],
        status="published",
    )
    db_session.add(paper)
    db_session.flush()
    return paper


def _make_paper_submission(db_session, paper_id: str, student_id: str, final_score: float) -> PaperSubmission:
    ps = PaperSubmission(
        id=str(uuid.uuid4()),
        paper_id=paper_id,
        student_id=student_id,
        final_score=final_score,
        status="reviewed",
    )
    db_session.add(ps)
    db_session.flush()
    return ps


# ============================================================
# 认证
# ============================================================
class TestInsightAuthentication:
    def test_all_endpoints_require_authentication(self, client):
        pid = "any-project"
        assert client.post(f"/api/v1/projects/{pid}/insights/generate").status_code == 401
        assert client.get(f"/api/v1/projects/{pid}/insights/latest").status_code == 401
        assert client.post(f"/api/v1/projects/{pid}/insights/any-id/confirm").status_code == 401


# ============================================================
# 权限：复用项目读写授权与学校作用域
# ============================================================
class TestInsightAuthorization:
    def test_other_teacher_cannot_generate(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        pid = _create_project_api(client, owner_token)

        assert client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(other_token)
        ).status_code == 403

    def test_other_teacher_cannot_read_latest(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        pid = _create_project_api(client, owner_token)

        assert client.get(
            f"/api/v1/projects/{pid}/insights/latest", headers=_auth(other_token)
        ).status_code == 403

    def test_other_school_admin_cannot_generate(self, client):
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
        _register(client, f"sb_{tag}", "school_admin", school_id=school_b["id"])
        ta_token = _login(client, f"ta_{tag}")
        sb_token = _login(client, f"sb_{tag}")
        pid = _create_project_api(client, ta_token, title=f"跨校诊断 {tag}")

        assert client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(sb_token)
        ).status_code == 403

    def test_same_school_admin_can_generate(self, client):
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
        pid = _create_project_api(client, t_token, title=f"同校诊断 {tag}")

        assert client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(sa_token)
        ).status_code == 200


# ============================================================
# 无证据 → insufficient_evidence（计划核心反例）
# ============================================================
class TestInsightInsufficientEvidence:
    def test_generate_without_evidence_returns_insufficient_state(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project_api(client, token)

        data = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]

        assert data["status"] == "insufficient_evidence"
        assert data["segments"] == []
        assert data["overall_mastery"] is None
        assert data["weak_points"] == []
        assert data["teaching_suggestions"] == []
        # 仍保存证据截止时间与来源计数
        assert data["evidence_cutoff"] is not None
        assert data["source_counts"] == {
            "pre_test": 0,
            "submissions": 0,
            "evaluations": 0,
            "question_answers": 0,
        }
        assert data["is_current"] is True

    def test_latest_returns_insufficient_when_no_evidence(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project_api(client, token)
        client.post(f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token))

        data = client.get(
            f"/api/v1/projects/{pid}/insights/latest", headers=_auth(token)
        ).json()["data"]
        assert data["status"] == "insufficient_evidence"
        assert data["segments"] == []


# ============================================================
# 有证据 → 基于真实数据生成诊断（非随机、可复现）
# ============================================================
class TestInsightGenerateWithEvidence:
    def test_generate_with_published_evals_produces_real_segments(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        teacher_id = _user_id(db_session, f"t_{tag}")
        pid = _create_project_api(client, token)
        task = _make_task(db_session, pid, teacher_id)

        # 3 名学生，已发布评价分数分别为 90/70/50（满分 100）
        s1 = _register_student(db_session, f"s1_{tag}")
        s2 = _register_student(db_session, f"s2_{tag}")
        s3 = _register_student(db_session, f"s3_{tag}")
        for stu, score in ((s1, 90), (s2, 70), (s3, 50)):
            _make_submission(db_session, task.id, stu.id)
            _make_published_eval(db_session, pid, task.id, stu.id, teacher_id, score)
        db_session.commit()

        data = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]

        # 有证据 → 不再是 insufficient_evidence
        assert data["status"] != "insufficient_evidence"
        assert data["status"] == "draft"
        # segments 来自真实学生分组，非空
        assert len(data["segments"]) > 0
        # overall_mastery 基于真实分数（90+70+50)/3/100 = 0.7
        assert data["overall_mastery"] is not None
        assert abs(data["overall_mastery"] - 0.7) < 0.01
        # 来源计数反映真实数据
        assert data["source_counts"]["submissions"] == 3
        assert data["source_counts"]["evaluations"] == 3
        # 证据截止时间已记录
        assert data["evidence_cutoff"] is not None
        assert data["generated_at"] is not None
        assert data["generated_by"] == teacher_id

    def test_generate_is_deterministic_not_random(self, client, db_session):
        """同样证据两次生成结果一致，证明非随机画像。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        teacher_id = _user_id(db_session, f"t_{tag}")
        pid = _create_project_api(client, token)
        task = _make_task(db_session, pid, teacher_id)
        s1 = _register_student(db_session, f"d1_{tag}")
        s2 = _register_student(db_session, f"d2_{tag}")
        _make_published_eval(db_session, pid, task.id, s1.id, teacher_id, 80)
        _make_published_eval(db_session, pid, task.id, s2.id, teacher_id, 60)
        db_session.commit()

        first = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]
        second = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]

        assert first["overall_mastery"] == second["overall_mastery"]
        assert first["segments"] == second["segments"]
        assert first["source_counts"] == second["source_counts"]

    def test_generate_counts_pre_test_and_question_answers(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        teacher_id = _user_id(db_session, f"t_{tag}")
        pid = _create_project_api(client, token)
        # 关联前测试卷 + 题目作答
        paper = _make_paper(db_session, teacher_id)
        _link_pre_test_paper(db_session, pid, paper.id, teacher_id)
        s1 = _register_student(db_session, f"q1_{tag}")
        s2 = _register_student(db_session, f"q2_{tag}")
        _make_paper_submission(db_session, paper.id, s1.id, 80)
        _make_paper_submission(db_session, paper.id, s2.id, 60)
        db_session.commit()

        data = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]

        assert data["source_counts"]["pre_test"] == 1
        assert data["source_counts"]["question_answers"] == 2
        # 仅前测+作答也算证据，不应返回 insufficient_evidence
        assert data["status"] != "insufficient_evidence"

    def test_generate_excludes_unpublished_evaluations_from_mastery(self, client, db_session):
        """未发布评价不计入掌握度（学生不可见），但仍计入来源计数的 evaluations。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        teacher_id = _user_id(db_session, f"t_{tag}")
        pid = _create_project_api(client, token)
        task = _make_task(db_session, pid, teacher_id)
        s1 = _register_student(db_session, f"u1_{tag}")
        # 已发布 80
        _make_published_eval(db_session, pid, task.id, s1.id, teacher_id, 80, status=EvaluationStatus.PUBLISHED)
        # 草稿 100（不计入掌握度）
        _make_published_eval(db_session, pid, task.id, s1.id, teacher_id, 100, status=EvaluationStatus.DRAFT)
        db_session.commit()

        data = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]
        # 掌握度仅按已发布评价 80 计算
        assert abs(data["overall_mastery"] - 0.8) < 0.01


# ============================================================
# latest：当前快照与历史快照
# ============================================================
class TestInsightLatest:
    def test_latest_none_before_generate(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project_api(client, token)

        resp = client.get(f"/api/v1/projects/{pid}/insights/latest", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_latest_returns_current_insight(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        teacher_id = _user_id(db_session, f"t_{tag}")
        pid = _create_project_api(client, token)
        task = _make_task(db_session, pid, teacher_id)
        s1 = _register_student(db_session, f"l1_{tag}")
        _make_published_eval(db_session, pid, task.id, s1.id, teacher_id, 85)
        db_session.commit()
        generated = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]

        latest = client.get(
            f"/api/v1/projects/{pid}/insights/latest", headers=_auth(token)
        ).json()["data"]
        assert latest["id"] == generated["id"]
        assert latest["is_current"] is True


# ============================================================
# confirm：教师确认诊断
# ============================================================
class TestInsightConfirm:
    def test_confirm_draft_insight(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        teacher_id = _user_id(db_session, f"t_{tag}")
        pid = _create_project_api(client, token)
        task = _make_task(db_session, pid, teacher_id)
        s1 = _register_student(db_session, f"c1_{tag}")
        _make_published_eval(db_session, pid, task.id, s1.id, teacher_id, 80)
        db_session.commit()
        insight = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]

        resp = client.post(
            f"/api/v1/projects/{pid}/insights/{insight['id']}/confirm",
            json={"teacher_note": "已核对前测与作业"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "confirmed"
        assert data["confirmed_by"] == teacher_id
        assert data["confirmed_at"] is not None
        assert data["teacher_note"] == "已核对前测与作业"

    def test_confirm_insufficient_evidence_rejected(self, client):
        """无证据诊断不可确认为正式结论。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project_api(client, token)
        insight = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]

        resp = client.post(
            f"/api/v1/projects/{pid}/insights/{insight['id']}/confirm", headers=_auth(token)
        )
        assert resp.status_code == 409

    def test_confirm_requires_manage_permission(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        owner_id = _user_id(db_session, f"owner_{tag}")
        pid = _create_project_api(client, owner_token)
        task = _make_task(db_session, pid, owner_id)
        s1 = _register_student(db_session, f"p1_{tag}")
        _make_published_eval(db_session, pid, task.id, s1.id, owner_id, 80)
        db_session.commit()
        insight = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(owner_token)
        ).json()["data"]

        assert client.post(
            f"/api/v1/projects/{pid}/insights/{insight['id']}/confirm",
            headers=_auth(other_token),
        ).status_code == 403

    def test_confirm_nonexistent_insight_returns_404(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project_api(client, token)
        assert client.post(
            f"/api/v1/projects/{pid}/insights/not-an-insight/confirm", headers=_auth(token)
        ).status_code == 404


# ============================================================
# 归档只读
# ============================================================
class TestInsightArchivedReadOnly:
    def test_generate_archived_returns_409(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        teacher_id = _user_id(db_session, f"t_{tag}")
        pid = _create_project_api(client, token)
        task = _make_task(db_session, pid, teacher_id)
        s1 = _register_student(db_session, f"a1_{tag}")
        _make_published_eval(db_session, pid, task.id, s1.id, teacher_id, 80)
        db_session.commit()
        # 先生成一条，再归档
        client.post(f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token))
        from sqlalchemy import update as sa_update

        db_session.execute(sa_update(Project).where(Project.id == pid).values(status=ProjectStatus.ARCHIVED))
        db_session.commit()

        assert client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).status_code == 409

    def test_confirm_archived_returns_409(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        teacher_id = _user_id(db_session, f"t_{tag}")
        pid = _create_project_api(client, token)
        task = _make_task(db_session, pid, teacher_id)
        s1 = _register_student(db_session, f"a2_{tag}")
        _make_published_eval(db_session, pid, task.id, s1.id, teacher_id, 80)
        db_session.commit()
        insight = client.post(
            f"/api/v1/projects/{pid}/insights/generate", headers=_auth(token)
        ).json()["data"]
        from sqlalchemy import update as sa_update

        db_session.execute(sa_update(Project).where(Project.id == pid).values(status=ProjectStatus.ARCHIVED))
        db_session.commit()

        assert client.post(
            f"/api/v1/projects/{pid}/insights/{insight['id']}/confirm", headers=_auth(token)
        ).status_code == 409


# ============================================================
# 项目不存在
# ============================================================
class TestInsightNonexistentProject:
    def test_generate_nonexistent_returns_404(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        assert client.post(
            "/api/v1/projects/not-a-project/insights/generate", headers=_auth(token)
        ).status_code == 404

    def test_latest_nonexistent_returns_404(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        assert client.get(
            "/api/v1/projects/not-a-project/insights/latest", headers=_auth(token)
        ).status_code == 404
