"""项目设计领域 HTTP 路由。

路由前缀：`/api/v1/projects/{project_id}/design/...`
所有写操作要求 teacher/school_admin/admin 角色；读操作沿用项目读取权限。
非法状态（如重复核心学科、编辑已激活项目设计）返回 409。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.project_designs import service
from app.schemas.project_design import (
    EvaluationIndicatorCreate,
    EvaluationIndicatorUpdate,
    EvidencePlanCreate,
    EvidencePlanUpdate,
    LearningGoalCreate,
    LearningGoalUpdate,
    ProjectProblemCreate,
    ProjectProblemUpdate,
    SubjectContributionCreate,
    SubjectContributionUpdate,
)


router = APIRouter(prefix="/projects/{project_id}/design", tags=["项目设计"])


# ── 真实问题 ───────────────────────────────────────────────────
@router.get("/problem", summary="获取当前真实问题")
def get_problem_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    problem = service.get_current_problem(db, current_user, project_id)
    return success_response(data=_problem_response(problem) if problem else None)


@router.put("/problem", summary="创建或更新真实问题（版本化）")
def upsert_problem_api(
    project_id: str,
    data: ProjectProblemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        problem = service.upsert_problem(db, current_user, project_id, data)
    except AppException:
        raise
    return success_response(
        data=_problem_response(problem), message="真实问题已保存"
    )


@router.patch("/problem", summary="局部更新当前真实问题")
def update_problem_api(
    project_id: str,
    data: ProjectProblemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        problem = service.update_problem(db, current_user, project_id, data)
    except AppException:
        raise
    return success_response(data=_problem_response(problem), message="已更新")


# ── 学科贡献 ───────────────────────────────────────────────────
@router.get("/contributions", summary="学科贡献列表")
def list_contributions_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_contributions(db, current_user, project_id)
    return success_response(data=[_contribution_response(c) for c in items])


@router.post("/contributions", summary="新增学科贡献")
def add_contribution_api(
    project_id: str,
    data: SubjectContributionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        contribution = service.add_contribution(db, current_user, project_id, data)
    except AppException:
        raise
    return success_response(
        data=_contribution_response(contribution), message="已添加学科贡献"
    )


@router.patch("/contributions/{contribution_id}", summary="更新学科贡献")
def update_contribution_api(
    project_id: str,
    contribution_id: str,
    data: SubjectContributionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        contribution = service.update_contribution(
            db, current_user, project_id, contribution_id, data
        )
    except AppException:
        raise
    return success_response(data=_contribution_response(contribution), message="已更新")


@router.delete("/contributions/{contribution_id}", summary="移除学科贡献")
def remove_contribution_api(
    project_id: str,
    contribution_id: str,
    confirm: bool = Query(False, description="确认破坏性删除（如移除核心学科）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        impact = service.remove_contribution(
            db, current_user, project_id, contribution_id, confirm=confirm
        )
    except AppException:
        raise
    if impact is not None:
        return JSONResponse(
            status_code=409,
            content=error_response(
                code=40901,
                message="该学科为核心学科，移除将清空项目核心学科，需显式确认",
                data=impact,
            ),
        )
    return success_response(message="已移除学科贡献")


# ── 学习目标 ───────────────────────────────────────────────────
@router.get("/goals", summary="学习目标列表")
def list_goals_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_goals(db, current_user, project_id)
    return success_response(data=[_goal_response(g) for g in items])


@router.post("/goals", summary="新增学习目标")
def add_goal_api(
    project_id: str,
    data: LearningGoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    goal = service.add_goal(db, current_user, project_id, data)
    return success_response(data=_goal_response(goal), message="已添加学习目标")


@router.patch("/goals/{goal_id}", summary="更新学习目标")
def update_goal_api(
    project_id: str,
    goal_id: str,
    data: LearningGoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        goal = service.update_goal(db, current_user, project_id, goal_id, data)
    except AppException:
        raise
    return success_response(data=_goal_response(goal), message="已更新")


@router.delete("/goals/{goal_id}", summary="删除学习目标")
def delete_goal_api(
    project_id: str,
    goal_id: str,
    confirm: bool = Query(False, description="确认级联删除关联指标与证据计划"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        impact = service.remove_goal(
            db, current_user, project_id, goal_id, confirm=confirm
        )
    except AppException:
        raise
    if impact is not None:
        return JSONResponse(
            status_code=409,
            content=error_response(
                code=40901,
                message="目标仍被指标引用，删除将级联清除关联指标与证据计划，需显式确认",
                data=impact,
            ),
        )
    return success_response(message="已删除学习目标")


# ── 评价指标 ───────────────────────────────────────────────────
@router.get("/indicators", summary="评价指标列表")
def list_indicators_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_indicators(db, current_user, project_id)
    return success_response(data=[_indicator_response(i) for i in items])


@router.post("/indicators", summary="新增评价指标")
def add_indicator_api(
    project_id: str,
    data: EvaluationIndicatorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        indicator = service.add_indicator(db, current_user, project_id, data)
    except AppException:
        raise
    return success_response(data=_indicator_response(indicator), message="已添加指标")


@router.patch("/indicators/{indicator_id}", summary="更新评价指标")
def update_indicator_api(
    project_id: str,
    indicator_id: str,
    data: EvaluationIndicatorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        indicator = service.update_indicator(
            db, current_user, project_id, indicator_id, data
        )
    except AppException:
        raise
    return success_response(data=_indicator_response(indicator), message="已更新")


@router.delete("/indicators/{indicator_id}", summary="删除评价指标")
def delete_indicator_api(
    project_id: str,
    indicator_id: str,
    confirm: bool = Query(False, description="确认级联删除关联证据计划"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        impact = service.remove_indicator(
            db, current_user, project_id, indicator_id, confirm=confirm
        )
    except AppException:
        raise
    if impact is not None:
        return JSONResponse(
            status_code=409,
            content=error_response(
                code=40901,
                message="指标仍被证据计划引用，删除将级联清除关联证据计划，需显式确认",
                data=impact,
            ),
        )
    return success_response(message="已删除指标")


# ── 证据计划 ───────────────────────────────────────────────────
@router.get("/evidence-plans", summary="证据计划列表")
def list_evidence_plans_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_evidence_plans(db, current_user, project_id)
    return success_response(data=[_evidence_plan_response(p) for p in items])


@router.post("/evidence-plans", summary="新增证据计划")
def add_evidence_plan_api(
    project_id: str,
    data: EvidencePlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        plan = service.add_evidence_plan(db, current_user, project_id, data)
    except AppException:
        raise
    return success_response(
        data=_evidence_plan_response(plan), message="已添加证据计划"
    )


@router.patch("/evidence-plans/{plan_id}", summary="更新证据计划")
def update_evidence_plan_api(
    project_id: str,
    plan_id: str,
    data: EvidencePlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        plan = service.update_evidence_plan(
            db, current_user, project_id, plan_id, data
        )
    except AppException:
        raise
    return success_response(data=_evidence_plan_response(plan), message="已更新")


@router.delete("/evidence-plans/{plan_id}", summary="删除证据计划")
def delete_evidence_plan_api(
    project_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        service.remove_evidence_plan(db, current_user, project_id, plan_id)
    except AppException:
        raise
    return success_response(message="已删除证据计划")


# ── 聚合视图 ───────────────────────────────────────────────────
@router.get("", summary="项目设计聚合快照")
def get_design_snapshot_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        snapshot = service.get_design_snapshot(db, current_user, project_id)
    except AppException:
        raise
    return success_response(data=snapshot)


# ── 序列化辅助 ────────────────────────────────────────────────
def _problem_response(problem) -> dict:
    return {
        "id": problem.id,
        "project_id": problem.project_id,
        "context": problem.context,
        "object": problem.object,
        "audience": problem.audience,
        "constraints": problem.constraints,
        "deliverable": problem.deliverable,
        "usage": problem.usage,
        "is_current": problem.is_current,
        "version": problem.version,
    }


def _contribution_response(c) -> dict:
    role = c.role.value if hasattr(c.role, "value") else str(c.role)
    return {
        "id": c.id,
        "project_id": c.project_id,
        "subject_id": c.subject_id,
        "role": role,
        "knowledge": c.knowledge,
        "thinking": c.thinking,
        "inquiry": c.inquiry,
        "removal_impact": c.removal_impact,
    }


def _goal_response(g) -> dict:
    goal_type = g.goal_type.value if hasattr(g.goal_type, "value") else str(g.goal_type)
    return {
        "id": g.id,
        "project_id": g.project_id,
        "goal_type": goal_type,
        "name": g.name,
        "description": g.description,
        "scope": g.scope,
    }


def _indicator_response(i) -> dict:
    return {
        "id": i.id,
        "goal_id": i.goal_id,
        "project_id": i.project_id,
        "observable_behavior": i.observable_behavior,
        "level_rule": i.level_rule,
    }


def _evidence_plan_response(p) -> dict:
    stage = p.stage.value if hasattr(p.stage, "value") else str(p.stage)
    evidence_type = (
        p.evidence_type.value
        if hasattr(p.evidence_type, "value")
        else str(p.evidence_type)
    )
    collector = (
        p.collector.value if hasattr(p.collector, "value") else str(p.collector)
    )
    return {
        "id": p.id,
        "indicator_id": p.indicator_id,
        "project_id": p.project_id,
        "stage": stage,
        "evidence_type": evidence_type,
        "collector": collector,
        "required": p.required,
        "description": p.description,
    }
