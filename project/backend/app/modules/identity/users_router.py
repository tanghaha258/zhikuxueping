from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.identity import service
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.shared.audit import log_action


router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", summary="用户列表")
def list_users_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str = Query("", description="搜索用户名/姓名"),
    role: str = Query("", description="筛选角色"),
    is_active: bool | None = Query(None, description="筛选状态"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    users = service.search_users(
        db, current_user, keyword=keyword, role=role, is_active=is_active, skip=skip, limit=limit
    )
    total = service.count_users(db, current_user, keyword=keyword, role=role, is_active=is_active)
    return success_response(
        data={
            "items": [UserResponse.model_validate(user) for user in users],
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit,
        }
    )


@router.post("", summary="创建用户")
def create_user_api(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    user = service.create_user(db, current_user, data)
    log_action(
        db,
        action="创建用户",
        user_id=current_user.id,
        username=current_user.username,
        resource="user",
        resource_id=user.id,
        detail=f"创建用户 {user.username}",
    )
    return success_response(data=UserResponse.model_validate(user), message="创建成功")


@router.get("/{user_id}", summary="用户详情")
def get_user_api(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    return success_response(data=UserResponse.model_validate(service.get_managed_user(db, current_user, user_id)))


@router.patch("/{user_id}", summary="更新用户")
def update_user_api(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    if not data.model_dump(exclude_unset=True):
        raise AppException(code=40001, message="未提供更新字段", status_code=400)
    user = service.update_managed_user(db, current_user, user_id, data)
    log_action(
        db,
        action="更新用户",
        user_id=current_user.id,
        username=current_user.username,
        resource="user",
        resource_id=user.id,
        detail=f"更新用户 {user.username}",
    )
    return success_response(data=UserResponse.model_validate(user), message="更新成功")


@router.patch("/{user_id}/status", summary="启用/停用用户")
def toggle_user_status(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    user = service.toggle_user_status(db, current_user, user_id)
    action_name = "启用用户" if user.is_active else "停用用户"
    log_action(
        db,
        action=action_name,
        user_id=current_user.id,
        username=current_user.username,
        resource="user",
        resource_id=user.id,
    )
    return success_response(data=UserResponse.model_validate(user), message=action_name + "成功")
