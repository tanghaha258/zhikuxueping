from sqlalchemy import false, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.question import Question
from app.models.user import Role, User


def question_visibility_filter(actor: User):
    if actor.role == Role.ADMIN:
        return None
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id:
        return Question.created_by.in_(
            select(User.id).where(User.school_id == actor.school_id)
        )
    if actor.role in {Role.SCHOOL_ADMIN, Role.TEACHER}:
        return Question.created_by == actor.id
    return false()


def ensure_can_read_question(db: Session, actor: User, question: Question) -> None:
    if actor.role == Role.ADMIN or actor.id == question.created_by:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id:
        owner = db.get(User, question.created_by)
        if owner and owner.school_id == actor.school_id:
            return
    raise AppException(code=40301, message="permission denied", status_code=403)


def ensure_can_manage_question(db: Session, actor: User, question: Question) -> None:
    if actor.role not in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        raise AppException(code=40301, message="permission denied", status_code=403)
    ensure_can_read_question(db, actor, question)
