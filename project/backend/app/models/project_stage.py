"""项目阶段进度模型（Task 2 / M1）。

依据全项目重构计划 4.M1 节与 Task 2：
- 一个项目对应七条阶段记录（diagnosis/design/preparation/implementation/
  evaluation/improvement/closure），由 ``(project_id, phase)`` 唯一约束保证。
- 阶段状态机：not_started -> in_progress -> completed；completed 可被有权限角色
  重新打开并记录 reopened_at/reopened_by/reopen_reason。
- 阶段进度独立于项目生命周期 ``Project.status``，服务层根据真实数据计算阻断。

设计约定：
- ``phase`` 与 ``status`` 使用 String 列存储，避免 SQLite/PostgreSQL 枚举行为差异；
  合法值由服务层校验，不在数据库层硬编码 CHECK（与现有 ``projects.status`` 一致）。
- 历史项目在 M2 回填时才创建阶段记录，本迁移不自动伪造进度。
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ProjectStageProgress(Base, TimestampMixin):
    """项目七阶段进度：状态、完成时间与重开信息。"""

    __tablename__ = "project_stage_progress"
    __table_args__ = (
        # 一个项目内每个阶段仅一条记录，避免重复阶段事实。
        UniqueConstraint("project_id", "phase", name="uq_project_stage_progress_project_phase"),
    )

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
    phase: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="项目阶段: diagnosis/design/preparation/implementation/evaluation/improvement/closure",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_started",
        comment="阶段状态: not_started/in_progress/completed/blocked",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="阶段完成时间"
    )
    reopened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="阶段重新开放时间"
    )
    reopened_by: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, comment="重新开放操作人 ID"
    )
    reopen_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="重新开放原因"
    )
