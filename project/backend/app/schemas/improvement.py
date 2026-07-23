"""学情改进与二次评价领域 Pydantic schema（计划 Task 7）。

覆盖改进建议、改进任务、二次评价的请求与响应，
以及建议采用/修改/拒绝、建议转任务、二次评价前后对比。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ImprovementSuggestionStatus,
    ImprovementTaskType,
)


# ── 改进建议 ──────────────────────────────────────────────────
class ImprovementSuggestionCreate(BaseModel):
    """教师创建改进建议。

    验收：建议必须引用评价证据（``evidence_reference`` 必填、
    ``created_from_evaluation_id`` 必填），无证据抛 400。
    """

    project_id: str = Field(..., description="所属项目 ID")
    created_from_evaluation_id: str = Field(
        ..., description="来源评价记录 ID（必填，无证据拒绝）"
    )
    evidence_reference: str = Field(
        ..., description="证据引用：EvaluationScore/Artifact/AiJob ID 等可追溯位置"
    )
    student_id: Optional[str] = Field(None, description="被建议学生 ID（班级共性建议可空）")
    title: str = Field(..., min_length=1, description="建议标题")
    description: str = Field(..., min_length=1, description="建议描述")


class ImprovementSuggestionResponse(BaseModel):
    id: str
    project_id: str
    student_id: Optional[str] = None
    created_from_evaluation_id: str
    evidence_reference: str
    title: str
    description: str
    status: str
    decision_reason: Optional[str] = None
    modified_description: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SuggestionDecisionRequest(BaseModel):
    """教师采用/修改/拒绝建议，必须留痕原因。"""

    status: ImprovementSuggestionStatus = Field(
        ..., description="目标状态：adopted/modified/rejected"
    )
    reason: str = Field(..., min_length=1, description="采用/修改/拒绝原因（必填留痕）")
    modified_description: Optional[str] = Field(
        None, description="修改后的建议描述（status=modified 时必填）"
    )


# ── 改进任务 ──────────────────────────────────────────────────
class ImprovementTaskCreate(BaseModel):
    """建议转任务/测评。

    验收：改进任务可追溯到原评价（``created_from_evaluation_id`` 必填）
    与原建议（``link_suggestion_id`` 可空）。
    """

    project_id: str = Field(..., description="所属项目 ID")
    created_from_evaluation_id: str = Field(
        ..., description="来源评价记录 ID（必填）"
    )
    task_type: ImprovementTaskType = Field(
        ..., description="改进任务类型：foundation_consolidation/enhancement_application/extension_transfer/second_evaluation"
    )
    title: str = Field(..., min_length=1, description="任务标题")
    description: str = Field(..., min_length=1, description="任务描述")
    link_suggestion_id: Optional[str] = Field(None, description="关联建议 ID（可空）")
    original_task_id: Optional[str] = Field(None, description="原任务 ID（可空）")
    publish_task: bool = Field(
        False, description="是否同步创建为正式 Task（学生可见）；False 时仅留痕"
    )


class ImprovementTaskResponse(BaseModel):
    id: str
    project_id: str
    link_suggestion_id: Optional[str] = None
    original_task_id: Optional[str] = None
    created_from_evaluation_id: str
    task_type: str
    title: str
    description: str
    generated_task_id: Optional[str] = None
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── 二次评价 ──────────────────────────────────────────────────
class SecondEvaluationCreate(BaseModel):
    """二次评价关联前后两次评价记录。

    验收：改进任务能追溯到原评价和二次评价；前后对比由教师填写或基于证据生成。
    """

    project_id: str = Field(..., description="所属项目 ID")
    student_id: str = Field(..., description="被评学生 ID")
    first_evaluation_id: str = Field(..., description="首次评价记录 ID")
    second_evaluation_id: str = Field(..., description="第二次评价记录 ID")
    link_suggestion_id: Optional[str] = Field(None, description="关联建议 ID（可空）")
    link_improvement_task_id: Optional[str] = Field(
        None, description="关联改进任务 ID（可空）"
    )
    comparison_summary: Optional[str] = Field(
        None, description="前后对比摘要（可空，服务层可基于证据生成草稿）"
    )


class SecondEvaluationResponse(BaseModel):
    id: str
    project_id: str
    student_id: str
    first_evaluation_id: str
    second_evaluation_id: str
    link_suggestion_id: Optional[str] = None
    link_improvement_task_id: Optional[str] = None
    comparison_summary: Optional[str] = None
    first_score: Optional[float] = None
    second_score: Optional[float] = None
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── 列表与聚合响应 ────────────────────────────────────────────
class ImprovementSuggestionListResponse(BaseModel):
    items: list[ImprovementSuggestionResponse] = Field(default_factory=list)
    total: int = 0


class ImprovementTaskListResponse(BaseModel):
    items: list[ImprovementTaskResponse] = Field(default_factory=list)
    total: int = 0


class SecondEvaluationListResponse(BaseModel):
    items: list[SecondEvaluationResponse] = Field(default_factory=list)
    total: int = 0
