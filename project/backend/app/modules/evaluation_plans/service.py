"""评价计划领域服务层（计划 Task 4）。

职责：
- 量规版本管理：新建版本、发布（含完整性校验）、归档。
- 量规维度 CRUD：发布后不可修改，需新建版本。
- 证据 CRUD：记录正式学习证据，关联提交/指标/计划。
- 评价记录创建 + 状态机迁移（计划 4.3）。
- 分维度评分：教师确认（校验人机差异原因）。
- 评价计划快照：一次渲染所需全部数据。
- 完整性校验：AI 默认权重为零、目标可观察、量规等级有描述、缺失证据。
- 复核队列：低置信度、边界分、规则冲突、申诉。
- 兼容旧评价：list_legacy_evaluations 显示"旧版评价记录"。

唯一提交点：服务层方法在事务结束时 `db.commit()`，失败回滚。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.evaluation import Evaluation
from app.models.evaluation_plan import (
    EvaluationRecord,
    EvaluationScore,
    EvidenceArtifact,
    Rubric,
    RubricCriterion,
)
from app.models.enums import (
    ArtifactSourceType,
    EvaluationSource,
    EvaluationStatus,
    EvaluationSubjectType,
    RubricStatus,
    SubmissionReviewStatus,
)
from app.models.project import Project
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import Role, User
from app.modules.evaluation_plans import policy, repository
from app.modules.projects.repository import ProjectRepository
from app.schemas.evaluation_plan import (
    EvaluationPlanValidationResult,
    EvaluationRecordCreate,
    EvaluationScoreCreate,
    EvaluationScoreUpdate,
    EvidenceArtifactCreate,
    ReviewConfirmRequest,
    RubricCreate,
    RubricCriterionCreate,
    RubricCriterionUpdate,
)


# ── 评价状态机（计划 4.3）──────────────────────────────────
_EVALUATION_TRANSITIONS: dict[EvaluationStatus, set[EvaluationStatus]] = {
    EvaluationStatus.DRAFT: {EvaluationStatus.COLLECTING_EVIDENCE},
    EvaluationStatus.COLLECTING_EVIDENCE: {
        EvaluationStatus.PENDING_TEACHER_CONFIRMATION,
    },
    EvaluationStatus.PENDING_TEACHER_CONFIRMATION: {
        EvaluationStatus.CONFIRMED,
        EvaluationStatus.COLLECTING_EVIDENCE,
    },
    EvaluationStatus.CONFIRMED: {EvaluationStatus.PUBLISHED},
    EvaluationStatus.PUBLISHED: {
        EvaluationStatus.APPEALED,
        EvaluationStatus.FINALIZED,
    },
    EvaluationStatus.APPEALED: {EvaluationStatus.RECHECKED},
    EvaluationStatus.RECHECKED: {EvaluationStatus.FINALIZED},
    EvaluationStatus.FINALIZED: set(),
}

# ── 提交状态机（计划 4.3）──────────────────────────────────
_SUBMISSION_TRANSITIONS: dict[SubmissionReviewStatus, set[SubmissionReviewStatus]] = {
    SubmissionReviewStatus.DRAFT: {SubmissionReviewStatus.SUBMITTED},
    SubmissionReviewStatus.SUBMITTED: {
        SubmissionReviewStatus.AI_REVIEWED,
        SubmissionReviewStatus.TEACHER_REVIEWED,
    },
    SubmissionReviewStatus.AI_REVIEWED: {SubmissionReviewStatus.TEACHER_REVIEWED},
    SubmissionReviewStatus.TEACHER_REVIEWED: {
        SubmissionReviewStatus.RETURNED,
        SubmissionReviewStatus.FINALIZED,
    },
    SubmissionReviewStatus.RETURNED: {SubmissionReviewStatus.RESUBMITTED},
    SubmissionReviewStatus.RESUBMITTED: {
        SubmissionReviewStatus.AI_REVIEWED,
        SubmissionReviewStatus.TEACHER_REVIEWED,
        SubmissionReviewStatus.FINALIZED,
    },
    SubmissionReviewStatus.FINALIZED: set(),
}


# ── 辅助 ──────────────────────────────────────────────────────
def _load_project(db: Session, project_id: str) -> Project:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise AppException(code=40401, message="项目不存在", status_code=404)
    return project


def _class_ids(db: Session, project_id: str) -> list[str]:
    return ProjectRepository(db).class_ids(project_id)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _parse_evaluation_status(value: str) -> EvaluationStatus:
    try:
        return EvaluationStatus(value)
    except ValueError:
        raise AppException(
            code=40001,
            message=f"无效的评价状态: {value}",
            status_code=400,
        )


def _parse_submission_status(value: str) -> SubmissionReviewStatus:
    try:
        return SubmissionReviewStatus(value)
    except ValueError:
        raise AppException(
            code=40001,
            message=f"无效的提交状态: {value}",
            status_code=400,
        )


def _parse_artifact_source_type(value: str) -> ArtifactSourceType:
    try:
        return ArtifactSourceType(value)
    except ValueError:
        raise AppException(
            code=40001,
            message=f"无效的证据来源类型: {value}",
            status_code=400,
        )


def _parse_evaluation_source(value: str) -> EvaluationSource:
    try:
        return EvaluationSource(value)
    except ValueError:
        raise AppException(
            code=40001,
            message=f"无效的评价来源: {value}",
            status_code=400,
        )


def _parse_evaluation_subject_type(value: str) -> EvaluationSubjectType:
    try:
        return EvaluationSubjectType(value)
    except ValueError:
        raise AppException(
            code=40001,
            message=f"无效的评价主体类型: {value}",
            status_code=400,
        )


def _parse_rubric_status(value: str) -> RubricStatus:
    try:
        return RubricStatus(value)
    except ValueError:
        raise AppException(
            code=40001,
            message=f"无效的量规状态: {value}",
            status_code=400,
        )


# ── Rubric 版本管理 ───────────────────────────────────────────
def create_rubric(
    db: Session, actor: User, project_id: str, data: RubricCreate
) -> Rubric:
    """新建量规版本：旧版本标记为非当前。"""
    project = _load_project(db, project_id)
    policy.ensure_plan_editable(actor, project, _class_ids(db, project_id))
    repository.mark_rubric_versions_non_current(db, project_id)
    version = repository.next_rubric_version(db, project_id)
    rubric = Rubric(
        project_id=project_id,
        version=version,
        is_current=True,
        status=RubricStatus.DRAFT,
        created_by=actor.id,
    )
    repository.create_rubric(db, rubric)
    _commit(db)
    db.refresh(rubric)
    return rubric


def publish_rubric(
    db: Session, actor: User, rubric_id: str
) -> dict:
    """发布量规：先校验完整性，通过后状态转为 PUBLISHED。

    验收：AI 默认权重为零；抽象目标未拆成可观察指标时禁止发布；
    量规等级必须有可观察描述。
    """
    rubric = repository.get_rubric(db, rubric_id)
    if not rubric:
        raise AppException(code=40401, message="量规不存在", status_code=404)
    project = _load_project(db, rubric.project_id)
    policy.ensure_can_manage_plan(actor, project, _class_ids(db, rubric.project_id))
    if rubric.status != RubricStatus.DRAFT:
        raise AppException(
            code=40901,
            message=f"量规当前状态 {rubric.status.value} 不可发布",
            status_code=409,
        )
    validation = validate_evaluation_plan(db, actor, rubric.project_id)
    if validation["blockers"]:
        repository.update_rubric_status(db, rubric, RubricStatus.DRAFT)
        _commit(db)
        return {
            "rubric": _rubric_dict(rubric),
            "blockers": validation["blockers"],
            "warnings": validation["warnings"],
        }
    repository.update_rubric_status(db, rubric, RubricStatus.PUBLISHED)
    _commit(db)
    db.refresh(rubric)
    return {
        "rubric": _rubric_dict(rubric),
        "blockers": [],
        "warnings": validation["warnings"],
    }


def archive_rubric(db: Session, actor: User, rubric_id: str) -> Rubric:
    """归档量规：归档后不可用于新评价。"""
    rubric = repository.get_rubric(db, rubric_id)
    if not rubric:
        raise AppException(code=40401, message="量规不存在", status_code=404)
    project = _load_project(db, rubric.project_id)
    policy.ensure_can_manage_plan(actor, project, _class_ids(db, rubric.project_id))
    if rubric.status != RubricStatus.PUBLISHED:
        raise AppException(
            code=40901,
            message=f"仅已发布量规可归档，当前状态 {rubric.status.value}",
            status_code=409,
        )
    repository.update_rubric_status(db, rubric, RubricStatus.ARCHIVED)
    _commit(db)
    db.refresh(rubric)
    return rubric


def get_current_rubric(
    db: Session, actor: User, project_id: str
) -> Optional[Rubric]:
    project = _load_project(db, project_id)
    policy.ensure_can_read_plan(actor, project, _class_ids(db, project_id))
    return repository.get_current_rubric(db, project_id)


# ── RubricCriterion CRUD ──────────────────────────────────────
def add_criterion(
    db: Session, actor: User, data: RubricCriterionCreate
) -> RubricCriterion:
    rubric = repository.get_rubric(db, data.rubric_id)
    if not rubric:
        raise AppException(code=40401, message="量规不存在", status_code=404)
    project = _load_project(db, rubric.project_id)
    policy.ensure_plan_editable(actor, project, _class_ids(db, rubric.project_id))
    if rubric.status != RubricStatus.DRAFT:
        raise AppException(
            code=40901,
            message="量规已发布，不可修改维度，请新建版本",
            status_code=409,
        )
    criterion = RubricCriterion(
        rubric_id=data.rubric_id,
        indicator_id=data.indicator_id,
        dimension=data.dimension,
        weight=data.weight,
        ai_weight=data.ai_weight,
        levels=[level.model_dump() for level in data.levels],
    )
    repository.create_criterion(db, criterion)
    _commit(db)
    db.refresh(criterion)
    return criterion


def update_criterion(
    db: Session, actor: User, criterion_id: str, data: RubricCriterionUpdate
) -> RubricCriterion:
    criterion = repository.get_criterion(db, criterion_id)
    if not criterion:
        raise AppException(code=40401, message="量规维度不存在", status_code=404)
    rubric = repository.get_rubric(db, criterion.rubric_id)
    if not rubric:
        raise AppException(code=40401, message="量规不存在", status_code=404)
    project = _load_project(db, rubric.project_id)
    policy.ensure_plan_editable(actor, project, _class_ids(db, rubric.project_id))
    if rubric.status != RubricStatus.DRAFT:
        raise AppException(
            code=40901,
            message="量规已发布，不可修改维度",
            status_code=409,
        )
    payload = data.model_dump(exclude_unset=True)
    if "levels" in payload and payload["levels"] is not None:
        payload["levels"] = [level if isinstance(level, dict) else level.model_dump() for level in payload["levels"]]
    for field, value in payload.items():
        setattr(criterion, field, value)
    _commit(db)
    db.refresh(criterion)
    return criterion


def remove_criterion(
    db: Session, actor: User, criterion_id: str
) -> None:
    criterion = repository.get_criterion(db, criterion_id)
    if not criterion:
        raise AppException(code=40401, message="量规维度不存在", status_code=404)
    rubric = repository.get_rubric(db, criterion.rubric_id)
    if not rubric:
        raise AppException(code=40401, message="量规不存在", status_code=404)
    project = _load_project(db, rubric.project_id)
    policy.ensure_plan_editable(actor, project, _class_ids(db, rubric.project_id))
    if rubric.status != RubricStatus.DRAFT:
        raise AppException(
            code=40901,
            message="量规已发布，不可删除维度",
            status_code=409,
        )
    repository.delete_criterion(db, criterion)
    _commit(db)


def list_criteria(
    db: Session, actor: User, rubric_id: str
) -> list[RubricCriterion]:
    rubric = repository.get_rubric(db, rubric_id)
    if not rubric:
        raise AppException(code=40401, message="量规不存在", status_code=404)
    project = _load_project(db, rubric.project_id)
    policy.ensure_can_read_plan(actor, project, _class_ids(db, rubric.project_id))
    return repository.list_criteria_by_rubric(db, rubric_id)


# ── EvidenceArtifact ──────────────────────────────────────────
def add_artifact(
    db: Session, actor: User, data: EvidenceArtifactCreate
) -> EvidenceArtifact:
    project = _load_project(db, data.project_id)
    policy.ensure_can_manage_plan(actor, project, _class_ids(db, data.project_id))
    artifact = EvidenceArtifact(
        project_id=data.project_id,
        submission_id=data.submission_id,
        indicator_id=data.indicator_id,
        plan_id=data.plan_id,
        source_type=_parse_artifact_source_type(data.source_type),
        content_ref=data.content_ref,
        collected_by=data.collected_by,
        collected_at=data.collected_at or datetime.now(timezone.utc),
    )
    repository.create_artifact(db, artifact)
    _commit(db)
    db.refresh(artifact)
    return artifact


def list_artifacts(
    db: Session, actor: User, project_id: str
) -> list[EvidenceArtifact]:
    project = _load_project(db, project_id)
    policy.ensure_can_read_plan(actor, project, _class_ids(db, project_id))
    return repository.list_artifacts_by_project(db, project_id)


# ── EvaluationRecord ──────────────────────────────────────────
def create_record(
    db: Session, actor: User, data: EvaluationRecordCreate
) -> EvaluationRecord:
    """创建评价记录：默认 DRAFT 状态。"""
    project = _load_project(db, data.project_id)
    policy.ensure_can_manage_record(actor, project, _class_ids(db, data.project_id))
    record = EvaluationRecord(
        project_id=data.project_id,
        task_id=data.task_id,
        student_id=data.student_id,
        evaluator_id=data.evaluator_id,
        subject_type=_parse_evaluation_subject_type(data.subject_type),
        subject_id=data.subject_id,
        source=_parse_evaluation_source(data.source),
        status=EvaluationStatus.DRAFT,
        rubric_id=data.rubric_id,
        comment=data.comment,
    )
    repository.create_record(db, record)
    _commit(db)
    db.refresh(record)
    return record


def get_record(
    db: Session, actor: User, record_id: str
) -> EvaluationRecord:
    record = repository.get_record(db, record_id)
    if not record:
        raise AppException(code=40401, message="评价记录不存在", status_code=404)
    project = _load_project(db, record.project_id)
    policy.ensure_student_can_read_record(actor, record, project, _class_ids(db, record.project_id))
    return record


def list_records(
    db: Session,
    actor: User,
    project_id: str,
    *,
    task_id: Optional[str] = None,
    student_id: Optional[str] = None,
    status: Optional[str] = None,
) -> list[EvaluationRecord]:
    """教师/管理员列出评价记录（全状态）；学生仅列自己的已发布记录。"""
    project = _load_project(db, project_id)
    class_ids = _class_ids(db, project_id)
    status_enum = _parse_evaluation_status(status) if status else None
    if actor.role == Role.STUDENT:
        policy.ensure_can_read_plan(actor, project, class_ids)
        return repository.list_student_visible_records(db, project_id, actor.id)
    policy.ensure_can_read_plan(actor, project, class_ids)
    return repository.list_records_by_project(
        db, project_id, task_id=task_id, student_id=student_id, status=status_enum
    )


def transition_record(
    db: Session, actor: User, record_id: str, target: str
) -> EvaluationRecord:
    """评价记录状态机迁移（计划 4.3）。非法跃迁返回 409。

    发布（PUBLISHED）时同步 `Submission.score/comment` 投影：
    `Submission` 字段只能作为由已发布 `EvaluationRecord` 同步的展示投影，
    不再作为评价主数据来源。
    """
    record = repository.get_record(db, record_id)
    if not record:
        raise AppException(code=40401, message="评价记录不存在", status_code=404)
    project = _load_project(db, record.project_id)
    policy.ensure_can_manage_record(actor, project, _class_ids(db, record.project_id))
    current = record.status
    target_enum = _parse_evaluation_status(target)
    allowed = _EVALUATION_TRANSITIONS.get(current, set())
    if target_enum not in allowed:
        current_val = current.value if hasattr(current, "value") else str(current)
        allowed_vals = [s.value for s in allowed]
        raise AppException(
            code=40901,
            message=f"评价状态 {current_val} 不可迁移到 {target}，允许: {allowed_vals}",
            status_code=409,
        )
    record.status = target_enum
    if target_enum == EvaluationStatus.CONFIRMED:
        record.confirmed_by = actor.id
        record.confirmed_at = datetime.now(timezone.utc)
    elif target_enum == EvaluationStatus.PUBLISHED:
        record.published_at = datetime.now(timezone.utc)
        # 同步 Submission 投影：仅展示投影，非主数据
        _sync_submission_projection(db, record)
    _commit(db)
    db.refresh(record)
    return record


def _sync_submission_projection(db: Session, record: EvaluationRecord) -> None:
    """将已发布评价记录的分数/评语同步到 Submission 投影字段。

    仅当评价记录关联了 task_id 且对应提交存在时执行。
    `Submission.score/comment` 仅作为展示投影，不能反向覆盖 `EvaluationRecord`。
    """
    if not record.task_id:
        return
    submission = db.execute(
        select(Submission).where(
            Submission.task_id == record.task_id,
            Submission.student_id == record.student_id,
        )
    ).scalars().first()
    if submission is None:
        return
    submission.score = int(record.total_score) if record.total_score is not None else None
    submission.comment = record.comment


# ── EvaluationScore ───────────────────────────────────────────
def add_score(
    db: Session, actor: User, data: EvaluationScoreCreate
) -> EvaluationScore:
    """新增分维度评分。

    验收：教师修改 AI 分数必须记录差异原因（difference_reason）。
    """
    record = repository.get_record(db, data.record_id)
    if not record:
        raise AppException(code=40401, message="评价记录不存在", status_code=404)
    project = _load_project(db, record.project_id)
    policy.ensure_can_manage_record(actor, project, _class_ids(db, record.project_id))
    # 若有 AI 建议分数且教师最终分数不同，必须填差异原因
    if (
        data.suggested_score is not None
        and data.final_score is not None
        and abs(data.suggested_score - data.final_score) > 0.01
        and not data.difference_reason
    ):
        raise AppException(
            code=40001,
            message="修改 AI 建议分数必须填写差异原因",
            status_code=400,
        )
    score = EvaluationScore(
        record_id=data.record_id,
        criterion_id=data.criterion_id,
        suggested_score=data.suggested_score,
        final_score=data.final_score,
        evidence_ref=data.evidence_ref,
        ai_confidence=data.ai_confidence,
        difference_reason=data.difference_reason,
    )
    repository.create_score(db, score)
    _commit(db)
    db.refresh(score)
    return score


def update_score(
    db: Session, actor: User, score_id: str, data: EvaluationScoreUpdate
) -> EvaluationScore:
    """教师修改分维度评分：若修改 final_score 且存在 suggested_score，必须填差异原因。"""
    score = repository.get_score(db, score_id)
    if not score:
        raise AppException(code=40401, message="评分记录不存在", status_code=404)
    record = repository.get_record(db, score.record_id)
    if not record:
        raise AppException(code=40401, message="评价记录不存在", status_code=404)
    project = _load_project(db, record.project_id)
    policy.ensure_can_manage_record(actor, project, _class_ids(db, record.project_id))
    payload = data.model_dump(exclude_unset=True)
    # 差异原因校验
    new_final = payload.get("final_score", score.final_score)
    if (
        score.suggested_score is not None
        and new_final is not None
        and abs(score.suggested_score - new_final) > 0.01
        and not payload.get("difference_reason", score.difference_reason)
    ):
        raise AppException(
            code=40001,
            message="修改 AI 建议分数必须填写差异原因",
            status_code=400,
        )
    for field, value in payload.items():
        setattr(score, field, value)
    _commit(db)
    db.refresh(score)
    return score


def list_scores(
    db: Session, actor: User, record_id: str
) -> list[EvaluationScore]:
    record = repository.get_record(db, record_id)
    if not record:
        raise AppException(code=40401, message="评价记录不存在", status_code=404)
    project = _load_project(db, record.project_id)
    policy.ensure_student_can_read_record(actor, record, project, _class_ids(db, record.project_id))
    return repository.list_scores_by_record(db, record_id)


# ── 评价计划快照 + 完整性校验 ──────────────────────────────────
def get_plan_snapshot(db: Session, actor: User, project_id: str) -> dict:
    """聚合返回评价计划页一次渲染所需的全部数据。"""
    project = _load_project(db, project_id)
    policy.ensure_can_read_plan(actor, project, _class_ids(db, project_id))
    rubric = repository.get_current_rubric(db, project_id)
    criteria = repository.list_criteria_by_rubric(db, rubric.id) if rubric else []
    goals = repository.list_goals_by_project(db, project_id)
    indicators = repository.list_indicators_by_project(db, project_id)
    evidence_plans = repository.list_evidence_plans_by_project(db, project_id)
    artifacts = repository.list_artifacts_by_project(db, project_id)
    validation = validate_evaluation_plan(db, actor, project_id)
    return {
        "rubric": _rubric_dict(rubric) if rubric else None,
        "criteria": [_criterion_dict(c) for c in criteria],
        "goals": [_goal_dict(g) for g in goals],
        "indicators": [_indicator_dict(i) for i in indicators],
        "evidence_plans": [_evidence_plan_dict(p) for p in evidence_plans],
        "evidence_artifacts": [_artifact_dict(a) for a in artifacts],
        "validation": validation,
    }


def validate_evaluation_plan(db: Session, actor: User, project_id: str) -> dict:
    """评价计划完整性校验（验收标准）。

    - AI 默认权重为零：ai_weight 非零阻断发布
    - 抽象目标未拆成可观察指标时禁止发布
    - 量规等级必须有可观察描述
    - 缺失证据显示"未采集"（不阻断发布，作为 warnings）
    """
    project = _load_project(db, project_id)
    policy.ensure_can_read_plan(actor, project, _class_ids(db, project_id))
    rubric = repository.get_current_rubric(db, project_id)
    criteria = repository.list_criteria_by_rubric(db, rubric.id) if rubric else []
    goals = repository.list_goals_by_project(db, project_id)
    indicators = repository.list_indicators_by_project(db, project_id)
    evidence_plans = repository.list_evidence_plans_by_project(db, project_id)
    artifacts = repository.list_artifacts_by_project(db, project_id)

    blockers: list[str] = []
    warnings: list[str] = []
    ai_weight_nonzero = False
    goals_without_indicators: list[str] = []
    criteria_without_level_description: list[str] = []
    missing_required_evidence: list[str] = []

    # 1. AI 默认权重为零
    for c in criteria:
        if c.ai_weight > 0:
            ai_weight_nonzero = True
            blockers.append(f"维度「{c.dimension}」AI 权重非零，AI 默认权重必须为零")
    # 2. 抽象目标未拆成可观察指标
    indicator_goal_ids = {i.goal_id for i in indicators}
    for g in goals:
        if g.id not in indicator_goal_ids:
            goals_without_indicators.append(g.id)
            blockers.append(f"目标「{g.name}」未拆解为可观察指标，禁止发布")
    # 3. 量规等级必须有可观察描述
    for c in criteria:
        for level in c.levels or []:
            desc = level.get("description") if isinstance(level, dict) else None
            if not desc or not str(desc).strip():
                criteria_without_level_description.append(c.id)
                blockers.append(f"维度「{c.dimension}」存在等级描述为空，量规等级必须有可观察描述")
                break
    # 4. 缺失证据显示"未采集"（warnings，不阻断）
    artifact_indicator_ids = {a.indicator_id for a in artifacts}
    required_plan_ids = repository.list_required_evidence_plan_ids(db, project_id)
    for plan_id in required_plan_ids:
        plan = next((p for p in evidence_plans if p.id == plan_id), None)
        if plan and plan.indicator_id not in artifact_indicator_ids:
            missing_required_evidence.append(plan.indicator_id)
            warnings.append(f"指标「{plan.indicator_id}」的必需证据未采集")

    ready = len(blockers) == 0
    return {
        "ready": ready,
        "blockers": blockers,
        "warnings": warnings,
        "ai_weight_nonzero": ai_weight_nonzero,
        "goals_without_indicators": goals_without_indicators,
        "criteria_without_level_description": criteria_without_level_description,
        "missing_required_evidence": missing_required_evidence,
    }


# ── 复核队列 + 教师确认 ────────────────────────────────────────
def get_review_queue(
    db: Session, actor: User, project_id: str, *, task_id: Optional[str] = None
) -> list[dict]:
    """复核队列：低置信度、边界分、规则冲突、申诉。"""
    project = _load_project(db, project_id)
    policy.ensure_can_manage_plan(actor, project, _class_ids(db, project_id))
    return repository.list_review_queue(db, project_id, task_id=task_id)


def confirm_review(
    db: Session, actor: User, submission_id: str, data: ReviewConfirmRequest
) -> dict:
    """教师确认复核：写入分维度最终分数与差异原因，提交转为 finalized。

    验收：教师修改 AI 分数必须记录差异原因；教师确认前不得发布。
    """
    submission = repository.get_submission(db, submission_id)
    if not submission:
        raise AppException(code=40401, message="提交不存在", status_code=404)
    task = db.get(Task, submission.task_id)
    if not task:
        raise AppException(code=40401, message="任务不存在", status_code=404)
    project = _load_project(db, task.project_id)
    policy.ensure_can_manage_record(actor, project, _class_ids(db, task.project_id))

    # 查找关联评价记录
    records = repository.list_records_by_task(db, submission.task_id, student_id=submission.student_id)
    record = records[0] if records else None
    if not record:
        raise AppException(
            code=40401,
            message="该提交尚无评价记录，无法确认复核",
            status_code=404,
        )

    # 写入分维度最终分数
    for score_data in data.scores:
        criterion_id = score_data.get("criterion_id")
        final_score = score_data.get("final_score")
        evidence_ref = score_data.get("evidence_ref")
        difference_reason = score_data.get("difference_reason")
        # 查找已有评分（AI 建议或教师草稿）
        existing_scores = repository.list_scores_by_record(db, record.id)
        existing = next((s for s in existing_scores if s.criterion_id == criterion_id), None)
        if existing:
            # 差异原因校验
            if (
                existing.suggested_score is not None
                and final_score is not None
                and abs(existing.suggested_score - final_score) > 0.01
                and not difference_reason
                and not existing.difference_reason
            ):
                raise AppException(
                    code=40001,
                    message=f"维度 {criterion_id} 修改 AI 建议分数必须填写差异原因",
                    status_code=400,
                )
            existing.final_score = final_score
            existing.evidence_ref = evidence_ref
            if difference_reason:
                existing.difference_reason = difference_reason
        else:
            # 新增教师评分
            score = EvaluationScore(
                record_id=record.id,
                criterion_id=criterion_id,
                final_score=final_score,
                evidence_ref=evidence_ref,
                difference_reason=difference_reason,
            )
            repository.create_score(db, score)

    # 更新总分与评语
    if data.total_score is not None:
        record.total_score = data.total_score
    if data.comment is not None:
        record.comment = data.comment

    # 整体人机差异原因（修改 AI 总分时必填）
    if data.difference_reason:
        record.comment = (record.comment or "") + f"\n[人机差异原因]{data.difference_reason}"

    # 评价记录状态迁移：confirmed -> published（教师确认后发布）
    if record.status == EvaluationStatus.PENDING_TEACHER_CONFIRMATION:
        record.status = EvaluationStatus.CONFIRMED
        record.confirmed_by = actor.id
        record.confirmed_at = datetime.now(timezone.utc)
    elif record.status == EvaluationStatus.CONFIRMED:
        pass  # 已确认
    elif record.status == EvaluationStatus.RECHECKED:
        pass  # 复核中，确认后保持
    # else: 其他状态不自动迁移

    # 提交状态迁移：teacher_reviewed -> finalized
    sub_enum = submission.review_status
    if sub_enum == SubmissionReviewStatus.TEACHER_REVIEWED:
        submission.review_status = SubmissionReviewStatus.FINALIZED
        submission.status = "finalized"

    _commit(db)
    db.refresh(record)
    db.refresh(submission)
    return {
        "record": _record_dict(record),
        "submission_id": submission.id,
        "review_status": submission.review_status.value if hasattr(submission.review_status, "value") else str(submission.review_status),
    }


# ── 提交状态机迁移 ────────────────────────────────────────────
def transition_submission(
    db: Session, actor: User, submission_id: str, target: str
) -> Submission:
    """提交复核状态机迁移（计划 4.3）。非法跃迁返回 409。"""
    submission = repository.get_submission(db, submission_id)
    if not submission:
        raise AppException(code=40401, message="提交不存在", status_code=404)
    task = db.get(Task, submission.task_id)
    if not task:
        raise AppException(code=40401, message="任务不存在", status_code=404)
    project = _load_project(db, task.project_id)
    # 学生可提交/重新提交，教师可推进复核状态
    policy.ensure_can_read_plan(actor, project, _class_ids(db, task.project_id))
    current = submission.review_status
    target_enum = _parse_submission_status(target)
    allowed = _SUBMISSION_TRANSITIONS.get(current, set())
    if target_enum not in allowed:
        current_val = current.value if hasattr(current, "value") else str(current)
        allowed_vals = [s.value for s in allowed]
        raise AppException(
            code=40901,
            message=f"提交状态 {current_val} 不可迁移到 {target}，允许: {allowed_vals}",
            status_code=409,
        )
    submission.review_status = target_enum
    submission.status = target_enum.value  # 镜像到旧 status 字段兼容旧接口
    _commit(db)
    db.refresh(submission)
    return submission


# ── 兼容旧评价 ────────────────────────────────────────────────
def list_legacy_evaluations(
    db: Session, actor: User, task_id: str
) -> list[Evaluation]:
    """列出旧版简单评价（显示为"旧版评价记录"）。

    复用 evaluations.policy 的读取权限判断。
    """
    from app.modules.evaluations.policy import ensure_can_read_task_evaluations
    ensure_can_read_task_evaluations(db, actor, task_id)
    statement = (
        select(Evaluation)
        .where(Evaluation.task_id == task_id, Evaluation.is_legacy.is_(True))
        .order_by(Evaluation.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


# ── 序列化辅助 ────────────────────────────────────────────────
def _rubric_dict(rubric: Rubric) -> dict:
    status = rubric.status.value if hasattr(rubric.status, "value") else str(rubric.status)
    return {
        "id": rubric.id,
        "project_id": rubric.project_id,
        "version": rubric.version,
        "is_current": rubric.is_current,
        "status": status,
        "created_by": rubric.created_by,
        "created_at": rubric.created_at.isoformat() if rubric.created_at else None,
    }


def _criterion_dict(c: RubricCriterion) -> dict:
    return {
        "id": c.id,
        "rubric_id": c.rubric_id,
        "indicator_id": c.indicator_id,
        "dimension": c.dimension,
        "weight": c.weight,
        "ai_weight": c.ai_weight,
        "levels": c.levels or [],
    }


def _goal_dict(g) -> dict:
    goal_type = g.goal_type.value if hasattr(g.goal_type, "value") else str(g.goal_type)
    return {
        "id": g.id,
        "project_id": g.project_id,
        "goal_type": goal_type,
        "name": g.name,
        "description": g.description,
        "scope": g.scope,
    }


def _indicator_dict(i) -> dict:
    return {
        "id": i.id,
        "goal_id": i.goal_id,
        "project_id": i.project_id,
        "observable_behavior": i.observable_behavior,
        "level_rule": i.level_rule,
    }


def _evidence_plan_dict(p) -> dict:
    stage = p.stage.value if hasattr(p.stage, "value") else str(p.stage)
    evidence_type = p.evidence_type.value if hasattr(p.evidence_type, "value") else str(p.evidence_type)
    collector = p.collector.value if hasattr(p.collector, "value") else str(p.collector)
    return {
        "id": p.id,
        "indicator_id": p.indicator_id,
        "project_id": p.project_id,
        "stage": stage,
        "evidence_type": evidence_type,
        "collector": collector,
        "required": p.required,
        "description": p.description,
    }


def _artifact_dict(a: EvidenceArtifact) -> dict:
    source_type = a.source_type.value if hasattr(a.source_type, "value") else str(a.source_type)
    return {
        "id": a.id,
        "project_id": a.project_id,
        "submission_id": a.submission_id,
        "indicator_id": a.indicator_id,
        "plan_id": a.plan_id,
        "source_type": source_type,
        "content_ref": a.content_ref,
        "collected_by": a.collected_by,
        "collected_at": a.collected_at.isoformat() if a.collected_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _record_dict(record: EvaluationRecord) -> dict:
    status = record.status.value if hasattr(record.status, "value") else str(record.status)
    source = record.source.value if hasattr(record.source, "value") else str(record.source)
    subject_type = record.subject_type.value if hasattr(record.subject_type, "value") else str(record.subject_type)
    return {
        "id": record.id,
        "project_id": record.project_id,
        "task_id": record.task_id,
        "student_id": record.student_id,
        "evaluator_id": record.evaluator_id,
        "subject_type": subject_type,
        "subject_id": record.subject_id,
        "source": source,
        "status": status,
        "rubric_id": record.rubric_id,
        "total_score": record.total_score,
        "comment": record.comment,
        "confirmed_by": record.confirmed_by,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
        "published_at": record.published_at.isoformat() if record.published_at else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
