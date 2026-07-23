"""
全局配置模块

使用 pydantic-settings 从环境变量和 .env 文件加载配置。
支持开发（SQLite）和生产（PostgreSQL）两种模式。
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional


# 计算项目后端根目录（config.py 位于 app/core/，往上3层为 backend 根目录）
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用全局配置"""

    # 应用基本信息
    APP_NAME: str = "初中跨学科教学评一体化平台"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    TESTING: bool = False

    # 数据库
    DATABASE_URL: str = "sqlite:///./data/platform.db"

    # JWT 认证
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 分钟（符合 API 规范）

    # 前端地址（CORS）
    FRONTEND_URL: str = "http://localhost:1800"

    # AI 服务（可选）
    AI_API_BASE_URL: Optional[str] = None
    AI_API_KEY: Optional[str] = None
    AI_MODEL: str = "deepseek-chat"

    # 文件上传
    UPLOAD_DIR: str = str(_BACKEND_ROOT / "uploads")
    MEDIA_SESSION_COOKIE: str = "platform_media_session"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_IMAGE_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_relative_sqlite_url(cls, value: str) -> str:
        prefix = "sqlite:///"
        if not value.startswith(prefix) or value.startswith("sqlite:////"):
            return value

        database_path = value.removeprefix(prefix)
        if database_path == ":memory:" or Path(database_path).is_absolute():
            return value

        return f"{prefix}{(_BACKEND_ROOT / database_path).resolve().as_posix()}"


# 全局单例
settings = Settings()
