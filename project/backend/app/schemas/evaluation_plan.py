"""评价计划领域 Pydantic schema（计划 4.1 / Task 4）。

覆盖量规、量规维度、证据、评价记录、分维度评分的请求与响应，
以及评价计划完整性校验结果、复核队列项、状态机迁移请求。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── 量规等级描述 ──────────────────────────────────────────────
class RubricLevel(BaseModel):
    """量规等级：等级名、分数、可观察描述。"""

    level: str = Field(..., description="等级名（如 优秀/良好/合格/待改进）")
    score: float = Field(..., description="该等级分数")
    description: str = Field(..., description="可观察描述（验收：必须有可观察描述）")


# ── 量规 ──────────────────────────────────────────────────────
class RubricCreate(BaseModel):
    project_id: str
    created_by: str


class RubricResponse(BaseModel):
    id: str
    project_id: str
    version: int
    is_current: bool
    status: str
    created_by: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RubricPublishResult(BaseModel):
    """量规发布结果：含完整性校验问题。"""

    rubric: RubricResponse
    blockers: list[str] = Field(default_factory=list, description="阻断问题")
    warnings: list[str] = Field(default_factory=list, description="警告")


# ── 量规维度 ──────────────────────────────────────────────────
class RubricCriterionCreate(BaseModel):
    rubric_id: str
    indicator_id: Optional[str] = None
    dimension: str
    weight: float = Field(0.0, ge=0.0, le=1.0, description="教师权重 0-1")
    ai_weight: float = Field(0.0, ge=0.0, le=1.0, description="AI 权重，默认 0")
    levels: list[RubricLevel] = Field(default_factory=list)


class RubricCriterionUpdate(BaseModel):
    indicator_id: Optional[str] = None
    dimension: Optional[str] = None
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    ai_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    levels: Optional[list[RubricLevel]] = None


class RubricCriterionResponse(BaseModel):
    id: str
    rubric_id: str
    indicator_id: Optional[str] = None
    dimension: str
    weight: float
    ai_weight: float
    levels: list[dict]

    model_config = ConfigDict(from_attributes=True)


# ── 证据 ──────────────────────────────────────────────────────
class EvidenceArtifactCreate(BaseModel):
    project_id: str
    submission_id: Optional[str] = None
    indicator_id: str
    plan_id: Optional[str] = None
    source_type: str
    content_ref: str
    collected_by: str
    collected_at: Optional[datetime] = None


class EvidenceArtifactResponse(BaseModel):
    id: str
    project_id: str
    submission_id: Optional[str] = None
    indicator_id: str
    plan_id: Optional[str] = None
    source_type: str
    content_ref: str
    collected_by: str
    collected_at: datetime
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── 评价记录 ──────────────────────────────────────────────────
class EvaluationRecordCreate(BaseModel):
    project_id: str
    task_id: Optional[str] = None
    student_id: str
    evaluator_id: str
    subject_type: str = "task"
    subject_id: str
    source: str = "teacher"
    rubric_id: Optional[str] = None
    comment: Optional[str] = None


class EvaluationRecordResponse(BaseModel):
    id: str
    project_id: str
    task_id: Optional[str] = None
    student_id: str
    evaluator_id: str
    subject_type: str
    subject_id: str
    source: str
    status: str
    rubric_id: Optional[str] = None
    total_score: Optional[float] = None
    comment: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── 分维度评分 ────────────────────────────────────────────────
class EvaluationScoreCreate(BaseModel):
    record_id: str
    criterion_id: str
    suggested_score: Optional[float] = None
    final_score: Optional[float] = None
    evidence_ref: Optional[str] = None
    ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    difference_reason: Optional[str] = None


class EvaluationScoreUpdate(BaseModel):
    """教师修改评分：若修改了 final_score 且存在 suggested_score，必须填差异原因。"""

    final_score: Optional[float] = None
    evidence_ref: Optional[str] = None
    difference_reason: Optional[str] = None


class EvaluationScoreResponse(BaseModel):
    id: str
    record_id: str
    criterion_id: str
    suggested_score: Optional[float] = None
    final_score: Optional[float] = None
    evidence_ref: Optional[str] = None
    ai_confidence: Optional[float] = None
    difference_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── 状态机迁移 ────────────────────────────────────────────────
class EvaluationTransitionRequest(BaseModel):
    """评价状态机迁移请求（计划 4.3）。"""

    target: str


class SubmissionTransitionRequest(BaseModel):
    """提交复核状态机迁移请求（计划 4.3）。"""

    target: str


# ── 评价计划完整性校验 ────────────────────────────────────────
class EvaluationPlanValidationResult(BaseModel):
    """评价计划完整性校验结果（验收标准）。

    - AI 默认权重为零：ai_weight_nonzero 为 True 时阻断发布
    - 抽象目标未拆成可观察指标时禁止发布：goals_without_indicators 非空时阻断
    - 量规等级必须有可观察描述：criteria_without_level_description 非空时阻断
    - 缺失证据显示"未采集"：missing_required_evidence 列出缺失的必需证据计划
    """

    ready: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ai_weight_nonzero: bool = Field(False, description="是否存在 AI 权重非零的维度")
    goals_without_indicators: list[str] = Field(default_factory=list, description="无指标的目标 ID")
    criteria_without_level_description: list[str] = Field(
        default_factory=list, description="等级描述缺失的维度 ID"
    )
    missing_required_evidence: list[str] = Field(
        default_factory=list, description="缺失必需证据的指标 ID"
    )


# ── 评价计划快照 ──────────────────────────────────────────────
class EvaluationPlanSnapshot(BaseModel):
    """评价计划页一次渲染所需的全部数据。"""

    rubric: Optional[RubricResponse] = None
    criteria: list[RubricCriterionResponse] = Field(default_factory=list)
    goals: list[dict] = Field(default_factory=list)
    indicators: list[dict] = Field(default_factory=list)
    evidence_plans: list[dict] = Field(default_factory=list)
    evidence_artifacts: list[EvidenceArtifactResponse] = Field(default_factory=list)
    validation: EvaluationPlanValidationResult


# ── 复核队列 ──────────────────────────────────────────────────
class ReviewQueueItem(BaseModel):
    """复核队列项：含提交、评价记录、入队原因。"""

    submission_id: str
    task_id: str
    student_id: str
    review_status: str
    record_id: Optional[str] = None
    reasons: list[str] = Field(default_factory=list, description="入队原因：低置信度/边界分/规则冲突/申诉等")
    ai_confidence: Optional[float] = None
    total_score: Optional[float] = None


class ReviewConfirmRequest(BaseModel):
    """教师确认复核：提交分维度最终分数与差异原因。"""

    scores: list[dict] = Field(
        default_factory=list,
        description="[{criterion_id, final_score, evidence_ref, difference_reason}]",
    )
    total_score: Optional[float] = None
    comment: Optional[str] = None
    difference_reason: Optional[str] = Field(
        None, description="整体人机差异原因（修改 AI 总分时必填）"
    )


class LegacyEvaluationResponse(BaseModel):
    """旧版简单评价响应（显示为"旧版评价记录"）。"""

    id: str
    task_id: str
    student_id: str
    evaluator_id: str
    score: int
    comment: Optional[str] = None
    eval_type: str
    is_legacy: bool = True
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
