from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.enums import ReviewStatus
from app.models.project import Project, ProjectClass
from app.models.resource import Resource
from app.models.user import Role, User
from app.modules.projects.policy import ensure_can_manage, ensure_can_read


# 学生可见的审核状态（计划 3.7）：仅已发布/已通过资源对学生可见。
_STUDENT_VISIBLE_REVIEW = {ReviewStatus.PUBLISHED, ReviewStatus.APPROVED}


def ensure_can_read_project_resources(db: Session, actor: User, project_id: str) -> None:
    project, class_ids = _project_context(db, project_id)
    ensure_can_read(actor, project, class_ids)


def ensure_can_manage_project_resources(db: Session, actor: User, project_id: str) -> None:
    project, class_ids = _project_context(db, project_id)
    ensure_can_manage(actor, project, class_ids)


def ensure_can_create_resource(db: Session, actor: User, project_id: str | None) -> None:
    if project_id:
        ensure_can_manage_project_resources(db, actor, project_id)
        return
    if actor.role not in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        raise AppException(code=40301, message="permission denied", status_code=403)


def ensure_can_read_resource(db: Session, actor: User, resource: Resource) -> None:
    if resource.project_id:
        ensure_can_read_project_resources(db, actor, resource.project_id)
        # 学生仅可读已发布/已通过资源（计划 3.7）
        if actor.role == Role.STUDENT and resource.review_status not in _STUDENT_VISIBLE_REVIEW:
            raise AppException(
                code=40301, message="资源尚未发布，无权访问", status_code=403
            )
        return
    if actor.role == Role.ADMIN or actor.id == resource.uploaded_by:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id:
        owner = db.get(User, resource.uploaded_by)
        if owner and owner.school_id == actor.school_id:
            return
    raise AppException(code=40301, message="permission denied", status_code=403)


def ensure_can_manage_resource(db: Session, actor: User, resource: Resource) -> None:
    if resource.project_id:
        ensure_can_manage_project_resources(db, actor, resource.project_id)
        return
    if actor.role not in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        raise AppException(code=40301, message="permission denied", status_code=403)
    ensure_can_read_resource(db, actor, resource)


def is_student(actor: User) -> bool:
    """判断 actor 是否为学生角色，用于资源列表学生侧过滤（计划 3.7）。"""
    return actor.role == Role.STUDENT


def _project_context(db: Session, project_id: str) -> tuple[Project, list[str]]:
    project = db.get(Project, project_id)
    if not project:
        raise AppException(code=40401, message="project not found", status_code=404)
    statement = select(ProjectClass.class_id).where(ProjectClass.project_id == project_id)
    class_ids = list(db.execute(statement).scalars().all())
    return project, class_ids
