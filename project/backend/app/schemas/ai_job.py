"""AI 治理领域 Pydantic schema（计划 Task 5）。

覆盖 AI 任务、输出版本、质量问题的请求与响应，
以及状态机迁移、教师审核、采用决定、局部重生成与质量问题处理。
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AdoptionStatus,
    AiJobScene,
    AiJobStatus,
    IssueStatus,
    QualityRuleCode,
    QualitySeverity,
    SchemaStatus,
)


# ── AI 任务 ──────────────────────────────────────────────────
class AiJobCreateRequest(BaseModel):
    """教师发起 AI 内容任务（携带项目上下文，不由页面重复录入）。"""

    project_id: str = Field(..., description="所属项目 ID")
    scene: AiJobScene = Field(..., description="AI 任务场景")
    output_type: str = Field(..., description="输出类型：教学设计/教案/PPT大纲/任务单/量规/题目")
    task_id: Optional[str] = Field(None, description="grading 场景关联任务")
    submission_id: Optional[str] = Field(None, description="grading 场景关联提交")


class AiJobResponse(BaseModel):
    id: str
    project_id: str
    scene: str
    status: str
    output_type: str
    provider_id: Optional[str] = None
    provider_model: Optional[str] = None
    prompt_version: Optional[str] = None
    input_summary: Optional[dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    initiated_by: str
    task_id: Optional[str] = None
    submission_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    adopted_by: Optional[str] = None
    adopted_at: Optional[datetime] = None
    adopted_version_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AiJobTransitionRequest(BaseModel):
    """AI 任务状态机迁移（计划 4.3）。"""

    target: AiJobStatus = Field(..., description="目标状态")


# ── 输出版本 ──────────────────────────────────────────────────
class AiOutputVersionResponse(BaseModel):
    id: str
    job_id: str
    version: int
    content: Optional[str] = None
    content_type: str
    schema_status: str
    schema_errors: Optional[list[Any]] = None
    adoption_status: str
    is_final: bool
    teacher_note: Optional[str] = None
    regenerated_from: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AiJobReviewRequest(BaseModel):
    """教师审核决定（标记 reviewed）。"""

    note: Optional[str] = Field(None, description="审核备注")


class AiJobAdoptRequest(BaseModel):
    """教师采用/拒绝输出版本。

    阻断性问题未处理时不能标记 adopted（验收标准 6）。
    """

    version_id: str = Field(..., description="采用的输出版本 ID")
    adoption_status: AdoptionStatus = Field(
        ..., description="采用状态：adopted/partially_adopted/rejected"
    )
    note: Optional[str] = Field(None, description="教师备注")


class AiJobRegenerateRequest(BaseModel):
    """局部重生成：基于已有任务创建新版本。"""

    note: Optional[str] = Field(None, description="重生成说明")
    base_version_id: Optional[str] = Field(
        None, description="基于哪个版本重生成（默认最新）"
    )


# ── 质量问题 ──────────────────────────────────────────────────
class QualityIssueResponse(BaseModel):
    id: str
    job_id: Optional[str] = None
    version_id: Optional[str] = None
    severity: str
    rule_code: str
    object_ref: str
    message: str
    status: str
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class QualityIssueResolveRequest(BaseModel):
    """教师处理质量问题。"""

    resolution: str = Field(..., description="处理说明")
    status: IssueStatus = Field(
        IssueStatus.RESOLVED, description="处理结果：resolved/wontfix"
    )


# ── 聚合响应 ──────────────────────────────────────────────────
class AiJobDetailResponse(BaseModel):
    """AI 任务详情：含全部输出版本与质量问题。"""

    job: AiJobResponse
    versions: list[AiOutputVersionResponse] = Field(default_factory=list)
    issues: list[QualityIssueResponse] = Field(default_factory=list)
    open_blockers: int = Field(0, description="未处理阻断问题数")


class AiJobListResponse(BaseModel):
    """AI 任务列表。"""

    items: list[AiJobResponse] = Field(default_factory=list)
    total: int = 0
