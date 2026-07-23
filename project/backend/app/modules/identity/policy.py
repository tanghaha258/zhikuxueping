from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.school import Class
from app.models.user import Role, User


_SCHOOL_ADMIN_MANAGED_ROLES = {Role.TEACHER, Role.STUDENT, Role.PARENT}


def user_visibility_filter(actor: User):
    if actor.role == Role.ADMIN:
        return None
    if actor.role == Role.SCHOOL_ADMIN:
        school_id = _require_school_id(actor)
        class_ids = select(Class.id).where(Class.school_id == school_id)
        return or_(User.school_id == school_id, User.class_id.in_(class_ids))
    return false()


def ensure_can_view_user(db: Session, actor: User, target: User) -> None:
    if actor.role == Role.ADMIN:
        return
    if actor.role != Role.SCHOOL_ADMIN:
        _deny()
    school_id = _require_school_id(actor)
    if target.school_id == school_id:
        return
    if target.class_id and db.scalar(select(Class.id).where(Class.id == target.class_id, Class.school_id == school_id)):
        return
    _deny()


def ensure_can_manage_user(db: Session, actor: User, target: User) -> None:
    ensure_can_view_user(db, actor, target)
    if actor.role == Role.SCHOOL_ADMIN and target.role not in _SCHOOL_ADMIN_MANAGED_ROLES:
        _deny()


def ensure_can_assign_role(actor: User, role: Role) -> None:
    if actor.role == Role.ADMIN:
        return
    if actor.role == Role.SCHOOL_ADMIN and role in _SCHOOL_ADMIN_MANAGED_ROLES:
        return
    _deny()


def resolve_school_and_class(
    db: Session,
    actor: User | None,
    *,
    requested_school_id: str | None,
    class_id: str | None,
) -> tuple[str | None, str | None]:
    school_id = requested_school_id
    if actor and actor.role == Role.SCHOOL_ADMIN:
        actor_school_id = _require_school_id(actor)
        if school_id is not None and school_id != actor_school_id:
            _deny()
        school_id = actor_school_id

    if class_id is None:
        return school_id, None

    cls = db.scalar(select(Class).where(Class.id == class_id))
    if not cls:
        raise AppException(code=41001, message="班级不存在", status_code=404)
    if school_id is not None and cls.school_id != school_id:
        raise AppException(code=40001, message="班级不属于指定学校", status_code=400)
    return cls.school_id, cls.id


def _require_school_id(actor: User) -> str:
    if not actor.school_id:
        _deny()
    return actor.school_id


def _deny() -> None:
    raise AppException(code=40301, message="权限不足", status_code=403)
