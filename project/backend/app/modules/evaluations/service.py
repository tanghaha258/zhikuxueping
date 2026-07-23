"""Evaluation persistence operations（Task 2 调整：旧写入入口已下线）。

旧 `Evaluation` 表只保留只读历史兼容：
- `create_evaluation` / `update_evaluation` 调用即抛 410，不再写入旧表。
- `list_evaluations_by_task` / `list_evaluations_by_student` / `get_evaluation`
  保留只读读取，用于展示历史"旧版评价记录"。

新评价（教师评价、AI 草稿、自评、互评）一律走 `EvaluationRecord`，
在 `app.modules.evaluation_plans.service` 与 `app.modules.evaluations.ai_grading`
中实现状态机与教师确认流程。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.evaluation import Evaluation
from app.repositories.base import BaseRepository
from app.schemas.evaluation import EvaluationCreate, EvaluationUpdate


_LEGACY_WRITE_DEPRECATED_MESSAGE = (
    "旧版评价写入入口已弃用，请使用 /api/v1/evaluation-plans/records 创建 EvaluationRecord"
)


def create_evaluation(
    db: Session,
    data: EvaluationCreate,
    evaluator_id: str,
) -> Evaluation:
    """已弃用：新评价必须写入 `EvaluationRecord`，不再向旧 `Evaluation` 表写入。"""
    raise AppException(
        code=41001,
        message=_LEGACY_WRITE_DEPRECATED_MESSAGE,
        status_code=410,
    )


def update_evaluation(
    db: Session,
    evaluation_id: str,
    data: EvaluationUpdate,
) -> Evaluation:
    """已弃用：旧版评价记录不可修改，保留为只读历史数据。"""
    raise AppException(
        code=41001,
        message=_LEGACY_WRITE_DEPRECATED_MESSAGE,
        status_code=410,
    )


def list_evaluations_by_task(db: Session, task_id: str) -> list[Evaluation]:
    statement = (
        select(Evaluation)
        .where(Evaluation.task_id == task_id)
        .order_by(Evaluation.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def list_evaluations_by_student(db: Session, student_id: str) -> list[Evaluation]:
    statement = (
        select(Evaluation)
        .where(Evaluation.student_id == student_id)
        .order_by(Evaluation.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def get_evaluation(db: Session, evaluation_id: str) -> Evaluation | None:
    return BaseRepository(db, Evaluation).get_by_id(evaluation_id)
