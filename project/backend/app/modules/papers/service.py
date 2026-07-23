"""Paper distribution, answer-key, and grading persistence operations."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.paper import AnswerKey, Paper, PaperStatus, PaperSubmission, SubmissionStatus
from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.paper import AnswerKeyUpsert, PaperCreate, PaperUpdate


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
    repository = BaseRepository(db, Paper)
    paper = repository.get_by_id(paper_id)
    if not paper:
        raise ValueError("\u8bd5\u5377\u4e0d\u5b58\u5728")
    return repository.update(paper, data.model_dump(exclude_unset=True))


def get_paper(db: Session, paper_id: str) -> Paper | None:
    return BaseRepository(db, Paper).get_by_id(paper_id)


def list_papers(
    db: Session,
    teacher_id: str = "",
    skip: int = 0,
    limit: int = 100,
    visibility_filter=None,
) -> list[Paper]:
    statement = select(Paper)
    if visibility_filter is not None:
        statement = statement.where(visibility_filter)
    elif teacher_id:
        statement = statement.where(Paper.teacher_id == teacher_id)
    statement = statement.order_by(Paper.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(statement).scalars().all())


def count_papers(db: Session, teacher_id: str = "", visibility_filter=None) -> int:
    statement = select(func.count()).select_from(Paper)
    if visibility_filter is not None:
        statement = statement.where(visibility_filter)
    elif teacher_id:
        statement = statement.where(Paper.teacher_id == teacher_id)
    return db.execute(statement).scalar() or 0


def delete_paper(db: Session, paper_id: str) -> bool:
    repository = BaseRepository(db, Paper)
    if not repository.get_by_id(paper_id):
        return False
    db.execute(AnswerKey.__table__.delete().where(AnswerKey.paper_id == paper_id))
    db.execute(PaperSubmission.__table__.delete().where(PaperSubmission.paper_id == paper_id))
    return repository.delete(paper_id)


def _calculate_total_score(data: AnswerKeyUpsert) -> float:
    if data.total_score is not None:
        return data.total_score
    return sum(question.score for question in data.questions) if data.questions else 0.0


def upsert_answer_key(db: Session, paper_id: str, data: AnswerKeyUpsert) -> AnswerKey:
    existing = db.execute(
        select(AnswerKey).where(AnswerKey.paper_id == paper_id)
    ).scalar_one_or_none()
    total_score = _calculate_total_score(data)
    if existing:
        existing.questions = [question.model_dump() for question in data.questions]
        existing.total_score = total_score
        db.commit()
        db.refresh(existing)
        return existing

    answer_key = AnswerKey(
        paper_id=paper_id,
        questions=[question.model_dump() for question in data.questions],
        total_score=total_score,
    )
    db.add(answer_key)
    db.commit()
    db.refresh(answer_key)
    return answer_key


def get_answer_key(db: Session, paper_id: str) -> AnswerKey | None:
    return db.execute(
        select(AnswerKey).where(AnswerKey.paper_id == paper_id)
    ).scalar_one_or_none()


def distribute_paper(db: Session, paper_id: str) -> int:
    paper = get_paper(db, paper_id)
    if not paper:
        raise ValueError("\u8bd5\u5377\u4e0d\u5b58\u5728")
    if not paper.class_ids:
        raise ValueError("\u8bd5\u5377\u672a\u8bbe\u7f6e\u76ee\u6807\u73ed\u7ea7")

    statement = select(User).where(
        User.class_id.in_(paper.class_ids),
        User.role == "student",
    )
    students = list(db.execute(statement).scalars().all())
    distributed = 0
    for student in students:
        existing = db.execute(
            select(PaperSubmission).where(
                PaperSubmission.paper_id == paper_id,
                PaperSubmission.student_id == student.id,
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(PaperSubmission(paper_id=paper_id, student_id=student.id))
        distributed += 1

    if distributed:
        paper.status = PaperStatus.PUBLISHED
        db.commit()
    return distributed


def list_submissions(db: Session, paper_id: str) -> list[PaperSubmission]:
    statement = (
        select(PaperSubmission)
        .where(PaperSubmission.paper_id == paper_id)
        .order_by(PaperSubmission.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def get_paper_stats(db: Session, paper_id: str) -> dict:
    submissions = list_submissions(db, paper_id)
    total = len(submissions)
    pending = sum(item.status == SubmissionStatus.PENDING for item in submissions)
    graded = sum(item.status == SubmissionStatus.GRADED for item in submissions)
    reviewed = sum(item.status == SubmissionStatus.REVIEWED for item in submissions)
    scores = [
        item.final_score or item.ai_score
        for item in submissions
        if (item.final_score or item.ai_score) is not None
    ]
    average = sum(scores) / len(scores) if scores else None
    return {
        "total": total,
        "pending": pending,
        "graded": graded,
        "reviewed": reviewed,
        "average_score": round(average, 1) if average else None,
    }
