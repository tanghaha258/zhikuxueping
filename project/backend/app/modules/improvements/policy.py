"""学情改进领域权限策略（计划 Task 7）。

复用 ``app.modules.projects.policy`` 的可见性与管理权限判断，
保证跨教师、跨学校、跨班级的访问规则与项目主表一致。
学生无权操作改进建议与改进任务。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.improvement import (
    ImprovementSuggestion,
    ImprovementTask,
)
from app.models.project import Project, ProjectClass
from app.models.user import Role, User
from app.modules.projects.policy import (
    ensure_can_manage,
    ensure_can_read,
)


def _class_ids(db: Session, project_id: str) -> list[str]:
    return list(
        db.execute(
            select(ProjectClass.class_id).where(ProjectClass.project_id == project_id)
        ).scalars().all()
    )


def _load_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise AppException(code=40401, message="项目不存在", status_code=404)
    return project


def ensure_can_manage_improvement(db: Session, actor: User, project_id: str) -> Project:
    """管理改进建议/任务/二次评价：教师/管理员，且具备项目管理权限。"""
    if actor.role not in {Role.TEACHER, Role.SCHOOL_ADMIN, Role.ADMIN}:
        raise AppException(
            code=40301, message="无权操作学情改进内容", status_code=403
        )
    project = _load_project(db, project_id)
    ensure_can_manage(actor, project, _class_ids(db, project_id))
    return project


def ensure_can_read_improvement(db: Session, actor: User, project_id: str) -> Project:
    """读取改进建议/任务/二次评价：与项目读取权限一致。"""
    project = _load_project(db, project_id)
    ensure_can_read(actor, project, _class_ids(db, project_id))
    return project


def ensure_can_manage_suggestion(
    db: Session, actor: User, suggestion: ImprovementSuggestion
) -> None:
    project = _load_project(db, suggestion.project_id)
    ensure_can_manage(actor, project, _class_ids(db, suggestion.project_id))


def ensure_can_manage_task_obj(
    db: Session, actor: User, task: ImprovementTask
) -> None:
    project = _load_project(db, task.project_id)
    ensure_can_manage(actor, project, _class_ids(db, task.project_id))
