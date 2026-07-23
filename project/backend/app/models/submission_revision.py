"""提交订正版本模型（Task 6）。

记录学生每次提交/再提交的内容快照，支撑：
- 订正版本追溯（草稿→首次提交→退回→再次提交→最终确认）。
- 幂等提交键：同一 idempotency_key 重复提交不生成新版本。
- 二次评价入口：reassess_reason 标记学生发起的二次评价请求。

设计约定：
- 一条 Submission（task+student 线程）可对应多条 SubmissionRevision。
- attempt_number 在同一线程内递增；最新版本的 content/file_urls 为当前内容。
- idempotency_key 由客户端生成（UUID），唯一约束防止重复点击生成重复提交。
- SQLAlchemy SAEnum 按枚举 name 存储，server_default 必须用 name。
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import SubmissionReviewStatus


class SubmissionRevision(Base, TimestampMixin):
    """提交订正版本：每次提交/再提交的内容快照。"""

    __tablename__ = "submission_revisions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    submission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属提交线程 ID",
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="尝试序号（同一线程内递增）"
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="作答内容")
    file_urls: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list, comment="附件 URL 列表"
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
        comment="客户端幂等键，重复提交不生成新版本",
    )
    review_status: Mapped[SubmissionReviewStatus] = mapped_column(
        nullable=False,
        default=SubmissionReviewStatus.SUBMITTED,
        comment="该版本创建时的复核状态枚举 name",
    )
    teacher_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="教师该轮反馈（学生可见）"
    )
    teacher_private_note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="教师私有备注（学生不可见）"
    )
    reassess_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="学生发起二次评价的理由"
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="提交时间"
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="教师复核时间"
    )
