import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import (
    ResourceTier,
    SubmissionType,
    TaskPublishStatus,
    TeachingStage,
)


class TaskType(str, enum.Enum):
    INDIVIDUAL = "individual"
    GROUP = "group"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"


class Task(Base, TimestampMixin):
    """项目任务。

    核心闭环扩展（计划 4.1）：增加教学阶段 stage、分层对象 tier、发布状态
    publish_status、提交类型 submission_type、最大提交次数 max_attempts、
    定时发布时间 scheduled_at。

    - `status`：学生侧执行进度（pending/in_progress/submitted/evaluated），保留不变。
    - `publish_status`：任务发布生命周期（draft/scheduled/published/in_progress/closed/archived），
      描述对学生可见性。新任务默认 DRAFT；旧任务迁移时映射为 PUBLISHED 以保留可见性。
    - `stage`/`tier`：与资源共享 stage+tier，使同项目内任务与资源、证据计划可按阶段关联查询。
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType), default=TaskType.INDIVIDUAL)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.PENDING)
    max_score: Mapped[int] = mapped_column(Integer, default=100)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    rubric: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None, comment="评分细则（JSON 格式的多维度量规）")

    # ── 核心闭环扩展字段（增量添加，历史任务为 NULL/PUBLISHED，保留原行为）────
    stage: Mapped[Optional[TeachingStage]] = mapped_column(
        SAEnum(TeachingStage), nullable=True, comment="教学阶段: pre/in/post_class"
    )
    tier: Mapped[Optional[ResourceTier]] = mapped_column(
        SAEnum(ResourceTier), nullable=True, comment="分层对象: foundation/enhancement/extension"
    )
    publish_status: Mapped[TaskPublishStatus] = mapped_column(
        SAEnum(TaskPublishStatus), default=TaskPublishStatus.DRAFT, nullable=False,
        comment="发布状态: DRAFT/SCHEDULED/PUBLISHED/IN_PROGRESS/CLOSED/ARCHIVED",
    )
    submission_type: Mapped[Optional[SubmissionType]] = mapped_column(
        SAEnum(SubmissionType), nullable=True, comment="提交类型: online/attachment/both/none"
    )
    max_attempts: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="最大提交次数；NULL 表示不限"
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="定时发布时间"
    )


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
