"""
FastAPI 应用入口

创建并配置 FastAPI 实例，包括：
- CORS 中间件（允许前端跨域访问）
- 全局路由注册
- 健康检查端点
- 全局异常处理器（将 AppException 转为统一响应格式）
- 启动时自动创建数据库表（仅开发环境自动建表）
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.response import error_response
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时执行检查。
    
    数据库迁移由 Alembic 管理:
      cd project/backend && python -m alembic upgrade head
    """
    yield


def create_app() -> FastAPI:
    """构造并返回 FastAPI 应用实例。"""
    app = FastAPI(
        lifespan=lifespan,
        title=f"{settings.APP_NAME} API",
        description="面向初中跨学科主题学习的 AI 智能平台后端服务",
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        contact={"name": "NZSK 科技"},
    )

    # ── CORS 中间件 ─────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.FRONTEND_URL,
            "http://localhost:1800",
            "http://localhost:1801",
            "http://localhost:1802",
            "http://localhost:5173",
            "http://127.0.0.1:1800",
            "http://127.0.0.1:1801",
            "http://127.0.0.1:1802",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 静态文件挂载（上传目录） ───────────────────────────────
    # ── 注册路由 ────────────────────────────────────────────────
    app.include_router(api_router)

    # ── 健康检查 ────────────────────────────────────────────────
    @app.get("/api/v1/health", tags=["系统"], summary="健康检查")
    async def health_check():
        return {
            "code": 0,
            "message": "success",
            "data": {"status": "ok", "version": settings.APP_VERSION},
        }

    # ── 全局异常处理器 ──────────────────────────────────────────
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(code=exc.code, message=exc.message),
        )

    return app


# 全局应用实例（uvicorn 直接引用此对象）
app = create_app()
