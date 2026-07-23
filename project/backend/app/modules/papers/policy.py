from sqlalchemy import false, select, true
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.paper import Paper
from app.models.user import Role, User


def paper_visibility_filter(db: Session, actor: User):
    if actor.role == Role.ADMIN:
        return true()
    if actor.role == Role.TEACHER:
        return Paper.teacher_id == actor.id
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id:
        teacher_ids = select(User.id).where(User.school_id == actor.school_id)
        return Paper.teacher_id.in_(teacher_ids)
    return false()


def ensure_can_read_paper(db: Session, actor: User, paper: Paper) -> None:
    if actor.role == Role.ADMIN or actor.id == paper.teacher_id:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id:
        owner = db.get(User, paper.teacher_id)
        if owner and owner.school_id == actor.school_id:
            return
    raise AppException(code=40301, message="permission denied", status_code=403)


def ensure_can_manage_paper(db: Session, actor: User, paper: Paper) -> None:
    if actor.role not in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        raise AppException(code=40301, message="permission denied", status_code=403)
    ensure_can_read_paper(db, actor, paper)
