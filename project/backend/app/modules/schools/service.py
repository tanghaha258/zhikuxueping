from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.school import Class, School
from app.models.teacher_class import TeacherClass
from app.models.user import User
from app.modules.schools import policy
from app.modules.schools.repository import SchoolRepository
from app.schemas.school import ClassCreate, ClassUpdate, SchoolCreate, SchoolUpdate


def list_schools(db: Session, actor: User, skip: int, limit: int) -> list[School]:
    policy.ensure_can_list_schools(actor)
    return SchoolRepository(db).list_schools(
        visibility_filter=policy.school_visibility_filter(actor), skip=skip, limit=limit
    )


def get_school(db: Session, actor: User, school_id: str) -> School:
    repository = SchoolRepository(db)
    school = _require_school(repository, school_id)
    policy.ensure_can_read_school(actor, school.id)
    return school


def create_school(db: Session, actor: User, data: SchoolCreate) -> School:
    if actor.role.value != "admin":
        raise AppException(code=40301, message="权限不足", status_code=403)
    school = School(**data.model_dump())
    SchoolRepository(db).add(school)
    return _commit_and_refresh(db, school)


def update_school(db: Session, actor: User, school_id: str, data: SchoolUpdate) -> School:
    repository = SchoolRepository(db)
    school = _require_school(repository, school_id)
    policy.ensure_can_manage_school(actor, school)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(school, field, value)
    return _commit_and_refresh(db, school)


def delete_school(db: Session, actor: User, school_id: str) -> None:
    repository = SchoolRepository(db)
    school = _require_school(repository, school_id)
    policy.ensure_can_manage_school(actor, school)
    if repository.school_has_dependencies(school.id):
        raise ValueError("学校仍有关联班级或用户，不能删除")
    repository.delete(school)
    _commit(db)


def list_classes(db: Session, actor: User, school_id: str, skip: int, limit: int) -> list[Class]:
    repository = SchoolRepository(db)
    _require_school(repository, school_id)
    return repository.list_classes(
        school_id,
        visibility_filter=policy.class_visibility_filter(actor, school_id),
        skip=skip,
        limit=limit,
    )


def get_class(db: Session, actor: User, class_id: str) -> Class:
    repository = SchoolRepository(db)
    cls = _require_class(repository, class_id)
    policy.ensure_can_read_class(db, actor, cls)
    return cls


def create_class(db: Session, actor: User, school_id: str, data: ClassCreate) -> Class:
    repository = SchoolRepository(db)
    school = _require_school(repository, school_id)
    if actor.role.value != "admin" and not (actor.role.value == "school_admin" and actor.school_id == school.id):
        raise AppException(code=40301, message="权限不足", status_code=403)
    cls = Class(school_id=school.id, **data.model_dump(exclude={"school_id"}))
    repository.add(cls)
    return _commit_and_refresh(db, cls)


def update_class(db: Session, actor: User, class_id: str, data: ClassUpdate) -> Class:
    repository = SchoolRepository(db)
    cls = _require_class(repository, class_id)
    policy.ensure_can_manage_class(actor, cls)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cls, field, value)
    return _commit_and_refresh(db, cls)


def delete_class(db: Session, actor: User, class_id: str) -> None:
    repository = SchoolRepository(db)
    cls = _require_class(repository, class_id)
    policy.ensure_can_manage_class(actor, cls)
    if repository.class_has_dependencies(cls.id):
        raise ValueError("班级仍有关联教学数据，不能删除")
    repository.delete(cls)
    _commit(db)


def list_students(db: Session, actor: User, class_id: str) -> list[User]:
    repository = SchoolRepository(db)
    cls = _require_class(repository, class_id)
    policy.ensure_can_read_students(db, actor, cls)
    return repository.list_students(cls.id)


def bind_teacher_class(db: Session, actor: User, teacher_id: str, class_id: str) -> TeacherClass:
    repository = SchoolRepository(db)
    teacher = _require_user(repository, teacher_id)
    cls = _require_class(repository, class_id)
    policy.ensure_can_manage_teacher_class(db, actor, teacher, cls)
    binding = repository.get_teacher_class(teacher.id, cls.id)
    if binding:
        return binding
    binding = TeacherClass(teacher_id=teacher.id, class_id=cls.id)
    repository.add(binding)
    return _commit_and_refresh(db, binding)


def unbind_teacher_class(db: Session, actor: User, teacher_id: str, class_id: str) -> None:
    repository = SchoolRepository(db)
    teacher = _require_user(repository, teacher_id)
    cls = _require_class(repository, class_id)
    policy.ensure_can_manage_teacher_class(db, actor, teacher, cls)
    binding = repository.get_teacher_class(teacher.id, cls.id)
    if not binding:
        raise ValueError("绑定关系不存在")
    repository.delete(binding)
    _commit(db)


def list_teacher_classes(db: Session, actor: User, teacher_id: str) -> list[TeacherClass]:
    repository = SchoolRepository(db)
    teacher = _require_user(repository, teacher_id)
    policy.ensure_can_read_teacher_classes(actor, teacher)
    return repository.list_teacher_classes(teacher.id)


def list_class_teachers(db: Session, actor: User, class_id: str) -> list[TeacherClass]:
    repository = SchoolRepository(db)
    cls = _require_class(repository, class_id)
    policy.ensure_can_read_class(db, actor, cls)
    return repository.list_class_teachers(cls.id)


def _require_school(repository: SchoolRepository, school_id: str) -> School:
    school = repository.get_school(school_id)
    if not school:
        raise AppException(code=41001, message="学校不存在", status_code=404)
    return school


def _require_class(repository: SchoolRepository, class_id: str) -> Class:
    cls = repository.get_class(class_id)
    if not cls:
        raise AppException(code=41001, message="班级不存在", status_code=404)
    return cls


def _require_user(repository: SchoolRepository, user_id: str) -> User:
    user = repository.get_user(user_id)
    if not user:
        raise AppException(code=40401, message="用户不存在", status_code=404)
    return user


def _commit_and_refresh(db: Session, record):
    _commit(db)
    db.refresh(record)
    return record


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
