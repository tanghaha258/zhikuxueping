"""项目设计领域持久化操作。

约定（与 `app.modules.projects.repository` 一致）：
- 仓库只负责读写 ORM，不调用 `db.commit()`。提交由服务层统一控制，
  便于跨表原子写入（如同时更新 problem 与 subject_contributions）。
- 列表查询显式使用 `select`，避免懒加载造成 N+1。
"""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.project_design import (
    EvaluationIndicator,
    EvidencePlan,
    LearningGoal,
    ProjectProblem,
    SubjectContribution,
    SubjectRole,
)


class ProjectDesignRepository:
    """Project design persistence operations. Never commits a transaction."""

    def __init__(self, db: Session):
        self.db = db

    # ── ProjectProblem ─────────────────────────────────────────
    def get_problem(self, project_id: str) -> ProjectProblem | None:
        """返回当前正式版本的真实问题（is_current=True）。"""
        return self.db.scalar(
            select(ProjectProblem)
            .where(
                ProjectProblem.project_id == project_id,
                ProjectProblem.is_current.is_(True),
            )
            .order_by(ProjectProblem.version.desc())
        )

    def list_problem_versions(self, project_id: str) -> list[ProjectProblem]:
        return list(
            self.db.scalars(
                select(ProjectProblem)
                .where(ProjectProblem.project_id == project_id)
                .order_by(ProjectProblem.version.desc())
            ).all()
        )

    def add_problem(self, problem: ProjectProblem) -> None:
        self.db.add(problem)

    def mark_problem_versions_non_current(self, project_id: str) -> None:
        self.db.execute(
            update(ProjectProblem)
            .where(
                ProjectProblem.project_id == project_id,
                ProjectProblem.is_current.is_(True),
            )
            .values(is_current=False)
        )

    def next_problem_version(self, project_id: str) -> int:
        latest = self.db.scalar(
            select(ProjectProblem.version)
            .where(ProjectProblem.project_id == project_id)
            .order_by(ProjectProblem.version.desc())
        )
        return int(latest or 0) + 1

    # ── SubjectContribution ────────────────────────────────────
    def list_contributions(self, project_id: str) -> list[SubjectContribution]:
        return list(
            self.db.scalars(
                select(SubjectContribution)
                .where(SubjectContribution.project_id == project_id)
                .order_by(SubjectContribution.created_at.asc())
            ).all()
        )

    def get_contribution(self, contribution_id: str) -> SubjectContribution | None:
        return self.db.scalar(
            select(SubjectContribution).where(SubjectContribution.id == contribution_id)
        )

    def find_contribution(
        self, project_id: str, subject_id: str
    ) -> SubjectContribution | None:
        return self.db.scalar(
            select(SubjectContribution).where(
                SubjectContribution.project_id == project_id,
                SubjectContribution.subject_id == subject_id,
            )
        )

    def find_core_contribution(
        self, project_id: str
    ) -> SubjectContribution | None:
        return self.db.scalar(
            select(SubjectContribution).where(
                SubjectContribution.project_id == project_id,
                SubjectContribution.role == SubjectRole.CORE,
            )
        )

    def add_contribution(self, contribution: SubjectContribution) -> None:
        self.db.add(contribution)

    def delete_contribution(self, contribution: SubjectContribution) -> None:
        self.db.delete(contribution)

    # ── LearningGoal ───────────────────────────────────────────
    def list_goals(self, project_id: str) -> list[LearningGoal]:
        return list(
            self.db.scalars(
                select(LearningGoal)
                .where(LearningGoal.project_id == project_id)
                .order_by(LearningGoal.created_at.asc())
            ).all()
        )

    def get_goal(self, goal_id: str) -> LearningGoal | None:
        return self.db.scalar(select(LearningGoal).where(LearningGoal.id == goal_id))

    def add_goal(self, goal: LearningGoal) -> None:
        self.db.add(goal)

    def delete_goal(self, goal: LearningGoal) -> None:
        self.db.delete(goal)

    # ── EvaluationIndicator ────────────────────────────────────
    def list_indicators(self, project_id: str) -> list[EvaluationIndicator]:
        return list(
            self.db.scalars(
                select(EvaluationIndicator)
                .where(EvaluationIndicator.project_id == project_id)
                .order_by(EvaluationIndicator.created_at.asc())
            ).all()
        )

    def list_indicators_by_goal(self, goal_id: str) -> list[EvaluationIndicator]:
        return list(
            self.db.scalars(
                select(EvaluationIndicator)
                .where(EvaluationIndicator.goal_id == goal_id)
                .order_by(EvaluationIndicator.created_at.asc())
            ).all()
        )

    def get_indicator(self, indicator_id: str) -> EvaluationIndicator | None:
        return self.db.scalar(
            select(EvaluationIndicator).where(EvaluationIndicator.id == indicator_id)
        )

    def add_indicator(self, indicator: EvaluationIndicator) -> None:
        self.db.add(indicator)

    def delete_indicator(self, indicator: EvaluationIndicator) -> None:
        self.db.delete(indicator)

    # ── EvidencePlan ───────────────────────────────────────────
    def list_evidence_plans(self, project_id: str) -> list[EvidencePlan]:
        return list(
            self.db.scalars(
                select(EvidencePlan)
                .where(EvidencePlan.project_id == project_id)
                .order_by(EvidencePlan.created_at.asc())
            ).all()
        )

    def list_evidence_plans_by_indicator(
        self, indicator_id: str
    ) -> list[EvidencePlan]:
        return list(
            self.db.scalars(
                select(EvidencePlan)
                .where(EvidencePlan.indicator_id == indicator_id)
                .order_by(EvidencePlan.created_at.asc())
            ).all()
        )

    def get_evidence_plan(self, plan_id: str) -> EvidencePlan | None:
        return self.db.scalar(
            select(EvidencePlan).where(EvidencePlan.id == plan_id)
        )

    def add_evidence_plan(self, plan: EvidencePlan) -> None:
        self.db.add(plan)

    def delete_evidence_plan(self, plan: EvidencePlan) -> None:
        self.db.delete(plan)
