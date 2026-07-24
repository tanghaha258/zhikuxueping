"""项目学情诊断持久化与真实数据聚合（Task 6）。

数据来源只包含项目班级、前测、提交、已发布评价与题目作答（计划 Task 6）：
- 前测：通过 ``ToolContextLink(artifact_type='paper', placement='pre_test')`` 关联项目的试卷数。
- 提交：``Submission`` 经 ``Task.project_id`` 聚合。
- 已发布评价：``EvaluationRecord`` 状态为 PUBLISHED/FINALIZED。
- 题目作答：``PaperSubmission`` 关联到项目链接的试卷。

本类只读聚合真实数据并写入诊断快照，不提交事务（由服务层控制边界），
不生成随机画像或模拟分层。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import EvaluationStatus
from app.models.evaluation_plan import EvaluationRecord
from app.models.paper import PaperSubmission
from app.models.project_learning_insight import ProjectLearningInsight
from app.models.submission import Submission
from app.models.task import Task
from app.models.tool_context import ToolContextLink

_PUBLISHED_EVAL_STATES = (EvaluationStatus.PUBLISHED, EvaluationStatus.FINALIZED)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectLearningInsightRepository:
    """项目学情诊断真实数据聚合与快照持久化。"""

    def __init__(self, db: Session):
        self.db = db

    # ── 四类数据来源计数 ───────────────────────────────────────
    def count_pre_tests(self, project_id: str) -> int:
        """关联到项目作为前测的试卷数（去重 artifact_id）。"""
        return self.db.scalar(
            select(func.count(func.distinct(ToolContextLink.artifact_id))).where(
                ToolContextLink.project_id == project_id,
                ToolContextLink.artifact_type == "paper",
                ToolContextLink.placement == "pre_test",
            )
        ) or 0

    def count_submissions(self, project_id: str) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(Submission)
            .join(Task, Submission.task_id == Task.id)
            .where(Task.project_id == project_id)
        ) or 0

    def count_published_evaluations(self, project_id: str) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(
                EvaluationRecord.project_id == project_id,
                EvaluationRecord.status.in_(_PUBLISHED_EVAL_STATES),
            )
        ) or 0

    def count_question_answers(self, project_id: str) -> int:
        """项目关联试卷的学生作答数。"""
        paper_ids_subq = select(ToolContextLink.artifact_id).where(
            ToolContextLink.project_id == project_id,
            ToolContextLink.artifact_type == "paper",
        )
        return self.db.scalar(
            select(func.count())
            .select_from(PaperSubmission)
            .where(PaperSubmission.paper_id.in_(paper_ids_subq))
        ) or 0

    def source_counts(self, project_id: str) -> dict:
        return {
            "pre_test": self.count_pre_tests(project_id),
            "submissions": self.count_submissions(project_id),
            "evaluations": self.count_published_evaluations(project_id),
            "question_answers": self.count_question_answers(project_id),
        }

    # ── 已发布评价明细（用于掌握度与分层）────────────────────
    def list_published_evaluations(self, project_id: str) -> list[EvaluationRecord]:
        return list(
            self.db.scalars(
                select(EvaluationRecord).where(
                    EvaluationRecord.project_id == project_id,
                    EvaluationRecord.status.in_(_PUBLISHED_EVAL_STATES),
                )
            ).all()
        )

    def task_max_scores(self, project_id: str) -> dict[str, int]:
        """项目内任务的满分映射，用于将评价分数换算为掌握度。"""
        rows = self.db.execute(
            select(Task.id, Task.max_score).where(Task.project_id == project_id)
        ).all()
        return {tid: (ms or 100) for tid, ms in rows}

    # ── 快照持久化 ────────────────────────────────────────────
    def get_current(self, project_id: str) -> Optional[ProjectLearningInsight]:
        return self.db.scalar(
            select(ProjectLearningInsight).where(
                ProjectLearningInsight.project_id == project_id,
                ProjectLearningInsight.is_current.is_(True),
            )
        )

    def get_by_id(self, project_id: str, insight_id: str) -> Optional[ProjectLearningInsight]:
        return self.db.scalar(
            select(ProjectLearningInsight).where(
                ProjectLearningInsight.id == insight_id,
                ProjectLearningInsight.project_id == project_id,
            )
        )

    def mark_previous_non_current(self, project_id: str) -> None:
        existing = list(
            self.db.scalars(
                select(ProjectLearningInsight).where(
                    ProjectLearningInsight.project_id == project_id,
                    ProjectLearningInsight.is_current.is_(True),
                )
            ).all()
        )
        for ins in existing:
            ins.is_current = False

    def create(self, insight: ProjectLearningInsight) -> ProjectLearningInsight:
        self.db.add(insight)
        self.db.flush()
        return insight
