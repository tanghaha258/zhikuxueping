"""项目设计领域权限策略。

复用 `app.modules.projects.policy` 的可见性与管理权限判断，
保证跨教师、跨学校、跨班级的访问规则与项目主表一致。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.models.project import Project
from app.models.user import User
from app.modules.projects.policy import (
    ensure_can_manage,
    ensure_can_read,
)


def ensure_can_read_design(actor: User, project: Project, class_ids: list[str]) -> None:
    """读取项目设计：与项目读取权限一致。"""
    ensure_can_read(actor, project, class_ids)


def ensure_can_manage_design(
    actor: User, project: Project, class_ids: list[str]
) -> None:
    """修改项目设计：与项目管理权限一致。

    设计编辑属于写操作，学生角色即便能读取项目也不允许编辑设计。
    """
    ensure_can_manage(actor, project, class_ids)


def ensure_design_editable(actor: User, project: Project, class_ids: list[str]) -> None:
    """仅在项目处于草稿/待审核/退回状态时允许编辑设计。

    正式（active 及之后）项目的设计进入只读，必须先重新开放或新建版本。
    本函数不抛 403 而抛 409，表示状态冲突而非权限不足。
    """
    ensure_can_manage_design(actor, project, class_ids)
    editable_statuses = {"draft", "pending_review", "returned"}
    current = project.status.value if hasattr(project.status, "value") else str(project.status)
    if current not in editable_statuses:
        raise AppException(
            code=40901,
            message=f"当前项目状态 {current} 不允许编辑设计",
            status_code=409,
        )
