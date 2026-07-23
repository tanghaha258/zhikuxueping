"""评价计划领域持久化操作（计划 Task 4）。

覆盖量规、量规维度、证据、评价记录、分维度评分的 CRUD，
以及复核队列查询。所有查询显式声明，避免 ORM 懒加载造成 N+1。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.evaluation_plan import (
    EvaluationRecord,
    EvaluationScore,
    EvidenceArtifact,
    Rubric,
    RubricCriterion,
)
from app.models.enums import EvaluationStatus, RubricStatus, SubmissionReviewStatus
from app.models.project_design import EvaluationIndicator, EvidencePlan, LearningGoal
from app.models.submission import Submission
from app.models.task import Task


# ── Rubric ────────────────────────────────────────────────────
def create_rubric(db: Session, rubric: Rubric) -> Rubric:
    db.add(rubric)
    db.flush()
    return rubric


def get_rubric(db: Session, rubric_id: str) -> Optional[Rubric]:
    return db.get(Rubric, rubric_id)


def get_current_rubric(db: Session, project_id: str) -> Optional[Rubric]:
    statement = select(Rubric).where(
        Rubric.project_id == project_id,
        Rubric.is_current.is_(True),
    )
    return db.execute(statement).scalars().first()


def list_rubrics_by_project(db: Session, project_id: str) -> list[Rubric]:
    statement = (
        select(Rubric)
        .where(Rubric.project_id == project_id)
        .order_by(Rubric.version.desc())
    )
    return list(db.execute(statement).scalars().all())


def mark_rubric_versions_non_current(db: Session, project_id: str) -> None:
    statement = select(Rubric).where(
        Rubric.project_id == project_id,
        Rubric.is_current.is_(True),
    )
    for rubric in db.execute(statement).scalars().all():
        rubric.is_current = False


def next_rubric_version(db: Session, project_id: str) -> int:
    statement = select(Rubric.version).where(Rubric.project_id == project_id)
    versions = db.execute(statement).scalars().all()
    return max(versions) + 1 if versions else 1


def update_rubric_status(db: Session, rubric: Rubric, status: RubricStatus) -> Rubric:
    rubric.status = status
    db.flush()
    return rubric


# ── RubricCriterion ───────────────────────────────────────────
def create_criterion(db: Session, criterion: RubricCriterion) -> RubricCriterion:
    db.add(criterion)
    db.flush()
    return criterion


def get_criterion(db: Session, criterion_id: str) -> Optional[RubricCriterion]:
    return db.get(RubricCriterion, criterion_id)


def list_criteria_by_rubric(db: Session, rubric_id: str) -> list[RubricCriterion]:
    statement = (
        select(RubricCriterion)
        .where(RubricCriterion.rubric_id == rubric_id)
        .order_by(RubricCriterion.created_at.asc())
    )
    return list(db.execute(statement).scalars().all())


def delete_criterion(db: Session, criterion: RubricCriterion) -> None:
    db.delete(criterion)


# ── EvidenceArtifact ──────────────────────────────────────────
def create_artifact(db: Session, artifact: EvidenceArtifact) -> EvidenceArtifact:
    db.add(artifact)
    db.flush()
    return artifact


def list_artifacts_by_project(db: Session, project_id: str) -> list[EvidenceArtifact]:
    statement = (
        select(EvidenceArtifact)
        .where(EvidenceArtifact.project_id == project_id)
        .order_by(EvidenceArtifact.collected_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def list_artifacts_by_indicator(
    db: Session, indicator_id: str
) -> list[EvidenceArtifact]:
    statement = select(EvidenceArtifact).where(
        EvidenceArtifact.indicator_id == indicator_id
    )
    return list(db.execute(statement).scalars().all())


# ── EvaluationRecord ──────────────────────────────────────────
def create_record(db: Session, record: EvaluationRecord) -> EvaluationRecord:
    db.add(record)
    db.flush()
    return record


def get_record(db: Session, record_id: str) -> Optional[EvaluationRecord]:
    return db.get(EvaluationRecord, record_id)


def list_records_by_project(
    db: Session,
    project_id: str,
    *,
    task_id: Optional[str] = None,
    student_id: Optional[str] = None,
    status: Optional[EvaluationStatus] = None,
) -> list[EvaluationRecord]:
    statement = select(EvaluationRecord).where(EvaluationRecord.project_id == project_id)
    if task_id:
        statement = statement.where(EvaluationRecord.task_id == task_id)
    if student_id:
        statement = statement.where(EvaluationRecord.student_id == student_id)
    if status:
        statement = statement.where(EvaluationRecord.status == status)
    statement = statement.order_by(EvaluationRecord.created_at.desc())
    return list(db.execute(statement).scalars().all())


def list_records_by_task(
    db: Session, task_id: str, *, student_id: Optional[str] = None
) -> list[EvaluationRecord]:
    statement = select(EvaluationRecord).where(EvaluationRecord.task_id == task_id)
    if student_id:
        statement = statement.where(EvaluationRecord.student_id == student_id)
    return list(db.execute(statement).scalars().all())


def list_student_visible_records(
    db: Session, project_id: str, student_id: str
) -> list[EvaluationRecord]:
    """学生可见的评价记录：仅自己且状态已发布。"""
    visible = {
        EvaluationStatus.PUBLISHED,
        EvaluationStatus.APPEALED,
        EvaluationStatus.RECHECKED,
        EvaluationStatus.FINALIZED,
    }
    statement = (
        select(EvaluationRecord)
        .where(
            EvaluationRecord.project_id == project_id,
            EvaluationRecord.student_id == student_id,
            EvaluationRecord.status.in_(visible),
        )
        .order_by(EvaluationRecord.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


# ── EvaluationScore ───────────────────────────────────────────
def create_score(db: Session, score: EvaluationScore) -> EvaluationScore:
    db.add(score)
    db.flush()
    return score


def bulk_create_scores(db: Session, scores: list[EvaluationScore]) -> list[EvaluationScore]:
    for score in scores:
        db.add(score)
    db.flush()
    return scores


def list_scores_by_record(db: Session, record_id: str) -> list[EvaluationScore]:
    statement = (
        select(EvaluationScore)
        .where(EvaluationScore.record_id == record_id)
        .order_by(EvaluationScore.created_at.asc())
    )
    return list(db.execute(statement).scalars().all())


def get_score(db: Session, score_id: str) -> Optional[EvaluationScore]:
    return db.get(EvaluationScore, score_id)


# ── 完整性校验辅助 ────────────────────────────────────────────
def list_goals_by_project(db: Session, project_id: str) -> list[LearningGoal]:
    statement = select(LearningGoal).where(LearningGoal.project_id == project_id)
    return list(db.execute(statement).scalars().all())


def list_indicators_by_project(
    db: Session, project_id: str
) -> list[EvaluationIndicator]:
    statement = select(EvaluationIndicator).where(
        EvaluationIndicator.project_id == project_id
    )
    return list(db.execute(statement).scalars().all())


def list_evidence_plans_by_project(
    db: Session, project_id: str
) -> list[EvidencePlan]:
    statement = select(EvidencePlan).where(EvidencePlan.project_id == project_id)
    return list(db.execute(statement).scalars().all())


def list_required_evidence_plan_ids(db: Session, project_id: str) -> list[str]:
    statement = select(EvidencePlan.id).where(
        EvidencePlan.project_id == project_id,
        EvidencePlan.required.is_(True),
    )
    return list(db.execute(statement).scalars().all())


# ── 复核队列 ──────────────────────────────────────────────────
def list_review_queue(
    db: Session,
    project_id: str,
    *,
    task_id: Optional[str] = None,
) -> list[dict]:
    """复核队列：低置信度、边界分、规则冲突、学生申诉。

    返回 [{submission, record, reasons, ai_confidence, total_score}]。
    - 低置信度：ai_confidence < 0.6
    - 边界分：total_score 在 60±5（及格线附近）
    - 规则冲突：suggested_score 与 final_score 差异 > 10
    - 学生申诉：record.status == APPEALED
    """
    # 查询项目下所有提交（含 review_status）
    task_ids_statement = select(Task.id).where(Task.project_id == project_id)
    task_ids = list(db.execute(task_ids_statement).scalars().all())
    if not task_ids:
        return []
    statement = select(Submission).where(Submission.task_id.in_(task_ids))
    if task_id:
        statement = statement.where(Submission.task_id == task_id)
    submissions = list(db.execute(statement).scalars().all())

    queue: list[dict] = []
    for sub in submissions:
        reasons: list[str] = []
        ai_confidence: Optional[float] = None
        total_score: Optional[float] = None
        record: Optional[EvaluationRecord] = None

        # 查找该提交关联的最新评价记录
        record_statement = (
            select(EvaluationRecord)
            .where(
                EvaluationRecord.task_id == sub.task_id,
                EvaluationRecord.student_id == sub.student_id,
            )
            .order_by(EvaluationRecord.created_at.desc())
        )
        record = db.execute(record_statement).scalars().first()

        if record:
            record_status = record.status.value if hasattr(record.status, "value") else str(record.status)
            try:
                status_enum = EvaluationStatus(record_status)
            except ValueError:
                status_enum = None
            if status_enum == EvaluationStatus.APPEALED:
                reasons.append("学生申诉")
            if record.total_score is not None:
                total_score = record.total_score
                if 55 <= record.total_score <= 65:
                    reasons.append("边界分")
            # 检查分维度评分的置信度与差异
            scores = list_scores_by_record(db, record.id)
            for score in scores:
                if score.ai_confidence is not None and score.ai_confidence < 0.6:
                    reasons.append("低置信度")
                    ai_confidence = score.ai_confidence
                    break
            for score in scores:
                if (
                    score.suggested_score is not None
                    and score.final_score is not None
                    and abs(score.suggested_score - score.final_score) > 10
                ):
                    reasons.append("规则冲突")
                    break

        # 仅入队未终态的提交
        sub_status = sub.review_status.value if hasattr(sub.review_status, "value") else str(sub.review_status)
        try:
            sub_enum = SubmissionReviewStatus(sub_status)
        except ValueError:
            sub_enum = None
        if sub_enum == SubmissionReviewStatus.FINALIZED:
            continue

        # 学生申诉的记录即使提交已 teacher_reviewed 也需入队
        if not reasons and sub_enum not in {
            SubmissionReviewStatus.TEACHER_REVIEWED,
            SubmissionReviewStatus.AI_REVIEWED,
        }:
            continue

        if not reasons:
            continue

        queue.append({
            "submission_id": sub.id,
            "task_id": sub.task_id,
            "student_id": sub.student_id,
            "review_status": sub_status,
            "record_id": record.id if record else None,
            "reasons": reasons,
            "ai_confidence": ai_confidence,
            "total_score": total_score,
        })
    return queue


# ── 提交状态机辅助 ────────────────────────────────────────────
def get_submission(db: Session, submission_id: str) -> Optional[Submission]:
    return db.get(Submission, submission_id)
