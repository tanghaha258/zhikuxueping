from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.submission import Submission
from app.schemas.submission import SubmissionCreate, SubmissionUpdate


def create_submission(db: Session, data: SubmissionCreate, student_id: str) -> Submission:
    existing = db.execute(
        select(Submission).where(Submission.task_id == data.task_id, Submission.student_id == student_id)
    ).scalar_one_or_none()

    if existing:
        existing.content = data.content
        existing.file_urls = data.file_urls
        existing.submitted_at = datetime.now()
        existing.status = "submitted"
        db.commit()
        db.refresh(existing)
        return existing

    sub = Submission(
        task_id=data.task_id,
        student_id=student_id,
        content=data.content,
        file_urls=data.file_urls,
        submitted_at=datetime.now(),
        status="submitted",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def update_submission(db: Session, submission_id: str, data: SubmissionUpdate) -> Submission:
    from app.repositories.base import BaseRepository
    sub = BaseRepository(db, Submission).get_by_id(submission_id)
    if not sub:
        raise ValueError("提交记录不存在")
    return BaseRepository(db, Submission).update(sub, data.model_dump(exclude_unset=True))


def get_submission(db: Session, submission_id: str) -> Submission | None:
    from app.repositories.base import BaseRepository
    return BaseRepository(db, Submission).get_by_id(submission_id)


def list_submissions_by_task(db: Session, task_id: str) -> list[Submission]:
    stmt = select(Submission).where(Submission.task_id == task_id).order_by(Submission.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def list_my_submissions(db: Session, student_id: str) -> list[Submission]:
    stmt = select(Submission).where(Submission.student_id == student_id).order_by(Submission.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_my_submission(db: Session, task_id: str, student_id: str) -> Submission | None:
    stmt = select(Submission).where(Submission.task_id == task_id, Submission.student_id == student_id)
    return db.execute(stmt).scalar_one_or_none()


def bulk_import_submissions(db: Session, task_id: str, items: list, teacher_id: str) -> dict:
    from app.models.task import Task
    from app.models.project import Project
    from app.models.submission import Submission

    task = db.get(Task, task_id)
    if not task:
        raise ValueError("任务不存在")

    created = []
    for item in items:
        sub = Submission(
            task_id=task_id,
            student_id=item.student_id,
            content=item.content or "",
            file_urls=[item.file_url],
            status="submitted",
        )
        db.add(sub)
        created.append(sub)
    db.commit()
    for sub in created:
        db.refresh(sub)
    return {"imported": len(created)}
