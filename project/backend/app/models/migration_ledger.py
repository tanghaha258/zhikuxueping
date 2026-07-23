"""数据迁移幂等记录模型（Task 2 / M1）。

依据全项目重构计划 4.M1 节与回滚规则：
- 记录每次数据迁移的批次、源表、源 ID、目标表、状态与校验摘要，
  支撑 M2-M4 回填迁移的幂等性校验。
- ``(source_table, source_id)`` 唯一约束保证同源记录不重复迁移；
  重复执行迁移时通过查表跳过已成功记录，而非覆盖或重复插入。
- ``verification_summary`` 保存迁移校验摘要（数量比对、孤儿外键、跨校异常等），
  供校验脚本输出与回滚决策使用。
- ``status`` 记录单条迁移结果：success/failed/skipped；
  failed 记录保留 ``error_message`` 供排查。

设计约定：
- 本表由数据迁移脚本写入，不由业务服务写入。
- ``executed_at`` 独立于 TimestampMixin 的 created_at/updated_at，
  记录迁移实际执行时间（可能与记录创建时间不同）。
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

_JSONType = JSON().with_variant(JSONB(), "postgresql")


class MigrationLedger(Base, TimestampMixin):
    """数据迁移幂等记录：批次、源/目标、状态与校验摘要。"""

    __tablename__ = "migration_ledger"
    __table_args__ = (
        # 同源记录不重复迁移，保证幂等。
        UniqueConstraint("source_table", "source_id", name="uq_migration_ledger_source"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    batch_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="迁移批次 ID（同一次回填执行共享一个 batch_id）",
    )
    source_table: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="源表名"
    )
    source_id: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="源记录 ID"
    )
    target_table: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="目标表名"
    )
    target_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, comment="目标记录 ID（迁移后生成）"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="迁移状态: success/failed/skipped",
    )
    row_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="本次迁移影响行数"
    )
    checksum: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="校验摘要（用于比对一致性）"
    )
    verification_summary: Mapped[Optional[dict]] = mapped_column(
        _JSONType,
        nullable=True,
        comment="校验摘要: 数量比对/孤儿外键/跨校异常等",
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="迁移实际执行时间",
    )
    executed_by: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, comment="执行人 ID（脚本或管理员）"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="失败详情（status=failed 时填写）"
    )
