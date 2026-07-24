"""工具上下文链接服务（Task 8）。

高层编排：
- ``link_asset``：校验上下文 → 跨校授权 → 唯一性检查 → 创建引用 → 提交。
- ``unlink_asset``：加载引用 → 跨校授权 → 删除引用（不删资产）→ 提交。
- ``list_project_links`` / ``list_artifact_links``：读授权后查询。

设计要点（spec 第 7 节）：
- 项目模式必须 project_id + placement；独立模式不通过本服务关联项目。
- 同一资产在同一项目同一位置仅一条引用（409 重复）。
- 取消关联只删引用，资产本体与文件由所有者保留。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.tool_context import ToolContextLink
from app.models.user import User
from app.modules.tool_context import policy
from app.modules.tool_context.repository import ToolContextRepository


def link_asset(
    db: Session,
    actor: User,
    *,
    artifact_type: str,
    artifact_id: str,
    project_id: str,
    placement: str,
    phase: str | None = None,
    task_id: str | None = None,
    goal_id: str | None = None,
    context_snapshot: dict | None = None,
) -> ToolContextLink:
    """将独立工具资产关联到项目指定位置。

    - 校验 artifact_type / placement / phase 合法性（400）。
    - 校验 actor 对项目有管理权（跨校 403）。
    - 唯一性约束：(artifact_type, artifact_id, project_id, placement) 重复返回 409。
    """
    if not project_id:
        raise AppException(
            code=40001,
            message="项目模式必须提供 project_id，独立模式不通过本端点关联",
            status_code=400,
        )
    if not placement:
        raise AppException(
            code=40001,
            message="项目模式必须提供 placement",
            status_code=400,
        )
    policy.validate_artifact_type(artifact_type)
    policy.validate_placement(placement)
    policy.validate_phase(phase)
    policy.ensure_can_link_to_project(db, actor, project_id)

    repo = ToolContextRepository(db)
    existing = repo.find(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        project_id=project_id,
        placement=placement,
    )
    if existing is not None:
        raise AppException(
            code=40901,
            message="该资产在此项目此位置已存在引用，不能重复挂载",
            status_code=409,
        )

    link = ToolContextLink(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        project_id=project_id,
        placement=placement,
        phase=(phase or None),
        task_id=task_id,
        goal_id=goal_id,
        context_snapshot=context_snapshot,
        created_by=actor.id,
    )
    repo.create(link)
    _commit(db)
    db.refresh(link)
    return link


def unlink_asset(db: Session, actor: User, link_id: str) -> dict:
    """取消关联：只删除引用，不删除资产本体或文件。

    返回 ``{"artifact_type", "artifact_id", "preserved": True}`` 供调用方
    向 UI 确认资产仍保留。
    """
    repo = ToolContextRepository(db)
    link = repo.get(link_id)
    if link is None:
        raise AppException(code=40401, message="context link not found", status_code=404)
    policy.ensure_can_manage_link(db, actor, link)

    artifact_type = link.artifact_type
    artifact_id = link.artifact_id
    repo.delete(link)
    _commit(db)
    return {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "preserved": True,
    }


def list_project_links(
    db: Session,
    actor: User,
    project_id: str,
    *,
    artifact_type: str | None = None,
) -> list[ToolContextLink]:
    """列出项目下的上下文引用；跨校读 403。"""
    if artifact_type:
        policy.validate_artifact_type(artifact_type)
    policy.ensure_can_read_project_links(db, actor, project_id)
    return ToolContextRepository(db).list_by_project(
        project_id, artifact_type=artifact_type
    )


def list_artifact_links(
    db: Session,
    actor: User,
    artifact_type: str,
    artifact_id: str,
) -> list[ToolContextLink]:
    """列出一项资产的所有项目引用。

    读授权由调用方在更上层保障（如资源/教案服务先验证资产可见性），
    本函数仅做类型校验与查询。
    """
    policy.validate_artifact_type(artifact_type)
    return ToolContextRepository(db).list_by_artifact(artifact_type, artifact_id)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
