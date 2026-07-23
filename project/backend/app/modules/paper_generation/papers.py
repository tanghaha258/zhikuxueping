"""Persistence operations for generated papers."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.paper import Paper
from app.models.paper_template import AiGeneratedPaper
from app.repositories.base import BaseRepository


def list_generated_papers(
    db: Session,
    teacher_id: str,
    skip: int = 0,
    limit: int = 100,
) -> list[AiGeneratedPaper]:
    statement = (
        select(AiGeneratedPaper)
        .where(AiGeneratedPaper.teacher_id == teacher_id)
        .order_by(AiGeneratedPaper.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())


def count_generated_papers(db: Session, teacher_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(AiGeneratedPaper)
        .where(AiGeneratedPaper.teacher_id == teacher_id)
    )
    return db.execute(statement).scalar() or 0


def get_generated_paper(db: Session, paper_id: str) -> Optional[AiGeneratedPaper]:
    return BaseRepository(db, AiGeneratedPaper).get_by_id(paper_id)


def update_generated_paper(db: Session, paper_id: str, data) -> AiGeneratedPaper:
    repository = BaseRepository(db, AiGeneratedPaper)
    paper = repository.get_by_id(paper_id)
    if not paper:
        raise ValueError("\u8bd5\u5377\u4e0d\u5b58\u5728")
    return repository.update(paper, data.model_dump(exclude_unset=True))


def finalize_paper(db: Session, paper_id: str) -> AiGeneratedPaper:
    repository = BaseRepository(db, AiGeneratedPaper)
    paper = repository.get_by_id(paper_id)
    if not paper:
        raise ValueError("\u8bd5\u5377\u4e0d\u5b58\u5728")

    paper.status = "finalized"
    existing = db.execute(
        select(Paper).where(Paper.title == paper.title, Paper.teacher_id == paper.teacher_id)
    ).scalars().first()
    if not existing:
        db.add(Paper(title=paper.title, teacher_id=paper.teacher_id, status="draft"))

    db.commit()
    db.refresh(paper)
    return paper


def delete_generated_paper(db: Session, paper_id: str) -> bool:
    repository = BaseRepository(db, AiGeneratedPaper)
    if not repository.get_by_id(paper_id):
        return False
    return repository.delete(paper_id)
