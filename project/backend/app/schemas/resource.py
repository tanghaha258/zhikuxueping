from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ResourceCreate(BaseModel):
    project_id: Optional[str] = None
    title: str
    res_type: str
    url: Optional[str] = None
    file_size: Optional[int] = None
    # 核心闭环扩展（计划 4.1）：层级、阶段、审核状态、来源等均可在创建时指定。
    tier: Optional[str] = None
    stage: Optional[str] = None
    cognitive_level: Optional[str] = None
    reading_level: Optional[str] = None
    prerequisites: Optional[str] = None
    review_status: Optional[str] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    usage_tip: Optional[str] = None


class ResourceUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    tier: Optional[str] = None
    stage: Optional[str] = None
    cognitive_level: Optional[str] = None
    reading_level: Optional[str] = None
    prerequisites: Optional[str] = None
    review_status: Optional[str] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    usage_tip: Optional[str] = None


class ResourceResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    title: str
    res_type: str
    url: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_by: str
    created_at: Optional[datetime] = None
    # 核心闭环扩展字段（历史资源为 NULL/DRAFT，向后兼容）
    tier: Optional[str] = None
    stage: Optional[str] = None
    cognitive_level: Optional[str] = None
    reading_level: Optional[str] = None
    prerequisites: Optional[str] = None
    review_status: Optional[str] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    usage_tip: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ResourceTierCoverage(BaseModel):
    """三级资源递进覆盖检查结果（计划 3.5.3）。

    `has_*` 表示该层是否至少有一项有效（已发布）资源；
    `counts` 为各层资源总数；`missing` 列出缺失层级。
    """

    foundation: bool
    enhancement: bool
    extension: bool
    counts: dict[str, int]
    missing: list[str]
    total: int

    model_config = ConfigDict(from_attributes=True)
