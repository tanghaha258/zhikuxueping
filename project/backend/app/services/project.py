import uuid
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.models.project import Project, ProjectStatus, ProjectSubject, ProjectClass, ProjectMember
from app.models.task import Task, TaskAssignment
from app.models.submission import Submission
from app.models.evaluation import Evaluation
from app.models.resource import Resource
from app.repositories.base import BaseRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


def create_project(db: Session, data: ProjectCreate, creator_id: str) -> Project:
    repo = BaseRepository(db, Project)
    obj = Project(
        title=data.title,
        description=data.description,
        cover_image_url=data.cover_image_url,
        grade=data.grade,
        start_date=data.start_date,
        end_date=data.end_date,
        creator_id=creator_id,
    )
    project = repo.create(obj)

    for subject_id in data.subject_ids:
        db.add(ProjectSubject(project_id=project.id, subject_id=subject_id))
    for class_id in data.class_ids:
        db.add(ProjectClass(project_id=project.id, class_id=class_id))
    if data.subject_ids or data.class_ids:
        db.commit()

    return project


def update_project(db: Session, project_id: str, data: ProjectUpdate) -> Project:
    repo = BaseRepository(db, Project)
    obj = repo.get_by_id(project_id)
    if not obj:
        raise ValueError("项目不存在")
    return repo.update(obj, data.model_dump(exclude_unset=True))


def get_project(db: Session, project_id: str) -> Project | None:
    return BaseRepository(db, Project).get_by_id(project_id)


def search_projects(
    db: Session,
    keyword: str = "",
    status: str = "",
    grade: str = "",
    creator_id: str = "",
    skip: int = 0,
    limit: int = 20,
) -> list[Project]:
    stmt = select(Project)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(Project.title.ilike(like))
    if status:
        stmt = stmt.where(Project.status == status)
    if grade:
        stmt = stmt.where(Project.grade == grade)
    if creator_id:
        stmt = stmt.where(Project.creator_id == creator_id)
    stmt = stmt.order_by(Project.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_projects(
    db: Session,
    keyword: str = "",
    status: str = "",
    grade: str = "",
    creator_id: str = "",
) -> int:
    stmt = select(func.count()).select_from(Project)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(Project.title.ilike(like))
    if status:
        stmt = stmt.where(Project.status == status)
    if grade:
        stmt = stmt.where(Project.grade == grade)
    if creator_id:
        stmt = stmt.where(Project.creator_id == creator_id)
    return db.execute(stmt).scalar() or 0


def list_projects(db: Session, skip: int = 0, limit: int = 100) -> list[Project]:
    return BaseRepository(db, Project).list_all(skip, limit)


def delete_project(db: Session, project_id: str) -> bool:
    repo = BaseRepository(db, Project)
    project = repo.get_by_id(project_id)
    if not project:
        return False

    # Cascade: find all tasks in this project
    task_ids = [
        row[0] for row in db.execute(
            select(Task.id).where(Task.project_id == project_id)
        ).all()
    ]

    # Delete evaluations for these tasks
    if task_ids:
        db.execute(
            Evaluation.__table__.delete().where(Evaluation.task_id.in_(task_ids))
        )
        # Delete submissions for these tasks
        db.execute(
            Submission.__table__.delete().where(Submission.task_id.in_(task_ids))
        )
        # Delete task assignments for these tasks
        db.execute(
            TaskAssignment.__table__.delete().where(TaskAssignment.task_id.in_(task_ids))
        )
        # Delete tasks
        db.execute(
            Task.__table__.delete().where(Task.project_id == project_id)
        )

    # Delete resources
    db.execute(
        Resource.__table__.delete().where(Resource.project_id == project_id)
    )

    # Delete project_subjects, project_classes, and project_members
    db.execute(
        ProjectSubject.__table__.delete().where(ProjectSubject.project_id == project_id)
    )
    db.execute(
        ProjectClass.__table__.delete().where(ProjectClass.project_id == project_id)
    )
    db.execute(
        ProjectMember.__table__.delete().where(ProjectMember.project_id == project_id)
    )

    return repo.delete(project_id)


def get_project_subject_ids(db: Session, project_id: str) -> list[str]:
    stmt = select(ProjectSubject.subject_id).where(ProjectSubject.project_id == project_id)
    return [row[0] for row in db.execute(stmt).all()]


def get_project_class_ids(db: Session, project_id: str) -> list[str]:
    stmt = select(ProjectClass.class_id).where(ProjectClass.project_id == project_id)
    return [row[0] for row in db.execute(stmt).all()]


def activate_project(db: Session, project_id: str) -> Project:
    """激活项目：DRAFT → ACTIVE"""
    repo = BaseRepository(db, Project)
    project = repo.get_by_id(project_id)
    if not project:
        raise ValueError("项目不存在")
    if project.status != ProjectStatus.DRAFT:
        raise ValueError(f"项目状态不允许激活，当前状态: {project.status.value}")
    return repo.update(project, {"status": ProjectStatus.ACTIVE})


def complete_project(db: Session, project_id: str) -> Project:
    """完成项目：ACTIVE → COMPLETED"""
    repo = BaseRepository(db, Project)
    project = repo.get_by_id(project_id)
    if not project:
        raise ValueError("项目不存在")
    if project.status != ProjectStatus.ACTIVE:
        raise ValueError(f"项目状态不允许完成，当前状态: {project.status.value}")
    return repo.update(project, {"status": ProjectStatus.COMPLETED})


def archive_project(db: Session, project_id: str) -> Project:
    """归档项目：COMPLETED → ARCHIVED"""
    repo = BaseRepository(db, Project)
    project = repo.get_by_id(project_id)
    if not project:
        raise ValueError("项目不存在")
    if project.status != ProjectStatus.COMPLETED:
        raise ValueError(f"项目状态不允许归档，当前状态: {project.status.value}")
    return repo.update(project, {"status": ProjectStatus.ARCHIVED})
