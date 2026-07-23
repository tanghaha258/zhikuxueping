from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subject import Subject


class SubjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, subject_id: str) -> Subject | None:
        return self.db.scalar(select(Subject).where(Subject.id == subject_id))

    def list(self, skip: int, limit: int) -> list[Subject]:
        statement = select(Subject).offset(skip).limit(limit)
        return list(self.db.scalars(statement).all())

    def add(self, subject: Subject) -> None:
        self.db.add(subject)

    def delete(self, subject: Subject) -> None:
        self.db.delete(subject)
