"""项目学情诊断 HTTP 路由（Task 6）。

路由前缀：/api/v1/projects/{project_id}/insights/...
- latest 沿用项目读取权限（get_current_user）。
- generate/confirm 要求 teacher/school_admin/admin 角色，服务层复用项目读写授权。
归档项目写操作返回 409；无证据诊断不可确认（409）。
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
from app.modules.project_learning_insights import service
from app.schemas.project_learning_insight import InsightConfirmRequest

router = APIRouter(prefix="/projects", tags=["项目学情诊断"])


@router.get("/{project_id}/insights/latest", summary="获取项目当前学情诊断")
def get_latest_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = service.get_latest(db, current_user, project_id)
    except AppException:
        raise
    return success_response(data=data)


@router.post("/{project_id}/insights/generate", summary="生成项目学情诊断")
def generate_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        data = service.generate(db, current_user, project_id)
    except AppException:
        raise
    return success_response(data=data, message="诊断已生成")


@router.post("/{project_id}/insights/{insight_id}/confirm", summary="确认项目学情诊断")
def confirm_api(
    project_id: str,
    insight_id: str,
    data: Optional[InsightConfirmRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    teacher_note = data.teacher_note if data else None
    try:
        result = service.confirm(db, current_user, project_id, insight_id, teacher_note)
    except AppException:
        raise
    return success_response(data=result, message="诊断已确认")
