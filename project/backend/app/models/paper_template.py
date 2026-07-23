import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Float, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class PaperTemplate(Base):
    __tablename__ = "paper_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    total_score: Mapped[float] = mapped_column(Float, default=100.0, comment="试卷总分")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称")
    exam_type: Mapped[str] = mapped_column(String(20), default="general", comment="考试类型: quiz=周测, midterm=期中, final=期末, general=通用")
    subject: Mapped[str] = mapped_column(String(50), nullable=False, comment="学科")
    grade: Mapped[str] = mapped_column(String(20), nullable=False, comment="年级")
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="模板配置(JSON)")
    sections: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="题型分布(JSON)")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AiGeneratedPaper(Base):
    __tablename__ = "ai_generated_papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="创建教师ID")
    template_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, comment="使用的模板ID")
    subject: Mapped[str] = mapped_column(String(50), nullable=False, comment="学科")
    grade: Mapped[str] = mapped_column(String(20), nullable=False, comment="年级")
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="试卷标题")
    difficulty: Mapped[str] = mapped_column(String(20), default="medium", comment="难度")
    knowledge_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="知识点(JSON)")
    questions: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="题目列表(JSON)")
    total_score: Mapped[float] = mapped_column(Float, default=100.0)
    duration: Mapped[int] = mapped_column(Integer, default=90, comment="建议时长(分钟)")
    status: Mapped[str] = mapped_column(String(20), default="draft", comment="状态")
    formatted_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="专业排版 HTML")
    template_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="模板类型: midterm/final/quiz")
    template_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="自定义排版参数 JSON")
    exported_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
