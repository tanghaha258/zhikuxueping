"""统一项目工作区上下文 Pydantic 模型（Task 3）。

字段命名与后端 snake_case 一致；HTTP 响应经前端拦截器转为 camelCase。
context 聚合真实项目、阶段、权限、blockers、warnings、counts 与 actions，
actions 全局至多一个 primary，next_action 基于真实数据计算。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── 阶段（固定顺序，单一来源）────────────────────────────────
PHASE_ORDER: tuple[str, ...] = (
    "diagnosis",
    "design",
    "preparation",
    "implementation",
    "evaluation",
    "improvement",
    "closure",
)


class ProjectWorkspacePhase(BaseModel):
    """单个项目阶段进度。"""

    phase: str
    status: str  # not_started / in_progress / completed / blocked
    completed_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    reopened_by: Optional[str] = None
    reopen_reason: Optional[str] = None


class ProjectWorkspacePermissions(BaseModel):
    """当前用户对该项目的权限快照。"""

    can_view: bool
    can_manage: bool
    can_reopen: bool  # 归档项目重新开放权限（school_admin）
    is_archived: bool


class ProjectWorkspaceIssue(BaseModel):
    """阻断或警告项，可定位到阶段/字段。"""

    code: str
    field: str = ""
    message: str
    phase: Optional[str] = None


class ProjectWorkspaceCounts(BaseModel):
    """真实数据计数，不伪造。"""

    tasks: int = 0
    published_tasks: int = 0
    submissions: int = 0
    evaluations: int = 0
    unpublished_evaluations: int = 0
    students: int = 0
    ai_jobs: int = 0
    pending_ai_reviews: int = 0


class ProjectWorkspaceAction(BaseModel):
    """可执行动作；primary=True 表示全局唯一主操作。"""

    id: str
    label: str
    type: str  # transition / phase_complete / phase_reopen / navigate / read
    primary: bool = False
    route: Optional[str] = None
    phase: Optional[str] = None
    reason: Optional[str] = None


class ProjectWorkspaceContext(BaseModel):
    """GET /project-workspace/{id}/context 统一上下文响应。"""

    project: dict
    phases: list[ProjectWorkspacePhase]
    permissions: ProjectWorkspacePermissions
    blockers: list[ProjectWorkspaceIssue]
    warnings: list[ProjectWorkspaceIssue]
    counts: ProjectWorkspaceCounts
    actions: list[ProjectWorkspaceAction]
    next_action: Optional[ProjectWorkspaceAction] = None


class ProjectWorkspaceTimelineEvent(BaseModel):
    """timeline 真实事件。"""

    type: str  # project_created / phase_completed / phase_reopened / project_reopened / evaluation_published / task_created
    label: str
    timestamp: datetime
    phase: Optional[str] = None
    actor: Optional[str] = None


class PhaseReopenRequest(BaseModel):
    """阶段重开请求体；reason 留痕便于审计。"""

    reason: Optional[str] = None
