"""运营证据领域模型（Task 8）。

依据核心闭环实施计划 4.1 节与 3.8 节管理员页面规格：
- ``OperationalMetric``：对外运营指标定义，含名称/代码/公式/周期/样本量/来源表/
  数据来源责任方/责任人/数据来源（real/test/demo/imported）。阶段验收要求
  “任何对外指标都能查看公式、周期、样本量、数据来源和责任人，且默认不含非真实数据”。
- ``EvidenceLedger``：证据台账，记录指标对应的证据引用、采集时间与核验人。
- ``ExportRecord``：导出审计，每次导出落审计，记录导出人/范围/是否脱敏/状态/备注。

设计约定：
- SQLAlchemy ``SAEnum`` 默认按枚举 *name* 存储，故 ``server_default`` 必须使用 name。
- 不手工填写成效值而不标记来源；所有导出记录操作人、范围、时间和脱敏规则（验收 3.8.3）。
- 不写入伪造数据：模型不可用/无来源数据时不产生随机指标值。
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import DataOrigin


class OperationalMetricPeriod(str, enum.Enum):
    """运营指标统计周期（计划 3.8.1 “统计周期、数据口径、更新时间”）。"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    AD_HOC = "ad_hoc"


class ExportStatus(str, enum.Enum):
    """导出审计状态机。

    previewed -> confirmed / failed / revoked。
    二次确认要求：preview 后必须再次确认才落 confirmed（验收 3.8.3）。
    """

    PENDING = "pending"
    PREVIEWED = "previewed"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REVOKED = "revoked"


class OperationalMetric(Base, TimestampMixin):
    """对外运营指标定义（计划 3.8.3 指标台账 / 4.1 MetricDefinition）。

    阶段验收：任何对外指标都能查看公式、周期、样本量、数据来源和责任人。
    默认 data_origin=REAL，对外驾驶舱只统计真实数据。
    """

    __tablename__ = "operational_metrics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(
        String(120), nullable=False, comment="指标名称"
    )
    code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="指标代码（唯一，便于引用与导出对照）",
    )
    formula: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="指标公式或计算口径，对外可见（验收 3.8.3）",
    )
    period: Mapped[OperationalMetricPeriod] = mapped_column(
        nullable=False,
        default=OperationalMetricPeriod.MONTHLY,
        server_default="MONTHLY",
        comment="统计周期枚举 name",
    )
    sample_size: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="样本量（数据条数）"
    )
    source_table: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True, comment="来源表或数据集名称"
    )
    source_owner: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        comment="数据来源责任方（系统/部门/录入人）",
    )
    responsible_person: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True, comment="指标责任人"
    )
    data_origin: Mapped[DataOrigin] = mapped_column(
        SAEnum(DataOrigin),
        nullable=False,
        default=DataOrigin.REAL,
        server_default="REAL",
        comment="数据来源枚举 name：real/test/demo/imported",
    )
    value: Mapped[Optional[float]] = mapped_column(
        nullable=True, comment="指标当前值（不伪造，未采集时为空）"
    )
    value_collected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="指标值采集时间（无值时为空，不补零）",
    )
    school_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=True,
        comment="所属学校 ID（NULL 表示跨校汇总）",
    )


class EvidenceLedger(Base, TimestampMixin):
    """证据台账（计划 3.8.3 “指标定义、公式、样本量、统计周期和原始记录入口”）。

    每条记录关联一个运营指标，登记证据引用、采集时间与核验人。
    不可手工填写成效值而不标记来源（验收 3.8.3）。
    """

    __tablename__ = "evidence_ledger"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    metric_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("operational_metrics.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联运营指标 ID",
    )
    evidence_ref: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="证据引用：表名+主键 / 文件路径 / 外部台账编号",
    )
    evidence_summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="证据摘要（脱敏后可见文本）"
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="证据采集时间",
    )
    verified_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="核验人 ID（教师/管理员）",
    )


class ExportRecord(Base, TimestampMixin):
    """导出审计记录（验收 3.8.3 “导出后可查询审计记录”）。

    每次导出落审计，记录导出人、范围（学校）、是否脱敏、状态与备注。
    二次确认流程：preview -> confirmed，禁止跳过预览直接确认。
    """

    __tablename__ = "export_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    exporter_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="导出操作人 ID",
    )
    scope_school_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        comment="导出范围学校 ID（NULL 表示跨校，仅系统管理员）",
    )
    metric_ids: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="导出涉及的指标 ID 列表（逗号分隔）",
    )
    anonymized: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        comment="是否启用脱敏（学生姓名→学号尾号、教师姓名→工号）",
    )
    status: Mapped[ExportStatus] = mapped_column(
        nullable=False,
        default=ExportStatus.PENDING,
        server_default="PENDING",
        comment="导出状态机枚举 name",
    )
    audit_note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="导出审计备注"
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="二次确认时间"
    )
    payload_ref: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="导出载荷引用（文件路径或快照 ID，预览阶段可空）",
    )
