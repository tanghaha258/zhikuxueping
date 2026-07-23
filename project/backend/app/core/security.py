"""
安全工具模块

提供 JWT 令牌创建/验证、密码哈希/校验等安全功能。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
import bcrypt as _bcrypt

from app.core.config import settings

# ── JWT 算法 ────────────────────────────────────────────────────
ALGORITHM = "HS256"


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建访问令牌（Access Token）。

    Args:
        data: 需包含 "sub" 字段（用户 ID）。
        expires_delta: 过期时间差，默认使用配置值。

    Returns:
        编码后的 JWT 字符串。
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建刷新令牌（Refresh Token），默认 7 天有效。

    Args:
        data: 需包含 "sub" 字段（用户 ID）。
        expires_delta: 过期时间差。

    Returns:
        编码后的 JWT 字符串。
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=7)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict[str, Any]]:
    """
    验证并解码 JWT 令牌。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 payload 字典，若无效则返回 None。
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def hash_password(password: str) -> str:
    """使用 bcrypt 对明文密码进行哈希。"""
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希值是否匹配。"""
    return _bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
