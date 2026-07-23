import uuid
from typing import Optional

from sqlalchemy import BigInteger, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import ResourceSourceType, ResourceTier, ReviewStatus, TeachingStage


class Resource(Base, TimestampMixin):
    """项目资源。

    核心闭环扩展（计划 4.1）：增加层级 tier、教学阶段 stage、认知/阅读难度、
    前置知识、审核状态、来源类型、版权出处与使用建议。

    历史资源（迁移前已存在）：tier/stage 为 NULL（未分层），review_status 默认
    DRAFT（未分层草稿），不伪造审核结果。
    """

    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    res_type: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)

    # ── 核心闭环扩展字段（增量添加，历史资源为 NULL/草稿，不伪造）──────────
    # 资源层级：基础/提升/拓展；历史资源为 NULL（未分层）。
    tier: Mapped[Optional[ResourceTier]] = mapped_column(
        SAEnum(ResourceTier), nullable=True, comment="资源层级: foundation/enhancement/extension"
    )
    # 教学阶段：课前/课中/课后；历史资源为 NULL。
    stage: Mapped[Optional[TeachingStage]] = mapped_column(
        SAEnum(TeachingStage), nullable=True, comment="教学阶段: pre/in/post_class"
    )
    cognitive_level: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="认知难度"
    )
    reading_level: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="阅读难度"
    )
    prerequisites: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="前置知识"
    )
    # 审核/发布状态，独立于项目生命周期；默认草稿，AI/导入资源需审核后发布。
    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus), default=ReviewStatus.DRAFT, nullable=False,
        comment="审核状态: DRAFT/PENDING_REVIEW/APPROVED/RETURNED/PUBLISHED/ARCHIVED",
    )
    source_type: Mapped[Optional[ResourceSourceType]] = mapped_column(
        SAEnum(ResourceSourceType), nullable=True, comment="来源类型: manual/ai/imported"
    )
    source_ref: Mapped[Optional[str]] = mapped_column(
        String(300), nullable=True, comment="版权/出处"
    )
    usage_tip: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="使用建议"
    )
