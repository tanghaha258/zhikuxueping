"""项目结项/归档/重新开放测试（计划 Task 9 验收标准）。

覆盖：
- 验收 1：结项完整性检查——存在未发布反馈或未处理阻断问题时 complete 返回 409；
  全部已发布时 complete 成功。
- 验收 2：归档只读——archived 状态下 update_project 返回 409。
- 验收 3：重新开放授权——普通 teacher 调用 reopen 返回 403；reason 为空返回 400；
  school_admin + reason 成功，状态 archived -> active，reason 被记录。
- 验收 4：结项数据摘要——返回正确学生数/任务数/评价数。
- 验收 5：教师反思——反思文本被持久化。
- 验收 6：案例归档脱敏预览——学生真实姓名被隐藏，编号代替。

不伪造数据：真实创建 Project/Task/Submission/EvaluationRecord/User 等记录。
用 uuid 唯一 ID 避免跨测试累积（conftest 的 db_session rollback 无法清除
service 内部 commit 的数据）。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import AppException
from app.models.enums import (
    EvaluationSource,
    EvaluationStatus,
    EvaluationSubjectType,
    SubmissionReviewStatus,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.project import Project, ProjectClass, ProjectStatus
from app.models.school import Class
from app.models.submission import Submission
from app.models.submission_revision import SubmissionRevision  # noqa: F401 — register model with Base.metadata
from app.models.task import Task, TaskStatus, TaskType
from app.models.user import Role, User
from app.modules.projects import service
from app.schemas.project import ProjectUpdate


# ── 测试辅助 ──────────────────────────────────────────────────

class _Actor:
    """轻量 actor 替身，避免依赖完整 User 注册流程。"""

    def __init__(
        self,
        user_id: str = "teacher-1",
        role: Role = Role.TEACHER,
        class_id: str | None = None,
        school_id: str | None = None,
    ):
        self.id = user_id
        self.role = role
        self.class_id = class_id
        self.school_id = school_id
        self.is_active = True


def _make_project(
    db_session,
    creator_id: str = "teacher-1",
    status: ProjectStatus = ProjectStatus.ACTIVE,
    school_id: str | None = None,
) -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        title=f"结项测试项目-{uuid.uuid4().hex[:6]}",
        status=status,
        creator_id=creator_id,
        school_id=school_id,
        is_template=False,
    )
    db_session.add(project)
    db_session.flush()
    return project


def _make_task(db_session, project_id: str, created_by: str = "teacher-1") -> Task:
    task = Task(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=f"结项任务-{uuid.uuid4().hex[:6]}",
        description="测试结项完整性",
        task_type=TaskType.INDIVIDUAL,
        status=TaskStatus.PENDING,
        max_score=100,
        created_by=created_by,
    )
    db_session.add(task)
    db_session.flush()
    return task


def _make_class(
    db_session,
    school_id: str = "school-1",
) -> Class:
    cls = Class(
        id=f"class-{uuid.uuid4().hex[:8]}",
        school_id=school_id,
        grade="grade-7",
        name=f"测试班级-{uuid.uuid4().hex[:4]}",
    )
    db_session.add(cls)
    db_session.flush()
    return cls


def _assign_project_to_class(db_session, project_id: str, class_id: str):
    db_session.add(ProjectClass(project_id=project_id, class_id=class_id))
    db_session.flush()


def _make_student_user(
    db_session,
    display_name: str,
    class_id: str | None = None,
) -> User:
    """创建真实学生 User 记录（用于脱敏预览测试）。"""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=f"stu-{suffix}",
        username=f"stu-{suffix}",
        email=f"stu-{suffix}@test.com",
        hashed_password="dummy",
        display_name=display_name,
        role=Role.STUDENT,
        class_id=class_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_submission(
    db_session,
    task_id: str,
    student_id: str,
    review_status: SubmissionReviewStatus = SubmissionReviewStatus.SUBMITTED,
) -> Submission:
    sub = Submission(
        id=str(uuid.uuid4()),
        task_id=task_id,
        student_id=student_id,
        content="作答内容",
        status="submitted",
        review_status=review_status,
    )
    db_session.add(sub)
    db_session.flush()
    return sub


def _make_evaluation_record(
    db_session,
    project_id: str,
    task_id: str,
    student_id: str,
    status: EvaluationStatus = EvaluationStatus.PUBLISHED,
    total_score: float = 85.0,
    confirmed_by: str | None = "teacher-1",
) -> EvaluationRecord:
    record = EvaluationRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        task_id=task_id,
        student_id=student_id,
        evaluator_id="teacher-1",
        subject_type=EvaluationSubjectType.TASK,
        subject_id=task_id,
        source=EvaluationSource.TEACHER,
        status=status,
        total_score=total_score,
        comment="教师评价反馈",
        confirmed_by=confirmed_by,
    )
    db_session.add(record)
    db_session.flush()
    return record


# ============================================================
# 验收 1：结项完整性检查
# ============================================================

class TestClosureCompletenessCheck:
    """存在未发布反馈或未处理阻断问题时拒绝结项；全部已发布时结项成功。"""

    def test_complete_project_blocked_by_unpublished_feedback(self, db_session):
        project = _make_project(db_session, status=ProjectStatus.ACTIVE)
        task = _make_task(db_session, project.id)
        # 使用唯一 student_id 避免跨测试数据累积
        student_id = f"stu-block-{uuid.uuid4().hex[:8]}"
        _make_evaluation_record(
            db_session,
            project.id,
            task.id,
            student_id,
            status=EvaluationStatus.DRAFT,  # 未发布
            confirmed_by=None,
        )

        actor = _Actor(user_id="teacher-1", role=Role.TEACHER)
        with pytest.raises(AppException) as exc_info:
            service.complete_project(db_session, actor, project.id)

        assert exc_info.value.status_code == 409
        assert "未发布评价" in exc_info.value.message

    def test_complete_project_success_when_all_published(self, db_session):
        project = _make_project(db_session, status=ProjectStatus.ACTIVE)
        task = _make_task(db_session, project.id)
        student_id = f"stu-ok-{uuid.uuid4().hex[:8]}"
        _make_evaluation_record(
            db_session,
            project.id,
            task.id,
            student_id,
            status=EvaluationStatus.PUBLISHED,
        )

        actor = _Actor(user_id="teacher-1", role=Role.TEACHER)
        completed = service.complete_project(db_session, actor, project.id)

        assert completed.status == ProjectStatus.COMPLETED


# ============================================================
# 验收 2：归档只读
# ============================================================

class TestArchivedReadOnly:
    """归档后所有写操作拒绝（409）。"""

    def test_archived_project_rejects_write(self, db_session):
        project = _make_project(db_session, status=ProjectStatus.ARCHIVED)
        actor = _Actor(user_id="teacher-1", role=Role.TEACHER)

        update_data = ProjectUpdate(title="越权修改归档项目")
        with pytest.raises(AppException) as exc_info:
            service.update_project(db_session, actor, project.id, update_data)

        assert exc_info.value.status_code == 409
        assert "已归档" in exc_info.value.message


# ============================================================
# 验收 3：重新开放授权
# ============================================================

class TestReopenAuthorization:
    """重新开放归档项目：仅 school_admin + reason 必填。"""

    def test_reopen_requires_school_admin(self, db_session):
        # 项目由 teacher-1 创建，school_id=school-1
        project = _make_project(
            db_session,
            status=ProjectStatus.ARCHIVED,
            school_id="school-1",
        )
        # 普通教师调用应 403
        actor = _Actor(user_id="teacher-1", role=Role.TEACHER)
        with pytest.raises(AppException) as exc_info:
            service.reopen_archived_project(
                db_session, actor, project.id, "需要修改"
            )
        assert exc_info.value.status_code == 403
        assert "学校管理员" in exc_info.value.message

    def test_reopen_requires_reason(self, db_session):
        project = _make_project(
            db_session,
            status=ProjectStatus.ARCHIVED,
            school_id="school-1",
        )
        # school_admin 调用但 reason 为空
        actor = _Actor(
            user_id="admin-1",
            role=Role.SCHOOL_ADMIN,
            school_id="school-1",
        )
        with pytest.raises(AppException) as exc_info:
            service.reopen_archived_project(db_session, actor, project.id, "")
        assert exc_info.value.status_code == 400
        assert "原因" in exc_info.value.message

    def test_reopen_success_records_reason(self, db_session):
        project = _make_project(
            db_session,
            status=ProjectStatus.ARCHIVED,
            school_id="school-1",
        )
        actor = _Actor(
            user_id="admin-reopen-1",
            role=Role.SCHOOL_ADMIN,
            school_id="school-1",
        )
        reason = f"结项后需补充案例素材-{uuid.uuid4().hex[:6]}"
        reopened = service.reopen_archived_project(
            db_session, actor, project.id, reason
        )

        assert reopened.status == ProjectStatus.ACTIVE
        assert reopened.reopen_reason == reason
        assert reopened.reopened_by == actor.id
        assert reopened.reopened_at is not None


# ============================================================
# 验收 4：结项数据摘要
# ============================================================

class TestClosureSummary:
    """结项摘要返回正确学生数/任务数/评价数。"""

    def test_closure_summary_aggregates_data(self, db_session):
        project = _make_project(db_session, status=ProjectStatus.ACTIVE)
        task1 = _make_task(db_session, project.id)
        task2 = _make_task(db_session, project.id)

        # 使用唯一 student_id 避免跨测试数据累积
        stu1 = f"stu-sum-{uuid.uuid4().hex[:8]}"
        stu2 = f"stu-sum-{uuid.uuid4().hex[:8]}"

        _make_submission(db_session, task1.id, stu1)
        _make_submission(db_session, task2.id, stu2)

        _make_evaluation_record(
            db_session, project.id, task1.id, stu1,
            status=EvaluationStatus.PUBLISHED,
        )
        _make_evaluation_record(
            db_session, project.id, task2.id, stu2,
            status=EvaluationStatus.PUBLISHED,
        )

        actor = _Actor(user_id="teacher-1", role=Role.TEACHER)
        summary = service.get_closure_summary(db_session, actor, project.id)

        assert summary["task_count"] == 2
        assert summary["student_count"] == 2
        assert summary["evaluation_count"] == 2
        # 订正率与证据完整率应为 [0, 1] 之间
        assert 0.0 <= summary["revision_rate"] <= 1.0
        assert 0.0 <= summary["evidence_completeness_rate"] <= 1.0
        assert "improvement_effect" in summary


# ============================================================
# 验收 5：教师反思
# ============================================================

class TestTeacherReflection:
    """教师结项反思文本被持久化。"""

    def test_teacher_reflection_saved(self, db_session):
        project = _make_project(db_session, status=ProjectStatus.COMPLETED)
        actor = _Actor(user_id="teacher-1", role=Role.TEACHER)

        reflection = (
            f"本次项目学生参与度高，但评价环节可改进-{uuid.uuid4().hex[:6]}"
        )
        service.save_teacher_reflection(db_session, actor, project.id, reflection)

        # 重新查询验证持久化（service 内部 commit 后字段已落库）
        from app.modules.projects.repository import ProjectRepository
        project_repo = ProjectRepository(db_session)
        refreshed = project_repo.get(project.id)
        assert refreshed.teacher_reflection == reflection


# ============================================================
# 验收 6：案例归档脱敏预览
# ============================================================

class TestCaseAnonymization:
    """案例归档脱敏预览隐藏学生真实姓名。"""

    def test_case_anonymization_hides_student_names(self, db_session):
        project = _make_project(db_session, status=ProjectStatus.COMPLETED)
        cls = _make_class(db_session, school_id="school-1")
        _assign_project_to_class(db_session, project.id, cls.id)
        task = _make_task(db_session, project.id)

        # 创建两个真实学生，姓名为可识别的中文
        student_a = _make_student_user(
            db_session, display_name="张三丰", class_id=cls.id
        )
        student_b = _make_student_user(
            db_session, display_name="李四娘", class_id=cls.id
        )

        _make_submission(db_session, task.id, student_a.id)
        _make_submission(db_session, task.id, student_b.id)

        actor = _Actor(user_id="teacher-1", role=Role.TEACHER)
        preview = service.preview_case_anonymization(
            db_session, actor, project.id
        )

        assert preview["anonymized"] is True
        assert preview["project"]["id"] == project.id

        students = preview["students"]
        assert len(students) == 2

        # 应有编号代替真实姓名
        codes = [s["code"] for s in students]
        assert any(c.startswith("学生-") for c in codes)

        # 真实姓名不应出现在响应中
        import json
        serialized = json.dumps(preview, ensure_ascii=False)
        assert "张三丰" not in serialized
        assert "李四娘" not in serialized

        # 联系方式应被隐藏标记
        for s in students:
            assert s["contact_hidden"] is True
            assert s["real_name"] is None
