"""运营证据领域 Pydantic schema（计划 Task 8）。

覆盖运营指标、证据台账、导出记录的请求与响应，
以及导出预览/脱敏/二次确认等管理端动作。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.operational_evidence import (
    ExportStatus,
    OperationalMetricPeriod,
)
from app.models.enums import DataOrigin


# ── 运营指标 ──────────────────────────────────────────────────
class OperationalMetricCreateRequest(BaseModel):
    """管理员登记运营指标（必须填写公式/周期/责任人/数据来源）。"""

    name: str = Field(..., description="指标名称")
    code: str = Field(..., description="指标代码（唯一）")
    formula: str = Field(..., description="指标公式或计算口径，对外可见")
    period: OperationalMetricPeriod = Field(
        OperationalMetricPeriod.MONTHLY, description="统计周期"
    )
    sample_size: Optional[int] = Field(None, description="样本量")
    source_table: Optional[str] = Field(None, description="来源表/数据集")
    source_owner: Optional[str] = Field(None, description="数据来源责任方")
    responsible_person: Optional[str] = Field(None, description="指标责任人")
    data_origin: DataOrigin = Field(
        DataOrigin.REAL, description="数据来源：real/test/demo/imported"
    )
    value: Optional[float] = Field(None, description="指标值（不伪造，未采集时为空）")
    value_collected_at: Optional[datetime] = Field(None, description="指标值采集时间")
    school_id: Optional[str] = Field(None, description="所属学校 ID（NULL 跨校）")


class OperationalMetricResponse(BaseModel):
    """对外指标响应：含公式/周期/样本量/来源/责任人，阶段验收要求。"""

    id: str
    name: str
    code: str
    formula: str
    period: str
    sample_size: Optional[int] = None
    source_table: Optional[str] = None
    source_owner: Optional[str] = None
    responsible_person: Optional[str] = None
    data_origin: str
    value: Optional[float] = None
    value_collected_at: Optional[datetime] = None
    school_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OperationalMetricListResponse(BaseModel):
    """指标列表（默认 data_origin=real 过滤）。"""

    items: list[OperationalMetricResponse] = Field(default_factory=list)
    total: int = 0


class OperationalMetricDetailResponse(BaseModel):
    """指标详情：含公式/周期/样本量/来源 + 关联证据台账。"""

    metric: OperationalMetricResponse
    evidence: list["EvidenceLedgerResponse"] = Field(default_factory=list)


# ── 证据台账 ──────────────────────────────────────────────────
class EvidenceLedgerResponse(BaseModel):
    id: str
    metric_id: str
    evidence_ref: str
    evidence_summary: Optional[str] = None
    collected_at: datetime
    verified_by: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceLedgerCreateRequest(BaseModel):
    """管理员登记证据台账记录（不能手工填写成效值而不标记来源）。"""

    metric_id: str = Field(..., description="关联运营指标 ID")
    evidence_ref: str = Field(..., description="证据引用：表名+主键 / 文件路径 / 外部台账编号")
    evidence_summary: Optional[str] = Field(None, description="证据摘要")
    collected_at: datetime = Field(..., description="证据采集时间")


# ── 导出审计 ──────────────────────────────────────────────────
class ExportPreviewRequest(BaseModel):
    """导出预览：返回脱敏后样本，不直接落 confirmed。

    二次确认要求：preview -> confirmed，禁止跳过预览直接确认（验收 3.8.3）。
    """

    metric_ids: list[str] = Field(default_factory=list, description="导出涉及的指标 ID")
    anonymized: bool = Field(
        True, description="是否启用脱敏：学生姓名→学号尾号、教师姓名→工号"
    )
    school_id: Optional[str] = Field(
        None, description="导出范围学校 ID（NULL 跨校，仅系统管理员）"
    )


class ExportConfirmRequest(BaseModel):
    """导出二次确认：必须基于已有 preview 记录。"""

    export_id: str = Field(..., description="预览阶段返回的导出记录 ID")
    audit_note: Optional[str] = Field(None, description="导出审计备注")


class ExportRecordResponse(BaseModel):
    id: str
    exporter_id: str
    scope_school_id: Optional[str] = None
    metric_ids: Optional[str] = None
    anonymized: bool
    status: str
    audit_note: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    payload_ref: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ExportPreviewResponse(BaseModel):
    """导出预览结果：脱敏后的指标+证据样本 + 导出记录 ID（待二次确认）。"""

    export: ExportRecordResponse
    metrics: list[OperationalMetricResponse] = Field(default_factory=list)
    evidence: list[EvidenceLedgerResponse] = Field(default_factory=list)
    anonymization_examples: list[str] = Field(
        default_factory=list,
        description="脱敏示例：例如 “张三 → S****1234 / 王老师 → T****56”",
    )


# 引用前向声明解析
OperationalMetricDetailResponse.model_rebuild()
