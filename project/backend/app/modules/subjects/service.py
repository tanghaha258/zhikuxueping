from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.subject import Subject
from app.modules.subjects.repository import SubjectRepository
from app.schemas.subject import SubjectCreate, SubjectUpdate


def list_subjects(db: Session, skip: int, limit: int) -> list[Subject]:
    return SubjectRepository(db).list(skip, limit)


def get_subject(db: Session, subject_id: str) -> Subject:
    return _require_subject(SubjectRepository(db), subject_id)


def create_subject(db: Session, data: SubjectCreate) -> Subject:
    subject = Subject(**data.model_dump())
    SubjectRepository(db).add(subject)
    return _commit_and_refresh(db, subject)


def update_subject(db: Session, subject_id: str, data: SubjectUpdate) -> Subject:
    subject = _require_subject(SubjectRepository(db), subject_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(subject, field, value)
    return _commit_and_refresh(db, subject)


def delete_subject(db: Session, subject_id: str) -> None:
    repository = SubjectRepository(db)
    subject = _require_subject(repository, subject_id)
    repository.delete(subject)
    _commit(db)


def _require_subject(repository: SubjectRepository, subject_id: str) -> Subject:
    subject = repository.get(subject_id)
    if not subject:
        raise AppException(code=40401, message="Subject not found", status_code=404)
    return subject


def _commit_and_refresh(db: Session, record: Subject) -> Subject:
    _commit(db)
    db.refresh(record)
    return record


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
