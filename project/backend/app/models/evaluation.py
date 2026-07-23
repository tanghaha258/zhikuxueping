import enum
import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EvaluationType(str, enum.Enum):
    SELF = "self"
    PEER = "peer"
    TEACHER = "teacher"
    AI = "ai"


class Evaluation(Base, TimestampMixin):
    """旧版简单评价记录（保留只读兼容）。

    Task 4 引入 EvaluationRecord 作为新的评价主记录，承载状态机与分维度评分。
    本表保留历史数据可读取，显示为"旧版评价记录"；
    `is_legacy=True` 标记历史数据，新评价不再写入本表。
    """

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    evaluator_id: Mapped[str] = mapped_column(String(36), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eval_type: Mapped[EvaluationType] = mapped_column(SAEnum(EvaluationType), nullable=False)
    is_legacy: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否旧版简单评价（Task 4 前的历史数据）",
    )
