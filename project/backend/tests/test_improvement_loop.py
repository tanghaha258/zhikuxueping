"""学情改进与二次评价领域测试（计划 Task 7 验收标准 1/2/3/4/5）。

覆盖：
- 验收 1：建议必须引用评价证据（无 evidence_reference 抛 400；评价记录不存在抛 404）。
- 验收 2：建议采用/修改/拒绝及原因留痕（reason 必填、modified 需 modified_description、
  状态机非法跃迁返回 409）。
- 验收 3：改进任务与二次评价前后关联（created_from_evaluation_id 追溯、
  second_evaluation 前后分数差）。
- 验收 4：建议转任务可同步发布为正式 Task（学生可见）。
- 验收 5：二次评价前后对比摘要（不伪造细节，基于证据生成）。

不伪造数据、不产生伪成功结果：无证据不创建建议；非法状态跃迁返回 409；
二次评价必须针对同一学生同一项目。
"""
from __future__ import annotations

import uuid

import pytest

# 显式导入模型模块，使 SQLAlchemy 在 Base.metadata 注册表结构
# （新模型未注册到 app/models/__init__.py 时由测试侧显式触发模块加载）
import app.models.improvement  # noqa: F401
from app.core.exceptions import AppException
from app.models.enums import (
    EvaluationSource,
    EvaluationStatus,
    EvaluationSubjectType,
    ImprovementSuggestionStatus,
    ImprovementTaskType,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus, TaskType
from app.models.user import Role
from app.modules.improvements import service
from app.schemas.improvement import (
    ImprovementSuggestionCreate,
    ImprovementTaskCreate,
    SecondEvaluationCreate,
    SuggestionDecisionRequest,
)


# ── 测试辅助 ──────────────────────────────────────────────────
class _Actor:
    """轻量 actor 替身，避免依赖完整 User 注册流程。"""

    def __init__(
        self,
        user_id: str = "teacher-1",
        role: Role = Role.TEACHER,
        school_id: str | None = None,
        class_id: str | None = None,
    ):
        self.id = user_id
        self.role = role
        self.school_id = school_id
        self.class_id = class_id
        self.is_active = True


def _make_project(db_session, creator_id="teacher-1") -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        title="改进循环测试项目",
        status=ProjectStatus.ACTIVE,
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
        title="改进循环测试任务",
        description="用于改进循环追溯",
        task_type=TaskType.INDIVIDUAL,
        status=TaskStatus.PENDING,
        max_score=100,
        created_by=created_by,
    )
    db_session.add(task)
    db_session.flush()
    return task


def _make_evaluation_record(
    db_session,
    *,
    project_id: str,
    task_id: str,
    student_id: str,
    evaluator_id: str = "teacher-1",
    status: EvaluationStatus = EvaluationStatus.PUBLISHED,
    total_score: float = 70.0,
) -> EvaluationRecord:
    """创建评价记录（改进建议与二次评价的证据来源）。"""
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


def _unique_student_id() -> str:
    """生成唯一学生 ID，避免 service 层 commit 跨测试累积污染。"""
    return f"stu-improve-{uuid.uuid4().hex[:8]}"


# ============================================================
# 验收 1：建议必须引用评价证据
# ============================================================
class TestSuggestionRequiresEvidence:
    """验收 1：无 evidence_reference 抛 400；评价记录不存在抛 404。"""

    def test_create_suggestion_rejects_empty_evidence_reference(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project.creator_id)

        # evidence_reference 为空字符串 → 400
        data = ImprovementSuggestionCreate(
            project_id=project.id,
            created_from_evaluation_id=record.id,
            evidence_reference="   ",
            title="基础巩固建议",
            description="针对薄弱知识点",
            student_id=student_id,
        )
        with pytest.raises(AppException) as exc_info:
            service.create_suggestion(db_session, actor, data)
        assert exc_info.value.status_code == 400
        assert "证据" in exc_info.value.message

    def test_create_suggestion_rejects_missing_evaluation_record(self, db_session):
        project = _make_project(db_session)
        _make_task(db_session, project.id)
        student_id = _unique_student_id()
        actor = _Actor(user_id=project.creator_id)

        # created_from_evaluation_id 指向不存在的评价记录 → 404
        data = ImprovementSuggestionCreate(
            project_id=project.id,
            created_from_evaluation_id=str(uuid.uuid4()),
            evidence_reference="evaluation_scores:fake-id",
            title="建议",
            description="描述",
            student_id=student_id,
        )
        with pytest.raises(AppException) as exc_info:
            service.create_suggestion(db_session, actor, data)
        assert exc_info.value.status_code == 404

    def test_create_suggestion_rejects_cross_project_evaluation(self, db_session):
        """评价记录不属于本项目 → 400（不能跨项目引用证据）。"""
        project_a = _make_project(db_session, creator_id="teacher-1")
        project_b = _make_project(db_session, creator_id="teacher-1")
        task_b = _make_task(db_session, project_b.id)
        student_id = _unique_student_id()
        record_b = _make_evaluation_record(
            db_session,
            project_id=project_b.id,
            task_id=task_b.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project_a.creator_id)

        data = ImprovementSuggestionCreate(
            project_id=project_a.id,
            created_from_evaluation_id=record_b.id,
            evidence_reference="evaluation_scores:abc",
            title="跨项目建议",
            description="不应允许",
            student_id=student_id,
        )
        with pytest.raises(AppException) as exc_info:
            service.create_suggestion(db_session, actor, data)
        assert exc_info.value.status_code == 400

    def test_create_suggestion_success_with_valid_evidence(self, db_session):
        """有效证据下创建建议成功，状态为 DRAFT。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project.creator_id)

        data = ImprovementSuggestionCreate(
            project_id=project.id,
            created_from_evaluation_id=record.id,
            evidence_reference=f"evaluation_records:{record.id}",
            title="基础巩固建议",
            description="针对分数薄弱点",
            student_id=student_id,
        )
        suggestion = service.create_suggestion(db_session, actor, data)
        assert suggestion.status == ImprovementSuggestionStatus.DRAFT
        assert suggestion.created_from_evaluation_id == record.id
        assert suggestion.evidence_reference == f"evaluation_records:{record.id}"
        assert suggestion.created_by == actor.id


# ============================================================
# 验收 2：建议采用/修改/拒绝留痕与状态机
# ============================================================
class TestSuggestionDecisionAndAuditTrail:
    """验收 2：reason 必填、modified 需 modified_description、状态机非法跃迁 409。"""

    def _make_suggestion(self, db_session, actor_id="teacher-1") -> tuple:
        project = _make_project(db_session, creator_id=actor_id)
        task = _make_task(db_session, project.id, created_by=actor_id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=actor_id)
        data = ImprovementSuggestionCreate(
            project_id=project.id,
            created_from_evaluation_id=record.id,
            evidence_reference=f"evaluation_records:{record.id}",
            title="待决定建议",
            description="原描述",
            student_id=student_id,
        )
        suggestion = service.create_suggestion(db_session, actor, data)
        return project, task, student_id, record, suggestion, actor

    def test_adopt_suggestion_records_reason_and_decider(self, db_session):
        project, task, student_id, record, suggestion, actor = self._make_suggestion(db_session)

        decided = service.decide_suggestion(
            db_session,
            actor,
            suggestion.id,
            SuggestionDecisionRequest(
                status=ImprovementSuggestionStatus.ADOPTED,
                reason="建议合理，可直接落地",
            ),
        )
        assert decided.status == ImprovementSuggestionStatus.ADOPTED
        assert decided.decision_reason == "建议合理，可直接落地"
        assert decided.decided_by == actor.id
        assert decided.decided_at is not None

    def test_modify_suggestion_requires_modified_description(self, db_session):
        project, task, student_id, record, suggestion, actor = self._make_suggestion(db_session)

        # modified 状态但缺少 modified_description → 400
        with pytest.raises(AppException) as exc_info:
            service.decide_suggestion(
                db_session,
                actor,
                suggestion.id,
                SuggestionDecisionRequest(
                    status=ImprovementSuggestionStatus.MODIFIED,
                    reason="部分采用，需调整描述",
                    modified_description="   ",
                ),
            )
        assert exc_info.value.status_code == 400

    def test_modify_suggestion_records_modified_description(self, db_session):
        project, task, student_id, record, suggestion, actor = self._make_suggestion(db_session)

        decided = service.decide_suggestion(
            db_session,
            actor,
            suggestion.id,
            SuggestionDecisionRequest(
                status=ImprovementSuggestionStatus.MODIFIED,
                reason="调整后采用",
                modified_description="修改后的建议描述",
            ),
        )
        assert decided.status == ImprovementSuggestionStatus.MODIFIED
        assert decided.modified_description == "修改后的建议描述"
        assert decided.decision_reason == "调整后采用"

    def test_reject_suggestion_records_reason(self, db_session):
        project, task, student_id, record, suggestion, actor = self._make_suggestion(db_session)

        decided = service.decide_suggestion(
            db_session,
            actor,
            suggestion.id,
            SuggestionDecisionRequest(
                status=ImprovementSuggestionStatus.REJECTED,
                reason="证据不充分",
            ),
        )
        assert decided.status == ImprovementSuggestionStatus.REJECTED
        assert decided.decision_reason == "证据不充分"

    def test_decide_suggestion_requires_reason(self, db_session):
        project, task, student_id, record, suggestion, actor = self._make_suggestion(db_session)

        # reason 为纯空白 → 400（留痕要求；schema min_length=1 已拦截空串，
        # 此处用空白串触发服务层 .strip() 校验）
        with pytest.raises(AppException) as exc_info:
            service.decide_suggestion(
                db_session,
                actor,
                suggestion.id,
                SuggestionDecisionRequest(
                    status=ImprovementSuggestionStatus.ADOPTED,
                    reason="   ",
                ),
            )
        assert exc_info.value.status_code == 400
        assert "原因" in exc_info.value.message

    def test_illegal_transition_from_adopted_to_rejected(self, db_session):
        """终态后不可变更：adopted → rejected 非法跃迁返回 409。"""
        project, task, student_id, record, suggestion, actor = self._make_suggestion(db_session)
        service.decide_suggestion(
            db_session,
            actor,
            suggestion.id,
            SuggestionDecisionRequest(
                status=ImprovementSuggestionStatus.ADOPTED,
                reason="已采用",
            ),
        )

        with pytest.raises(AppException) as exc_info:
            service.decide_suggestion(
                db_session,
                actor,
                suggestion.id,
                SuggestionDecisionRequest(
                    status=ImprovementSuggestionStatus.REJECTED,
                    reason="尝试再次决定",
                ),
            )
        assert exc_info.value.status_code == 409

    def test_illegal_transition_from_rejected_to_adopted(self, db_session):
        """终态后不可变更：rejected → adopted 非法跃迁返回 409。"""
        project, task, student_id, record, suggestion, actor = self._make_suggestion(db_session)
        service.decide_suggestion(
            db_session,
            actor,
            suggestion.id,
            SuggestionDecisionRequest(
                status=ImprovementSuggestionStatus.REJECTED,
                reason="已拒绝",
            ),
        )

        with pytest.raises(AppException) as exc_info:
            service.decide_suggestion(
                db_session,
                actor,
                suggestion.id,
                SuggestionDecisionRequest(
                    status=ImprovementSuggestionStatus.ADOPTED,
                    reason="尝试再次决定",
                ),
            )
        assert exc_info.value.status_code == 409

    def test_decide_nonexistent_suggestion_returns_404(self, db_session):
        actor = _Actor()
        with pytest.raises(AppException) as exc_info:
            service.decide_suggestion(
                db_session,
                actor,
                "nonexistent-suggestion-id",
                SuggestionDecisionRequest(
                    status=ImprovementSuggestionStatus.ADOPTED,
                    reason="理由",
                ),
            )
        assert exc_info.value.status_code == 404


# ============================================================
# 验收 3/4：改进任务可追溯到原评价
# ============================================================
class TestImprovementTaskTraceability:
    """验收 3/4：改进任务 created_from_evaluation_id 追溯原评价；
    publish_task=True 时同步创建正式 Task。"""

    def test_create_improvement_task_traces_to_evaluation(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project.creator_id)

        improvement_task = service.create_improvement_task(
            db_session,
            actor,
            ImprovementTaskCreate(
                project_id=project.id,
                created_from_evaluation_id=record.id,
                task_type=ImprovementTaskType.FOUNDATION_CONSOLIDATION,
                title="基础巩固改进任务",
                description="针对薄弱知识点",
                original_task_id=task.id,
                publish_task=False,
            ),
        )
        # 验收：改进任务可追溯到原评价
        assert improvement_task.created_from_evaluation_id == record.id
        assert improvement_task.original_task_id == task.id
        assert improvement_task.task_type == ImprovementTaskType.FOUNDATION_CONSOLIDATION
        # 未发布为正式 Task 时 generated_task_id 为空
        assert improvement_task.generated_task_id is None

    def test_publish_task_creates_visible_formal_task(self, db_session):
        """publish_task=True 时同步创建正式 Task，学生可见。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project.creator_id)

        improvement_task = service.create_improvement_task(
            db_session,
            actor,
            ImprovementTaskCreate(
                project_id=project.id,
                created_from_evaluation_id=record.id,
                task_type=ImprovementTaskType.ENHANCEMENT_APPLICATION,
                title="提升应用改进任务",
                description="发布给学生",
                publish_task=True,
            ),
        )
        assert improvement_task.generated_task_id is not None
        # 验证正式 Task 已创建并可被查询
        formal_task = db_session.get(Task, improvement_task.generated_task_id)
        assert formal_task is not None
        assert formal_task.title == "提升应用改进任务"
        # 学生可见（publish_status=PUBLISHED）
        from app.models.enums import TaskPublishStatus
        assert formal_task.publish_status == TaskPublishStatus.PUBLISHED

    def test_create_improvement_task_rejects_missing_evaluation(self, db_session):
        """评价记录不存在 → 404。"""
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)

        with pytest.raises(AppException) as exc_info:
            service.create_improvement_task(
                db_session,
                actor,
                ImprovementTaskCreate(
                    project_id=project.id,
                    created_from_evaluation_id=str(uuid.uuid4()),
                    task_type=ImprovementTaskType.EXTENSION_TRANSFER,
                    title="拓展任务",
                    description="不应创建",
                ),
            )
        assert exc_info.value.status_code == 404

    def test_create_improvement_task_validates_linked_suggestion(self, db_session):
        """关联建议不存在 → 404；不属于本项目 → 400。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project.creator_id)

        # link_suggestion_id 指向不存在的建议 → 404
        with pytest.raises(AppException) as exc_info:
            service.create_improvement_task(
                db_session,
                actor,
                ImprovementTaskCreate(
                    project_id=project.id,
                    created_from_evaluation_id=record.id,
                    task_type=ImprovementTaskType.FOUNDATION_CONSOLIDATION,
                    title="关联不存在建议",
                    description="测试",
                    link_suggestion_id=str(uuid.uuid4()),
                ),
            )
        assert exc_info.value.status_code == 404

    def test_improvement_task_traces_back_to_suggestion(self, db_session):
        """改进任务可追溯到原建议（link_suggestion_id）。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project.creator_id)

        # 先创建建议
        suggestion = service.create_suggestion(
            db_session,
            actor,
            ImprovementSuggestionCreate(
                project_id=project.id,
                created_from_evaluation_id=record.id,
                evidence_reference=f"evaluation_records:{record.id}",
                title="建议",
                description="描述",
                student_id=student_id,
            ),
        )
        # 再创建改进任务并关联建议
        improvement_task = service.create_improvement_task(
            db_session,
            actor,
            ImprovementTaskCreate(
                project_id=project.id,
                created_from_evaluation_id=record.id,
                task_type=ImprovementTaskType.SECOND_EVALUATION,
                title="二次评价测评",
                description="验证改进效果",
                link_suggestion_id=suggestion.id,
            ),
        )
        assert improvement_task.link_suggestion_id == suggestion.id
        assert improvement_task.created_from_evaluation_id == record.id


# ============================================================
# 验收 5：二次评价前后关联与分数差
# ============================================================
class TestSecondEvaluationScoreDelta:
    """验收 5：二次评价关联首次与第二次评价，记录前后分数差。"""

    def test_second_evaluation_records_score_delta(self, db_session):
        """二次评价记录首次与第二次评价总分快照与对比摘要。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        # 首次评价 60 分，第二次评价 85 分 → 提升 25 分
        first = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
            total_score=60.0,
        )
        second = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
            total_score=85.0,
        )
        actor = _Actor(user_id=project.creator_id)

        evaluation = service.create_second_evaluation(
            db_session,
            actor,
            SecondEvaluationCreate(
                project_id=project.id,
                student_id=student_id,
                first_evaluation_id=first.id,
                second_evaluation_id=second.id,
            ),
        )
        assert evaluation.first_evaluation_id == first.id
        assert evaluation.second_evaluation_id == second.id
        assert evaluation.first_score == 60.0
        assert evaluation.second_score == 85.0
        # 未提供 comparison_summary 时服务层基于证据生成草稿
        assert evaluation.comparison_summary is not None
        assert "60" in evaluation.comparison_summary
        assert "85" in evaluation.comparison_summary
        assert "提升" in evaluation.comparison_summary

    def test_second_evaluation_rejects_same_record(self, db_session):
        """首次与第二次评价为同一条记录 → 400。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project.creator_id)

        with pytest.raises(AppException) as exc_info:
            service.create_second_evaluation(
                db_session,
                actor,
                SecondEvaluationCreate(
                    project_id=project.id,
                    student_id=student_id,
                    first_evaluation_id=record.id,
                    second_evaluation_id=record.id,
                ),
            )
        assert exc_info.value.status_code == 400

    def test_second_evaluation_rejects_mismatched_student(self, db_session):
        """两次评价学生不一致 → 400。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_a = _unique_student_id()
        student_b = _unique_student_id()
        first = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_a,
        )
        second = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_b,
        )
        actor = _Actor(user_id=project.creator_id)

        with pytest.raises(AppException) as exc_info:
            service.create_second_evaluation(
                db_session,
                actor,
                SecondEvaluationCreate(
                    project_id=project.id,
                    student_id=student_a,
                    first_evaluation_id=first.id,
                    second_evaluation_id=second.id,
                ),
            )
        assert exc_info.value.status_code == 400

    def test_second_evaluation_rejects_missing_record(self, db_session):
        """首次评价记录不存在 → 404。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        second = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        actor = _Actor(user_id=project.creator_id)

        with pytest.raises(AppException) as exc_info:
            service.create_second_evaluation(
                db_session,
                actor,
                SecondEvaluationCreate(
                    project_id=project.id,
                    student_id=student_id,
                    first_evaluation_id=str(uuid.uuid4()),
                    second_evaluation_id=second.id,
                ),
            )
        assert exc_info.value.status_code == 404

    def test_second_evaluation_accepts_custom_summary(self, db_session):
        """教师可自定义 comparison_summary，服务层不覆盖。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        first = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
            total_score=70.0,
        )
        second = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
            total_score=90.0,
        )
        actor = _Actor(user_id=project.creator_id)

        custom_summary = "教师自定义：学生在二次评价中显著提升，达成度从 70% 提升至 90%。"
        evaluation = service.create_second_evaluation(
            db_session,
            actor,
            SecondEvaluationCreate(
                project_id=project.id,
                student_id=student_id,
                first_evaluation_id=first.id,
                second_evaluation_id=second.id,
                comparison_summary=custom_summary,
            ),
        )
        assert evaluation.comparison_summary == custom_summary

    def test_second_evaluation_links_to_suggestion_and_task(self, db_session):
        """二次评价可关联建议与改进任务，实现全链路追溯。"""
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        first = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
            total_score=55.0,
        )
        second = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
            total_score=80.0,
        )
        actor = _Actor(user_id=project.creator_id)

        # 创建建议
        suggestion = service.create_suggestion(
            db_session,
            actor,
            ImprovementSuggestionCreate(
                project_id=project.id,
                created_from_evaluation_id=first.id,
                evidence_reference=f"evaluation_records:{first.id}",
                title="建议",
                description="描述",
                student_id=student_id,
            ),
        )
        # 创建改进任务
        improvement_task = service.create_improvement_task(
            db_session,
            actor,
            ImprovementTaskCreate(
                project_id=project.id,
                created_from_evaluation_id=first.id,
                task_type=ImprovementTaskType.SECOND_EVALUATION,
                title="二次评价任务",
                description="验证改进",
                link_suggestion_id=suggestion.id,
            ),
        )
        # 创建二次评价并关联建议与改进任务
        evaluation = service.create_second_evaluation(
            db_session,
            actor,
            SecondEvaluationCreate(
                project_id=project.id,
                student_id=student_id,
                first_evaluation_id=first.id,
                second_evaluation_id=second.id,
                link_suggestion_id=suggestion.id,
                link_improvement_task_id=improvement_task.id,
            ),
        )
        assert evaluation.link_suggestion_id == suggestion.id
        assert evaluation.link_improvement_task_id == improvement_task.id
        assert evaluation.first_score == 55.0
        assert evaluation.second_score == 80.0
        # 全链路追溯：二次评价 → 改进任务 → 原建议 → 原评价
        assert improvement_task.created_from_evaluation_id == first.id
        assert suggestion.created_from_evaluation_id == first.id


# ============================================================
# 验收：学生无权操作改进建议
# ============================================================
class TestImprovementAuthorization:
    """学生无权操作改进建议/任务/二次评价。"""

    def test_student_cannot_create_suggestion(self, db_session):
        project = _make_project(db_session)
        task = _make_task(db_session, project.id)
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        student_actor = _Actor(user_id=student_id, role=Role.STUDENT)

        with pytest.raises(AppException) as exc_info:
            service.create_suggestion(
                db_session,
                student_actor,
                ImprovementSuggestionCreate(
                    project_id=project.id,
                    created_from_evaluation_id=record.id,
                    evidence_reference=f"evaluation_records:{record.id}",
                    title="学生尝试创建建议",
                    description="应被拒绝",
                    student_id=student_id,
                ),
            )
        assert exc_info.value.status_code == 403

    def test_non_project_teacher_cannot_create_suggestion(self, db_session):
        """非项目创建者的教师无权管理该项目改进建议。"""
        project = _make_project(db_session, creator_id="teacher-owner")
        task = _make_task(db_session, project.id, created_by="teacher-owner")
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
            evaluator_id="teacher-owner",
        )
        other_teacher = _Actor(user_id="teacher-other", role=Role.TEACHER)

        with pytest.raises(AppException) as exc_info:
            service.create_suggestion(
                db_session,
                other_teacher,
                ImprovementSuggestionCreate(
                    project_id=project.id,
                    created_from_evaluation_id=record.id,
                    evidence_reference=f"evaluation_records:{record.id}",
                    title="其他教师尝试",
                    description="应被拒绝",
                    student_id=student_id,
                ),
            )
        assert exc_info.value.status_code == 403

    def test_admin_can_manage_any_project_improvement(self, db_session):
        """系统管理员可管理任意项目的改进建议。"""
        project = _make_project(db_session, creator_id="teacher-1")
        task = _make_task(db_session, project.id, created_by="teacher-1")
        student_id = _unique_student_id()
        record = _make_evaluation_record(
            db_session,
            project_id=project.id,
            task_id=task.id,
            student_id=student_id,
        )
        admin = _Actor(user_id="admin-1", role=Role.ADMIN)

        suggestion = service.create_suggestion(
            db_session,
            admin,
            ImprovementSuggestionCreate(
                project_id=project.id,
                created_from_evaluation_id=record.id,
                evidence_reference=f"evaluation_records:{record.id}",
                title="管理员创建建议",
                description="应允许",
                student_id=student_id,
            ),
        )
        assert suggestion.created_by == admin.id
