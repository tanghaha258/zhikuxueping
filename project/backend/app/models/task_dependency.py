"""任务依赖关系模型。

依据核心闭环实施计划 4.1 节：`TaskDependency(predecessor_id, successor_id)`
表达任务链中"前置 -> 后置"的有向边。

规则（由服务层强制，计划 3.5.4 验收）：
- 同一对 (predecessor, successor) 唯一，不重复登记。
- 禁止自环（predecessor == successor）。
- 禁止形成环（添加后若存在环则拒绝）。
- 后置任务的截止时间不能早于前置任务（日期冲突），由服务层校验。
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskDependency(Base):
    """任务依赖：predecessor 完成后 successor 才可开始。"""

    __tablename__ = "task_dependencies"
    __table_args__ = (
        # 同一对前后置只能登记一次。
        UniqueConstraint("predecessor_id", "successor_id", name="uq_task_dependency_pair"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    predecessor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="前置任务 ID",
    )
    successor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="后置任务 ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp(),
        comment="创建时间",
    )
