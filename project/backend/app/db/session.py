"""
数据库会话模块

创建同步 SQLAlchemy 引擎和会话工厂，提供 get_db 依赖注入。
开发环境使用 SQLite，生产环境可切换为 PostgreSQL。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# ── 数据库引擎 ──────────────────────────────────────────────────
# SQLite 需要 check_same_thread=False 以支持 FastAPI 多线程
_connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=_connect_args,
)

# ── 会话工厂 ────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    FastAPI 依赖注入函数，提供数据库会话。

    用法：
        @router.get("/users")
        def list_users(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
