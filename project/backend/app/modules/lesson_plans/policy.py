from sqlalchemy import false, or_, select, true
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.saved_lesson_plan import SavedLessonPlan
from app.models.user import Role, User


def lesson_plan_visibility_filter(db: Session, actor: User):
    if actor.role == Role.ADMIN:
        return true()
    if actor.role == Role.TEACHER:
        return SavedLessonPlan.user_id == actor.id
    if actor.role == Role.SCHOOL_ADMIN:
        if not actor.school_id:
            return SavedLessonPlan.user_id == actor.id
        owner_ids = select(User.id).where(User.school_id == actor.school_id)
        return or_(
            SavedLessonPlan.user_id == actor.id,
            SavedLessonPlan.user_id.in_(owner_ids),
        )
    return false()


def ensure_can_read_lesson_plan(
    db: Session,
    actor: User,
    lesson_plan: SavedLessonPlan,
) -> None:
    if actor.role == Role.ADMIN or lesson_plan.user_id == actor.id:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id:
        owner = db.get(User, lesson_plan.user_id)
        if owner and owner.school_id == actor.school_id:
            return
    raise AppException(code=40301, message="permission denied", status_code=403)


def ensure_can_manage_lesson_plan(
    db: Session,
    actor: User,
    lesson_plan: SavedLessonPlan,
) -> None:
    if actor.role not in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        raise AppException(code=40301, message="permission denied", status_code=403)
    ensure_can_read_lesson_plan(db, actor, lesson_plan)
