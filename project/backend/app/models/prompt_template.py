import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称")
    subject: Mapped[str] = mapped_column(String(50), nullable=False, comment="适用学科")
    exam_type: Mapped[str] = mapped_column(String(20), nullable=False, default="quiz", comment="考试类型: quiz/midterm/final")
    template: Mapped[str] = mapped_column(Text, nullable=False, comment="提示词模板内容，支持变量占位符")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="模板说明")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
