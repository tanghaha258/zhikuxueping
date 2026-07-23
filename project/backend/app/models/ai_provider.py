import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AiProvider(Base, TimestampMixin):
    __tablename__ = "ai_providers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Provider 名称")
    api_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="API 地址")
    model: Mapped[str] = mapped_column(String(100), nullable=False, comment="模型名称")
    api_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="API Key")
    status: Mapped[str] = mapped_column(String(20), default="active", comment="状态: active/inactive")
