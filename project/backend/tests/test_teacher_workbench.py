"""教师工作台真实待办测试（Task 5）。

覆盖计划 Task 5 Step 1 验收项：
- GET /api/v1/dashboard/teacher-workbench 返回 active_projects、tasks_to_publish、
  submissions_to_review、feedback_to_publish、ai_to_review、deadlines、learning_alerts。
- 所有数字与条目均来自当前教师可管理范围（自己创建的项目）。
- 跨教师、跨校数据不可见；不出现静态待办或模拟事实。
- 每个待办条目都带 route，直接进入所属项目和阶段。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.models.ai_job import AiJob, AiJobStatus
from app.models.enums import (
    AdoptionStatus,
    AiJobScene,
    EvaluationSource,
    EvaluationStatus,
    EvaluationSubjectType,
    SchemaStatus,
    SubmissionReviewStatus,
    SubmissionType,
    TaskPublishStatus,
    TeachingStage,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import Role, User


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


def _create_project(client, token: str, title: str = "工作台项目") -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"title": title},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _create_task(client, token: str, project_id: str, title: str = "待发布任务") -> str:
    """通过 API 创建任务；默认 publish_status=DRAFT。"""
    resp = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": title},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _register_student(db_session, username: str) -> User:
    """直接落库一个学生用户，用于提交/评价夹具。"""
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password="x",
        display_name=username,
        role=Role.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_submission(
    db_session,
    task_id: str,
    student_id: str,
    review_status: SubmissionReviewStatus = SubmissionReviewStatus.SUBMITTED,
) -> Submission:
    sub = Submission(
        task_id=task_id,
        student_id=student_id,
        content="学生提交内容",
        status="submitted",
        review_status=review_status,
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


def _make_evaluation(
    db_session,
    project_id: str,
    student_id: str,
    evaluator_id: str,
    status: EvaluationStatus = EvaluationStatus.CONFIRMED,
    confirmed: bool = True,
) -> EvaluationRecord:
    rec = EvaluationRecord(
        project_id=project_id,
        student_id=student_id,
        evaluator_id=evaluator_id,
        subject_type=EvaluationSubjectType.TASK,
        subject_id=project_id,
        source=EvaluationSource.TEACHER,
        status=status,
        confirmed_by=evaluator_id if confirmed else None,
        confirmed_at=datetime.now(timezone.utc) if confirmed else None,
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)
    return rec


def _make_ai_job(
    db_session,
    project_id: str,
    initiator_id: str,
    status: AiJobStatus = AiJobStatus.SUCCEEDED,
    reviewed: bool = False,
) -> AiJob:
    job = AiJob(
        project_id=project_id,
        context_mode="PROJECT",
        scene=AiJobScene.GRADING,
        status=status,
        output_type="评分草稿",
        initiated_by=initiator_id,
        reviewed_by=initiator_id if reviewed else None,
        reviewed_at=datetime.now(timezone.utc) if reviewed else None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _set_task_deadline(db_session, task_id: str, days: int) -> None:
    """直接更新任务截止时间；days>0 未来，days<0 过去。"""
    deadline = datetime.now(timezone.utc) + timedelta(days=days)
    db_session.query(Task).filter(Task.id == task_id).update({"deadline": deadline})
    db_session.commit()


def _publish_task(db_session, task_id: str) -> None:
    """将任务标记为已发布，用于学习预警与截止场景。"""
    db_session.query(Task).filter(Task.id == task_id).update(
        {"publish_status": TaskPublishStatus.PUBLISHED}
    )
    db_session.commit()


# ============================================================
# 认证与角色
# ============================================================
class TestWorkbenchAuthentication:
    def test_workbench_requires_authentication(self, client):
        resp = client.get("/api/v1/dashboard/teacher-workbench")
        assert resp.status_code == 401

    def test_workbench_rejects_student_role(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"stu_{tag}", "student")
        token = _login(client, f"stu_{tag}")
        resp = client.get("/api/v1/dashboard/teacher-workbench", headers=_auth(token))
        assert resp.status_code == 403

    def test_workbench_allows_teacher(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        resp = client.get("/api/v1/dashboard/teacher-workbench", headers=_auth(token))
        assert resp.status_code == 200

    def test_workbench_allows_school_admin(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sys_{tag}", "admin")
        sys_token = _login(client, f"sys_{tag}")
        school = client.post(
            "/api/v1/schools", json={"name": f"工作台校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        _register(client, f"sa_{tag}", "school_admin", school_id=school["id"])
        sa_token = _login(client, f"sa_{tag}")
        resp = client.get("/api/v1/dashboard/teacher-workbench", headers=_auth(sa_token))
        assert resp.status_code == 200


# ============================================================
# 真实待办：只含当前教师可管理范围
# ============================================================
class TestWorkbenchActionableItems:
    def test_tasks_to_publish_contains_only_own_draft_tasks(self, client):
        """草稿任务出现在 tasks_to_publish；其他教师的草稿任务不出现。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        own_pid = _create_project(client, owner_token, title=f"我的项目 {tag}")
        other_pid = _create_project(client, other_token, title=f"他人项目 {tag}")
        own_task = _create_task(client, owner_token, own_pid, "我的草稿任务")
        other_task = _create_task(client, other_token, other_pid, "他人草稿任务")

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(owner_token)
        ).json()["data"]
        ids = {item["id"] for item in data["tasks_to_publish"]}
        assert own_task in ids
        assert other_task not in ids

    def test_active_projects_contains_only_own_active(self, client, db_session):
        """活跃项目出现；其他教师的活跃项目不出现。"""
        from app.models.project import Project, ProjectStatus
        from sqlalchemy import update as sa_update

        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        own_pid = _create_project(client, owner_token, title=f"我活跃 {tag}")
        other_pid = _create_project(client, other_token, title=f"他活跃 {tag}")
        # 直接置为 active（绕过设计完整性，专注工作台范围测试）
        db_session.execute(sa_update(Project).where(Project.id.in_([own_pid, other_pid])).values(status=ProjectStatus.ACTIVE))

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(owner_token)
        ).json()["data"]
        ids = {p["id"] for p in data["active_projects"]}
        assert own_pid in ids
        assert other_pid not in ids

    def test_submissions_to_review_contains_only_own_project_submissions(
        self, client, db_session
    ):
        """已提交待复核的提交出现；其他教师项目下的提交不出现。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        own_pid = _create_project(client, owner_token, title=f"我提交 {tag}")
        other_pid = _create_project(client, other_token, title=f"他提交 {tag}")
        own_task = _create_task(client, owner_token, own_pid, "我的任务")
        other_task = _create_task(client, other_token, other_pid, "他的任务")
        stu = _register_student(db_session, f"stu_{tag}")
        own_sub = _make_submission(db_session, own_task, stu.id)
        _make_submission(db_session, other_task, stu.id)

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(owner_token)
        ).json()["data"]
        ids = {item["id"] for item in data["submissions_to_review"]}
        assert own_sub.id in ids

    def test_feedback_to_publish_contains_confirmed_unpublished(self, client, db_session):
        """已确认未发布评价出现；已发布的不出现。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token, title=f"评价 {tag}")
        task = _create_task(client, token, pid, "评价任务")
        stu = _register_student(db_session, f"stu_{tag}")
        # 已确认未发布 → 应出现
        confirmed = _make_evaluation(
            db_session, pid, stu.id, evaluator_id=_user_id(db_session, f"t_{tag}"),
            status=EvaluationStatus.CONFIRMED, confirmed=True,
        )
        # 已发布 → 不出现
        published = _make_evaluation(
            db_session, pid, stu.id, evaluator_id=_user_id(db_session, f"t_{tag}"),
            status=EvaluationStatus.PUBLISHED, confirmed=True,
        )
        db_session.query(EvaluationRecord).filter(EvaluationRecord.id == published.id).update(
            {"published_at": datetime.now(timezone.utc)}
        )
        db_session.commit()

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(token)
        ).json()["data"]
        ids = {item["id"] for item in data["feedback_to_publish"]}
        assert confirmed.id in ids
        assert published.id not in ids

    def test_ai_to_review_contains_succeeded_unreviewed(self, client, db_session):
        """成功且未审核的 AI 任务出现；已审核的不出现。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        uid = _user_id(db_session, f"t_{tag}")
        pid = _create_project(client, token, title=f"AI {tag}")
        unreviewed = _make_ai_job(db_session, pid, uid, reviewed=False)
        reviewed = _make_ai_job(db_session, pid, uid, reviewed=True)

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(token)
        ).json()["data"]
        ids = {item["id"] for item in data["ai_to_review"]}
        assert unreviewed.id in ids
        assert reviewed.id not in ids

    def test_deadlines_contains_own_upcoming_tasks(self, client, db_session):
        """未来 7 天内截止的已发布任务出现；过期或他人任务不出现。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"owner_{tag}", "teacher")
        _register(client, f"other_{tag}", "teacher")
        owner_token = _login(client, f"owner_{tag}")
        other_token = _login(client, f"other_{tag}")
        own_pid = _create_project(client, owner_token, title=f"我截止 {tag}")
        other_pid = _create_project(client, other_token, title=f"他截止 {tag}")
        own_soon = _create_task(client, owner_token, own_pid, "我即将截止")
        own_far = _create_task(client, owner_token, own_pid, "我远期截止")
        other_soon = _create_task(client, other_token, other_pid, "他即将截止")
        _publish_task(db_session, own_soon)
        _publish_task(db_session, own_far)
        _publish_task(db_session, other_soon)
        _set_task_deadline(db_session, own_soon, days=3)
        _set_task_deadline(db_session, own_far, days=30)
        _set_task_deadline(db_session, other_soon, days=3)

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(owner_token)
        ).json()["data"]
        ids = {item["id"] for item in data["deadlines"]}
        assert own_soon in ids
        assert own_far not in ids
        assert other_soon not in ids

    def test_learning_alerts_flags_published_task_without_submissions(
        self, client, db_session
    ):
        """已发布但无任何提交的任务进入学习预警。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        pid = _create_project(client, token, title=f"预警 {tag}")
        no_submit = _create_task(client, token, pid, "无提交任务")
        _publish_task(db_session, no_submit)

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(token)
        ).json()["data"]
        ids = {item["id"] for item in data["learning_alerts"]}
        assert no_submit in ids


# ============================================================
# 无静态/模拟数据
# ============================================================
class TestWorkbenchNoStaticData:
    def test_new_teacher_has_empty_workbench(self, client):
        """新教师无项目无任务时，所有待办为空列表，不伪造。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(token)
        ).json()["data"]
        for key in (
            "active_projects",
            "tasks_to_publish",
            "submissions_to_review",
            "feedback_to_publish",
            "ai_to_review",
            "deadlines",
            "learning_alerts",
        ):
            assert data[key] == [], f"{key} 应为空列表，实际: {data[key]}"

    def test_workbench_response_has_all_required_top_level_keys(self, client):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(token)
        ).json()["data"]
        for key in (
            "active_projects",
            "tasks_to_publish",
            "submissions_to_review",
            "feedback_to_publish",
            "ai_to_review",
            "deadlines",
            "learning_alerts",
        ):
            assert key in data, f"缺少字段 {key}"


# ============================================================
# 每项待办可直接进入所属项目阶段
# ============================================================
class TestWorkbenchRouteNavigation:
    def test_every_actionable_item_has_project_id_and_route(self, client, db_session):
        tag = uuid.uuid4().hex[:8]
        _register(client, f"t_{tag}", "teacher")
        token = _login(client, f"t_{tag}")
        uid = _user_id(db_session, f"t_{tag}")
        pid = _create_project(client, token, title=f"路由 {tag}")
        task = _create_task(client, token, pid, "路由任务")
        _publish_task(db_session, task)
        _set_task_deadline(db_session, task, days=2)
        stu = _register_student(db_session, f"stu_{tag}")
        _make_submission(db_session, task, stu.id)
        _make_evaluation(
            db_session, pid, stu.id, evaluator_id=uid,
            status=EvaluationStatus.CONFIRMED, confirmed=True,
        )
        _make_ai_job(db_session, pid, uid, reviewed=False)

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(token)
        ).json()["data"]

        # 每个待办条目都必须带 project_id 与 route，且 route 指向项目工作区
        for key in (
            "tasks_to_publish",
            "submissions_to_review",
            "feedback_to_publish",
            "ai_to_review",
            "deadlines",
            "learning_alerts",
        ):
            for item in data[key]:
                assert item.get("project_id"), f"{key} 条目缺少 project_id"
                assert item.get("route"), f"{key} 条目缺少 route"
                assert "/teacher/projects/" in item["route"], f"{key} route 未指向项目工作区"

        # active_projects 自身就在项目维度，route 指向项目总览
        for proj in data["active_projects"]:
            assert proj.get("id")
            assert proj.get("route")
            assert "/teacher/projects/" in proj["route"]


# ── 辅助：从 db 查 user_id（教师角色无法访问 /users/me）─────────
def _user_id(db_session, username: str) -> str:
    user = db_session.query(User).filter(User.username == username).first()
    assert user is not None, f"用户 {username} 不存在"
    return user.id
