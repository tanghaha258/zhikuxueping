from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.learning_profile import ClassLearningReport, LearningSnapshot
from app.models.project import ProjectClass
from app.models.school import Class, School
from app.models.teacher_class import TeacherClass
from app.models.user import User


class SchoolRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_school(self, school_id: str) -> School | None:
        return self.db.scalar(select(School).where(School.id == school_id))

    def list_schools(self, *, visibility_filter, skip: int, limit: int) -> list[School]:
        statement = select(School)
        if visibility_filter is not None:
            statement = statement.where(visibility_filter)
        return list(self.db.scalars(statement.order_by(School.created_at.desc()).offset(skip).limit(limit)).all())

    def get_class(self, class_id: str) -> Class | None:
        return self.db.scalar(select(Class).where(Class.id == class_id))

    def list_classes(self, school_id: str, *, visibility_filter, skip: int, limit: int) -> list[Class]:
        statement = select(Class).where(Class.school_id == school_id)
        if visibility_filter is not None:
            statement = statement.where(visibility_filter)
        return list(self.db.scalars(statement.order_by(Class.created_at.desc()).offset(skip).limit(limit)).all())

    def get_user(self, user_id: str) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id))

    def list_students(self, class_id: str) -> list[User]:
        return list(self.db.scalars(select(User).where(User.class_id == class_id, User.role == "student")).all())

    def get_teacher_class(self, teacher_id: str, class_id: str) -> TeacherClass | None:
        return self.db.scalar(
            select(TeacherClass).where(TeacherClass.teacher_id == teacher_id, TeacherClass.class_id == class_id)
        )

    def list_teacher_classes(self, teacher_id: str) -> list[TeacherClass]:
        return list(self.db.scalars(select(TeacherClass).where(TeacherClass.teacher_id == teacher_id)).all())

    def list_class_teachers(self, class_id: str) -> list[TeacherClass]:
        return list(self.db.scalars(select(TeacherClass).where(TeacherClass.class_id == class_id)).all())

    def add(self, record) -> None:
        self.db.add(record)

    def delete(self, record) -> None:
        self.db.delete(record)

    def school_has_dependencies(self, school_id: str) -> bool:
        return any(
            self.db.scalar(statement)
            for statement in (
                select(exists().where(Class.school_id == school_id)),
                select(exists().where(User.school_id == school_id)),
            )
        )

    def class_has_dependencies(self, class_id: str) -> bool:
        return any(
            self.db.scalar(statement)
            for statement in (
                select(exists().where(User.class_id == class_id)),
                select(exists().where(TeacherClass.class_id == class_id)),
                select(exists().where(ProjectClass.class_id == class_id)),
                select(exists().where(LearningSnapshot.class_id == class_id)),
                select(exists().where(ClassLearningReport.class_id == class_id)),
            )
        )
