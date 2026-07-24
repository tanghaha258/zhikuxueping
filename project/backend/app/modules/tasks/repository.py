"""任务持久化操作。

约定（与 project_designs.repository 一致）：仓库只负责读写 ORM，
不调用 `db.commit()`，提交由服务层统一控制。

核心闭环扩展（计划 4.1/3.5/3.7）：
- `list_by_project` 支持 stage/tier/publish_status 过滤。
- `list_for_student` 增加 publish_status=PUBLISHED 过滤（学生仅见已发布任务）。
- 依赖管理：增删查 + `exists_path` 环检测（DFS）。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.evaluation import Evaluation
from app.models.project import Project, ProjectClass, ProjectStatus
from app.models.resource import Resource
from app.models.submission import Submission
from app.models.task import Task, TaskAssignment
from app.models.task_dependency import TaskDependency
from app.models.enums import TaskPublishStatus


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, task_id: str) -> Task | None:
        return self.db.get(Task, task_id)

    def get_project(self, project_id: str) -> Project | None:
        return self.db.get(Project, project_id)

    def project_class_ids(self, project_id: str) -> list[str]:
        statement = select(ProjectClass.class_id).where(ProjectClass.project_id == project_id)
        return list(self.db.execute(statement).scalars().all())

    def list_by_project(
        self,
        project_id: str,
        skip: int,
        limit: int,
        *,
        stage: str | None = None,
        tier: str | None = None,
        publish_status: str | None = None,
    ) -> list[Task]:
        statement = (
            select(Task)
            .where(Task.project_id == project_id)
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if stage:
            statement = statement.where(Task.stage == stage)
        if tier:
            statement = statement.where(Task.tier == tier)
        if publish_status:
            statement = statement.where(Task.publish_status == publish_status)
        return list(self.db.execute(statement).scalars().all())

    def count_by_project(
        self,
        project_id: str,
        *,
        stage: str | None = None,
        tier: str | None = None,
        publish_status: str | None = None,
    ) -> int:
        statement = select(func.count()).select_from(Task).where(Task.project_id == project_id)
        if stage:
            statement = statement.where(Task.stage == stage)
        if tier:
            statement = statement.where(Task.tier == tier)
        if publish_status:
            statement = statement.where(Task.publish_status == publish_status)
        return self.db.execute(statement).scalar() or 0

    def list_assignments(self, task_id: str) -> list[TaskAssignment]:
        statement = select(TaskAssignment).where(TaskAssignment.task_id == task_id)
        return list(self.db.execute(statement).scalars().all())

    def list_assignment_student_ids(self, task_id: str) -> list[str]:
        statement = select(TaskAssignment.student_id).where(TaskAssignment.task_id == task_id)
        return list(self.db.execute(statement).scalars().all())

    def list_for_student(
        self, student_id: str, class_id: str | None, *, published_only: bool = True
    ) -> list[Task]:
        """学生任务列表。

        `published_only=True` 时仅返回 publish_status=PUBLISHED/IN_PROGRESS 的任务
        （计划 3.7：学生仅见已发布任务；IN_PROGRESS 表示发布后进行中，仍对学生可见）。
        旧任务迁移后映射为 PUBLISHED，保留可见性。
        """
        statement = (
            select(Task)
            .join(TaskAssignment, TaskAssignment.task_id == Task.id)
            .where(TaskAssignment.student_id == student_id)
        )
        if published_only:
            statement = statement.where(
                Task.publish_status.in_(
                    [TaskPublishStatus.PUBLISHED, TaskPublishStatus.IN_PROGRESS]
                )
            )
        if class_id:
            statement = statement.join(Project, Task.project_id == Project.id)
            statement = statement.join(ProjectClass, ProjectClass.project_id == Project.id)
            statement = statement.where(ProjectClass.class_id == class_id)
        return list(self.db.execute(statement.order_by(Task.created_at.desc())).scalars().all())

    def add(self, task: Task) -> None:
        self.db.add(task)

    def add_assignments(self, task_id: str, student_ids: list[str]) -> None:
        for student_id in student_ids:
            self.db.add(TaskAssignment(task_id=task_id, student_id=student_id, assigned_at=datetime.now()))

    def replace_assignments(self, task_id: str, student_ids: list[str]) -> None:
        """整体替换任务分配：先删除旧分配，再写入去重后的新分配（Task 1）。"""
        self.db.execute(delete(TaskAssignment).where(TaskAssignment.task_id == task_id))
        for student_id in student_ids:
            self.db.add(TaskAssignment(task_id=task_id, student_id=student_id, assigned_at=datetime.now()))

    def delete_with_dependents(self, task: Task) -> None:
        task_id = task.id
        self.db.execute(delete(Evaluation).where(Evaluation.task_id == task_id))
        self.db.execute(delete(Submission).where(Submission.task_id == task_id))
        self.db.execute(delete(TaskAssignment).where(TaskAssignment.task_id == task_id))
        # 同步删除该任务参与的依赖边（CASCADE 已设，显式删除保险）
        self.db.execute(
            delete(TaskDependency).where(
                (TaskDependency.predecessor_id == task_id)
                | (TaskDependency.successor_id == task_id)
            )
        )
        self.db.delete(task)

    # ── 依赖管理 ───────────────────────────────────────────────
    def find_dependency(self, predecessor_id: str, successor_id: str) -> TaskDependency | None:
        return self.db.scalar(
            select(TaskDependency).where(
                TaskDependency.predecessor_id == predecessor_id,
                TaskDependency.successor_id == successor_id,
            )
        )

    def list_predecessors(self, task_id: str) -> list[TaskDependency]:
        return list(
            self.db.scalars(
                select(TaskDependency)
                .where(TaskDependency.successor_id == task_id)
                .order_by(TaskDependency.created_at.asc())
            ).all()
        )

    def list_successors(self, task_id: str) -> list[TaskDependency]:
        return list(
            self.db.scalars(
                select(TaskDependency)
                .where(TaskDependency.predecessor_id == task_id)
                .order_by(TaskDependency.created_at.asc())
            ).all()
        )

    def add_dependency(self, dependency: TaskDependency) -> None:
        self.db.add(dependency)

    def remove_dependency(self, dependency: TaskDependency) -> None:
        self.db.delete(dependency)

    def exists_path(self, start_id: str, target_id: str) -> bool:
        """检查是否存在从 start 沿 successor 方向到达 target 的有向路径。

        用于环检测：添加 (predecessor, successor) 前，若
        exists_path(successor, predecessor) 为真，则添加后会形成环。
        自环（start == target）视为存在路径。
        """
        if start_id == target_id:
            return True
        visited: set[str] = set()
        stack: list[str] = [start_id]
        while stack:
            node = stack.pop()
            if node == target_id:
                return True
            if node in visited:
                continue
            visited.add(node)
            succ_ids = self.db.execute(
                select(TaskDependency.successor_id).where(
                    TaskDependency.predecessor_id == node
                )
            ).scalars().all()
            for s in succ_ids:
                if s not in visited:
                    stack.append(s)
        return False

    def teacher_stats(self, teacher_id: str) -> dict:
        active_projects = self.db.execute(
            select(func.count()).select_from(Project).where(
                Project.creator_id == teacher_id,
                Project.status == ProjectStatus.ACTIVE,
            )
        ).scalar() or 0
        pending_evaluation = self.db.execute(
            select(func.count()).select_from(Task).join(Project, Task.project_id == Project.id).where(
                Project.creator_id == teacher_id,
                Task.status == "submitted",
            )
        ).scalar() or 0
        total_resources = self.db.execute(
            select(func.count()).select_from(Resource).where(Resource.uploaded_by == teacher_id)
        ).scalar() or 0
        now = datetime.now(timezone.utc)
        upcoming_deadlines = self.db.execute(
            select(func.count()).select_from(Task).join(Project, Task.project_id == Project.id).where(
                Project.creator_id == teacher_id,
                Task.deadline.isnot(None),
                Task.deadline >= now,
                Task.deadline <= now + timedelta(days=7),
            )
        ).scalar() or 0
        return {
            "active_projects": active_projects,
            "pending_evaluation": pending_evaluation,
            "total_resources": total_resources,
            "upcoming_deadlines": upcoming_deadlines,
        }

    # ── Task 9：跨项目任务中心与执行进度聚合 ───────────────────
    def list_for_center(self, visibility_filter) -> list[tuple[Task, str]]:
        """返回 actor 可管理项目下的任务，附带项目标题。

        `visibility_filter` 与 projects 模块一致：
        - admin → None（全部）
        - school_admin → Project.school_id == actor.school_id
        - teacher → Project.creator_id == actor.id
        - 其他角色 → 不返回任何任务
        归档项目下的任务仍返回（用于"待关闭/归档"提醒），由服务层分类。
        """
        statement = (
            select(Task, Project.title.label("project_title"))
            .join(Project, Task.project_id == Project.id)
            .order_by(Task.created_at.desc())
        )
        if visibility_filter is not None:
            statement = statement.where(visibility_filter)
        rows = self.db.execute(statement).all()
        return [(row[0], row[1]) for row in rows]

    def count_assignments(self, task_id: str) -> int:
        return self.db.scalar(
            select(func.count()).select_from(TaskAssignment).where(
                TaskAssignment.task_id == task_id
            )
        ) or 0

    def count_submitted_students(self, task_id: str) -> int:
        """已提交学生数：submission.status 非 draft 的不同学生数。"""
        return self.db.scalar(
            select(func.count(func.distinct(Submission.student_id))).where(
                Submission.task_id == task_id,
                Submission.status != "draft",
            )
        ) or 0

    def count_evaluated_students(self, task_id: str) -> int:
        """已评价学生数：submission.status 为 evaluated 的不同学生数。"""
        return self.db.scalar(
            select(func.count(func.distinct(Submission.student_id))).where(
                Submission.task_id == task_id,
                Submission.status == "evaluated",
            )
        ) or 0

    def list_predecessor_publish_statuses(self, task_id: str) -> list[str]:
        """返回任务所有前置任务的 publish_status 值列表。"""
        return list(
            self.db.execute(
                select(Task.publish_status)
                .join(TaskDependency, TaskDependency.predecessor_id == Task.id)
                .where(TaskDependency.successor_id == task_id)
            ).scalars().all()
        )
