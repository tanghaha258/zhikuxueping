"""统一项目工作区上下文服务（Task 3）。

聚合真实项目、阶段、权限、blockers、warnings、counts 与 actions；
actions 全局至多一个 primary，next_action 基于真实数据计算。
所有查询和操作复用项目读写授权策略，带学校作用域。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.project import Project, ProjectStatus
from app.models.user import Role, User
from app.modules.project_designs.validators import validate_activation as validate_activation_internal
from app.modules.project_workspace import policy
from app.modules.project_workspace.repository import ProjectWorkspaceRepository, utc_now
from app.modules.projects.policy import ensure_can_manage, ensure_can_read, ensure_not_archived
from app.modules.projects.repository import ProjectRepository
from app.schemas.project_workspace import PHASE_ORDER

# 阶段中文标签（与 spec 3.1 一致）
_PHASE_LABELS = {
    "diagnosis": "学情诊断",
    "design": "跨学科设计",
    "preparation": "备课与准备",
    "implementation": "学习实施",
    "evaluation": "多元评价",
    "improvement": "改进循环",
    "closure": "结项归档",
}


# ============================================================
# context
# ============================================================
def get_context(db: Session, actor: User, project_id: str) -> dict:
    """GET /project-workspace/{id}/context 服务实现。"""
    project = _require_project(db, project_id)
    class_ids = ProjectRepository(db).class_ids(project.id)
    ensure_can_read(actor, project, class_ids)

    repo = ProjectWorkspaceRepository(db)
    stages = {s.phase: s for s in repo.list_stages(project.id)}

    # 七阶段固定顺序，缺失记录视为 not_started（读操作不创建记录）
    phases = [_phase_dict(phase, stages.get(phase)) for phase in PHASE_ORDER]

    permissions = _build_permissions(actor, project, class_ids)
    counts = _build_counts(repo, project.id)

    # 复用设计完整性校验（读真实设计数据）
    validation = validate_activation_internal(db, project)
    blockers, warnings = _build_issues(repo, project.id, validation)

    actions, next_action = _compute_actions(project, phases, counts, permissions, validation)

    return {
        "project": _project_dict(db, project, class_ids),
        "phases": phases,
        "permissions": permissions,
        "blockers": blockers,
        "warnings": warnings,
        "counts": counts,
        "actions": actions,
        "next_action": next_action,
    }


# ============================================================
# timeline
# ============================================================
def get_timeline(db: Session, actor: User, project_id: str) -> list[dict]:
    """GET /project-workspace/{id}/timeline 服务实现。"""
    project = _require_project(db, project_id)
    class_ids = ProjectRepository(db).class_ids(project.id)
    ensure_can_read(actor, project, class_ids)
    return ProjectWorkspaceRepository(db).list_timeline_events(project)


# ============================================================
# 阶段完成 / 重开
# ============================================================
def complete_phase(db: Session, actor: User, project_id: str, phase: str) -> dict:
    """POST .../phases/{phase}/complete：标记阶段完成。"""
    policy.validate_phase(phase)
    project = _require_project(db, project_id)
    class_ids = ProjectRepository(db).class_ids(project.id)
    ensure_can_manage(actor, project, class_ids)
    ensure_not_archived(project)

    repo = ProjectWorkspaceRepository(db)
    stage = repo.get_or_create_stage(project.id, phase)
    if stage.status == "completed":
        raise AppException(
            code=40901,
            message=f"阶段 {phase} 已完成，无需重复标记",
            status_code=409,
        )
    stage.status = "completed"
    stage.completed_at = utc_now()
    _commit(db)
    db.refresh(stage)
    return _phase_dict(phase, stage)


def reopen_phase(
    db: Session, actor: User, project_id: str, phase: str, reason: Optional[str]
) -> dict:
    """POST .../phases/{phase}/reopen：重新开放已完成阶段。"""
    policy.validate_phase(phase)
    project = _require_project(db, project_id)
    class_ids = ProjectRepository(db).class_ids(project.id)
    ensure_can_manage(actor, project, class_ids)
    ensure_not_archived(project)

    repo = ProjectWorkspaceRepository(db)
    stage = repo.get_stage(project.id, phase)
    if stage is None or stage.status != "completed":
        raise AppException(
            code=40901,
            message=f"阶段 {phase} 未完成，无法重新开放",
            status_code=409,
        )
    stage.status = "in_progress"
    stage.reopened_at = utc_now()
    stage.reopened_by = actor.id
    stage.reopen_reason = reason.strip() if reason and reason.strip() else None
    _commit(db)
    db.refresh(stage)
    return _phase_dict(phase, stage)


# ============================================================
# 内部辅助
# ============================================================
def _require_project(db: Session, project_id: str) -> Project:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise AppException(code=40401, message="项目不存在", status_code=404)
    return project


def _phase_dict(phase: str, stage) -> dict:
    if stage is None:
        return {
            "phase": phase,
            "status": "not_started",
            "completed_at": None,
            "reopened_at": None,
            "reopened_by": None,
            "reopen_reason": None,
        }
    return {
        "phase": stage.phase,
        "status": stage.status,
        "completed_at": stage.completed_at,
        "reopened_at": stage.reopened_at,
        "reopened_by": stage.reopened_by,
        "reopen_reason": stage.reopen_reason,
    }


def _build_permissions(actor: User, project: Project, class_ids: list[str]) -> dict:
    is_archived = project.status == ProjectStatus.ARCHIVED
    can_manage = _can_manage(actor, project, class_ids)
    can_reopen = can_manage and actor.role == Role.SCHOOL_ADMIN
    return {
        "can_view": True,  # ensure_can_read 已通过
        "can_manage": can_manage,
        "can_reopen": can_reopen,
        "is_archived": is_archived,
    }


def _can_manage(actor: User, project: Project, class_ids: list[str]) -> bool:
    """非抛出版权限检查，复用 ensure_can_manage 的判定逻辑。"""
    try:
        ensure_can_manage(actor, project, class_ids)
        return True
    except AppException:
        return False


def _build_counts(repo: ProjectWorkspaceRepository, project_id: str) -> dict:
    return {
        "tasks": repo.count_tasks(project_id),
        "published_tasks": repo.count_published_tasks(project_id),
        "submissions": repo.count_submissions(project_id),
        "evaluations": repo.count_evaluations(project_id),
        "unpublished_evaluations": repo.count_unpublished_evaluations(project_id),
        "students": repo.count_students(project_id),
        "ai_jobs": repo.count_ai_jobs(project_id),
        "pending_ai_reviews": repo.count_pending_ai_reviews(project_id),
    }


def _build_issues(repo: ProjectWorkspaceRepository, project_id: str, validation) -> tuple[list, list]:
    """从真实设计校验与运营数据构造 blockers/warnings。"""
    blockers = [
        {"code": b.code, "field": b.field, "message": b.message, "phase": "design"}
        for b in validation.blockers
    ]
    warnings = [
        {"code": w.code, "field": w.field, "message": w.message, "phase": "design"}
        for w in validation.warnings
    ]

    # 未处理阻断质量问题
    open_blockers = repo.count_open_blocker_issues(project_id)
    if open_blockers > 0:
        blockers.append(
            {
                "code": "open_quality_blocker",
                "field": "ai_quality",
                "message": f"存在 {open_blockers} 条未处理的阻断质量问题",
                "phase": None,
            }
        )

    # 未发布评价（warning，项目进行中属正常状态，临近结项需处理）
    unpublished = repo.count_unpublished_evaluations(project_id)
    if unpublished > 0:
        warnings.append(
            {
                "code": "unpublished_evaluations",
                "field": "evaluations",
                "message": f"存在 {unpublished} 条未发布评价",
                "phase": "evaluation",
            }
        )

    return blockers, warnings


def _compute_actions(
    project: Project,
    phases: list[dict],
    counts: dict,
    permissions: dict,
    validation,
) -> tuple[list[dict], Optional[dict]]:
    """基于真实数据计算 actions 与唯一 next_action。"""
    actions: list[dict] = []
    overview_route = f"/teacher/projects/{project.id}/overview"

    if permissions["is_archived"]:
        if permissions["can_reopen"]:
            actions.append(
                _action(
                    "reopen_project",
                    "申请重新开放",
                    "transition",
                    primary=True,
                    route=f"/teacher/projects/{project.id}/closure",
                    reason="归档项目需学校管理员重新开放",
                )
            )
        return actions, _primary(actions)

    status = project.status

    if status in (ProjectStatus.DRAFT, ProjectStatus.PENDING_REVIEW):
        if validation.blockers:
            actions.append(
                _action(
                    "complete_design",
                    "完善设计",
                    "navigate",
                    primary=True,
                    route=f"/teacher/projects/{project.id}/design",
                    phase="design",
                    reason=f"存在 {len(validation.blockers)} 项设计阻断",
                )
            )
        elif status == ProjectStatus.DRAFT:
            actions.append(
                _action("submit_for_review", "提交审核", "transition", primary=True, route=overview_route)
            )
        else:  # PENDING_REVIEW 且无阻断
            actions.append(
                _action("activate", "激活项目", "transition", primary=True, route=overview_route)
            )
    elif status == ProjectStatus.ACTIVE:
        current = next((p for p in phases if p["status"] != "completed"), None)
        if current:
            actions.append(
                _action(
                    f"work_{current['phase']}",
                    f"进入{_PHASE_LABELS[current['phase']]}",
                    "navigate",
                    primary=True,
                    route=policy.phase_route(project.id, current["phase"]),
                    phase=current["phase"],
                )
            )
        else:
            actions.append(
                _action(
                    "complete_project",
                    "结项",
                    "transition",
                    primary=True,
                    route=f"/teacher/projects/{project.id}/closure",
                    phase="closure",
                )
            )
    elif status == ProjectStatus.COMPLETED:
        actions.append(
            _action(
                "archive",
                "归档项目",
                "transition",
                primary=True,
                route=f"/teacher/projects/{project.id}/closure",
                phase="closure",
            )
        )

    return actions, _primary(actions)


def _action(
    id_: str,
    label: str,
    type_: str,
    *,
    primary: bool = False,
    route: Optional[str] = None,
    phase: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    return {
        "id": id_,
        "label": label,
        "type": type_,
        "primary": primary,
        "route": route,
        "phase": phase,
        "reason": reason,
    }


def _primary(actions: list[dict]) -> Optional[dict]:
    return next((a for a in actions if a["primary"]), None)


def _project_dict(db: Session, project: Project, class_ids: list[str]) -> dict:
    repo = ProjectRepository(db)
    status_value = (
        project.status.value if hasattr(project.status, "value") else str(project.status)
    )
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "status": status_value,
        "creator_id": project.creator_id,
        "school_id": project.school_id,
        "grade": project.grade,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
        "project_type": project.project_type,
        "core_subject_id": project.core_subject_id,
        "review_status": (
            project.review_status.value
            if hasattr(project.review_status, "value")
            else str(project.review_status)
        ),
        "class_ids": class_ids,
        "subject_ids": repo.subject_ids(project.id),
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
