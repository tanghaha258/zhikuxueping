from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.models.teacher_class import TeacherClass


def bind_class(db: Session, teacher_id: str, class_id: str) -> TeacherClass:
    existing = db.execute(
        select(TeacherClass).where(
            TeacherClass.teacher_id == teacher_id,
            TeacherClass.class_id == class_id,
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    tc = TeacherClass(teacher_id=teacher_id, class_id=class_id)
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return tc


def unbind_class(db: Session, teacher_id: str, class_id: str) -> bool:
    result = db.execute(
        delete(TeacherClass).where(
            TeacherClass.teacher_id == teacher_id,
            TeacherClass.class_id == class_id,
        )
    )
    db.commit()
    return result.rowcount > 0


def list_teacher_classes(db: Session, teacher_id: str) -> list[TeacherClass]:
    stmt = select(TeacherClass).where(TeacherClass.teacher_id == teacher_id)
    return list(db.execute(stmt).scalars().all())


def list_class_teachers(db: Session, class_id: str) -> list[TeacherClass]:
    stmt = select(TeacherClass).where(TeacherClass.class_id == class_id)
    return list(db.execute(stmt).scalars().all())
