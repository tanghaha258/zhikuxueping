"""工具上下文授权与校验（Task 8）。

- 校验 artifact_type / placement / phase 合法值（非法返回 400）。
- 项目关联复用项目读写授权（``app.modules.projects.policy``），跨校访问 403。
- 独立模式不得伪造 project_id；context-links 端点只接受项目模式。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.project import Project, ProjectClass
from app.models.tool_context import ToolContextLink
from app.models.user import User
from app.modules.projects.policy import ensure_can_manage, ensure_can_read


# ── 合法值集合（与 ToolContextLink 模型 comment 一致）──────────────
ARTIFACT_TYPES = frozenset(
    {"lesson_plan", "resource", "paper", "ai_output", "question_bank"}
)

PLACEMENTS = frozenset(
    {
        "pre_test",
        "in_class",
        "post_test",
        "resource",
        "lesson_plan",
        "ai_draft",
        "task_sheet",
        "rubric",
    }
)

PHASES = frozenset(
    {
        "diagnosis",
        "design",
        "preparation",
        "implementation",
        "evaluation",
        "improvement",
        "closure",
    }
)


def validate_artifact_type(artifact_type: str) -> None:
    if artifact_type not in ARTIFACT_TYPES:
        raise AppException(
            code=40001,
            message=f"无效的资产类型: {artifact_type}，合法值为 {sorted(ARTIFACT_TYPES)}",
            status_code=400,
        )


def validate_placement(placement: str) -> None:
    if placement not in PLACEMENTS:
        raise AppException(
            code=40001,
            message=f"无效的放置位置: {placement}，合法值为 {sorted(PLACEMENTS)}",
            status_code=400,
        )


def validate_phase(phase: str | None) -> None:
    if phase is not None and phase != "" and phase not in PHASES:
        raise AppException(
            code=40001,
            message=f"无效的项目阶段: {phase}，合法值为 {sorted(PHASES)}",
            status_code=400,
        )


def ensure_can_link_to_project(db: Session, actor: User, project_id: str) -> None:
    """关联资产到项目需要项目管理权；跨校访问 403。"""
    project, class_ids = _project_context(db, project_id)
    ensure_can_manage(actor, project, class_ids)


def ensure_can_read_project_links(db: Session, actor: User, project_id: str) -> None:
    """读取项目上下文链接需要项目读权限；跨校访问 403。"""
    project, class_ids = _project_context(db, project_id)
    ensure_can_read(actor, project, class_ids)


def ensure_can_manage_link(db: Session, actor: User, link: ToolContextLink) -> None:
    """取消关联需要对链接所属项目有管理权；跨校访问 403。"""
    ensure_can_link_to_project(db, actor, link.project_id)


def _project_context(db: Session, project_id: str) -> tuple[Project, list[str]]:
    project = db.get(Project, project_id)
    if not project:
        raise AppException(code=40401, message="project not found", status_code=404)
    class_ids = list(
        db.execute(
            select(ProjectClass.class_id).where(ProjectClass.project_id == project_id)
        ).scalars().all()
    )
    return project, class_ids
