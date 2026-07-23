"""统一项目工作区持久化（Task 3）。

只读聚合阶段进度、真实计数与时间线事件；写操作仅限阶段完成/重开。
本类不提交事务，由服务层控制事务边界。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_job import AiJob, AiJobStatus
from app.models.enums import (
    EvaluationStatus,
    IssueStatus,
    QualitySeverity,
    TaskPublishStatus,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.project import Project, ProjectClass
from app.models.project_stage import ProjectStageProgress
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import Role, User
from app.schemas.project_workspace import PHASE_ORDER

_PUBLISHED_EVAL_STATES = (EvaluationStatus.PUBLISHED, EvaluationStatus.FINALIZED)


class ProjectWorkspaceRepository:
    """项目工作区上下文只读聚合与阶段记录写入。"""

    def __init__(self, db: Session):
        self.db = db

    # ── 阶段进度 ──────────────────────────────────────────────
    def list_stages(self, project_id: str) -> list[ProjectStageProgress]:
        return list(
            self.db.scalars(
                select(ProjectStageProgress).where(
                    ProjectStageProgress.project_id == project_id
                )
            ).all()
        )

    def get_stage(self, project_id: str, phase: str) -> Optional[ProjectStageProgress]:
        return self.db.scalar(
            select(ProjectStageProgress).where(
                ProjectStageProgress.project_id == project_id,
                ProjectStageProgress.phase == phase,
            )
        )

    def get_or_create_stage(
        self, project_id: str, phase: str
    ) -> ProjectStageProgress:
        stage = self.get_stage(project_id, phase)
        if stage is None:
            stage = ProjectStageProgress(
                project_id=project_id,
                phase=phase,
                status="not_started",
            )
            self.db.add(stage)
            self.db.flush()
        return stage

    # ── 真实计数 ──────────────────────────────────────────────
    def count_tasks(self, project_id: str) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.project_id == project_id)
        ) or 0

    def count_published_tasks(self, project_id: str) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.project_id == project_id,
                Task.publish_status == TaskPublishStatus.PUBLISHED,
            )
        ) or 0

    def count_submissions(self, project_id: str) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(Submission)
            .join(Task, Submission.task_id == Task.id)
            .where(Task.project_id == project_id)
        ) or 0

    def count_evaluations(self, project_id: str) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(EvaluationRecord.project_id == project_id)
        ) or 0

    def count_unpublished_evaluations(self, project_id: str) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(
                EvaluationRecord.project_id == project_id,
                EvaluationRecord.status.not_in(_PUBLISHED_EVAL_STATES),
            )
        ) or 0

    def count_students(self, project_id: str) -> int:
        """项目关联班级中的启用学生数。"""
        class_ids_subq = select(ProjectClass.class_id).where(
            ProjectClass.project_id == project_id
        )
        return self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.class_id.in_(class_ids_subq),
                User.role == Role.STUDENT,
                User.is_active.is_(True),
            )
        ) or 0

    def count_ai_jobs(self, project_id: str) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(AiJob)
            .where(AiJob.project_id == project_id)
        ) or 0

    def count_pending_ai_reviews(self, project_id: str) -> int:
        """AI 已成功但待教师审核/采纳的数量。"""
        return self.db.scalar(
            select(func.count())
            .select_from(AiJob)
            .where(
                AiJob.project_id == project_id,
                AiJob.status == AiJobStatus.SUCCEEDED,
            )
        ) or 0

    def count_open_blocker_issues(self, project_id: str) -> int:
        """项目关联的未处理阻断质量问题数。"""
        from app.models.ai_job import QualityIssue

        return self.db.scalar(
            select(func.count())
            .select_from(QualityIssue)
            .join(AiJob, QualityIssue.job_id == AiJob.id)
            .where(
                AiJob.project_id == project_id,
                QualityIssue.severity == QualitySeverity.BLOCKER,
                QualityIssue.status == IssueStatus.OPEN,
            )
        ) or 0

    # ── 时间线事件 ────────────────────────────────────────────
    def list_timeline_events(self, project: Project) -> list[dict]:
        """聚合真实事件，按时间倒序返回。不伪造事件或时间戳。"""
        events: list[dict] = []

        # 项目创建
        if project.created_at:
            events.append(
                {
                    "type": "project_created",
                    "label": f"项目「{project.title}」创建",
                    "timestamp": project.created_at,
                    "actor": project.creator_id,
                }
            )

        # 阶段完成 / 重开
        for stage in self.list_stages(project.id):
            if stage.completed_at:
                events.append(
                    {
                        "type": "phase_completed",
                        "label": f"完成阶段：{_phase_label(stage.phase)}",
                        "timestamp": stage.completed_at,
                        "phase": stage.phase,
                        "actor": None,
                    }
                )
            if stage.reopened_at:
                events.append(
                    {
                        "type": "phase_reopened",
                        "label": f"重新开放阶段：{_phase_label(stage.phase)}",
                        "timestamp": stage.reopened_at,
                        "phase": stage.phase,
                        "actor": stage.reopened_by,
                    }
                )

        # 项目重新开放（归档后）
        if project.reopened_at:
            events.append(
                {
                    "type": "project_reopened",
                    "label": "归档项目重新开放",
                    "timestamp": project.reopened_at,
                    "actor": project.reopened_by,
                }
            )

        # 评价发布
        published_rows = list(
            self.db.execute(
                select(EvaluationRecord.published_at, EvaluationRecord.evaluator_id)
                .where(
                    EvaluationRecord.project_id == project.id,
                    EvaluationRecord.published_at.is_not(None),
                )
                .order_by(EvaluationRecord.published_at.desc())
            ).all()
        )
        for published_at, evaluator_id in published_rows:
            events.append(
                {
                    "type": "evaluation_published",
                    "label": "发布评价反馈",
                    "timestamp": published_at,
                    "actor": evaluator_id,
                }
            )

        # 任务创建
        task_rows = list(
            self.db.execute(
                select(Task.created_at, Task.created_by)
                .where(Task.project_id == project.id)
                .order_by(Task.created_at.desc())
                .limit(50)
            ).all()
        )
        for created_at, created_by in task_rows:
            if created_at:
                events.append(
                    {
                        "type": "task_created",
                        "label": "新增任务",
                        "timestamp": created_at,
                        "actor": created_by,
                    }
                )

        events.sort(key=lambda e: e["timestamp"], reverse=True)
        return events


def _phase_label(phase: str) -> str:
    labels = {
        "diagnosis": "学情诊断",
        "design": "跨学科设计",
        "preparation": "备课与准备",
        "implementation": "学习实施",
        "evaluation": "多元评价",
        "improvement": "改进循环",
        "closure": "结项归档",
    }
    return labels.get(phase, phase)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
