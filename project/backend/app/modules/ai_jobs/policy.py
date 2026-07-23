"""AI 治理领域权限策略。

教师/管理员可发起 AI 任务并审核；学生无权访问 AI 治理。
权限校验复用项目归属规则，确保跨教师、跨学校隔离不放宽。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.ai_job import AiJob
from app.models.project import Project, ProjectClass
from app.models.user import Role, User
from app.modules.projects.policy import ensure_can_manage, ensure_can_read


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


def ensure_can_create_job(db: Session, actor: User, project_id: str) -> Project:
    """发起 AI 任务需具备项目管理权限（教师/管理员）。"""
    project = _load_project(db, project_id)
    ensure_can_manage(actor, project, _class_ids(db, project_id))
    return project


def ensure_can_read_job(db: Session, actor: User, job: AiJob) -> None:
    """读取 AI 任务需具备项目读取权限。"""
    project = _load_project(db, job.project_id)
    ensure_can_read(actor, project, _class_ids(db, job.project_id))


def ensure_can_manage_job(db: Session, actor: User, job: AiJob) -> None:
    """审核/采用/重生成 AI 任务需具备项目管理权限。"""
    project = _load_project(db, job.project_id)
    ensure_can_manage(actor, project, _class_ids(db, job.project_id))


def require_teacher_or_admin(actor: User) -> None:
    """AI 治理操作仅限教师/管理员，学生无权。"""
    if actor.role not in {Role.TEACHER, Role.SCHOOL_ADMIN, Role.ADMIN}:
        raise AppException(code=40301, message="无权操作 AI 内容任务", status_code=403)
