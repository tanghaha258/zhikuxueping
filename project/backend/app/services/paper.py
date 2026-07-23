import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.paper import Paper, PaperStatus, AnswerKey, PaperSubmission, SubmissionStatus
from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.paper import PaperCreate, PaperUpdate, AnswerKeyUpsert


def create_paper(db: Session, data: PaperCreate, teacher_id: str) -> Paper:
    paper = Paper(
        title=data.title,
        teacher_id=teacher_id,
        class_ids=data.class_ids,
        file_url=data.file_url,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


def update_paper(db: Session, paper_id: str, data: PaperUpdate) -> Paper:
    repo = BaseRepository(db, Paper)
    paper = repo.get_by_id(paper_id)
    if not paper:
        raise ValueError("试卷不存在")
    return repo.update(paper, data.model_dump(exclude_unset=True))


def get_paper(db: Session, paper_id: str) -> Paper | None:
    return BaseRepository(db, Paper).get_by_id(paper_id)


def list_papers(db: Session, teacher_id: str = "", skip: int = 0, limit: int = 100, visibility_filter=None) -> list[Paper]:
    stmt = select(Paper)
    if visibility_filter is not None:
        stmt = stmt.where(visibility_filter)
    elif teacher_id:
        stmt = stmt.where(Paper.teacher_id == teacher_id)
    stmt = stmt.order_by(Paper.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_papers(db: Session, teacher_id: str = "", visibility_filter=None) -> int:
    stmt = select(func.count()).select_from(Paper)
    if visibility_filter is not None:
        stmt = stmt.where(visibility_filter)
    elif teacher_id:
        stmt = stmt.where(Paper.teacher_id == teacher_id)
    return db.execute(stmt).scalar() or 0


def delete_paper(db: Session, paper_id: str) -> bool:
    repo = BaseRepository(db, Paper)
    if not repo.get_by_id(paper_id):
        return False
    db.execute(AnswerKey.__table__.delete().where(AnswerKey.paper_id == paper_id))
    db.execute(PaperSubmission.__table__.delete().where(PaperSubmission.paper_id == paper_id))
    return repo.delete(paper_id)


def _calc_total_score(data: AnswerKeyUpsert) -> float:
    if data.total_score is not None:
        return data.total_score
    return sum(q.score for q in data.questions) if data.questions else 0.0


def upsert_answer_key(db: Session, paper_id: str, data: AnswerKeyUpsert) -> AnswerKey:
    existing = db.execute(
        select(AnswerKey).where(AnswerKey.paper_id == paper_id)
    ).scalar_one_or_none()
    total_score = _calc_total_score(data)
    if existing:
        existing.questions = [q.model_dump() for q in data.questions]
        existing.total_score = total_score
        db.commit()
        db.refresh(existing)
        return existing
    ak = AnswerKey(
        paper_id=paper_id,
        questions=[q.model_dump() for q in data.questions],
        total_score=total_score,
    )
    db.add(ak)
    db.commit()
    db.refresh(ak)
    return ak


def get_answer_key(db: Session, paper_id: str) -> AnswerKey | None:
    return db.execute(
        select(AnswerKey).where(AnswerKey.paper_id == paper_id)
    ).scalar_one_or_none()


def distribute_paper(db: Session, paper_id: str) -> int:
    paper = get_paper(db, paper_id)
    if not paper:
        raise ValueError("试卷不存在")
    if not paper.class_ids:
        raise ValueError("试卷未设置目标班级")

    class_ids = paper.class_ids
    stmt = select(User).where(
        User.class_id.in_(class_ids),
        User.role == "student",
    )
    students = list(db.execute(stmt).scalars().all())

    count = 0
    for student in students:
        existing = db.execute(
            select(PaperSubmission).where(
                PaperSubmission.paper_id == paper_id,
                PaperSubmission.student_id == student.id,
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(PaperSubmission(
            paper_id=paper_id,
            student_id=student.id,
        ))
        count += 1

    if count > 0:
        paper.status = PaperStatus.PUBLISHED
        db.commit()
    return count


def list_submissions(db: Session, paper_id: str) -> list[PaperSubmission]:
    stmt = select(PaperSubmission).where(
        PaperSubmission.paper_id == paper_id
    ).order_by(PaperSubmission.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_paper_stats(db: Session, paper_id: str) -> dict:
    subs = list_submissions(db, paper_id)
    total = len(subs)
    pending = sum(1 for s in subs if s.status == SubmissionStatus.PENDING)
    graded = sum(1 for s in subs if s.status == SubmissionStatus.GRADED)
    reviewed = sum(1 for s in subs if s.status == SubmissionStatus.REVIEWED)
    scored = [s.final_score or s.ai_score for s in subs if (s.final_score or s.ai_score) is not None]
    avg = sum(scored) / len(scored) if scored else None
    return {
        "total": total,
        "pending": pending,
        "graded": graded,
        "reviewed": reviewed,
        "average_score": round(avg, 1) if avg else None,
    }
 
