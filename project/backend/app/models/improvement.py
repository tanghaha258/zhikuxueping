"""学情改进与二次评价领域模型（Task 7）。

依据核心闭环实施计划 4.1 节与 3.5.8 学情与改进页面规格：
- ``ImprovementSuggestion``：改进建议，必须引用评价证据（无证据抛 400）。
  承载状态机 draft -> adopted/modified/rejected，每次采用/修改/拒绝均留痕。
- ``ImprovementTask``：建议转换为改进任务（基础巩固 / 提升应用 / 拓展迁移）。
  关联原建议与原任务，便于追溯到原评价。
- ``SecondEvaluation``：二次评价，关联首次评价记录与第二次评价记录，
  记录前后对比摘要，验证改进效果。

设计约定：
- SQLAlchemy ``SAEnum`` 默认按枚举 *name* 存储，故 ``server_default`` 必须使用 name。
- 评价证据来源：``EvaluationRecord``/``EvaluationScore`` 或 ``AiJob``（评分场景）。
- 无证据不生成确定性学生标签：``evidence_reference`` 必填，缺失时服务层抛 400。
- 改进任务与二次评价均可追溯到原评价 ID（``created_from_evaluation_id`` 等）。
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import (
    ImprovementSuggestionStatus,
    ImprovementTaskType,
)


class ImprovementSuggestion(Base, TimestampMixin):
    """改进建议：必须引用评价证据，承载采用/修改/拒绝状态机。

    阶段验收：无证据不生成确定性学生标签；教师可采用、修改或拒绝建议；
    改进任务能追溯到原评价和二次评价。
    """

    __tablename__ = "improvement_suggestions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    student_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="被建议学生 ID（班级共性建议可空）",
    )
    created_from_evaluation_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="来源评价记录 ID（验收：建议必须引用评价证据）",
    )
    evidence_reference: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="证据引用：EvaluationScore ID / EvidenceArtifact ID / AiJob ID 等可追溯位置",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="建议标题")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="建议描述")
    status: Mapped[ImprovementSuggestionStatus] = mapped_column(
        SAEnum(ImprovementSuggestionStatus),
        nullable=False,
        default=ImprovementSuggestionStatus.DRAFT,
        server_default="DRAFT",
        comment="建议状态机枚举 name: DRAFT/ADOPTED/MODIFIED/REJECTED",
    )
    # 教师决定留痕：采用/修改/拒绝原因 + 决定者 + 决定时间
    decision_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="采用/修改/拒绝原因留痕"
    )
    modified_description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="教师修改后的建议描述（modified 状态时使用）"
    )
    decided_by: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, comment="决定教师 ID"
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="决定时间"
    )
    created_by: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="创建教师 ID"
    )


class ImprovementTask(Base, TimestampMixin):
    """改进任务：建议转换为对应类型的任务或测评。

    阶段验收：改进任务能追溯到原评价（``created_from_evaluation_id``）
    和原建议（``link_suggestion_id``），并关联原任务（``original_task_id``）。
    """

    __tablename__ = "improvement_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    link_suggestion_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("improvement_suggestions.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联建议 ID（可空：教师可直接创建改进任务）",
    )
    original_task_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        comment="原任务 ID（用于追溯到首次评价对应的任务）",
    )
    created_from_evaluation_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="来源评价记录 ID（验收：改进任务可追溯到原评价）",
    )
    task_type: Mapped[ImprovementTaskType] = mapped_column(
        SAEnum(ImprovementTaskType),
        nullable=False,
        comment="改进任务类型枚举 name",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="任务标题")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="任务描述")
    # 改进任务可创建为正式 Task 记录（学生可见）；不创建时仅作为改进计划留痕
    generated_task_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        comment="生成的正式任务 ID（若已发布给学生）",
    )
    created_by: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="创建教师 ID"
    )


class SecondEvaluation(Base, TimestampMixin):
    """二次评价：关联首次评价与第二次评价，记录前后对比摘要。

    阶段验收：教师可以从评价结果创建改进任务，并通过二次评价验证变化。
    ``comparison_summary`` 描述前后变化（分数差、达成度变化等），
    不自动生成结论，由教师填写或服务层基于证据聚合生成草稿。
    """

    __tablename__ = "second_evaluations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    student_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="被评学生 ID",
    )
    first_evaluation_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="首次评价记录 ID（EvaluationRecord.id）",
    )
    second_evaluation_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="第二次评价记录 ID（EvaluationRecord.id）",
    )
    link_suggestion_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("improvement_suggestions.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联建议 ID（可空）",
    )
    link_improvement_task_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("improvement_tasks.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联改进任务 ID（可空）",
    )
    comparison_summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="前后对比摘要：分数差/达成度变化/证据引用"
    )
    first_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="首次评价总分快照"
    )
    second_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="第二次评价总分快照"
    )
    created_by: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="创建教师 ID"
    )
