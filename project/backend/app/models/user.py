"""
用户模型

定义 User 表和 Role 枚举，涵盖用户认证与基础信息字段。
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Role(str, enum.Enum):
    """用户角色枚举"""

    ADMIN = "admin"                # 系统管理员
    SCHOOL_ADMIN = "school_admin"  # 学校管理员
    TEACHER = "teacher"            # 教师
    STUDENT = "student"            # 学生
    PARENT = "parent"              # 家长


class User(Base, TimestampMixin):
    """用户表"""

    __tablename__ = "users"

    # ── 主键 ────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="用户 UUID",
    )

    # ── 账号信息 ────────────────────────────────────────────────
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="用户名（登录用）",
    )
    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="电子邮箱",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt 加密后的密码哈希",
    )

    # ── 个人信息 ────────────────────────────────────────────────
    display_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="显示名称",
    )
    role: Mapped[Role] = mapped_column(
        SAEnum(Role),
        nullable=False,
        default=Role.TEACHER,
        comment="用户角色",
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default=None,
        comment="手机号",
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        default=None,
        comment="头像 URL",
    )

    # ── 学校关联 ────────────────────────────────────────────────
    school_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        default=None,
        comment="所属学校 ID",
    )

    # ── 班级关联 ────────────────────────────────────────────────
    class_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("classes.id"),
        nullable=True,
        default=None,
        comment="所属班级 ID（仅学生角色使用）",
    )

    # ── 账号状态 ────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否启用",
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否锁定",
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="连续登录失败次数",
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="锁定截止时间",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
