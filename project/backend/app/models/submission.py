import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import SubmissionReviewStatus


class Submission(Base, TimestampMixin):
    """学生提交记录。

    Task 4 扩展：`review_status` 驱动复核状态机（计划 4.3）：
    draft -> submitted -> ai_reviewed -> teacher_reviewed
    -> returned -> resubmitted -> finalized

    旧 `status` 字段保留兼容（自由字符串），新数据由 review_status 驱动，
    service 层同步镜像到 status 以兼容旧接口。
    """

    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_urls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    status: Mapped[str] = mapped_column(String(20), default="submitted")
    review_status: Mapped[SubmissionReviewStatus] = mapped_column(
        SAEnum(SubmissionReviewStatus),
        default=SubmissionReviewStatus.SUBMITTED,
        nullable=False,
        comment="复核状态机",
    )
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
