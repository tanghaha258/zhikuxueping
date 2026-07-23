import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum as SAEnum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PaperStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    GRADING = "grading"
    DONE = "done"


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    GRADED = "graded"
    REVIEWED = "reviewed"


class Paper(Base, TimestampMixin):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    teacher_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    class_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list, comment="目标班级 ID 列表")
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="试卷文件路径")
    status: Mapped[PaperStatus] = mapped_column(SAEnum(PaperStatus), default=PaperStatus.DRAFT)


class AnswerKey(Base, TimestampMixin):
    __tablename__ = "answer_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list, comment="题目列表 [{index, type, score, answer, rubric}]")
    total_score: Mapped[float] = mapped_column(Float, default=100)


class PaperSubmission(Base, TimestampMixin):
    __tablename__ = "paper_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="学生答卷文件")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="文本答案")
    ai_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(SAEnum(SubmissionStatus), default=SubmissionStatus.PENDING)
