import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, Numeric, DateTime, Date, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class LearningSnapshot(TimestampMixin, Base):
    __tablename__ = "learning_snapshots"
    __table_args__ = (
        Index("ix_learning_snapshots_student_class", "student_id", "class_id"),
        Index("ix_learning_snapshots_subject_date", "subject", "snapshot_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, comment="学生ID")
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), nullable=False, comment="班级ID")
    subject: Mapped[str] = mapped_column(String(32), nullable=False, comment="学科")
    knowledge_mastery: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="知识点掌握度 JSON: {\"知识点ID\": 0-1}")
    difficulty_performance: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="难度表现 JSON: {\"easy\": 0.9, \"medium\": 0.7}")
    total_questions: Mapped[int] = mapped_column(Integer, default=0, comment="总题数")
    correct_count: Mapped[int] = mapped_column(Integer, default=0, comment="正确题数")
    avg_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True, comment="平均分")
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, comment="快照日期")


class ClassLearningReport(TimestampMixin, Base):
    __tablename__ = "class_learning_reports"
    __table_args__ = (
        Index("ix_class_learning_reports_class_subject", "class_id", "subject"),
        Index("ix_class_learning_reports_date", "report_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), nullable=False, comment="班级ID")
    subject: Mapped[str] = mapped_column(String(32), nullable=False, comment="学科")
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="报告类型: daily/weekly/monthly")
    report_date: Mapped[date] = mapped_column(Date, nullable=False, comment="报告日期")
    overall_mastery: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True, comment="整体掌握度 0-100")
    knowledge_mastery: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="知识点掌握度 JSON")
    weak_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="薄弱知识点 JSON")
    strong_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="优势知识点 JSON")
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="教学建议 JSON")
    student_count: Mapped[int] = mapped_column(Integer, default=0, comment="参与学生数")


class QuestionUsageLog(TimestampMixin, Base):
    __tablename__ = "question_usage_logs"
    __table_args__ = (
        Index("ix_question_usage_logs_question", "question_id"),
        Index("ix_question_usage_logs_paper", "paper_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"), nullable=False, comment="题目ID")
    paper_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("papers.id"), nullable=True, comment="试卷ID")
    usage_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="使用类型: paper/assignment/diagnostic")
    class_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, comment="班级ID")
    total_count: Mapped[int] = mapped_column(Integer, default=0, comment="作答总数")
    correct_count: Mapped[int] = mapped_column(Integer, default=0, comment="正确数")
    correct_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True, comment="正确率")
    avg_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="平均作答时间(秒)")


class DifficultyCalibrationHistory(TimestampMixin, Base):
    __tablename__ = "difficulty_calibration_history"
    __table_args__ = (
        Index("ix_difficulty_calibration_history_question", "question_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"), nullable=False, comment="题目ID")
    old_difficulty: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True, comment="原难度")
    new_difficulty: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True, comment="新难度")
    sample_size: Mapped[int] = mapped_column(Integer, default=0, comment="样本量")
    old_correct_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True, comment="原正确率")
    new_correct_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True, comment="新正确率")
    calibration_method: Mapped[str] = mapped_column(String(32), default="raw", comment="校准方法: bayesian/irt/raw")
