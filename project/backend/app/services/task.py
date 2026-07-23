from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.task import Task, TaskAssignment, TaskStatus
from app.models.project import Project, ProjectStatus, ProjectClass
from app.models.resource import Resource
from app.models.submission import Submission
from app.models.evaluation import Evaluation
from app.repositories.base import BaseRepository
from app.schemas.task import TaskCreate, TaskUpdate


def create_task(db: Session, data: TaskCreate, created_by: str) -> Task:
    task = Task(
        project_id=data.project_id,
        title=data.title,
        description=data.description,
        task_type=data.task_type,
        max_score=data.max_score,
        deadline=data.deadline,
        rubric=data.rubric,
        created_by=created_by,
    )
    db.add(task)
    db.flush()

    for student_id in data.student_ids:
        db.add(TaskAssignment(
            task_id=task.id,
            student_id=student_id,
            assigned_at=datetime.now(),
        ))
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: str, data: TaskUpdate) -> Task:
    repo = BaseRepository(db, Task)
    task = repo.get_by_id(task_id)
    if not task:
        raise ValueError("任务不存在")
    return repo.update(task, data.model_dump(exclude_unset=True))


def get_task(db: Session, task_id: str) -> Task | None:
    return BaseRepository(db, Task).get_by_id(task_id)


def list_tasks_by_project(db: Session, project_id: str, skip: int = 0, limit: int = 100) -> list[Task]:
    stmt = select(Task).where(Task.project_id == project_id).order_by(Task.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def delete_task(db: Session, task_id: str) -> bool:
    repo = BaseRepository(db, Task)
    task = repo.get_by_id(task_id)
    if not task:
        return False

    # Cascade: delete evaluations, submissions, assignments for this task
    db.execute(
        Evaluation.__table__.delete().where(Evaluation.task_id == task_id)
    )
    db.execute(
        Submission.__table__.delete().where(Submission.task_id == task_id)
    )
    db.execute(
        TaskAssignment.__table__.delete().where(TaskAssignment.task_id == task_id)
    )

    return repo.delete(task_id)


def list_assignments(db: Session, task_id: str) -> list[TaskAssignment]:
    stmt = select(TaskAssignment).where(TaskAssignment.task_id == task_id)
    return list(db.execute(stmt).scalars().all())


def count_tasks_by_project(db: Session, project_id: str) -> int:
    stmt = select(func.count()).select_from(Task).where(Task.project_id == project_id)
    return db.execute(stmt).scalar() or 0


def list_my_tasks(db: Session, student_id: str, class_id: str | None = None) -> list[Task]:
    """返回分配给指定学生的所有任务，按班级过滤项目"""
    from app.models.user import User
    if class_id is None:
        user = db.get(User, student_id)
        class_id = user.class_id if user else None

    stmt = (
        select(Task)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(TaskAssignment.student_id == student_id)
    )

    if class_id:
        # Only show tasks from projects linked to the student's class
        stmt = stmt.join(Project, Task.project_id == Project.id)
        stmt = stmt.join(ProjectClass, ProjectClass.project_id == Project.id)
        stmt = stmt.where(ProjectClass.class_id == class_id)

    stmt = stmt.order_by(Task.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def publish_task(db: Session, task_id: str) -> Task:
    """发布任务：PENDING → IN_PROGRESS"""
    repo = BaseRepository(db, Task)
    task = repo.get_by_id(task_id)
    if not task:
        raise ValueError("任务不存在")
    if task.status != TaskStatus.PENDING:
        raise ValueError(f"任务状态不允许发布，当前状态: {task.status.value}")
    return repo.update(task, {"status": TaskStatus.IN_PROGRESS})


def close_task(db: Session, task_id: str) -> Task:
    """关闭任务：IN_PROGRESS → EVALUATED"""
    repo = BaseRepository(db, Task)
    task = repo.get_by_id(task_id)
    if not task:
        raise ValueError("任务不存在")
    if task.status != TaskStatus.IN_PROGRESS:
        raise ValueError(f"任务状态不允许关闭，当前状态: {task.status.value}")
    return repo.update(task, {"status": TaskStatus.EVALUATED})


def get_teacher_stats(db: Session, teacher_id: str) -> dict:
    """获取教师工作台统计数据"""
    active_projects = db.execute(
        select(func.count()).select_from(Project).where(
            Project.creator_id == teacher_id,
            Project.status == ProjectStatus.ACTIVE,
        )
    ).scalar() or 0

    # 教师创建的项目下的待评价任务
    pending_eval = db.execute(
        select(func.count()).select_from(Task).join(
            Project, Task.project_id == Project.id
        ).where(
            Project.creator_id == teacher_id,
            Task.status == TaskStatus.SUBMITTED,
        )
    ).scalar() or 0

    total_resources = db.execute(
        select(func.count()).select_from(Resource).where(
            Resource.uploaded_by == teacher_id,
        )
    ).scalar() or 0

    now = datetime.now(timezone.utc)
    week_later = now + timedelta(days=7)
    upcoming = db.execute(
        select(func.count()).select_from(Task).join(
            Project, Task.project_id == Project.id
        ).where(
            Project.creator_id == teacher_id,
            Task.deadline.isnot(None),
            Task.deadline >= now,
            Task.deadline <= week_later,
        )
    ).scalar() or 0

    return {
        "active_projects": active_projects,
        "pending_evaluation": pending_eval,
        "total_resources": total_resources,
        "upcoming_deadlines": upcoming,
    }
