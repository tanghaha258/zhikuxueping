import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (
        UniqueConstraint("subject", "grade", "name", name="uq_kp_subject_grade_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject: Mapped[str] = mapped_column(String(50), nullable=False, comment="学科")
    grade: Mapped[str] = mapped_column(String(20), nullable=False, comment="年级")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="知识点名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="描述")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
