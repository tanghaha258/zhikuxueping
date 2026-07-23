import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, Float, Numeric, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class Question(TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_subject_grade_type", "subject", "grade", "question_type"),
        Index("ix_questions_quality", "quality_score", "quality_level"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject: Mapped[str] = mapped_column(String(50), nullable=False, comment="学科")
    grade: Mapped[str] = mapped_column(String(10), nullable=False, comment="年级")
    question_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="题型")
    difficulty: Mapped[int] = mapped_column(Integer, default=3, comment="难度 1-5")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="题目内容(HTML)")
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="选择题选项 JSON")
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="答案/参考答案")
    analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="解析(HTML)")
    score: Mapped[float] = mapped_column(Float, default=5.0, comment="默认分值")
    knowledge_points: Mapped[str] = mapped_column(Text, default="[]", comment="知识点 JSON 数组")
    source: Mapped[str] = mapped_column(String(20), default="manual", comment="来源: ai_generated/manual/batch_import")
    status: Mapped[str] = mapped_column(String(20), default="published", comment="状态: draft/published/archived")
    usage_count: Mapped[int] = mapped_column(Integer, default=0, comment="被引用次数")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, comment="创建者ID")

    quality_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), default=50, comment="质量评分 0-100")
    quality_level: Mapped[Optional[str]] = mapped_column(String(16), default="normal", comment="质量等级: excellent/good/normal/poor")
    avg_correct_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True, comment="平均正确率")
    difficulty_calibrated: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True, comment="校准后难度 0-1")
    discrimination: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True, comment="区分度 0-1")
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="最近使用时间")


class PaperQuestion(Base):
    __tablename__ = "paper_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="试卷ID")
    question_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="题目ID")
    section_label: Mapped[str] = mapped_column(String(50), default="", comment="大题标签")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    score: Mapped[float] = mapped_column(Float, default=5.0, comment="实际分值")
