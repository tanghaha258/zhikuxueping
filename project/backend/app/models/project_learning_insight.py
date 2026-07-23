"""项目学情诊断快照模型（Task 2 / M1）。

依据全项目重构计划 4.M1 节与规格 3.1、6 节：
- 保存项目学情诊断的结构化快照（班级画像、薄弱点、分层建议），
  支撑后续「学」（任务分层、资源推荐）和「评」（评价依据、改进建议）闭环。
- ``evidence_cutoff`` 记录诊断所依据证据的截止时间，过期后诊断标记为 stale，
  不允许直接用于正式决策。
- ``status`` 状态机：draft -> insufficient_evidence -> confirmed / stale；
  无证据时返回 ``insufficient_evidence``，由教师确认后才进入正式使用。
- ``is_current`` 标记当前正式快照，历史快照保留只读以追溯诊断演进。
- ``source_counts`` 记录数据来源数量（前测/提交/已发布评价/题目作答），
  用于校验诊断是否基于真实证据而非随机数据。

设计约定：
- ``snapshot``/``source_counts`` 使用 JSON 列，SQLite 回退为 JSON、PostgreSQL 使用 JSONB。
- 学情只能由真实数据计算，禁止随机画像或模拟分层；AI 失败时由教师人工诊断。
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

_JSONType = JSON().with_variant(JSONB(), "postgresql")


class ProjectLearningInsight(Base, TimestampMixin):
    """项目学情诊断快照：证据截止时间、来源计数与教师确认状态。"""

    __tablename__ = "project_learning_insights"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    class_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="诊断班级 ID",
    )
    snapshot: Mapped[Optional[dict]] = mapped_column(
        _JSONType,
        nullable=True,
        comment="诊断快照: 班级画像/薄弱点/分层建议等结构化结果",
    )
    source_counts: Mapped[Optional[dict]] = mapped_column(
        _JSONType,
        nullable=True,
        comment="数据来源计数: pre_test/submissions/evaluations/question_answers",
    )
    evidence_cutoff: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="诊断所依据证据的截止时间，过期后诊断标记为 stale",
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="draft",
        comment="诊断状态: draft/insufficient_evidence/confirmed/stale",
    )
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="诊断生成时间"
    )
    generated_by: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, comment="生成者（教师 ID 或 AI Provider ID）"
    )
    confirmed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="确认诊断的教师 ID",
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="教师确认时间"
    )
    teacher_note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="教师人工诊断备注"
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否当前正式快照，历史快照保留只读",
    )
