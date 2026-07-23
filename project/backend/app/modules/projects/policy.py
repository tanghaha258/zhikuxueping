from sqlalchemy import false, select

from app.core.exceptions import AppException
from app.models.project import Project, ProjectClass, ProjectStatus
from app.models.user import Role, User


def project_visibility_filter(actor: User):
    """Return the SQL predicate that limits a project list to the actor's scope."""
    if actor.role == Role.ADMIN:
        return None
    if actor.role == Role.SCHOOL_ADMIN:
        if actor.school_id:
            return Project.school_id == actor.school_id
        return Project.creator_id == actor.id
    if actor.role == Role.TEACHER:
        return Project.creator_id == actor.id
    if actor.class_id:
        return Project.id.in_(
            select(ProjectClass.project_id).where(ProjectClass.class_id == actor.class_id)
        )
    return false()


def ensure_can_read(actor: User, project: Project, class_ids: list[str]) -> None:
    if actor.role == Role.ADMIN:
        return
    if actor.id == project.creator_id:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id and actor.school_id == project.school_id:
        return
    if actor.class_id and actor.class_id in class_ids:
        return
    raise AppException(code=40301, message="无权访问该项目", status_code=403)


def ensure_can_manage(actor: User, project: Project, class_ids: list[str]) -> None:
    if actor.role not in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        raise AppException(code=40301, message="无权管理该项目", status_code=403)
    ensure_can_read(actor, project, class_ids)


def ensure_not_archived(project: Project) -> None:
    """归档只读守卫：archived 状态下所有写操作拒绝（409）。

    依据计划 Task 9 验收：归档后只读；重新开放必须授权并记录原因。
    若需修改归档项目，应先由 school_admin 调用 reopen 流程。
    """
    if project.status == ProjectStatus.ARCHIVED:
        raise AppException(
            code=40903,
            message="项目已归档，禁止写操作；如需修改请先申请重新开放",
            status_code=409,
        )


def ensure_can_reopen(actor: User, project: Project) -> None:
    """重新开放归档项目授权守卫：仅 school_admin 可调用。

    依据计划 Task 9 验收：重新开放必须授权并记录原因。
    普通教师/学生无权重新开放归档项目。
    """
    if actor.role != Role.SCHOOL_ADMIN:
        raise AppException(
            code=40301,
            message="仅学校管理员可重新开放归档项目",
            status_code=403,
        )
