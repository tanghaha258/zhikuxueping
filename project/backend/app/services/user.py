"""
用户服务层（Service）

封装用户相关的业务逻辑：
- 注册时校验唯一性、加密密码
- 登录时校验凭证、管理失败计数
- 提供用户查询接口与 API 层 / Repository 层解耦
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate


def create_user(db: Session, user_data: UserCreate) -> User:
    """
    创建新用户。

    流程：
        1. 检查用户名和邮箱是否已存在
        2. 使用 bcrypt 加密密码
        3. 持久化用户记录

    Args:
        db: 数据库会话。
        user_data: 用户注册请求数据。

    Returns:
        已创建的 User 对象。

    Raises:
        AppException: 用户名或邮箱已存在（409）。
    """
    repo = UserRepository(db)

    # 检查唯一性
    if repo.get_by_username(user_data.username):
        raise AppException(code=40001, message="用户名已被注册", status_code=409)

    if repo.get_by_email(user_data.email):
        raise AppException(code=40001, message="邮箱已被注册", status_code=409)

    # 创建用户 ORM 对象
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        display_name=user_data.display_name,
        role=user_data.role,
        school_id=user_data.school_id,
        class_id=user_data.class_id,
    )

    return repo.create(user)


def authenticate_user(db: Session, username: str, password: str) -> User:
    """
    验证用户登录凭证。

    流程：
        1. 根据用户名查找用户
        2. 校验密码是否匹配
        3. 检查账号是否启用
        4. 成功后重置失败计数；失败则递增

    Args:
        db: 数据库会话。
        username: 用户名。
        password: 明文密码。

    Returns:
        通过认证的 User 对象。

    Raises:
        AppException: 用户不存在/密码错误（401），账号停用（403）。
    """
    repo = UserRepository(db)
    user = repo.get_by_username(username)

    if not user:
        raise AppException(code=40001, message="用户名或密码错误", status_code=401)

    if not user.is_active:
        raise AppException(code=40003, message="账号已被停用", status_code=403)

    if not verify_password(password, user.hashed_password):
        # 记录失败次数（可用于后续账户锁定策略）
        repo.update(user, {"failed_attempts": (user.failed_attempts or 0) + 1})
        raise AppException(code=40001, message="用户名或密码错误", status_code=401)

    # 登录成功，重置失败计数
    if user.failed_attempts > 0:
        repo.update(user, {"failed_attempts": 0})

    return user


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """
    按 ID 获取用户。

    Args:
        db: 数据库会话。
        user_id: 用户 UUID。

    Returns:
        User 对象，未找到返回 None。
    """
    repo = UserRepository(db)
    return repo.get_by_id(user_id)


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    按用户名获取用户。

    Args:
        db: 数据库会话。
        username: 用户名。

    Returns:
        User 对象，未找到返回 None。
    """
    repo = UserRepository(db)
    return repo.get_by_username(username)
