"""学情改进领域持久化操作（计划 Task 7）。

函数式 repository，唯一提交点在服务层；本模块只负责查询与对象装配。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    ImprovementSuggestionStatus,
    ImprovementTaskType,
)
from app.models.improvement import (
    ImprovementSuggestion,
    ImprovementTask,
    SecondEvaluation,
)


# ── ImprovementSuggestion ────────────────────────────────────
def create_suggestion(
    db: Session, suggestion: ImprovementSuggestion
) -> ImprovementSuggestion:
    db.add(suggestion)
    db.flush()
    return suggestion


def get_suggestion(db: Session, suggestion_id: str) -> Optional[ImprovementSuggestion]:
    return db.get(ImprovementSuggestion, suggestion_id)


def list_suggestions(
    db: Session,
    *,
    project_id: str,
    student_id: Optional[str] = None,
    status: Optional[ImprovementSuggestionStatus] = None,
    limit: int = 200,
) -> list[ImprovementSuggestion]:
    stmt = (
        select(ImprovementSuggestion)
        .where(ImprovementSuggestion.project_id == project_id)
        .order_by(ImprovementSuggestion.created_at.desc())
    )
    if student_id:
        stmt = stmt.where(ImprovementSuggestion.student_id == student_id)
    if status is not None:
        stmt = stmt.where(ImprovementSuggestion.status == status)
    stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


# ── ImprovementTask ─────────────────────────────────────────
def create_improvement_task(
    db: Session, task: ImprovementTask
) -> ImprovementTask:
    db.add(task)
    db.flush()
    return task


def get_improvement_task(
    db: Session, task_id: str
) -> Optional[ImprovementTask]:
    return db.get(ImprovementTask, task_id)


def list_improvement_tasks(
    db: Session,
    *,
    project_id: str,
    task_type: Optional[ImprovementTaskType] = None,
    link_suggestion_id: Optional[str] = None,
    limit: int = 200,
) -> list[ImprovementTask]:
    stmt = (
        select(ImprovementTask)
        .where(ImprovementTask.project_id == project_id)
        .order_by(ImprovementTask.created_at.desc())
    )
    if task_type is not None:
        stmt = stmt.where(ImprovementTask.task_type == task_type)
    if link_suggestion_id:
        stmt = stmt.where(ImprovementTask.link_suggestion_id == link_suggestion_id)
    stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


# ── SecondEvaluation ────────────────────────────────────────
def create_second_evaluation(
    db: Session, evaluation: SecondEvaluation
) -> SecondEvaluation:
    db.add(evaluation)
    db.flush()
    return evaluation


def get_second_evaluation(
    db: Session, evaluation_id: str
) -> Optional[SecondEvaluation]:
    return db.get(SecondEvaluation, evaluation_id)


def list_second_evaluations(
    db: Session,
    *,
    project_id: str,
    student_id: Optional[str] = None,
    link_suggestion_id: Optional[str] = None,
    link_improvement_task_id: Optional[str] = None,
    limit: int = 200,
) -> list[SecondEvaluation]:
    stmt = (
        select(SecondEvaluation)
        .where(SecondEvaluation.project_id == project_id)
        .order_by(SecondEvaluation.created_at.desc())
    )
    if student_id:
        stmt = stmt.where(SecondEvaluation.student_id == student_id)
    if link_suggestion_id:
        stmt = stmt.where(SecondEvaluation.link_suggestion_id == link_suggestion_id)
    if link_improvement_task_id:
        stmt = stmt.where(
            SecondEvaluation.link_improvement_task_id == link_improvement_task_id
        )
    stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())
