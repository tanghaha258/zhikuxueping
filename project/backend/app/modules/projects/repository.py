from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.evaluation import Evaluation
from app.models.project import Project, ProjectClass, ProjectMember, ProjectSubject
from app.models.resource import Resource
from app.models.school import Class
from app.models.submission import Submission
from app.models.task import Task, TaskAssignment
from app.models.user import Role, User


class ProjectRepository:
    """Project persistence operations. This class never commits a transaction."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, project_id: str) -> Project | None:
        return self.db.scalar(select(Project).where(Project.id == project_id))

    def list(
        self,
        *,
        keyword: str,
        status: str,
        grade: str,
        creator_id: str,
        visibility_filter,
        skip: int,
        limit: int,
    ) -> list[Project]:
        statement = self._filtered_statement(keyword, status, grade, creator_id, visibility_filter)
        statement = statement.order_by(Project.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(statement).all())

    def count(
        self,
        *,
        keyword: str,
        status: str,
        grade: str,
        creator_id: str,
        visibility_filter,
    ) -> int:
        statement = self._filtered_statement(keyword, status, grade, creator_id, visibility_filter)
        return self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    def add(self, project: Project) -> None:
        self.db.add(project)

    def add_subjects(self, project_id: str, subject_ids: list[str]) -> None:
        for subject_id in subject_ids:
            self.db.add(ProjectSubject(project_id=project_id, subject_id=subject_id))

    def add_classes(self, project_id: str, class_ids: list[str]) -> None:
        for class_id in class_ids:
            self.db.add(ProjectClass(project_id=project_id, class_id=class_id))

    def subject_ids(self, project_id: str) -> list[str]:
        statement = select(ProjectSubject.subject_id).where(ProjectSubject.project_id == project_id)
        return list(self.db.scalars(statement).all())

    def class_ids(self, project_id: str) -> list[str]:
        statement = select(ProjectClass.class_id).where(ProjectClass.project_id == project_id)
        return list(self.db.scalars(statement).all())

    def list_active_students_in_project_classes(self, project_id: str) -> list[tuple[User, str | None, str | None]]:
        """返回项目关联班级中启用学生，附带班级 ID 与名称（Task 1）。

        仅返回 role=STUDENT、is_active=True、且 class_id 命中项目关联班级的学生。
        结果按班级名、学生显示名排序，保证稳定顺序。
        """
        class_ids_subq = select(ProjectClass.class_id).where(
            ProjectClass.project_id == project_id
        )
        statement = (
            select(User, Class.id, Class.name)
            .join(Class, User.class_id == Class.id)
            .where(
                User.class_id.in_(class_ids_subq),
                User.role == Role.STUDENT,
                User.is_active.is_(True),
            )
            .order_by(Class.name.asc(), User.display_name.asc())
        )
        return list(self.db.execute(statement).all())

    def get_student_class_info(self, student_id: str) -> tuple[str | None, str | None] | None:
        """返回学生的 class_id 与 class_name（若学生不存在或无班级返回 None）。"""
        row = self.db.execute(
            select(User.class_id, Class.name)
            .join(Class, User.class_id == Class.id, isouter=True)
            .where(User.id == student_id, User.role == Role.STUDENT)
        ).first()
        if row is None:
            return None
        return row[0], row[1]

    def delete_with_dependents(self, project: Project) -> None:
        task_ids = list(self.db.scalars(select(Task.id).where(Task.project_id == project.id)).all())
        if task_ids:
            self.db.execute(Evaluation.__table__.delete().where(Evaluation.task_id.in_(task_ids)))
            self.db.execute(Submission.__table__.delete().where(Submission.task_id.in_(task_ids)))
            self.db.execute(TaskAssignment.__table__.delete().where(TaskAssignment.task_id.in_(task_ids)))
            self.db.execute(Task.__table__.delete().where(Task.project_id == project.id))

        self.db.execute(Resource.__table__.delete().where(Resource.project_id == project.id))
        self.db.execute(ProjectSubject.__table__.delete().where(ProjectSubject.project_id == project.id))
        self.db.execute(ProjectClass.__table__.delete().where(ProjectClass.project_id == project.id))
        self.db.execute(ProjectMember.__table__.delete().where(ProjectMember.project_id == project.id))
        self.db.delete(project)

    @staticmethod
    def _filtered_statement(
        keyword: str,
        status: str,
        grade: str,
        creator_id: str,
        visibility_filter,
    ):
        statement = select(Project)
        if visibility_filter is not None:
            statement = statement.where(visibility_filter)
        if keyword:
            statement = statement.where(Project.title.ilike(f"%{keyword}%"))
        if status:
            statement = statement.where(Project.status == status)
        if grade:
            statement = statement.where(Project.grade == grade)
        if creator_id:
            statement = statement.where(Project.creator_id == creator_id)
        return statement
