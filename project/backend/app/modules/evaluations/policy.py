from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.evaluation import Evaluation
from app.models.project import Project, ProjectClass
from app.models.task import Task
from app.models.user import Role, User
from app.modules.tasks.policy import ensure_can_manage_task, ensure_can_read_task


def ensure_can_read_task_evaluations(db: Session, actor: User, task_id: str) -> None:
    task, project, class_ids = _task_context(db, task_id)
    ensure_can_read_task(actor, project, class_ids)


def ensure_can_manage_task_evaluations(db: Session, actor: User, task_id: str) -> None:
    task, project, class_ids = _task_context(db, task_id)
    ensure_can_manage_task(actor, project, class_ids)


def ensure_can_read_evaluation(db: Session, actor: User, evaluation: Evaluation) -> None:
    ensure_can_read_task_evaluations(db, actor, evaluation.task_id)
    if actor.role == Role.STUDENT and actor.id != evaluation.student_id:
        raise AppException(code=40301, message="permission denied", status_code=403)


def ensure_can_manage_evaluation(db: Session, actor: User, evaluation: Evaluation) -> None:
    ensure_can_manage_task_evaluations(db, actor, evaluation.task_id)


def can_read_evaluation(db: Session, actor: User, evaluation: Evaluation) -> bool:
    try:
        ensure_can_read_evaluation(db, actor, evaluation)
    except AppException:
        return False
    return True


def _task_context(db: Session, task_id: str) -> tuple[Task, Project, list[str]]:
    task = db.get(Task, task_id)
    if not task:
        raise AppException(code=40401, message="task not found", status_code=404)
    project = db.get(Project, task.project_id)
    if not project:
        raise AppException(code=40401, message="project not found", status_code=404)
    statement = select(ProjectClass.class_id).where(ProjectClass.project_id == project.id)
    class_ids = list(db.execute(statement).scalars().all())
    return task, project, class_ids
