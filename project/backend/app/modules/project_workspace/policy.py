"""统一项目工作区授权与阶段校验（Task 3）。

复用项目读写授权策略（app.modules.projects.policy），确保所有查询和操作带
学校作用域：跨教师、跨学校访问由 ensure_can_read / ensure_can_manage 统一拒绝。
阶段固定为七阶段，非法阶段返回 400。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.projects.policy import (  # noqa: F401 — re-export for router
    ensure_can_manage,
    ensure_can_read,
    ensure_not_archived,
)
from app.schemas.project_workspace import PHASE_ORDER

_PHASE_SET = frozenset(PHASE_ORDER)


def validate_phase(phase: str) -> None:
    """校验阶段合法性；非法阶段返回 400。"""
    if phase not in _PHASE_SET:
        raise AppException(
            code=40001,
            message=f"非法阶段: {phase}，合法阶段为 {list(PHASE_ORDER)}",
            status_code=400,
        )


def phase_route(project_id: str, phase: str) -> str:
    """阶段在前端工作区的路由路径。"""
    # implementation 阶段对应任务实施页（spec 3.1 路由 :id/tasks）
    if phase == "implementation":
        return f"/teacher/projects/{project_id}/tasks"
    return f"/teacher/projects/{project_id}/{phase}"
