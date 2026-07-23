"""AI 内容任务治理领域模型（Task 5）。

依据核心闭环实施计划 4.1 节：
- ``AiJob``：一次 AI 内容生成任务，承载状态机、Provider、提示版本、输入摘要与失败原因。
- ``AiOutputVersion``：同一任务的多次输出版本，支持局部重生成与版本对比。
- ``QualityIssue``：质量校验产出的阻断/警告/建议，阻断问题未处理不能标记正式版本。

状态机（计划 4.3）：
    created -> queued -> running -> succeeded/failed -> reviewed -> adopted/rejected

设计约定：
- SQLAlchemy ``SAEnum`` 默认按枚举 *name* 存储，故 ``server_default`` 必须使用 name。
- 原始 AI 输出、教师修改、采用状态和最终版本完整留存，满足 AI 可信验收（8.3）。
- 模型不可用时不写入随机分、模拟内容或伪成功结果；失败统一映射到 ``error_code``。
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin
from app.models.enums import (
    AdoptionStatus,
    AiJobScene,
    AiJobStatus,
    IssueStatus,
    QualityRuleCode,
    QualitySeverity,
    SchemaStatus,
)

# SQLite 测试与 PostgreSQL 生产均需可用；JSONB 在 SQLite 回退为 JSON。
_JSONType = JSON().with_variant(JSONB(), "postgresql")


class AiJob(Base, TimestampMixin):
    """AI 内容生成任务主记录。"""

    __tablename__ = "ai_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        comment="所属项目 ID（独立模式为空，项目模式必填，由服务层校验）",
    )
    # 工具上下文模式：INDEPENDENT=独立使用，PROJECT=关联项目。
    # 独立模式 project_id 为空；项目模式由服务层强制要求 project_id 非空。
    context_mode: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="工具上下文模式: INDEPENDENT/PROJECT",
    )
    project_phase: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment="项目阶段（项目模式时标记 AI 产出的阶段位置）",
    )
    scene: Mapped[AiJobScene] = mapped_column(
        nullable=False,
        comment="AI 任务场景枚举 name: LESSON_PLAN/PAPER/RUBRIC/TASK_SHEET/QUESTION/GRADING",
    )
    status: Mapped[AiJobStatus] = mapped_column(
        nullable=False,
        default=AiJobStatus.CREATED,
        server_default="CREATED",
        comment="任务状态机枚举 name",
    )
    output_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="输出类型：教学设计/教案/PPT大纲/任务单/量规/题目",
    )
    provider_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="调用的 Provider ID（无 Provider 时为空）",
    )
    provider_model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="调用时使用的模型名快照"
    )
    prompt_version: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="提示词版本"
    )
    input_summary: Mapped[Optional[dict]] = mapped_column(
        _JSONType, nullable=True, comment="结构化输入摘要：项目/学情/学科贡献/资源/任务/目标"
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="失败原因码 AiErrorCode name"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="失败详情"
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Provider 调用耗时（毫秒）"
    )
    initiated_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="发起教师 ID",
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        comment="grading 场景关联的任务",
    )
    submission_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="grading 场景关联的提交",
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    adopted_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    adopted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    adopted_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="教师最终采用的输出版本 ID（应用层维护，避免与 ai_output_versions 循环外键）",
    )


class AiOutputVersion(Base, TimestampMixin):
    """AI 输出版本（同一任务可多次生成，支持版本对比与局部重生成）。"""

    __tablename__ = "ai_output_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_jobs.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属 AI 任务 ID",
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="版本号（同任务内递增）"
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="原始 AI 输出"
    )
    content_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="html", comment="内容类型：html/json/text"
    )
    schema_status: Mapped[SchemaStatus] = mapped_column(
        nullable=False,
        default=SchemaStatus.PENDING,
        server_default="PENDING",
        comment="结构校验状态枚举 name",
    )
    schema_errors: Mapped[Optional[list]] = mapped_column(
        _JSONType, nullable=True, comment="结构校验错误列表"
    )
    adoption_status: Mapped[AdoptionStatus] = mapped_column(
        nullable=False,
        default=AdoptionStatus.PENDING,
        server_default="PENDING",
        comment="采用状态枚举 name",
    )
    is_final: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="是否教师采用的最终版本",
    )
    teacher_note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="教师审核备注"
    )
    regenerated_from: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_output_versions.id", ondelete="SET NULL"),
        nullable=True,
        comment="局部重生成来源版本 ID",
    )


class QualityIssue(Base, TimestampMixin):
    """AI 内容质量问题（阻断/警告/建议三级）。"""

    __tablename__ = "quality_issues"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_jobs.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联 AI 任务（跨学科规则校验在任务维度）",
    )
    version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_output_versions.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联具体输出版本（结构/内容校验在版本维度）",
    )
    severity: Mapped[QualitySeverity] = mapped_column(
        nullable=False,
        comment="严重级别枚举 name: BLOCKER/WARNING/SUGGESTION",
    )
    rule_code: Mapped[QualityRuleCode] = mapped_column(
        nullable=False, comment="质量规则代码枚举 name"
    )
    object_ref: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="问题对象引用，如 subject:math / stage:pre_class"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="问题描述")
    status: Mapped[IssueStatus] = mapped_column(
        nullable=False,
        default=IssueStatus.OPEN,
        server_default="OPEN",
        comment="处理状态枚举 name",
    )
    resolution: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="处理说明"
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
