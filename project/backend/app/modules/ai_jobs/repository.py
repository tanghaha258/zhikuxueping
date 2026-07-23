"""AI 治理领域持久化操作。

函数式 repository，唯一提交点在服务层；本模块只负责查询与对象装配。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_job import AiJob, AiOutputVersion, QualityIssue
from app.models.ai_provider import AiProvider
from app.models.enums import (
    AiJobScene,
    AiJobStatus,
    IssueStatus,
    QualitySeverity,
)


# ── AiJob ────────────────────────────────────────────────────
def create_job(db: Session, job: AiJob) -> AiJob:
    db.add(job)
    db.flush()
    return job


def get_job(db: Session, job_id: str) -> AiJob | None:
    return db.get(AiJob, job_id)


def list_jobs(
    db: Session,
    *,
    project_id: str | None = None,
    scene: AiJobScene | None = None,
    status: AiJobStatus | None = None,
    initiated_by: str | None = None,
    limit: int = 100,
) -> list[AiJob]:
    stmt = select(AiJob).order_by(AiJob.created_at.desc())
    if project_id:
        stmt = stmt.where(AiJob.project_id == project_id)
    if scene is not None:
        stmt = stmt.where(AiJob.scene == scene)
    if status is not None:
        stmt = stmt.where(AiJob.status == status)
    if initiated_by:
        stmt = stmt.where(AiJob.initiated_by == initiated_by)
    stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_job_status(db: Session, job: AiJob, status: AiJobStatus) -> AiJob:
    job.status = status
    db.flush()
    return job


# ── AiOutputVersion ──────────────────────────────────────────
def create_version(db: Session, version: AiOutputVersion) -> AiOutputVersion:
    db.add(version)
    db.flush()
    return version


def get_version(db: Session, version_id: str) -> AiOutputVersion | None:
    return db.get(AiOutputVersion, version_id)


def list_versions_by_job(db: Session, job_id: str) -> list[AiOutputVersion]:
    stmt = (
        select(AiOutputVersion)
        .where(AiOutputVersion.job_id == job_id)
        .order_by(AiOutputVersion.version.asc())
    )
    return list(db.execute(stmt).scalars().all())


def next_version_number(db: Session, job_id: str) -> int:
    stmt = select(func.max(AiOutputVersion.version)).where(
        AiOutputVersion.job_id == job_id
    )
    current = db.execute(stmt).scalar()
    return (current or 0) + 1


def update_version(db: Session, version: AiOutputVersion, **fields) -> AiOutputVersion:
    for key, value in fields.items():
        setattr(version, key, value)
    db.flush()
    return version


# ── QualityIssue ─────────────────────────────────────────────
def create_issue(db: Session, issue: QualityIssue) -> QualityIssue:
    db.add(issue)
    db.flush()
    return issue


def create_issues(db: Session, issues: list[QualityIssue]) -> list[QualityIssue]:
    for issue in issues:
        db.add(issue)
    db.flush()
    return issues


def get_issue(db: Session, issue_id: str) -> QualityIssue | None:
    return db.get(QualityIssue, issue_id)


def list_issues_by_job(db: Session, job_id: str) -> list[QualityIssue]:
    stmt = (
        select(QualityIssue)
        .where(QualityIssue.job_id == job_id)
        .order_by(QualityIssue.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def list_issues_by_version(db: Session, version_id: str) -> list[QualityIssue]:
    stmt = select(QualityIssue).where(QualityIssue.version_id == version_id)
    return list(db.execute(stmt).scalars().all())


def update_issue(db: Session, issue: QualityIssue, **fields) -> QualityIssue:
    for key, value in fields.items():
        setattr(issue, key, value)
    db.flush()
    return issue


def count_open_blockers(db: Session, job_id: str) -> int:
    stmt = select(func.count()).select_from(QualityIssue).where(
        QualityIssue.job_id == job_id,
        QualityIssue.severity == QualitySeverity.BLOCKER,
        QualityIssue.status == IssueStatus.OPEN,
    )
    return int(db.execute(stmt).scalar() or 0)


# ── AiProvider ───────────────────────────────────────────────
def get_active_provider(db: Session) -> AiProvider | None:
    stmt = select(AiProvider).where(AiProvider.status == "active")
    return db.execute(stmt).scalars().first()
