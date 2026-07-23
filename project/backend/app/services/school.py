from sqlalchemy.orm import Session
from app.models.school import School, Class
from app.repositories.base import BaseRepository
from app.schemas.school import SchoolCreate, SchoolUpdate, ClassCreate, ClassUpdate


def create_school(db: Session, data: SchoolCreate) -> School:
    repo = BaseRepository(db, School)
    obj = School(**data.model_dump())
    return repo.create(obj)


def update_school(db: Session, school_id: str, data: SchoolUpdate) -> School:
    repo = BaseRepository(db, School)
    obj = repo.get_by_id(school_id)
    if not obj:
        raise ValueError("学校不存在")
    return repo.update(obj, data.model_dump(exclude_unset=True))


def get_school(db: Session, school_id: str) -> School | None:
    return BaseRepository(db, School).get_by_id(school_id)


def list_schools(db: Session, skip: int = 0, limit: int = 100) -> list[School]:
    return BaseRepository(db, School).list_all(skip, limit)


def delete_school(db: Session, school_id: str) -> bool:
    return BaseRepository(db, School).delete(school_id)


def create_class(db: Session, data: ClassCreate) -> Class:
    repo = BaseRepository(db, Class)
    obj = Class(**data.model_dump())
    return repo.create(obj)


def update_class(db: Session, class_id: str, data: ClassUpdate) -> Class:
    repo = BaseRepository(db, Class)
    obj = repo.get_by_id(class_id)
    if not obj:
        raise ValueError("班级不存在")
    return repo.update(obj, data.model_dump(exclude_unset=True))


def get_class(db: Session, class_id: str) -> Class | None:
    return BaseRepository(db, Class).get_by_id(class_id)


def list_classes(db: Session, skip: int = 0, limit: int = 100) -> list[Class]:
    return BaseRepository(db, Class).list_all(skip, limit)


def delete_class(db: Session, class_id: str) -> bool:
    return BaseRepository(db, Class).delete(class_id)
