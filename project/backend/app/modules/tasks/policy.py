from app.core.exceptions import AppException
from app.models.project import Project
from app.models.user import Role, User
from app.modules.projects.policy import ensure_can_manage, ensure_can_read


def ensure_can_read_task(actor: User, project: Project, class_ids: list[str]) -> None:
    ensure_can_read(actor, project, class_ids)


def ensure_can_manage_task(actor: User, project: Project, class_ids: list[str]) -> None:
    if actor.role not in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        raise AppException(code=40301, message="permission denied", status_code=403)
    ensure_can_manage(actor, project, class_ids)
