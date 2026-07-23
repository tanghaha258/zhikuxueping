"""跨学科 AI 内容质量规则（计划 Task 5 验收标准 2）。

规则分两类：
- 项目级规则：校验项目结构完整性，在 AI 任务创建时与输出后执行。
  - unused_contribution：支撑学科贡献未转化为任务/资源
  - missing_stage：课前/课中/课后三阶段任务链不完整
  - missing_resource_tier：基础/提升/拓展三级资源不全
  - missing_evaluation：缺少量规或评价指标
- 版本级规则：校验 AI 输出内容。
  - subject_mismatch：输出学科与项目核心学科不一致（学科拼盘）
  - invalid_schema：输出结构无效（JSON 解析失败）

safety_blocked / timeout 由 service 在调用 Provider 时映射为 AiJob 失败原因，
不作为输出校验规则。

所有规则产出 IssueDraft，由 service 关联 job_id/version_id 落库为 QualityIssue。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    QualityRuleCode,
    QualitySeverity,
    ResourceTier,
    TeachingStage,
)
from app.models.project_design import (
    EvaluationIndicator,
    EvidencePlan,
    LearningGoal,
    SubjectContribution,
    SubjectRole,
)
from app.models.resource import Resource
from app.models.subject import Subject
from app.models.task import Task
from app.models.evaluation_plan import Rubric


@dataclass
class IssueDraft:
    """质量问题描述草稿，由 service 关联 job/version 后落库。"""

    severity: QualitySeverity
    rule_code: QualityRuleCode
    object_ref: str
    message: str


# ── 项目级规则 ────────────────────────────────────────────────
def validate_project_context(db: Session, project_id: str) -> list[IssueDraft]:
    """校验项目结构完整性，返回全部问题草稿。"""
    issues: list[IssueDraft] = []
    issues.extend(_check_unused_contribution(db, project_id))
    issues.extend(_check_missing_stage(db, project_id))
    issues.extend(_check_missing_resource_tier(db, project_id))
    issues.extend(_check_missing_evaluation(db, project_id))
    return issues


def _check_unused_contribution(db: Session, project_id: str) -> list[IssueDraft]:
    """支撑学科贡献未转化为任务或资源（验收：贡献未使用）。"""
    contributions = list(
        db.execute(
            select(SubjectContribution).where(
                SubjectContribution.project_id == project_id,
                SubjectContribution.role == SubjectRole.SUPPORT,
            )
        ).scalars().all()
    )
    if not contributions:
        return []
    task_count = db.execute(
        select(Task).where(Task.project_id == project_id)
    ).scalars().first()
    resource_count = db.execute(
        select(Resource).where(Resource.project_id == project_id)
    ).scalars().first()
    # 有支撑学科贡献但项目无任何任务或资源，视为贡献未落地
    if not task_count and not resource_count:
        return [
            IssueDraft(
                severity=QualitySeverity.WARNING,
                rule_code=QualityRuleCode.UNUSED_CONTRIBUTION,
                object_ref=f"project:{project_id}",
                message="支撑学科贡献尚未转化为具体任务或资源",
            )
        ]
    return []


def _check_missing_stage(db: Session, project_id: str) -> list[IssueDraft]:
    """三阶段任务链不完整（验收：三阶段缺失）。"""
    stages = set(
        db.execute(
            select(Task.stage).where(
                Task.project_id == project_id, Task.stage.is_not(None)
            )
        ).scalars().all()
    )
    issues: list[IssueDraft] = []
    for stage in TeachingStage:
        if stage not in stages:
            issues.append(
                IssueDraft(
                    severity=QualitySeverity.BLOCKER,
                    rule_code=QualityRuleCode.MISSING_STAGE,
                    object_ref=f"stage:{stage.value}",
                    message=f"任务链缺少「{ _STAGE_LABELS[stage]}」阶段任务",
                )
            )
    return issues


_STAGE_LABELS = {
    TeachingStage.PRE_CLASS: "课前",
    TeachingStage.IN_CLASS: "课中",
    TeachingStage.POST_CLASS: "课后",
}


def _check_missing_resource_tier(db: Session, project_id: str) -> list[IssueDraft]:
    """三级资源层级不全（验收：资源层级缺失）。"""
    tiers = set(
        db.execute(
            select(Resource.tier).where(
                Resource.project_id == project_id, Resource.tier.is_not(None)
            )
        ).scalars().all()
    )
    issues: list[IssueDraft] = []
    for tier in ResourceTier:
        if tier not in tiers:
            issues.append(
                IssueDraft(
                    severity=QualitySeverity.BLOCKER,
                    rule_code=QualityRuleCode.MISSING_RESOURCE_TIER,
                    object_ref=f"tier:{tier.value}",
                    message=f"资源缺少「{_TIER_LABELS[tier]}」层级",
                )
            )
    return issues


_TIER_LABELS = {
    ResourceTier.FOUNDATION: "基础",
    ResourceTier.ENHANCEMENT: "提升",
    ResourceTier.EXTENSION: "拓展",
}


def _check_missing_evaluation(db: Session, project_id: str) -> list[IssueDraft]:
    """缺少量规或评价指标（验收：评价缺失）。"""
    issues: list[IssueDraft] = []
    has_rubric = db.execute(
        select(Rubric).where(Rubric.project_id == project_id)
    ).scalars().first()
    if not has_rubric:
        issues.append(
            IssueDraft(
                severity=QualitySeverity.BLOCKER,
                rule_code=QualityRuleCode.MISSING_EVALUATION,
                object_ref=f"project:{project_id}:rubric",
                message="项目尚未配置量规，评价维度缺失",
            )
        )
    has_indicator = db.execute(
        select(EvaluationIndicator).where(
            EvaluationIndicator.project_id == project_id
        )
    ).scalars().first()
    if not has_indicator:
        issues.append(
            IssueDraft(
                severity=QualitySeverity.BLOCKER,
                rule_code=QualityRuleCode.MISSING_EVALUATION,
                object_ref=f"project:{project_id}:indicator",
                message="项目尚未定义评价指标，无法衡量目标达成",
            )
        )
    return issues


# ── 版本级规则 ────────────────────────────────────────────────
def core_subject_name(db: Session, project_id: str) -> str | None:
    """获取项目核心学科名称，用于学科匹配校验。"""
    row = db.execute(
        select(Subject.name)
        .join(SubjectContribution, Subject.id == SubjectContribution.subject_id)
        .where(
            SubjectContribution.project_id == project_id,
            SubjectContribution.role == SubjectRole.CORE,
        )
    ).scalars().first()
    return row


def validate_output(
    db: Session,
    project_id: str,
    content: str | None,
    content_type: str,
) -> tuple[list[IssueDraft], bool]:
    """校验 AI 输出内容，返回（问题草稿列表, 结构是否有效）。

    - invalid_schema：JSON 输出解析失败
    - subject_mismatch：输出未体现核心学科（学科拼盘）
    """
    issues: list[IssueDraft] = []
    schema_valid = True

    # 1. 结构校验：JSON 输出必须可解析
    if content_type == "json":
        if not content:
            schema_valid = False
            issues.append(
                IssueDraft(
                    severity=QualitySeverity.BLOCKER,
                    rule_code=QualityRuleCode.INVALID_SCHEMA,
                    object_ref=f"project:{project_id}:output",
                    message="AI 输出为空，无法解析为有效结构",
                )
            )
        else:
            try:
                json.loads(content)
            except (json.JSONDecodeError, TypeError):
                schema_valid = False
                issues.append(
                    IssueDraft(
                        severity=QualitySeverity.BLOCKER,
                        rule_code=QualityRuleCode.INVALID_SCHEMA,
                        object_ref=f"project:{project_id}:output",
                        message="AI 输出 JSON 结构无效，无法解析",
                    )
                )

    # 2. 学科匹配：输出应体现核心学科
    subject = core_subject_name(db, project_id)
    if subject and content:
        if subject not in content:
            issues.append(
                IssueDraft(
                    severity=QualitySeverity.BLOCKER,
                    rule_code=QualityRuleCode.SUBJECT_MISMATCH,
                    object_ref=f"project:{project_id}:subject:{subject}",
                    message=f"AI 输出未体现核心学科「{subject}」，疑似学科拼盘",
                )
            )

    return issues, schema_valid
