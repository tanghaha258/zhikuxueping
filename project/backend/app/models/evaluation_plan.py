"""评价计划领域模型（计划 4.1 / Task 4）。

建立核心闭环"证据 -> 评价 -> 改进"环节所需的评价结构化对象：
量规与维度、正式学习证据、评价主记录、分维度评分。

设计原则：
- 量规版本化：一个项目可有多个量规版本，`is_current=True` 为当前正式版本；
  发布后不可修改维度，需新建版本，避免覆盖历史评价依据。
- 证据可追溯：EvidenceArtifact 关联提交/指标/证据计划，缺失证据不自动计零分。
- 评价主记录承载状态机（计划 4.3），分维度评分区分 AI 建议（suggested_score）
  与教师最终结论（final_score），人机差异必须记录原因。
- AI 来源默认权重为零：量规维度权重对 AI 来源独立配置，AI 仅提供建议，
  需教师确认后才转为正式结论。
- 历史简单评价（旧 Evaluation 表）保留只读，标记为 is_legacy，新评价走 EvaluationRecord。
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import (
    ArtifactSourceType,
    EvaluationSource,
    EvaluationStatus,
    EvaluationSubjectType,
    RubricStatus,
)


class Rubric(Base, TimestampMixin):
    """量规：一个项目可有多个版本，`is_current=True` 为当前正式版本。

    发布后不可修改维度（需新建版本），归档后不可用于新评价。
    """

    __tablename__ = "rubrics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="版本号")
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否当前正式版本"
    )
    status: Mapped[RubricStatus] = mapped_column(
        SAEnum(RubricStatus),
        default=RubricStatus.DRAFT,
        nullable=False,
        comment="量规状态",
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, comment="创建教师 ID")


class RubricCriterion(Base, TimestampMixin):
    """量规维度：绑定指标（可选）、维度名、权重、等级描述。

    `weight` 为 0-1 之间的浮点数，所有维度权重之和应为 1。
    `levels` 为 JSON 数组：[{level, score, description}]，每个等级必须有可观察描述。
    `ai_weight` 独立于教师权重，默认 0：AI 建议不参与加权计分，仅作参考。
    """

    __tablename__ = "rubric_criteria"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    rubric_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rubrics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    indicator_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("evaluation_indicators.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联指标（可空）",
    )
    dimension: Mapped[str] = mapped_column(String(200), nullable=False, comment="维度名称")
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="教师权重 0-1")
    ai_weight: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, comment="AI 权重，默认 0"
    )
    levels: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False, comment="[{level, score, description}]"
    )


class EvidenceArtifact(Base, TimestampMixin):
    """正式学习证据：关联提交/指标/证据计划，记录来源与内容引用。

    缺失证据（required=True 但无 artifact）在完整性检查中作为 blockers 返回，
    不自动计为零分。
    """

    __tablename__ = "evidence_artifacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submission_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联提交（可空，观察/测试类证据无提交）",
    )
    indicator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evaluation_indicators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联指标",
    )
    plan_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("evidence_plans.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联证据计划（可空）",
    )
    source_type: Mapped[ArtifactSourceType] = mapped_column(
        SAEnum(ArtifactSourceType), nullable=False, comment="证据来源类型"
    )
    content_ref: Mapped[str] = mapped_column(
        Text, nullable=False, comment="内容引用（URL/文本摘要/附件路径）"
    )
    collected_by: Mapped[str] = mapped_column(String(36), nullable=False, comment="采集者 ID")
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="采集时间"
    )


class EvaluationRecord(Base, TimestampMixin):
    """评价主记录：承载状态机，关联主体、指标、量规、确认教师。

    阶段验收：每条正式评价均可追溯到评价主体、指标、证据、时间和确认教师。
    `status` 驱动状态机（计划 4.3）。
    `confirmed_by`/`confirmed_at` 记录教师确认；`published_at` 记录发布给学生时间。
    旧 Evaluation 表的简单评价保留为 is_legacy，新评价走本表。
    """

    __tablename__ = "evaluation_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="任务级评价时关联任务",
    )
    student_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="被评学生 ID")
    evaluator_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="评价者 ID")
    subject_type: Mapped[EvaluationSubjectType] = mapped_column(
        SAEnum(EvaluationSubjectType), nullable=False, comment="评价主体类型"
    )
    subject_id: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="主体 ID（任务/指标/项目 ID）"
    )
    source: Mapped[EvaluationSource] = mapped_column(
        SAEnum(EvaluationSource), nullable=False, comment="评价来源"
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        SAEnum(EvaluationStatus),
        default=EvaluationStatus.DRAFT,
        nullable=False,
        comment="评价状态机",
    )
    rubric_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("rubrics.id", ondelete="SET NULL"),
        nullable=True,
        comment="使用的量规版本",
    )
    total_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="总分（加权后）"
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="总评语")
    confirmed_by: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, comment="确认教师 ID"
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="确认时间"
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="发布给学生时间"
    )


class EvaluationScore(Base, TimestampMixin):
    """分维度评分：区分 AI 建议（suggested_score）与教师最终结论（final_score）。

    阶段验收：教师修改 AI 分数必须记录差异原因（difference_reason）。
    `evidence_ref` 引用支撑该维度评分的证据（EvidenceArtifact ID 或描述）。
    `ai_confidence` 为 AI 置信度（0-1），用于复核队列筛选低置信度评分。
    """

    __tablename__ = "evaluation_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evaluation_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criterion_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rubric_criteria.id", ondelete="CASCADE"),
        nullable=False,
        comment="量规维度 ID",
    )
    suggested_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="AI 建议分数"
    )
    final_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="教师最终分数"
    )
    evidence_ref: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="证据引用"
    )
    ai_confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="AI 置信度 0-1"
    )
    difference_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="人机差异原因（教师修改 AI 分数时必填）"
    )
