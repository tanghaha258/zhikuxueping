from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.school import Class, School
from app.models.teacher_class import TeacherClass
from app.models.user import Role, User


def school_visibility_filter(actor: User):
    if actor.role == Role.ADMIN:
        return None
    if actor.role in {Role.SCHOOL_ADMIN, Role.TEACHER} and actor.school_id:
        return School.id == actor.school_id
    return false()


def ensure_can_list_schools(actor: User) -> None:
    if actor.role in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        return
    _deny()


def class_visibility_filter(actor: User, school_id: str):
    ensure_can_read_school(actor, school_id)
    if actor.role in {Role.ADMIN, Role.SCHOOL_ADMIN}:
        return None
    return or_(
        Class.head_teacher_id == actor.id,
        Class.id.in_(select(TeacherClass.class_id).where(TeacherClass.teacher_id == actor.id)),
    )


def ensure_can_read_school(actor: User, school_id: str) -> None:
    if actor.role == Role.ADMIN:
        return
    if actor.role in {Role.SCHOOL_ADMIN, Role.TEACHER} and actor.school_id == school_id:
        return
    _deny()


def ensure_can_manage_school(actor: User, school: School) -> None:
    if actor.role == Role.ADMIN:
        return
    _deny()


def ensure_can_read_class(db: Session, actor: User, cls: Class) -> None:
    if actor.role == Role.ADMIN:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id == cls.school_id:
        return
    if actor.role == Role.TEACHER and actor.school_id == cls.school_id:
        if cls.head_teacher_id == actor.id:
            return
        if db.scalar(select(TeacherClass.id).where(TeacherClass.teacher_id == actor.id, TeacherClass.class_id == cls.id)):
            return
    _deny()


def ensure_can_manage_class(actor: User, cls: Class) -> None:
    if actor.role == Role.ADMIN:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id == cls.school_id:
        return
    _deny()


def ensure_can_manage_teacher_class(db: Session, actor: User, teacher: User, cls: Class) -> None:
    if actor.role == Role.SCHOOL_ADMIN:
        if actor.school_id != cls.school_id or actor.school_id != teacher.school_id:
            _deny()
    if teacher.role != Role.TEACHER or teacher.school_id != cls.school_id:
        raise AppException(code=40001, message="教师与班级必须属于同一学校", status_code=400)
    if actor.role == Role.ADMIN:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id == cls.school_id:
        return
    _deny()


def ensure_can_read_teacher_classes(actor: User, teacher: User) -> None:
    if actor.role == Role.ADMIN:
        return
    if actor.role == Role.SCHOOL_ADMIN and actor.school_id and actor.school_id == teacher.school_id:
        return
    if actor.role == Role.TEACHER and actor.id == teacher.id:
        return
    _deny()


def ensure_can_read_students(db: Session, actor: User, cls: Class) -> None:
    ensure_can_read_class(db, actor, cls)


def _deny() -> None:
    raise AppException(code=40301, message="权限不足", status_code=403)
