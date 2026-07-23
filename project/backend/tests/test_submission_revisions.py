"""提交订正版本与状态机测试（计划 Task 6 验收标准 1/2/4/5）。

覆盖：
- 验收 1：草稿→首次提交→退回→再次提交→最终确认状态机；非法跃迁返回 409。
- 验收 2：学生项目可见性、分层资源授权和敏感信息隐藏。
- 验收 4：客户端自动保存与服务端幂等提交键。
- 验收 5：订正版本和二次评价入口。

不伪造数据：状态机非法跃迁返回 409，幂等重复提交不生成新版本，
未发布评价不可见，教师私有备注不暴露给学生。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import AppException
from app.models.enums import (
    EvaluationSource,
    EvaluationStatus,
    EvaluationSubjectType,
    ResourceTier,
    ReviewStatus,
    SubmissionReviewStatus,
    TeachingStage,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.project import Project, ProjectClass, ProjectStatus
from app.models.resource import Resource
from app.models.school import Class
from app.models.submission import Submission
from app.models.submission_revision import SubmissionRevision  # noqa: F401 — register model with Base.metadata
from app.models.task import Task, TaskStatus, TaskType
from app.models.user import Role, User
from app.modules.submissions import service


# ── 测试辅助 ──────────────────────────────────────────────────

class _Actor:
    """轻量 actor 替身，避免依赖完整 User 注册流程。"""

    def __init__(
        self,
        user_id: str = "student-1",
        role: Role = Role.STUDENT,
        class_id: str | None = None,
        school_id: str | None = None,
    ):
        self.id = user_id
        self.role = role
        self.class_id = class_id
        self.school_id = school_id
        self.is_active = True


def _make_project(db_session, creator_id="teacher-1", status=ProjectStatus.ACTIVE) -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        title="订正测试项目",
        status=status,
        creator_id=creator_id,
        is_template=False,
    )
    db_session.add(project)
    db_session.flush()
    return project


def _make_task(db_session, project_id: str, created_by="teacher-1") -> Task:
    task = Task(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title="订正测试任务",
        description="测试订正状态机",
        task_type=TaskType.INDIVIDUAL,
        status=TaskStatus.PENDING,
        max_score=100,
        created_by=created_by,
    )
    db_session.add(task)
    db_session.flush()
    return task


def _make_class(db_session, class_id="class-1", school_id="school-1") -> Class:
    cls = Class(
        id=class_id,
        school_id=school_id,
        grade="grade-7",
        name="测试班级",
    )
    db_session.add(cls)
    db_session.flush()
    return cls


def _assign_project_to_class(db_session, project_id: str, class_id: str):
    db_session.add(ProjectClass(project_id=project_id, class_id=class_id))
    db_session.flush()


def _make_resource(
    db_session,
    project_id: str,
    tier: ResourceTier,
    review_status: ReviewStatus = ReviewStatus.PUBLISHED,
    uploaded_by="teacher-1",
) -> Resource:
    resource = Resource(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=f"{tier.value}-资源",
        res_type="document",
        uploaded_by=uploaded_by,
        tier=tier,
        stage=TeachingStage.IN_CLASS,
        review_status=review_status,
    )
    db_session.add(resource)
    db_session.flush()
    return resource


def _make_evaluation_record(
    db_session,
    project_id: str,
    task_id: str,
    student_id: str,
    status: EvaluationStatus = EvaluationStatus.PUBLISHED,
    total_score: float = 85.0,
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
    )
    db_session.add(record)
    db_session.flush()
    return record


# ============================================================
# 验收 1：草稿→首次提交→退回→再次提交→最终确认状态机
# ============================================================

class TestSubmissionRevisionStateMachine:
    """验收 1：订正状态机覆盖合法跃迁与非法跃迁（409）。"""

    def test_full_lifecycle_draft_submit_return_resubmit_finalize(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        # 1. 保存草稿
        draft = service.save_draft(db_session, task.id, student.id, "草稿内容", [])
        assert draft.review_status == SubmissionReviewStatus.DRAFT

        # 2. 首次提交（幂等）
        key1 = str(uuid.uuid4())
        sub, rev1, created1 = service.submit_with_idempotency(
            db_session, task.id, student.id, "首次提交内容", [], key1
        )
        assert created1 is True
        assert sub.review_status == SubmissionReviewStatus.SUBMITTED
        assert rev1.attempt_number == 1
        assert rev1.review_status == SubmissionReviewStatus.SUBMITTED

        # 3. 教师退回
        returned = service.return_submission(
            db_session, sub.id,
            teacher_comment="需要补充细节",
            teacher_private_note="学生理解不深",
        )
        assert returned.review_status == SubmissionReviewStatus.RETURNED

        # 4. 学生再次提交
        key2 = str(uuid.uuid4())
        sub2, rev2, created2 = service.submit_with_idempotency(
            db_session, task.id, student.id, "订正后内容", [], key2
        )
        assert created2 is True
        assert sub2.review_status == SubmissionReviewStatus.RESUBMITTED
        assert rev2.attempt_number == 2

        # 5. 教师最终确认
        finalized = service.finalize_submission(
            db_session, sub2.id, teacher_comment="订正合格"
        )
        assert finalized.review_status == SubmissionReviewStatus.FINALIZED

        # 验证版本记录
        revisions = service.list_revisions(db_session, sub2.id)
        assert len(revisions) == 2
        assert revisions[0].attempt_number == 1
        assert revisions[1].attempt_number == 2

    def test_illegal_transition_from_finalized_to_submitted(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        # 直接造一个 SUBMITTED 状态提交
        sub = Submission(
            id=str(uuid.uuid4()),
            task_id=task.id,
            student_id=student.id,
            content="内容",
            status="submitted",
            review_status=SubmissionReviewStatus.SUBMITTED,
        )
        db_session.add(sub)
        db_session.flush()

        # SUBMITTED -> FINALIZED 是非法跃迁（需先 teacher_reviewed）
        with pytest.raises(AppException) as exc_info:
            service.transition_submission(
                db_session, sub.id, SubmissionReviewStatus.FINALIZED
            )
        assert exc_info.value.status_code == 409

    def test_illegal_transition_from_draft_to_finalized(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        draft = service.save_draft(db_session, task.id, student.id, "草稿", [])
        # DRAFT -> FINALIZED 非法
        with pytest.raises(AppException) as exc_info:
            service.transition_submission(
                db_session, draft.id, SubmissionReviewStatus.FINALIZED
            )
        assert exc_info.value.status_code == 409

    def test_cannot_submit_when_already_submitted(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        # 首次提交
        key1 = str(uuid.uuid4())
        service.submit_with_idempotency(
            db_session, task.id, student.id, "内容", [], key1
        )
        # 再次提交（无退回）应失败
        key2 = str(uuid.uuid4())
        with pytest.raises(AppException) as exc_info:
            service.submit_with_idempotency(
                db_session, task.id, student.id, "内容2", [], key2
            )
        assert exc_info.value.status_code == 409


# ============================================================
# 验收 4：幂等提交键
# ============================================================

class TestIdempotencyKey:
    """验收 4：同一 idempotency_key 重复提交不生成重复版本。"""

    def test_duplicate_idempotency_key_returns_existing(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        key = str(uuid.uuid4())
        # 第一次提交
        sub1, rev1, created1 = service.submit_with_idempotency(
            db_session, task.id, student.id, "首次内容", [], key
        )
        assert created1 is True

        # 重复点击：同一 key
        sub2, rev2, created2 = service.submit_with_idempotency(
            db_session, task.id, student.id, "重复内容", [], key
        )
        assert created2 is False
        assert rev2.id == rev1.id
        assert sub2.id == sub1.id

        # 只有一个版本
        revisions = service.list_revisions(db_session, sub1.id)
        assert len(revisions) == 1

    def test_different_keys_create_different_revisions(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        key1 = str(uuid.uuid4())
        service.submit_with_idempotency(
            db_session, task.id, student.id, "v1", [], key1
        )
        # 退回后用不同 key 再提交
        sub = service.get_my_submission(db_session, task.id, student.id)
        service.return_submission(db_session, sub.id)

        key2 = str(uuid.uuid4())
        _, rev2, created2 = service.submit_with_idempotency(
            db_session, task.id, student.id, "v2", [], key2
        )
        assert created2 is True
        assert rev2.attempt_number == 2


# ============================================================
# 验收 5：二次评价入口
# ============================================================

class TestReassessment:
    """验收 5：finalized 后学生可发起二次评价。"""

    def test_reassessment_creates_new_revision(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        # 完整走到 finalized
        key1 = str(uuid.uuid4())
        sub, _, _ = service.submit_with_idempotency(
            db_session, task.id, student.id, "内容", [], key1
        )
        service.return_submission(db_session, sub.id)
        key2 = str(uuid.uuid4())
        service.submit_with_idempotency(
            db_session, task.id, student.id, "订正", [], key2
        )
        service.finalize_submission(db_session, sub.id)

        # 学生发起二次评价
        updated = service.request_reassessment(
            db_session, sub.id, student.id, "希望重新评价此题"
        )
        assert updated.review_status == SubmissionReviewStatus.RESUBMITTED

        revisions = service.list_revisions(db_session, sub.id)
        # 应有 3 个版本：首次、订正、二次评价
        assert len(revisions) == 3
        assert revisions[-1].reassess_reason == "希望重新评价此题"

    def test_reassessment_blocked_when_not_finalized(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        key1 = str(uuid.uuid4())
        sub, _, _ = service.submit_with_idempotency(
            db_session, task.id, student.id, "内容", [], key1
        )
        # SUBMITTED 状态不能发起二次评价
        with pytest.raises(AppException) as exc_info:
            service.request_reassessment(db_session, sub.id, student.id, "理由")
        assert exc_info.value.status_code == 409

    def test_reassessment_blocked_for_other_student(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)
        other = _Actor(user_id="stu-2", role=Role.STUDENT)

        key1 = str(uuid.uuid4())
        sub, _, _ = service.submit_with_idempotency(
            db_session, task.id, student.id, "内容", [], key1
        )
        service.finalize_submission(
            db_session, sub.id
        ) if False else None
        # 直接造 finalized 状态
        sub.review_status = SubmissionReviewStatus.TEACHER_REVIEWED
        db_session.flush()
        service.finalize_submission(db_session, sub.id)

        # 其他学生不能对别人的提交发起二次评价
        with pytest.raises(AppException) as exc_info:
            service.request_reassessment(db_session, sub.id, other.id, "理由")
        assert exc_info.value.status_code == 403

    def test_reassessment_requires_reason(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        key1 = str(uuid.uuid4())
        sub, _, _ = service.submit_with_idempotency(
            db_session, task.id, student.id, "内容", [], key1
        )
        sub.review_status = SubmissionReviewStatus.TEACHER_REVIEWED
        db_session.flush()
        service.finalize_submission(db_session, sub.id)

        with pytest.raises(AppException) as exc_info:
            service.request_reassessment(db_session, sub.id, student.id, "")
        assert exc_info.value.status_code == 400


# ============================================================
# 验收 2：学生项目可见性、分层资源授权和敏感信息隐藏
# ============================================================

class TestStudentProjectVisibility:
    """验收 2：学生只能访问自己班级被分配的项目。"""

    def test_student_can_view_assigned_project(self, db_session):
        project = _make_project(db_session)
        _make_task(db_session, project.id)
        # 使用 uuid 班级 ID 避免跨测试数据累积导致的 UNIQUE 冲突
        # （conftest 的 autouse fixture 会 commit 测试数据）
        class_id = f"class-{uuid.uuid4().hex[:8]}"
        _make_class(db_session, class_id=class_id)
        _assign_project_to_class(db_session, project.id, class_id)

        view = service.get_student_project_view(db_session, project.id, class_id)
        assert view["project"]["id"] == project.id
        assert view["project"]["title"] == "订正测试项目"

    def test_student_cannot_view_unassigned_project(self, db_session):
        project = _make_project(db_session)
        _make_task(db_session, project.id)
        # 使用 uuid 班级 ID 避免跨测试数据累积导致的 UNIQUE 冲突
        assigned_class = f"class-{uuid.uuid4().hex[:8]}"
        unassigned_class = f"class-{uuid.uuid4().hex[:8]}"
        _make_class(db_session, class_id=assigned_class)
        _make_class(db_session, class_id=unassigned_class)
        _assign_project_to_class(db_session, project.id, assigned_class)

        # 未被分配的班级应 403
        with pytest.raises(AppException) as exc_info:
            service.get_student_project_view(
                db_session, project.id, unassigned_class
            )
        assert exc_info.value.status_code == 403


class TestTieredResourceAuthorization:
    """验收 2：分层资源授权，仅 PUBLISHED 资源可见，按 tier 分组。"""

    def test_only_published_resources_visible(self, db_session):
        project = _make_project(db_session)
        _make_resource(db_session, project.id, ResourceTier.FOUNDATION, ReviewStatus.PUBLISHED)
        _make_resource(db_session, project.id, ResourceTier.ENHANCEMENT, ReviewStatus.DRAFT)
        _make_resource(db_session, project.id, ResourceTier.EXTENSION, ReviewStatus.PUBLISHED)

        view = service.get_student_project_view(db_session, project.id, None)
        resources = view["resources"]
        # foundation 1 个（PUBLISHED），enhancement 0 个（DRAFT 被过滤），extension 1 个
        assert len(resources["foundation"]) == 1
        assert len(resources["enhancement"]) == 0
        assert len(resources["extension"]) == 1

    def test_resources_grouped_by_tier_with_friendly_labels(self, db_session):
        project = _make_project(db_session)
        _make_resource(db_session, project.id, ResourceTier.FOUNDATION, ReviewStatus.PUBLISHED)
        _make_resource(db_session, project.id, ResourceTier.ENHANCEMENT, ReviewStatus.PUBLISHED)
        _make_resource(db_session, project.id, ResourceTier.EXTENSION, ReviewStatus.PUBLISHED)

        view = service.get_student_project_view(db_session, project.id, None)
        resources = view["resources"]
        assert resources["foundation"][0]["tier_label"] == "基础资源"
        assert resources["enhancement"][0]["tier_label"] == "进阶资源"
        assert resources["extension"][0]["tier_label"] == "拓展资源"
        # 不展示负面分层名称
        for tier_key in ("foundation", "enhancement", "extension"):
            for r in resources[tier_key]:
                assert "差" not in r["tier_label"]
                assert "低" not in r["tier_label"]

    def test_unpublished_resources_hidden_from_student(self, db_session):
        project = _make_project(db_session)
        # 所有资源都是 DRAFT，学生应看不到任何资源
        _make_resource(db_session, project.id, ResourceTier.FOUNDATION, ReviewStatus.DRAFT)
        _make_resource(db_session, project.id, ResourceTier.ENHANCEMENT, ReviewStatus.PENDING_REVIEW)

        view = service.get_student_project_view(db_session, project.id, None)
        resources = view["resources"]
        assert len(resources["foundation"]) == 0
        assert len(resources["enhancement"]) == 0
        assert len(resources["extension"]) == 0


class TestSensitiveInfoHiding:
    """验收 2：教师私有备注不暴露给学生，未发布评价不可见。"""

    def test_teacher_private_note_hidden_from_student(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)
        teacher = _Actor(user_id="tea-1", role=Role.TEACHER)

        # 提交 + 退回（带私有备注）
        key = str(uuid.uuid4())
        sub, _, _ = service.submit_with_idempotency(
            db_session, task.id, student.id, "内容", [], key
        )
        service.return_submission(
            db_session, sub.id,
            teacher_comment="公开反馈",
            teacher_private_note="这是私有备注",
        )

        # 学生视角版本：不含 teacher_private_note
        feedback = service.get_student_feedback(db_session, sub.id)
        for rev in feedback["revisions"]:
            assert "teacher_private_note" not in rev
            assert rev.get("teacher_comment") in (None, "公开反馈")

        # 教师视角版本：含 teacher_private_note
        from app.modules.submissions import policy as sub_policy
        teacher_view = sub_policy.hide_submission_sensitive_fields(sub, teacher)
        assert "teacher_private_note" not in teacher_view  # Submission 层无此字段

        revisions_full = service.list_revisions(db_session, sub.id)
        full_dicts = [service.revision_dict(r) for r in revisions_full]
        assert any(d["teacher_private_note"] == "这是私有备注" for d in full_dicts)

    def test_unpublished_evaluation_hidden_from_student(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)

        # 提交
        key = str(uuid.uuid4())
        sub, _, _ = service.submit_with_idempotency(
            db_session, task.id, student.id, "内容", [], key
        )

        # 创建草稿评价（未发布）+ 已发布评价
        _make_evaluation_record(
            db_session, project.id, task.id, student.id,
            status=EvaluationStatus.DRAFT, total_score=50.0,
        )
        _make_evaluation_record(
            db_session, project.id, task.id, student.id,
            status=EvaluationStatus.PUBLISHED, total_score=85.0,
        )

        feedback = service.get_student_feedback(db_session, sub.id)
        # 仅 1 条已发布评价可见
        assert len(feedback["evaluations"]) == 1
        assert feedback["evaluations"][0]["total_score"] == 85.0

    def test_student_cannot_read_other_student_submission(self, db_session):
        from app.modules.submissions import policy as sub_policy

        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student = _Actor(user_id="stu-1", role=Role.STUDENT)
        other = _Actor(user_id="stu-2", role=Role.STUDENT)

        key = str(uuid.uuid4())
        sub, _, _ = service.submit_with_idempotency(
            db_session, task.id, student.id, "我的提交", [], key
        )

        # 其他学生不能读取
        with pytest.raises(AppException) as exc_info:
            sub_policy.ensure_student_can_read_submission(db_session, other, sub)
        assert exc_info.value.status_code == 403


# ============================================================
# 验收 2：学生项目空间任务可见性
# ============================================================

class TestStudentTaskVisibility:
    """学生只能看到已发布状态的任务（draft/scheduled 不可见）。"""

    def test_draft_tasks_hidden_from_student(self, db_session):
        from app.models.enums import TaskPublishStatus

        project = _make_project(db_session)
        # published 任务
        task1 = _make_task(db_session, project.id)
        task1.publish_status = TaskPublishStatus.PUBLISHED
        # draft 任务
        task2 = _make_task(db_session, project.id)
        task2.title = "草稿任务"
        task2.publish_status = TaskPublishStatus.DRAFT
        db_session.flush()

        view = service.get_student_project_view(db_session, project.id, None)
        titles = [t["title"] for t in view["tasks"]]
        assert "订正测试任务" in titles
        assert "草稿任务" not in titles


# ============================================================
# 成长档案：不补零、不排名
# ============================================================

class TestGrowthPortfolio:
    """验收 3.7.5：缺失周期显示未采集，不补零；不提供公开横向排名。"""

    def test_empty_portfolio_returns_uncollected_note(self, db_session):
        student = _Actor(user_id="stu-empty", role=Role.STUDENT)
        portfolio = service.get_growth_portfolio(db_session, student.id)
        assert portfolio["trajectories"] == []
        # 不补零：average_score 为 None 而非 0
        assert portfolio["evidence_summary"]["average_score"] is None
        assert "未采集" in portfolio["note"]
        assert "排名" in portfolio["note"]

    def test_portfolio_aggregates_trajectories(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        # 使用唯一 student_id 避免跨测试数据累积污染
        # （service 内部 db.commit() 会持久化提交，导致全局计数失真）
        student_id = f"stu-portfolio-{uuid.uuid4().hex[:8]}"
        student = _Actor(user_id=student_id, role=Role.STUDENT)

        key = str(uuid.uuid4())
        sub, _, _ = service.submit_with_idempotency(
            db_session, task.id, student.id, "内容", [], key
        )
        service.return_submission(db_session, sub.id)
        key2 = str(uuid.uuid4())
        service.submit_with_idempotency(
            db_session, task.id, student.id, "订正", [], key2
        )

        portfolio = service.get_growth_portfolio(db_session, student.id)
        assert len(portfolio["trajectories"]) == 1
        traj = portfolio["trajectories"][0]
        assert traj["attempt_count"] == 2
        assert traj["task_title"] == "订正测试任务"
