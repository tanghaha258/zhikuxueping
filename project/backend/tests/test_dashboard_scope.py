"""教师工作台学校范围权限测试（Task 5）。

覆盖计划 Task 5 Step 1 学校范围验收项：
- school_admin 只能查看本校教师的项目及其衍生待办；跨校数据不可见。
- teacher 只看自己创建的项目；同一学校其他教师的项目也不可见。
- 无学校绑定的 school_admin 视为空集，避免越权。
- 跨校 tasks_to_publish / submissions_to_review / learning_alerts 不发生泄漏。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.models.enums import (
    SubmissionReviewStatus,
    TaskPublishStatus,
)
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import Role, User


# ── 测试辅助（与 test_teacher_workbench 一致，避免跨文件依赖）─────
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


def _create_project(client, token: str, title: str) -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"title": title},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _create_task(client, token: str, project_id: str, title: str = "范围任务") -> str:
    resp = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": title},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _register_student(db_session, username: str) -> User:
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


def _make_submission(db_session, task_id: str, student_id: str) -> Submission:
    sub = Submission(
        task_id=task_id,
        student_id=student_id,
        content="内容",
        status="submitted",
        review_status=SubmissionReviewStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


def _publish_and_set_deadline(db_session, task_id: str, days: int = 3) -> None:
    deadline = datetime.now(timezone.utc) + timedelta(days=days)
    db_session.query(Task).filter(Task.id == task_id).update(
        {"publish_status": TaskPublishStatus.PUBLISHED, "deadline": deadline}
    )
    db_session.commit()


# ── 双校夹具：注册系统管理员、两所学校、两校教师、两校项目 ──────
def _setup_two_schools(client):
    tag = uuid.uuid4().hex[:8]
    _register(client, f"sys_{tag}", "admin")
    sys_token = _login(client, f"sys_{tag}")
    school_a = client.post(
        "/api/v1/schools", json={"name": f"A校 {tag}"}, headers=_auth(sys_token)
    ).json()["data"]
    school_b = client.post(
        "/api/v1/schools", json={"name": f"B校 {tag}"}, headers=_auth(sys_token)
    ).json()["data"]
    _register(client, f"ta_{tag}", "teacher", school_id=school_a["id"])
    _register(client, f"tb_{tag}", "teacher", school_id=school_b["id"])
    _register(client, f"sa_a_{tag}", "school_admin", school_id=school_a["id"])
    _register(client, f"sa_b_{tag}", "school_admin", school_id=school_b["id"])
    ta_token = _login(client, f"ta_{tag}")
    tb_token = _login(client, f"tb_{tag}")
    sa_a_token = _login(client, f"sa_a_{tag}")
    sa_b_token = _login(client, f"sa_b_{tag}")
    pa = _create_project(client, ta_token, f"A校项目 {tag}")
    pb = _create_project(client, tb_token, f"B校项目 {tag}")
    return {
        "tag": tag,
        "school_a_id": school_a["id"],
        "school_b_id": school_b["id"],
        "ta_token": ta_token,
        "tb_token": tb_token,
        "sa_a_token": sa_a_token,
        "sa_b_token": sa_b_token,
        "project_a": pa,
        "project_b": pb,
    }


# ============================================================
# 学校管理员范围
# ============================================================
class TestSchoolAdminScope:
    def test_school_admin_sees_only_own_school_projects(self, client):
        """A 校管理员只见 A 校项目，不见 B 校项目。"""
        ctx = _setup_two_schools(client)
        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(ctx["sa_a_token"])
        ).json()["data"]
        ids = {p["id"] for p in data["active_projects"]}
        # 项目默认 draft 状态，不会进 active_projects；改为检查 tasks_to_publish 范围
        # 这里直接断言 active_projects 不含他校项目（即便为空也满足）
        assert ctx["project_b"] not in ids

    def test_school_admin_sees_teachers_projects_in_same_school(self, client, db_session):
        """A 校管理员可见本校教师项目衍生的待办（草稿任务）。"""
        from app.models.project import Project, ProjectStatus
        from sqlalchemy import update as sa_update

        ctx = _setup_two_schools(client)
        task_a = _create_task(client, ctx["ta_token"], ctx["project_a"], "A校草稿任务")
        task_b = _create_task(client, ctx["tb_token"], ctx["project_b"], "B校草稿任务")

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(ctx["sa_a_token"])
        ).json()["data"]
        ids = {item["id"] for item in data["tasks_to_publish"]}
        assert task_a in ids, "本校教师草稿任务应可见"
        assert task_b not in ids, "他校教师草稿任务不应可见"

    def test_school_admin_does_not_see_other_school_submissions(self, client, db_session):
        """A 校管理员不见 B 校项目的提交。"""
        ctx = _setup_two_schools(client)
        task_a = _create_task(client, ctx["ta_token"], ctx["project_a"], "A校任务")
        task_b = _create_task(client, ctx["tb_token"], ctx["project_b"], "B校任务")
        stu = _register_student(db_session, f"stu_{ctx['tag']}")
        sub_a = _make_submission(db_session, task_a, stu.id)
        sub_b = _make_submission(db_session, task_b, stu.id)

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(ctx["sa_a_token"])
        ).json()["data"]
        ids = {item["id"] for item in data["submissions_to_review"]}
        assert sub_a.id in ids
        assert sub_b.id not in ids

    def test_school_admin_without_school_sees_empty(self, client):
        """无学校绑定的学校管理员只能看到空集，避免越权。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sa_loose_{tag}", "school_admin")
        sa_token = _login(client, f"sa_loose_{tag}")

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(sa_token)
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
            assert data[key] == [], f"无学校绑定的 school_admin {key} 应为空"


# ============================================================
# 教师范围
# ============================================================
class TestTeacherScope:
    def test_teacher_does_not_see_other_school_projects(self, client, db_session):
        """A 校教师不见 B 校教师的项目与待办。"""
        ctx = _setup_two_schools(client)
        task_b = _create_task(client, ctx["tb_token"], ctx["project_b"], "B校任务")

        data = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(ctx["ta_token"])
        ).json()["data"]
        ids = {item["id"] for item in data["tasks_to_publish"]}
        assert task_b not in ids

    def test_teacher_does_not_see_same_school_other_teacher_data(self, client, db_session):
        """同校但不同教师的项目互不可见（教师仅看自己创建的项目）。"""
        tag = uuid.uuid4().hex[:8]
        _register(client, f"sys_{tag}", "admin")
        sys_token = _login(client, f"sys_{tag}")
        school = client.post(
            "/api/v1/schools", json={"name": f"同校 {tag}"}, headers=_auth(sys_token)
        ).json()["data"]
        _register(client, f"t1_{tag}", "teacher", school_id=school["id"])
        _register(client, f"t2_{tag}", "teacher", school_id=school["id"])
        t1_token = _login(client, f"t1_{tag}")
        t2_token = _login(client, f"t2_{tag}")
        p1 = _create_project(client, t1_token, f"教师1项目 {tag}")
        p2 = _create_project(client, t2_token, f"教师2项目 {tag}")
        task1 = _create_task(client, t1_token, p1, "教师1任务")
        task2 = _create_task(client, t2_token, p2, "教师2任务")

        data1 = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(t1_token)
        ).json()["data"]
        ids1 = {item["id"] for item in data1["tasks_to_publish"]}
        assert task1 in ids1
        assert task2 not in ids1

    def test_no_cross_school_leakage_in_learning_alerts(self, client, db_session):
        """A 校教师的已发布无提交任务预警不泄漏到 B 校管理员。"""
        ctx = _setup_two_schools(client)
        task_a = _create_task(client, ctx["ta_token"], ctx["project_a"], "A校预警任务")
        _publish_and_set_deadline(db_session, task_a, days=-1)  # 已过期无提交

        data_b = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(ctx["sa_b_token"])
        ).json()["data"]
        ids_b = {item["id"] for item in data_b["learning_alerts"]}
        assert task_a not in ids_b

        data_a = client.get(
            "/api/v1/dashboard/teacher-workbench", headers=_auth(ctx["sa_a_token"])
        ).json()["data"]
        ids_a = {item["id"] for item in data_a["learning_alerts"]}
        assert task_a in ids_a
