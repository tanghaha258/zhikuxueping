from fastapi import APIRouter, Depends, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.exceptions import AppException
from app.core.response import success_response
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.db.session import get_db
from app.models.user import User
from app.modules.identity import service
from app.schemas.user import (
    LoginResponse,
    PasswordChange,
    ProfileUpdate,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.shared.audit import log_action


router = APIRouter(prefix="/auth", tags=["认证管理"])


def _authenticated_response(data, message: str) -> JSONResponse:
    response = JSONResponse(content=jsonable_encoder(success_response(data=data, message=message)))
    response.set_cookie(
        key=settings.MEDIA_SESSION_COOKIE,
        value=data.access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/api/v1/upload/files",
    )
    return response


@router.post("/register", summary="注册新用户")
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if not settings.TESTING:
        raise AppException(code=40301, message="公开注册已关闭", status_code=403)
    user = service.register_test_user(db, user_data)
    return success_response(data=UserResponse.model_validate(user), message="注册成功")


@router.post("/login", summary="用户登录")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = service.authenticate_user(db, login_data.username, login_data.password)
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    log_action(db, action="用户登录", user_id=user.id, username=user.username)
    return _authenticated_response(
        data=LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        ),
        message="登录成功",
    )


@router.post("/logout", summary="退出登录")
def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.delete_cookie(key=settings.MEDIA_SESSION_COOKIE, path="/api/v1/upload/files")
    log_action(db, action="退出登录", user_id=current_user.id, username=current_user.username)
    return success_response(message="已退出登录")


@router.post("/refresh", summary="刷新访问令牌")
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    payload = verify_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise AppException(code=40002, message="刷新令牌无效或已过期", status_code=401)
    user_id = payload.get("sub")
    user = service.get_user_by_id(db, user_id) if user_id else None
    if not user:
        raise AppException(code=40001, message="用户不存在", status_code=401)
    return _authenticated_response(
        data=TokenResponse(
            access_token=create_access_token(data={"sub": user.id}),
            refresh_token=create_refresh_token(data={"sub": user.id}),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
        message="令牌刷新成功",
    )


@router.get("/me", summary="获取当前用户信息")
def get_me(current_user: User = Depends(get_current_user)):
    return success_response(data=UserResponse.model_validate(current_user))


@router.put("/me", summary="更新个人资料")
def update_profile(data: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = service.update_profile(db, current_user, data)
    return success_response(data=UserResponse.model_validate(user), message="更新成功")


@router.put("/me/password", summary="修改密码")
def change_password(data: PasswordChange, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.change_password(db, current_user, data)
    return success_response(message="密码修改成功")
