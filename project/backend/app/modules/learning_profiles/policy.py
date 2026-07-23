from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.school import Class
from app.models.teacher_class import TeacherClass
from app.models.user import Role, User


def ensure_can_access_class_learning_profile(
    db: Session,
    actor: User,
    class_id: str,
) -> Class:
    class_obj = db.get(Class, class_id)
    if not class_obj:
        raise AppException(code=40401, message="class not found", status_code=404)
    if actor.role == Role.ADMIN:
        return class_obj
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id == class_obj.school_id:
        return class_obj
    if actor.role == Role.TEACHER:
        if class_obj.head_teacher_id == actor.id:
            return class_obj
        statement = select(TeacherClass.id).where(
            TeacherClass.teacher_id == actor.id,
            TeacherClass.class_id == class_id,
        )
        if db.execute(statement).scalar_one_or_none():
            return class_obj
    raise AppException(code=40301, message="permission denied", status_code=403)
