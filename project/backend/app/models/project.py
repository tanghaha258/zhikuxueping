import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import DataOrigin, ReviewStatus


class ProjectStatus(str, enum.Enum):
    """项目生命周期状态。

    状态机：draft -> pending_review -> active -> completed -> archived。
    非法跃迁由服务层拒绝并返回 409。
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(SAEnum(ProjectStatus), default=ProjectStatus.DRAFT)
    creator_id: Mapped[str] = mapped_column(String(36), nullable=False)
    school_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    grade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── 核心闭环扩展字段（增量添加，历史项目保持空值，不伪造）──────────
    # 项目类型，例如 cross_subject；历史项目为 NULL。
    project_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # 唯一核心学科 ID；历史项目为 NULL，未设置前无法进入正式状态。
    core_subject_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # 设计/内容审核状态，独立于生命周期 status；默认草稿。
    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus), default=ReviewStatus.DRAFT, nullable=False
    )
    # 数据来源标识，用于运营证据过滤；历史项目为 NULL（未知来源）。
    data_origin: Mapped[Optional[DataOrigin]] = mapped_column(
        SAEnum(DataOrigin), nullable=True
    )

    # ── 结项/归档扩展字段（Task 9）──────────
    # 教师结项反思文本（教师对项目结项的回顾与改进建议）。
    teacher_reflection: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="教师结项反思"
    )
    # 重新开放归档项目的原因留痕（school_admin 重新开放归档项目时填写）。
    reopen_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="重新开放归档项目的原因"
    )
    # 重新开放时间。
    reopened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="重新开放时间"
    )
    # 重新开放操作人 ID。
    reopened_by: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, comment="重新开放操作人 ID"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, title={self.title}, status={self.status})>"


class ProjectSubject(Base):
    __tablename__ = "project_subjects"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(36), primary_key=True)


class ProjectClass(Base):
    __tablename__ = "project_classes"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    class_id: Mapped[str] = mapped_column(String(36), primary_key=True)


class ProjectMember(Base):
    __tablename__ = "project_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
