"""
API 依赖项模块

提供常用的 FastAPI 依赖注入函数，如获取当前认证用户。
"""

from typing import Optional

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import verify_token
from app.db.session import get_db
from app.models.user import User
from app.modules.identity.service import get_user_by_id

# Bearer token 安全方案
security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    从请求头 Authorization: Bearer <token> 中解析当前用户。

    Raises:
        AppException: token 无效/过期或用户不存在时抛出 401。
    """
    if credentials is None:
        raise AppException(
            code=40002,
            message="not authenticated",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    payload = verify_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise AppException(
            code=40002,
            message="token expired or invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user_id = payload.get("sub")
    if not user_id:
        raise AppException(
            code=40002,
            message="invalid token payload",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise AppException(
            code=40001,
            message="user not found",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise AppException(
            code=40003,
            message="account is disabled",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user


def get_current_media_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Authenticate media downloads without enabling cookie auth for write APIs."""
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    if not token:
        token = request.cookies.get(settings.MEDIA_SESSION_COOKIE, "")

    if not token:
        raise AppException(
            code=40002,
            message="not authenticated",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    payload = verify_token(token)
    if payload is None or payload.get("type") != "access":
        raise AppException(
            code=40002,
            message="token expired or invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user_id = payload.get("sub")
    user = get_user_by_id(db, user_id) if user_id else None
    if not user:
        raise AppException(
            code=40001,
            message="user not found",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise AppException(
            code=40003,
            message="account is disabled",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user


def _get_role_value(role) -> str:
    """安全获取角色字符串值，兼容 enum 和 str 类型"""
    if isinstance(role, str):
        return role
    if hasattr(role, 'value'):
        return role.value
    return str(role)


def require_roles(roles: list[str]):
    """角色校验依赖工厂 — 返回一个 FastAPI Depends 可用的依赖。

    用法:
        @router.get("/something")
        def endpoint(current_user: User = Depends(require_roles(["admin", "school_admin"]))):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        role_val = _get_role_value(current_user.role)
        if role_val not in roles:
            raise AppException(
                code=40301,
                message="权限不足",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return current_user
    return role_checker
