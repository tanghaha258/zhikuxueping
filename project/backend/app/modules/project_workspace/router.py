"""统一项目工作区 HTTP 路由（Task 3）。

路由前缀：/api/v1/project-workspace/{project_id}/...
- context/timeline 沿用项目读取权限（get_current_user）。
- complete/reopen 要求 teacher/school_admin/admin 角色，服务层复用项目读写授权。
归档项目写操作返回 409；非法阶段返回 400。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.project_workspace import service
from app.schemas.project_workspace import PhaseReopenRequest


router = APIRouter(prefix="/project-workspace", tags=["项目工作区"])


@router.get("/{project_id}/context", summary="统一项目上下文")
def get_context_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = service.get_context(db, current_user, project_id)
    except AppException:
        raise
    return success_response(data=data)


@router.get("/{project_id}/timeline", summary="项目时间线")
def get_timeline_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = service.get_timeline(db, current_user, project_id)
    except AppException:
        raise
    return success_response(data=data)


@router.post("/{project_id}/phases/{phase}/complete", summary="完成项目阶段")
def complete_phase_api(
    project_id: str,
    phase: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        phase_data = service.complete_phase(db, current_user, project_id, phase)
    except AppException:
        raise
    return success_response(data=phase_data, message="阶段已标记完成")


@router.post("/{project_id}/phases/{phase}/reopen", summary="重新开放项目阶段")
def reopen_phase_api(
    project_id: str,
    phase: str,
    data: Optional[PhaseReopenRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    reason = data.reason if data else None
    try:
        phase_data = service.reopen_phase(db, current_user, project_id, phase, reason)
    except AppException:
        raise
    return success_response(data=phase_data, message="阶段已重新开放")
