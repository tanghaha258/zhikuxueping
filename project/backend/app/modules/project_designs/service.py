"""项目设计领域服务层。

职责：
- 组合 repository / policy / validators 完成跨表原子写入。
- 唯一提交点：服务层方法在事务结束时 `db.commit()`，失败回滚。
- 跨教师、跨学校访问通过 `projects.policy` 强制；非法状态通过 409 返回。
- 真实问题编辑采用版本化：每次更新把旧版本标记为非当前并写入新版本，
  历史版本保留只读，不覆盖。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.project import Project
from app.models.project_design import (
    EvaluationIndicator,
    EvidencePlan,
    LearningGoal,
    ProjectProblem,
    SubjectContribution,
    SubjectRole,
)
from app.models.user import User
from app.modules.project_designs.policy import (
    ensure_can_read_design,
    ensure_design_editable,
)
from app.modules.project_designs.repository import ProjectDesignRepository
from app.modules.project_designs.validators import (
    validate_activation,
    validate_contribution_uniqueness,
)
from app.modules.projects.repository import ProjectRepository
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


# ── 辅助 ──────────────────────────────────────────────────────
def _load_project(db: Session, project_id: str) -> Project:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise AppException(code=40401, message="项目不存在", status_code=404)
    return project


def _class_ids(db: Session, project_id: str) -> list[str]:
    return ProjectRepository(db).class_ids(project_id)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


# ── ProjectProblem ────────────────────────────────────────────
def get_current_problem(db: Session, actor: User, project_id: str) -> ProjectProblem | None:
    project = _load_project(db, project_id)
    ensure_can_read_design(actor, project, _class_ids(db, project_id))
    return ProjectDesignRepository(db).get_problem(project_id)


def upsert_problem(
    db: Session, actor: User, project_id: str, data: ProjectProblemCreate
) -> ProjectProblem:
    """写入真实问题的新版本。

    历史版本保留为 `is_current=False`，便于追溯设计演进；
    不直接覆盖旧记录，避免丢失审计轨迹。
    """
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    repository.mark_problem_versions_non_current(project_id)
    version = repository.next_problem_version(project_id)
    problem = ProjectProblem(
        project_id=project_id,
        context=data.context,
        object=data.object,
        audience=data.audience,
        constraints=data.constraints,
        deliverable=data.deliverable,
        usage=data.usage,
        is_current=True,
        version=version,
    )
    repository.add_problem(problem)
    db.flush()
    _commit(db)
    db.refresh(problem)
    return problem


def update_problem(
    db: Session, actor: User, project_id: str, data: ProjectProblemUpdate
) -> ProjectProblem:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    problem = repository.get_problem(project_id)
    if not problem:
        raise AppException(code=40401, message="项目尚未定义真实问题", status_code=404)
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(problem, field, value)
    _commit(db)
    db.refresh(problem)
    return problem


# ── SubjectContribution ───────────────────────────────────────
def list_contributions(
    db: Session, actor: User, project_id: str
) -> list[SubjectContribution]:
    project = _load_project(db, project_id)
    ensure_can_read_design(actor, project, _class_ids(db, project_id))
    return ProjectDesignRepository(db).list_contributions(project_id)


def add_contribution(
    db: Session, actor: User, project_id: str, data: SubjectContributionCreate
) -> SubjectContribution:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    issues = validate_contribution_uniqueness(
        project_id, data.subject_id, data.role, repository
    )
    if issues:
        # 重复学科/重复核心属于状态冲突，返回 409 而非 400。
        raise AppException(
            code=40901,
            message=issues[0].message,
            status_code=409,
        )
    contribution = SubjectContribution(
        project_id=project_id,
        subject_id=data.subject_id,
        role=data.role,
        knowledge=data.knowledge,
        thinking=data.thinking,
        inquiry=data.inquiry,
        removal_impact=data.removal_impact,
    )
    repository.add_contribution(contribution)
    db.flush()
    # 若新增的是核心学科，同步项目主表 core_subject_id，保持一致性。
    if data.role == SubjectRole.CORE:
        project.core_subject_id = data.subject_id
    _commit(db)
    db.refresh(contribution)
    return contribution


def update_contribution(
    db: Session,
    actor: User,
    project_id: str,
    contribution_id: str,
    data: SubjectContributionUpdate,
) -> SubjectContribution:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    contribution = repository.get_contribution(contribution_id)
    if not contribution or contribution.project_id != project_id:
        raise AppException(code=40401, message="学科贡献不存在", status_code=404)
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(contribution, field, value)
    _commit(db)
    db.refresh(contribution)
    return contribution


def remove_contribution(
    db: Session,
    actor: User,
    project_id: str,
    contribution_id: str,
    *,
    confirm: bool = False,
) -> dict | None:
    """移除学科贡献。

    核心学科被移除会清空项目主表 `core_subject_id`，属破坏性操作：
    - 未带 `confirm=True` 时返回引用影响，不执行删除；
    - `confirm=True` 时执行删除并同步清空主表字段。
    支撑学科无下游引用，可直接删除。返回 impact dict 表示需要确认。
    """
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    contribution = repository.get_contribution(contribution_id)
    if not contribution or contribution.project_id != project_id:
        raise AppException(code=40401, message="学科贡献不存在", status_code=404)
    if contribution.role == SubjectRole.CORE and not confirm:
        return {
            "requires_confirmation": True,
            "will_clear_core_subject": True,
        }
    # 移除核心学科时同步清空主表字段，避免一致性缺口。
    if contribution.role == SubjectRole.CORE and project.core_subject_id == contribution.subject_id:
        project.core_subject_id = None
    repository.delete_contribution(contribution)
    _commit(db)
    return None


# ── LearningGoal ──────────────────────────────────────────────
def list_goals(db: Session, actor: User, project_id: str) -> list[LearningGoal]:
    project = _load_project(db, project_id)
    ensure_can_read_design(actor, project, _class_ids(db, project_id))
    return ProjectDesignRepository(db).list_goals(project_id)


def add_goal(
    db: Session, actor: User, project_id: str, data: LearningGoalCreate
) -> LearningGoal:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    goal = LearningGoal(
        project_id=project_id,
        goal_type=data.goal_type,
        name=data.name,
        description=data.description,
        scope=data.scope,
    )
    ProjectDesignRepository(db).add_goal(goal)
    db.flush()
    _commit(db)
    db.refresh(goal)
    return goal


def update_goal(
    db: Session, actor: User, project_id: str, goal_id: str, data: LearningGoalUpdate
) -> LearningGoal:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    goal = repository.get_goal(goal_id)
    if not goal or goal.project_id != project_id:
        raise AppException(code=40401, message="学习目标不存在", status_code=404)
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(goal, field, value)
    _commit(db)
    db.refresh(goal)
    return goal


def remove_goal(
    db: Session,
    actor: User,
    project_id: str,
    goal_id: str,
    *,
    confirm: bool = False,
) -> dict | None:
    """删除学习目标。

    被指标引用时属关联删除：
    - 未带 `confirm=True` 返回引用影响，不删除；
    - `confirm=True` 级联删除指标及其证据计划，再删除目标。
    返回 impact dict 表示需要确认。
    """
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    goal = repository.get_goal(goal_id)
    if not goal or goal.project_id != project_id:
        raise AppException(code=40401, message="学习目标不存在", status_code=404)
    linked_indicators = repository.list_indicators_by_goal(goal_id)
    if linked_indicators and not confirm:
        return {
            "requires_confirmation": True,
            "referenced_by": {"indicators": len(linked_indicators)},
        }
    # 级联删除：先清除指标引用的证据计划，再删除指标，最后删除目标。
    for ind in linked_indicators:
        for plan in repository.list_evidence_plans_by_indicator(ind.id):
            repository.delete_evidence_plan(plan)
        repository.delete_indicator(ind)
    repository.delete_goal(goal)
    _commit(db)
    return None


# ── EvaluationIndicator ───────────────────────────────────────
def list_indicators(
    db: Session, actor: User, project_id: str
) -> list[EvaluationIndicator]:
    project = _load_project(db, project_id)
    ensure_can_read_design(actor, project, _class_ids(db, project_id))
    return ProjectDesignRepository(db).list_indicators(project_id)


def add_indicator(
    db: Session,
    actor: User,
    project_id: str,
    data: EvaluationIndicatorCreate,
) -> EvaluationIndicator:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    goal = repository.get_goal(data.goal_id)
    if not goal or goal.project_id != project_id:
        raise AppException(
            code=40001,
            message="指标必须绑定本项目内的学习目标",
            status_code=400,
        )
    indicator = EvaluationIndicator(
        goal_id=data.goal_id,
        project_id=project_id,
        observable_behavior=data.observable_behavior,
        level_rule=data.level_rule,
    )
    repository.add_indicator(indicator)
    db.flush()
    _commit(db)
    db.refresh(indicator)
    return indicator


def update_indicator(
    db: Session,
    actor: User,
    project_id: str,
    indicator_id: str,
    data: EvaluationIndicatorUpdate,
) -> EvaluationIndicator:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    indicator = repository.get_indicator(indicator_id)
    if not indicator or indicator.project_id != project_id:
        raise AppException(code=40401, message="评价指标不存在", status_code=404)
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(indicator, field, value)
    _commit(db)
    db.refresh(indicator)
    return indicator


def remove_indicator(
    db: Session,
    actor: User,
    project_id: str,
    indicator_id: str,
    *,
    confirm: bool = False,
) -> dict | None:
    """删除评价指标。

    被证据计划引用时属关联删除：
    - 未带 `confirm=True` 返回引用影响，不删除；
    - `confirm=True` 级联删除证据计划，再删除指标。
    返回 impact dict 表示需要确认。
    """
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    indicator = repository.get_indicator(indicator_id)
    if not indicator or indicator.project_id != project_id:
        raise AppException(code=40401, message="评价指标不存在", status_code=404)
    linked_plans = repository.list_evidence_plans_by_indicator(indicator_id)
    if linked_plans and not confirm:
        return {
            "requires_confirmation": True,
            "referenced_by": {"evidence_plans": len(linked_plans)},
        }
    for plan in linked_plans:
        repository.delete_evidence_plan(plan)
    repository.delete_indicator(indicator)
    _commit(db)
    return None


# ── EvidencePlan ──────────────────────────────────────────────
def list_evidence_plans(
    db: Session, actor: User, project_id: str
) -> list[EvidencePlan]:
    project = _load_project(db, project_id)
    ensure_can_read_design(actor, project, _class_ids(db, project_id))
    return ProjectDesignRepository(db).list_evidence_plans(project_id)


def add_evidence_plan(
    db: Session,
    actor: User,
    project_id: str,
    data: EvidencePlanCreate,
) -> EvidencePlan:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    indicator = repository.get_indicator(data.indicator_id)
    if not indicator or indicator.project_id != project_id:
        raise AppException(
            code=40001,
            message="证据计划必须绑定本项目内的指标",
            status_code=400,
        )
    plan = EvidencePlan(
        indicator_id=data.indicator_id,
        project_id=project_id,
        stage=data.stage,
        evidence_type=data.evidence_type,
        collector=data.collector,
        required=data.required,
        description=data.description,
    )
    repository.add_evidence_plan(plan)
    db.flush()
    _commit(db)
    db.refresh(plan)
    return plan


def update_evidence_plan(
    db: Session,
    actor: User,
    project_id: str,
    plan_id: str,
    data: EvidencePlanUpdate,
) -> EvidencePlan:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    plan = repository.get_evidence_plan(plan_id)
    if not plan or plan.project_id != project_id:
        raise AppException(code=40401, message="证据计划不存在", status_code=404)
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(plan, field, value)
    _commit(db)
    db.refresh(plan)
    return plan


def remove_evidence_plan(
    db: Session, actor: User, project_id: str, plan_id: str
) -> None:
    project = _load_project(db, project_id)
    ensure_design_editable(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    plan = repository.get_evidence_plan(plan_id)
    if not plan or plan.project_id != project_id:
        raise AppException(code=40401, message="证据计划不存在", status_code=404)
    repository.delete_evidence_plan(plan)
    _commit(db)


# ── 完整性检查 + 设计快照 ──────────────────────────────────────
def validate_project_activation(db: Session, actor: User, project_id: str) -> dict:
    """`POST /api/v1/projects/{id}/validate-activation` 服务实现。"""
    project = _load_project(db, project_id)
    ensure_can_read_design(actor, project, _class_ids(db, project_id))
    result = validate_activation(db, project)
    return result.to_dict()


def get_design_snapshot(db: Session, actor: User, project_id: str) -> dict:
    """聚合返回项目设计页一次渲染所需的全部数据。"""
    project = _load_project(db, project_id)
    ensure_can_read_design(actor, project, _class_ids(db, project_id))
    repository = ProjectDesignRepository(db)
    problem = repository.get_problem(project_id)
    return {
        "problem": _problem_dict(problem) if problem else None,
        "contributions": [
            _contribution_dict(c) for c in repository.list_contributions(project_id)
        ],
        "goals": [_goal_dict(g) for g in repository.list_goals(project_id)],
        "indicators": [
            _indicator_dict(i) for i in repository.list_indicators(project_id)
        ],
        "evidence_plans": [
            _evidence_plan_dict(p)
            for p in repository.list_evidence_plans(project_id)
        ],
    }


# ── 序列化辅助 ────────────────────────────────────────────────
def _problem_dict(problem: ProjectProblem) -> dict:
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


def _contribution_dict(c: SubjectContribution) -> dict:
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


def _goal_dict(g: LearningGoal) -> dict:
    goal_type = g.goal_type.value if hasattr(g.goal_type, "value") else str(g.goal_type)
    return {
        "id": g.id,
        "project_id": g.project_id,
        "goal_type": goal_type,
        "name": g.name,
        "description": g.description,
        "scope": g.scope,
    }


def _indicator_dict(i: EvaluationIndicator) -> dict:
    return {
        "id": i.id,
        "goal_id": i.goal_id,
        "project_id": i.project_id,
        "observable_behavior": i.observable_behavior,
        "level_rule": i.level_rule,
    }


def _evidence_plan_dict(p: EvidencePlan) -> dict:
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
