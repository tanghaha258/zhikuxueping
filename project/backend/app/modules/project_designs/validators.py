"""项目设计领域校验规则。

集中实现：
1. 唯一核心学科、至少一门支撑学科、同一学科不重复登记。
2. 每个学科必须有贡献说明（knowledge/thinking/inquiry 至少一项非空）。
3. 真实问题必须有最终成果（deliverable）。
4. 指标必须绑定目标、证据计划必须绑定指标。
5. 激活完整性检查：返回 blockers、warnings 和 completion。

校验函数只读数据库，不抛异常，返回结构化结果，便于在
- 编辑设计时即时给出问题清单（warnings）
- 在 submit_for_review / activate 时阻断（blockers 非空）

每个 issue 携带 fix_route，前端据此定位到具体编辑区锚点。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_design import (
    EvidencePlan,
    EvaluationIndicator,
    LearningGoal,
    ProjectProblem,
    SubjectContribution,
    SubjectRole,
)
from app.modules.project_designs.repository import ProjectDesignRepository


@dataclass
class ValidationIssue:
    code: str
    field: str
    message: str
    # 修复路由：前端据此定位到具体编辑区（锚点），缺项必须可定位。
    fix_route: str = ""

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
            "fix_route": self.fix_route,
        }


@dataclass
class ValidationResult:
    can_activate: bool
    blockers: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    completion: float = 0.0
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "can_activate": self.can_activate,
            "blockers": [i.to_dict() for i in self.blockers],
            "warnings": [i.to_dict() for i in self.warnings],
            "completion": self.completion,
            "details": self.details,
        }


# 完整性检查项总数，用于计算 completion。
_TOTAL_CHECKS = 7


def _fix_route(project_id: str, anchor: str) -> str:
    """构造修复路由，前端据此跳转到具体编辑区锚点。"""
    return f"/projects/{project_id}/design#{anchor}"


def validate_contribution_uniqueness(
    project_id: str,
    subject_id: str,
    role: SubjectRole,
    repository: ProjectDesignRepository,
    *,
    exclude_id: str | None = None,
) -> list[ValidationIssue]:
    """校验学科贡献唯一性：同一项目内同一 subject_id 不重复，core 角色唯一。"""
    issues: list[ValidationIssue] = []
    existing = repository.find_contribution(project_id, subject_id)
    if existing and existing.id != exclude_id:
        issues.append(
            ValidationIssue(
                code="duplicate_subject",
                field=f"contributions[{subject_id}]",
                message=f"学科 {subject_id} 在项目中已登记贡献，不能重复",
                fix_route=_fix_route(project_id, "contributions"),
            )
        )
    if role == SubjectRole.CORE:
        core = repository.find_core_contribution(project_id)
        if core and core.id != exclude_id:
            issues.append(
                ValidationIssue(
                    code="duplicate_core_subject",
                    field=f"contributions[{subject_id}].role",
                    message="一个项目仅允许一个核心学科",
                    fix_route=_fix_route(project_id, "contributions"),
                )
            )
    return issues


def validate_activation(db: Session, project: Project) -> ValidationResult:
    """`POST /api/v1/projects/{id}/validate-activation` 的核心实现。

    blockers（未解决不能激活）：
    - 缺少核心学科
    - 缺少至少一个支撑学科
    - 缺少当前正式版本的真实问题
    - 真实问题缺少最终成果（deliverable）
    - 学科贡献说明全空（knowledge/thinking/inquiry 均为空）
    - 存在学习目标但未拆解为可观测指标
    - 存在指标但缺少 required 证据计划
    - 项目主表 core_subject_id 与学科贡献 core 角色不一致

    warnings（可激活但建议处理）：
    - 缺少学习目标
    - 缺少证据计划（在无指标时也提示）
    - 学科贡献缺少 knowledge/thinking/inquiry 任意一项（但至少一项非空）
    """
    repository = ProjectDesignRepository(db)
    contributions = repository.list_contributions(project.id)
    problem = repository.get_problem(project.id)
    goals = repository.list_goals(project.id)
    indicators = repository.list_indicators(project.id)
    evidence_plans = repository.list_evidence_plans(project.id)

    blockers: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    core_contribs = [c for c in contributions if c.role == SubjectRole.CORE]
    support_contribs = [c for c in contributions if c.role == SubjectRole.SUPPORT]

    # 1) 唯一核心学科
    if len(core_contribs) == 0:
        blockers.append(
            ValidationIssue(
                code="missing_core_subject",
                field="contributions",
                message="缺少核心学科，正式项目必须指定一个核心学科",
                fix_route=_fix_route(project.id, "contributions"),
            )
        )
    elif len(core_contribs) > 1:
        blockers.append(
            ValidationIssue(
                code="multiple_core_subjects",
                field="contributions",
                message=f"存在 {len(core_contribs)} 个核心学科，仅允许一个",
                fix_route=_fix_route(project.id, "contributions"),
            )
        )

    # 2) 至少一个支撑学科
    if len(support_contribs) == 0:
        blockers.append(
            ValidationIssue(
                code="missing_support_subject",
                field="contributions",
                message="缺少支撑学科，跨学科项目至少需要一门支撑学科",
                fix_route=_fix_route(project.id, "contributions"),
            )
        )

    # 3) 主表 core_subject_id 与贡献一致
    if core_contribs:
        core_subject_id = core_contribs[0].subject_id
        if project.core_subject_id and project.core_subject_id != core_subject_id:
            blockers.append(
                ValidationIssue(
                    code="core_subject_mismatch",
                    field="core_subject_id",
                    message=(
                        f"项目主表 core_subject_id={project.core_subject_id} "
                        f"与学科贡献核心 {core_subject_id} 不一致"
                    ),
                    fix_route=_fix_route(project.id, "contributions"),
                )
            )

    # 4) 真实问题（含最终成果 deliverable）
    if problem is None:
        blockers.append(
            ValidationIssue(
                code="missing_problem",
                field="problem",
                message="缺少真实问题，正式项目必须描述情境、对象、受众和成果",
                fix_route=_fix_route(project.id, "problem"),
            )
        )
    else:
        if not problem.context.strip():
            blockers.append(
                ValidationIssue(
                    code="empty_problem_context",
                    field="problem.context",
                    message="真实问题情境描述不能为空",
                    fix_route=_fix_route(project.id, "problem"),
                )
            )
        # 真实问题必须有最终成果
        if not (problem.deliverable or "").strip():
            blockers.append(
                ValidationIssue(
                    code="PROBLEM_DELIVERABLE_MISSING",
                    field="problem.deliverable",
                    message="真实问题缺少最终成果（deliverable），正式项目必须明确产出物",
                    fix_route=_fix_route(project.id, "problem"),
                )
            )

    # 5) 学习目标存在且拆解为指标
    if not goals:
        warnings.append(
            ValidationIssue(
                code="missing_goals",
                field="goals",
                message="缺少学习目标，建议补充以便后续评价",
                fix_route=_fix_route(project.id, "goals"),
            )
        )
    else:
        indicators_by_goal = {ind.goal_id for ind in indicators}
        for goal in goals:
            if goal.id not in indicators_by_goal:
                blockers.append(
                    ValidationIssue(
                        code="goal_without_indicator",
                        field=f"goals[{goal.id}]",
                        message=f"学习目标 {goal.name} 未拆解为可观测指标，禁止发布",
                        fix_route=_fix_route(project.id, "indicators"),
                    )
                )

    # 6) 指标必须有 required 证据计划
    if indicators:
        required_plans_by_indicator = {
            p.indicator_id for p in evidence_plans if p.required
        }
        for ind in indicators:
            if ind.id not in required_plans_by_indicator:
                blockers.append(
                    ValidationIssue(
                        code="indicator_without_required_evidence",
                        field=f"evidence_plans[{ind.id}]",
                        message=f"指标 {ind.id} 缺少必须采集的证据计划",
                        fix_route=_fix_route(project.id, "evidence_plans"),
                    )
                )
    elif not evidence_plans:
        warnings.append(
            ValidationIssue(
                code="missing_evidence_plans",
                field="evidence_plans",
                message="缺少证据计划，建议在指标建立后补充",
                fix_route=_fix_route(project.id, "evidence_plans"),
            )
        )

    # 7) 学科贡献完整性
    # - knowledge/thinking/inquiry 全空 → blocker（无贡献说明）
    # - 部分缺失 → warning（建议补全）
    for c in contributions:
        has_any = bool(c.knowledge) or bool(c.thinking) or bool(c.inquiry)
        if not has_any:
            blockers.append(
                ValidationIssue(
                    code="SUBJECT_CONTRIBUTION_MISSING",
                    field=f"contributions[{c.subject_id}]",
                    message=f"学科 {c.subject_id} 缺少贡献说明，至少填写知识、思维或探究中的一项",
                    fix_route=_fix_route(project.id, "contributions"),
                )
            )
        elif not (c.knowledge and c.thinking and c.inquiry):
            missing = [
                name
                for name, val in (
                    ("knowledge", c.knowledge),
                    ("thinking", c.thinking),
                    ("inquiry", c.inquiry),
                )
                if not val
            ]
            warnings.append(
                ValidationIssue(
                    code="incomplete_contribution",
                    field=f"contributions[{c.subject_id}]",
                    message=f"学科 {c.subject_id} 贡献缺少：{'、'.join(missing)}",
                    fix_route=_fix_route(project.id, "contributions"),
                )
            )

    # 完整度计算：以 7 项关键检查为分母，blockers 计为缺失项。
    blocker_codes = {b.code for b in blockers}
    key_checks = [
        "missing_core_subject",
        "multiple_core_subjects",
        "missing_support_subject",
        "missing_problem",
        "PROBLEM_DELIVERABLE_MISSING",
        "goal_without_indicator",
        "indicator_without_required_evidence",
        "core_subject_mismatch",
        "SUBJECT_CONTRIBUTION_MISSING",
    ]
    triggered = sum(1 for code in key_checks if code in blocker_codes)
    completion = max(0.0, (_TOTAL_CHECKS - min(triggered, _TOTAL_CHECKS)) / _TOTAL_CHECKS)

    return ValidationResult(
        can_activate=len(blockers) == 0,
        blockers=blockers,
        warnings=warnings,
        completion=round(completion, 4),
        details={
            "core_subjects": len(core_contribs),
            "support_subjects": len(support_contribs),
            "has_problem": problem is not None,
            "goals": len(goals),
            "indicators": len(indicators),
            "evidence_plans": len(evidence_plans),
        },
    )
