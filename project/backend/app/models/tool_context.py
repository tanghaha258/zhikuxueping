"""工具上下文链接模型（Task 2 / M1）。

依据全项目重构计划 4.M1 节与规格 7 节：
- 独立工具（备课/资源/试卷/AI 产出等）关联到项目时，通过本表建立一次引用关系，
  不复制业务资产。
- ``(artifact_type, artifact_id, project_id, placement)`` 唯一，避免同一资产在同一
  项目同一位置被重复挂载。
- ``context_snapshot`` 保存关联时刻的结构化上下文快照（项目主题、阶段、目标等），
  供后续展示与审计追溯，不替代资产本体。
- 跨校项目关联由服务层在写入前校验并返回 403，不在数据库层硬编码学校约束。

设计约定：
- ``artifact_type``/``placement`` 使用 String 列，合法值由服务层校验。
- 外键 SET NULL：资产被删除时仅解除引用，不级联删除链接（保护审计轨迹）。
"""
import uuid
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

# SQLite 测试与 PostgreSQL 生产均需可用；JSONB 在 SQLite 回退为 JSON。
_JSONType = JSON().with_variant(JSONB(), "postgresql")


class ToolContextLink(Base, TimestampMixin):
    """独立工具产出与项目、阶段、任务、目标的关联引用。"""

    __tablename__ = "tool_context_links"
    __table_args__ = (
        # 同一资产在同一项目同一位置仅一条引用，防止重复挂载。
        UniqueConstraint(
            "artifact_type",
            "artifact_id",
            "project_id",
            "placement",
            name="uq_tool_context_links_artifact_placement",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    artifact_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="资产类型: lesson_plan/resource/paper/ai_output/question_bank等",
    )
    artifact_id: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="资产 ID"
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联项目 ID",
    )
    phase: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment="项目阶段: diagnosis/design/preparation/implementation/evaluation/improvement/closure",
    )
    placement: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="放置位置: pre_test/in_class/post_test/resource/lesson_plan/ai_draft等",
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联任务 ID（可选）",
    )
    goal_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("learning_goals.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联学习目标 ID（可选）",
    )
    indicator_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("evaluation_indicators.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联评价指标 ID（可选）",
    )
    context_snapshot: Mapped[Optional[dict]] = mapped_column(
        _JSONType,
        nullable=True,
        comment="关联时刻的结构化上下文快照（项目主题/阶段/目标等），不替代资产本体",
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建链接的教师 ID",
    )
