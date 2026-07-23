"""
数据库声明基类模块

提供 SQLAlchemy 2.0 声明式 Base 和公共混入类（TimestampMixin）。
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有模型类的声明基类"""
    pass


class TimestampMixin:
    """
    时间戳混入类，自动管理 created_at 和 updated_at 字段。

    - created_at: 创建时自动写入当前时间
    - updated_at: 更新时自动刷新为当前时间
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
