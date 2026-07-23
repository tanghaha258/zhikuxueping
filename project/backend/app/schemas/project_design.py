"""项目设计领域 Pydantic schemas。

字段与 `app.models.project_design` 对齐；写入模型不允许传入 id/timestamps，
读取模型通过 `from_attributes` 从 ORM 对象构造。
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TeachingStage
from app.models.project_design import (
    EvidenceCollector,
    EvidenceType,
    GoalType,
    SubjectRole,
)


# ── ProjectProblem ─────────────────────────────────────────────
class ProjectProblemCreate(BaseModel):
    context: str = Field(..., min_length=1, description="情境描述")
    object: Optional[str] = None
    audience: Optional[str] = None
    constraints: Optional[str] = None
    deliverable: Optional[str] = None
    usage: Optional[str] = None


class ProjectProblemUpdate(BaseModel):
    context: Optional[str] = None
    object: Optional[str] = None
    audience: Optional[str] = None
    constraints: Optional[str] = None
    deliverable: Optional[str] = None
    usage: Optional[str] = None


class ProjectProblemResponse(BaseModel):
    id: str
    project_id: str
    context: str
    object: Optional[str] = None
    audience: Optional[str] = None
    constraints: Optional[str] = None
    deliverable: Optional[str] = None
    usage: Optional[str] = None
    is_current: bool
    version: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── SubjectContribution ────────────────────────────────────────
class SubjectContributionCreate(BaseModel):
    subject_id: str = Field(..., min_length=1)
    role: SubjectRole
    knowledge: Optional[str] = None
    thinking: Optional[str] = None
    inquiry: Optional[str] = None
    removal_impact: Optional[str] = None


class SubjectContributionUpdate(BaseModel):
    knowledge: Optional[str] = None
    thinking: Optional[str] = None
    inquiry: Optional[str] = None
    removal_impact: Optional[str] = None


class SubjectContributionResponse(BaseModel):
    id: str
    project_id: str
    subject_id: str
    role: SubjectRole
    knowledge: Optional[str] = None
    thinking: Optional[str] = None
    inquiry: Optional[str] = None
    removal_impact: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── LearningGoal ───────────────────────────────────────────────
class LearningGoalCreate(BaseModel):
    goal_type: GoalType
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    scope: Optional[str] = None


class LearningGoalUpdate(BaseModel):
    goal_type: Optional[GoalType] = None
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None


class LearningGoalResponse(BaseModel):
    id: str
    project_id: str
    goal_type: GoalType
    name: str
    description: Optional[str] = None
    scope: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── EvaluationIndicator ────────────────────────────────────────
class EvaluationIndicatorCreate(BaseModel):
    goal_id: str
    observable_behavior: str = Field(..., min_length=1)
    level_rule: Optional[str] = None


class EvaluationIndicatorUpdate(BaseModel):
    observable_behavior: Optional[str] = None
    level_rule: Optional[str] = None


class EvaluationIndicatorResponse(BaseModel):
    id: str
    goal_id: str
    project_id: str
    observable_behavior: str
    level_rule: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── EvidencePlan ───────────────────────────────────────────────
class EvidencePlanCreate(BaseModel):
    indicator_id: str
    stage: TeachingStage
    evidence_type: EvidenceType
    collector: EvidenceCollector
    required: bool = True
    description: Optional[str] = None


class EvidencePlanUpdate(BaseModel):
    stage: Optional[TeachingStage] = None
    evidence_type: Optional[EvidenceType] = None
    collector: Optional[EvidenceCollector] = None
    required: Optional[bool] = None
    description: Optional[str] = None


class EvidencePlanResponse(BaseModel):
    id: str
    indicator_id: str
    project_id: str
    stage: TeachingStage
    evidence_type: EvidenceType
    collector: EvidenceCollector
    required: bool
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── 完整性检查结果 ──────────────────────────────────────────────
class CompletionIssue(BaseModel):
    """完整性检查中的单项问题。"""

    code: str = Field(..., description="问题代码，如 missing_core_subject")
    field: str = Field(..., description="相关字段路径")
    message: str = Field(..., description="面向用户的中文说明")


class ProjectValidationResult(BaseModel):
    """`POST /api/v1/projects/{id}/validate-activation` 返回结构。"""

    can_activate: bool
    blockers: list[CompletionIssue] = Field(
        default_factory=list, description="阻断性问题，未解决不能激活"
    )
    warnings: list[CompletionIssue] = Field(
        default_factory=list, description="警告性问题，可激活但建议处理"
    )
    completion: float = Field(..., ge=0.0, le=1.0, description="完整度 0-1")
    details: dict = Field(default_factory=dict, description="各检查项明细")


# ── 项目设计聚合视图 ────────────────────────────────────────────
class ProjectDesignSnapshot(BaseModel):
    """项目设计页一次性拉取的聚合快照，供前端工作区渲染。"""

    problem: Optional[ProjectProblemResponse] = None
    contributions: list[SubjectContributionResponse] = []
    goals: list[LearningGoalResponse] = []
    indicators: list[EvaluationIndicatorResponse] = []
    evidence_plans: list[EvidencePlanResponse] = []
