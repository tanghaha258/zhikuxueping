from sqlalchemy.orm import Session
from app.models.subject import Subject
from app.repositories.base import BaseRepository
from app.schemas.subject import SubjectCreate, SubjectUpdate


def create_subject(db: Session, data: SubjectCreate) -> Subject:
    repo = BaseRepository(db, Subject)
    obj = Subject(**data.model_dump())
    return repo.create(obj)


def update_subject(db: Session, subject_id: str, data: SubjectUpdate) -> Subject:
    repo = BaseRepository(db, Subject)
    obj = repo.get_by_id(subject_id)
    if not obj:
        raise ValueError("学科不存在")
    return repo.update(obj, data.model_dump(exclude_unset=True))


def get_subject(db: Session, subject_id: str) -> Subject | None:
    return BaseRepository(db, Subject).get_by_id(subject_id)


def list_subjects(db: Session, skip: int = 0, limit: int = 100) -> list[Subject]:
    return BaseRepository(db, Subject).list_all(skip, limit)


def delete_subject(db: Session, subject_id: str) -> bool:
    return BaseRepository(db, Subject).delete(subject_id)
