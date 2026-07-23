"""学情改进领域服务层（计划 Task 7）。

职责：
- 创建改进建议：必须引用评价证据（``evidence_reference`` 必填），
  且来源评价记录必须存在；无证据抛 400（验收：无证据不生成确定性学生标签）。
- 教师采用/修改/拒绝建议：每次决定必须留痕原因与决定者；modified 状态需提供
  修改后的描述；状态机校验非法跃迁返回 409。
- 建议转任务/测评：改进任务可追溯到原评价（``created_from_evaluation_id``）
  与原建议（``link_suggestion_id``），可选同步创建正式 Task（学生可见）。
- 二次评价关联：关联首次评价与第二次评价，记录前后分数差与对比摘要，
  可关联建议与改进任务，实现"建议 -> 任务 -> 二次评价"全链路追溯。

唯一提交点：服务层方法在事务结束时 ``db.commit()``，失败回滚。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.enums import (
    ImprovementSuggestionStatus,
    ImprovementTaskType,
    TaskPublishStatus,
    TeachingStage,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.improvement import (
    ImprovementSuggestion,
    ImprovementTask,
    SecondEvaluation,
)
from app.models.task import Task
from app.models.user import User
from app.modules.improvements import policy, repository
from app.schemas.improvement import (
    ImprovementSuggestionCreate,
    ImprovementTaskCreate,
    SecondEvaluationCreate,
    SuggestionDecisionRequest,
)


# ── 建议状态机（计划 4.3）────────────────────────────────────
# draft -> adopted/modified/rejected；终态后不可变更。
_SUGGESTION_TRANSITIONS: dict[
    ImprovementSuggestionStatus, set[ImprovementSuggestionStatus]
] = {
    ImprovementSuggestionStatus.DRAFT: {
        ImprovementSuggestionStatus.ADOPTED,
        ImprovementSuggestionStatus.MODIFIED,
        ImprovementSuggestionStatus.REJECTED,
    },
    ImprovementSuggestionStatus.ADOPTED: set(),
    ImprovementSuggestionStatus.MODIFIED: set(),
    ImprovementSuggestionStatus.REJECTED: set(),
}


# ── 辅助 ──────────────────────────────────────────────────────
def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _enum_value(value) -> Optional[str]:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _load_evaluation_record(db: Session, record_id: str) -> EvaluationRecord:
    """加载评价记录；不存在抛 404。

    验收：建议必须引用评价证据——评价记录是证据的来源载体。
    """
    record = db.get(EvaluationRecord, record_id)
    if not record:
        raise AppException(
            code=40401,
            message=f"评价记录 {record_id} 不存在，无法创建改进建议",
            status_code=404,
        )
    return record


# ── 创建建议 ─────────────────────────────────────────────────
def create_suggestion(
    db: Session,
    actor: User,
    data: ImprovementSuggestionCreate,
) -> ImprovementSuggestion:
    """创建改进建议。

    验收：建议必须引用评价证据——``evidence_reference`` 必填，
    ``created_from_evaluation_id`` 必须指向已存在的评价记录；无证据抛 400。
    """
    policy.ensure_can_manage_improvement(db, actor, data.project_id)
    # 校验证据来源：评价记录必须存在
    record = _load_evaluation_record(db, data.created_from_evaluation_id)
    if record.project_id != data.project_id:
        raise AppException(
            code=40001,
            message="评价记录不属于该项目，不能跨项目引用证据",
            status_code=400,
        )
    if not data.evidence_reference or not data.evidence_reference.strip():
        raise AppException(
            code=40001,
            message="改进建议必须引用评价证据（evidence_reference 不能为空）",
            status_code=400,
        )
    suggestion = ImprovementSuggestion(
        project_id=data.project_id,
        student_id=data.student_id,
        created_from_evaluation_id=data.created_from_evaluation_id,
        evidence_reference=data.evidence_reference.strip(),
        title=data.title,
        description=data.description,
        status=ImprovementSuggestionStatus.DRAFT,
        created_by=actor.id,
    )
    repository.create_suggestion(db, suggestion)
    _commit(db)
    db.refresh(suggestion)
    return suggestion


def list_suggestions(
    db: Session,
    actor: User,
    *,
    project_id: str,
    student_id: Optional[str] = None,
    status: Optional[ImprovementSuggestionStatus] = None,
) -> list[ImprovementSuggestion]:
    policy.ensure_can_read_improvement(db, actor, project_id)
    return repository.list_suggestions(
        db, project_id=project_id, student_id=student_id, status=status
    )


def get_suggestion_detail(
    db: Session, actor: User, suggestion_id: str
) -> ImprovementSuggestion:
    suggestion = repository.get_suggestion(db, suggestion_id)
    if not suggestion:
        raise AppException(
            code=40401, message="改进建议不存在", status_code=404
        )
    policy.ensure_can_read_improvement(db, actor, suggestion.project_id)
    return suggestion


# ── 采用/修改/拒绝 ────────────────────────────────────────────
def decide_suggestion(
    db: Session,
    actor: User,
    suggestion_id: str,
    data: SuggestionDecisionRequest,
) -> ImprovementSuggestion:
    """教师采用/修改/拒绝建议，每次决定必须留痕原因。

    - adopted：采用原建议
    - modified：修改后采用（``modified_description`` 必填）
    - rejected：拒绝

    状态机校验：draft 才能迁移；终态后不可变更（409）。
    """
    suggestion = repository.get_suggestion(db, suggestion_id)
    if not suggestion:
        raise AppException(
            code=40401, message="改进建议不存在", status_code=404
        )
    policy.ensure_can_manage_suggestion(db, actor, suggestion)

    target = data.status
    allowed = _SUGGESTION_TRANSITIONS.get(suggestion.status, set())
    if target not in allowed:
        raise AppException(
            code=40901,
            message=(
                f"建议状态非法跃迁：当前「{suggestion.status.value}」，"
                f"目标「{target.value}」，允许："
                f"{','.join(s.value for s in allowed) or '无（终态）'}"
            ),
            status_code=409,
        )

    if not data.reason or not data.reason.strip():
        raise AppException(
            code=40001,
            message="采用/修改/拒绝原因必填（留痕要求）",
            status_code=400,
        )

    if target == ImprovementSuggestionStatus.MODIFIED:
        if not data.modified_description or not data.modified_description.strip():
            raise AppException(
                code=40001,
                message="修改后采用必须提供修改后的建议描述",
                status_code=400,
            )
        suggestion.modified_description = data.modified_description.strip()

    suggestion.status = target
    suggestion.decision_reason = data.reason.strip()
    suggestion.decided_by = actor.id
    suggestion.decided_at = datetime.now(timezone.utc)
    _commit(db)
    db.refresh(suggestion)
    return suggestion


# ── 建议转任务/测评 ──────────────────────────────────────────
def create_improvement_task(
    db: Session,
    actor: User,
    data: ImprovementTaskCreate,
) -> ImprovementTask:
    """建议转换为改进任务或二次评价测评。

    验收：改进任务可追溯到原评价（``created_from_evaluation_id`` 必填、必须存在）
    与原建议（``link_suggestion_id`` 可空）。
    ``publish_task=True`` 时同步创建正式 Task（学生可见），否则仅作为改进计划留痕。
    """
    policy.ensure_can_manage_improvement(db, actor, data.project_id)
    # 校验来源评价记录存在且属于本项目
    record = _load_evaluation_record(db, data.created_from_evaluation_id)
    if record.project_id != data.project_id:
        raise AppException(
            code=40001,
            message="评价记录不属于该项目，不能跨项目创建改进任务",
            status_code=400,
        )
    # 若关联建议，需校验建议存在且属于本项目
    if data.link_suggestion_id:
        suggestion = repository.get_suggestion(db, data.link_suggestion_id)
        if not suggestion:
            raise AppException(
                code=40401, message="关联建议不存在", status_code=404
            )
        if suggestion.project_id != data.project_id:
            raise AppException(
                code=40001,
                message="关联建议不属于该项目",
                status_code=400,
            )

    generated_task_id: Optional[str] = None
    if data.publish_task:
        # 同步创建正式 Task（学生可见）；任务类型 second_evaluation 也创建为正式测评任务
        task = _build_published_task(actor, data)
        db.add(task)
        db.flush()
        generated_task_id = task.id

    improvement_task = ImprovementTask(
        project_id=data.project_id,
        link_suggestion_id=data.link_suggestion_id,
        original_task_id=data.original_task_id,
        created_from_evaluation_id=data.created_from_evaluation_id,
        task_type=data.task_type,
        title=data.title,
        description=data.description,
        generated_task_id=generated_task_id,
        created_by=actor.id,
    )
    repository.create_improvement_task(db, improvement_task)
    _commit(db)
    db.refresh(improvement_task)
    return improvement_task


def _build_published_task(actor: User, data: ImprovementTaskCreate) -> Task:
    """根据改进任务类型生成正式 Task 记录。

    - foundation_consolidation -> stage=POST_CLASS, tier=FOUNDATION
    - enhancement_application -> stage=POST_CLASS, tier=ENHANCEMENT
    - extension_transfer -> stage=POST_CLASS, tier=EXTENSION
    - second_evaluation -> stage=POST_CLASS, tier=None（测评）
    """
    stage = TeachingStage.POST_CLASS
    tier = _tier_for_task_type(data.task_type)
    return Task(
        project_id=data.project_id,
        title=data.title,
        description=data.description,
        created_by=actor.id,
        stage=stage,
        tier=tier,
        publish_status=TaskPublishStatus.PUBLISHED,
    )


def _tier_for_task_type(task_type: ImprovementTaskType):
    from app.models.enums import ResourceTier

    mapping = {
        ImprovementTaskType.FOUNDATION_CONSOLIDATION: ResourceTier.FOUNDATION,
        ImprovementTaskType.ENHANCEMENT_APPLICATION: ResourceTier.ENHANCEMENT,
        ImprovementTaskType.EXTENSION_TRANSFER: ResourceTier.EXTENSION,
        ImprovementTaskType.SECOND_EVALUATION: None,
    }
    return mapping.get(task_type)


def list_improvement_tasks(
    db: Session,
    actor: User,
    *,
    project_id: str,
    task_type: Optional[ImprovementTaskType] = None,
    link_suggestion_id: Optional[str] = None,
) -> list[ImprovementTask]:
    policy.ensure_can_read_improvement(db, actor, project_id)
    return repository.list_improvement_tasks(
        db,
        project_id=project_id,
        task_type=task_type,
        link_suggestion_id=link_suggestion_id,
    )


# ── 二次评价 ─────────────────────────────────────────────────
def create_second_evaluation(
    db: Session,
    actor: User,
    data: SecondEvaluationCreate,
) -> SecondEvaluation:
    """创建二次评价关联：首次评价 -> 第二次评价，记录前后分数差。

    验收：改进任务能追溯到原评价和二次评价——``first_evaluation_id``/
    ``second_evaluation_id`` 必须指向已存在的评价记录，且属于同一项目同一学生。
    """
    policy.ensure_can_manage_improvement(db, actor, data.project_id)
    first = _load_evaluation_record(db, data.first_evaluation_id)
    second = _load_evaluation_record(db, data.second_evaluation_id)
    if first.project_id != data.project_id or second.project_id != data.project_id:
        raise AppException(
            code=40001,
            message="评价记录不属于该项目，不能跨项目创建二次评价",
            status_code=400,
        )
    if first.student_id != data.student_id or second.student_id != data.student_id:
        raise AppException(
            code=40001,
            message="评价记录与学生不匹配，二次评价必须针对同一学生",
            status_code=400,
        )
    if data.first_evaluation_id == data.second_evaluation_id:
        raise AppException(
            code=40001,
            message="首次评价与第二次评价不能为同一条记录",
            status_code=400,
        )

    # 关联建议/改进任务需校验归属
    if data.link_suggestion_id:
        suggestion = repository.get_suggestion(db, data.link_suggestion_id)
        if not suggestion or suggestion.project_id != data.project_id:
            raise AppException(
                code=40001,
                message="关联建议不存在或不属于该项目",
                status_code=400,
            )
    if data.link_improvement_task_id:
        task_obj = repository.get_improvement_task(db, data.link_improvement_task_id)
        if not task_obj or task_obj.project_id != data.project_id:
            raise AppException(
                code=40001,
                message="关联改进任务不存在或不属于该项目",
                status_code=400,
            )

    # 若未提供对比摘要，服务层基于证据（分数差）生成草稿（不伪造细节）
    summary = data.comparison_summary
    if not summary:
        summary = _build_comparison_summary(first, second)

    evaluation = SecondEvaluation(
        project_id=data.project_id,
        student_id=data.student_id,
        first_evaluation_id=data.first_evaluation_id,
        second_evaluation_id=data.second_evaluation_id,
        link_suggestion_id=data.link_suggestion_id,
        link_improvement_task_id=data.link_improvement_task_id,
        comparison_summary=summary,
        first_score=first.total_score,
        second_score=second.total_score,
        created_by=actor.id,
    )
    repository.create_second_evaluation(db, evaluation)
    _commit(db)
    db.refresh(evaluation)
    return evaluation


def _build_comparison_summary(
    first: EvaluationRecord, second: EvaluationRecord
) -> str:
    """基于两次评价总分生成前后对比摘要（不伪造未提供的细节）。"""
    first_score = first.total_score if first.total_score is not None else 0.0
    second_score = second.total_score if second.total_score is not None else 0.0
    delta = second_score - first_score
    direction = "提升" if delta > 0 else ("下降" if delta < 0 else "持平")
    return (
        f"首次评价总分 {first_score}，第二次评价总分 {second_score}，"
        f"变化 {direction} {abs(delta)} 分。"
    )


def list_second_evaluations(
    db: Session,
    actor: User,
    *,
    project_id: str,
    student_id: Optional[str] = None,
    link_suggestion_id: Optional[str] = None,
    link_improvement_task_id: Optional[str] = None,
) -> list[SecondEvaluation]:
    policy.ensure_can_read_improvement(db, actor, project_id)
    return repository.list_second_evaluations(
        db,
        project_id=project_id,
        student_id=student_id,
        link_suggestion_id=link_suggestion_id,
        link_improvement_task_id=link_improvement_task_id,
    )


# ── 序列化辅助 ───────────────────────────────────────────────
def suggestion_dict(suggestion: ImprovementSuggestion) -> dict:
    return {
        "id": suggestion.id,
        "project_id": suggestion.project_id,
        "student_id": suggestion.student_id,
        "created_from_evaluation_id": suggestion.created_from_evaluation_id,
        "evidence_reference": suggestion.evidence_reference,
        "title": suggestion.title,
        "description": suggestion.description,
        "status": _enum_value(suggestion.status),
        "decision_reason": suggestion.decision_reason,
        "modified_description": suggestion.modified_description,
        "decided_by": suggestion.decided_by,
        "decided_at": suggestion.decided_at,
        "created_by": suggestion.created_by,
        "created_at": suggestion.created_at,
        "updated_at": suggestion.updated_at,
    }


def improvement_task_dict(task: ImprovementTask) -> dict:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "link_suggestion_id": task.link_suggestion_id,
        "original_task_id": task.original_task_id,
        "created_from_evaluation_id": task.created_from_evaluation_id,
        "task_type": _enum_value(task.task_type),
        "title": task.title,
        "description": task.description,
        "generated_task_id": task.generated_task_id,
        "created_by": task.created_by,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def second_evaluation_dict(evaluation: SecondEvaluation) -> dict:
    return {
        "id": evaluation.id,
        "project_id": evaluation.project_id,
        "student_id": evaluation.student_id,
        "first_evaluation_id": evaluation.first_evaluation_id,
        "second_evaluation_id": evaluation.second_evaluation_id,
        "link_suggestion_id": evaluation.link_suggestion_id,
        "link_improvement_task_id": evaluation.link_improvement_task_id,
        "comparison_summary": evaluation.comparison_summary,
        "first_score": evaluation.first_score,
        "second_score": evaluation.second_score,
        "created_by": evaluation.created_by,
        "created_at": evaluation.created_at,
        "updated_at": evaluation.updated_at,
    }
