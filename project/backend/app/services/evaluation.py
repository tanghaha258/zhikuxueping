from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.evaluation import Evaluation
from app.schemas.evaluation import EvaluationCreate, EvaluationUpdate


def create_evaluation(db: Session, data: EvaluationCreate, evaluator_id: str) -> Evaluation:
    from app.repositories.base import BaseRepository
    eval_obj = Evaluation(
        task_id=data.task_id,
        student_id=data.student_id,
        evaluator_id=evaluator_id,
        score=data.score,
        comment=data.comment,
        eval_type=data.eval_type,
    )
    return BaseRepository(db, Evaluation).create(eval_obj)


def update_evaluation(db: Session, evaluation_id: str, data: EvaluationUpdate) -> Evaluation:
    from app.repositories.base import BaseRepository
    eval_obj = BaseRepository(db, Evaluation).get_by_id(evaluation_id)
    if not eval_obj:
        raise ValueError("评价记录不存在")
    return BaseRepository(db, Evaluation).update(eval_obj, data.model_dump(exclude_unset=True))


def list_evaluations_by_task(db: Session, task_id: str) -> list[Evaluation]:
    stmt = select(Evaluation).where(Evaluation.task_id == task_id).order_by(Evaluation.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def list_evaluations_by_student(db: Session, student_id: str) -> list[Evaluation]:
    stmt = select(Evaluation).where(Evaluation.student_id == student_id).order_by(Evaluation.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_evaluation(db: Session, evaluation_id: str) -> Evaluation | None:
    from app.repositories.base import BaseRepository
    return BaseRepository(db, Evaluation).get_by_id(evaluation_id)
