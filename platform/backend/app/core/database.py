"""数据库连接管理 — SQLAlchemy 异步 + 同步引擎."""

from sqlalchemy import create_engine as sync_create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# 异步引擎 (FastAPI 请求用)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=False,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False,
)

# 同步引擎 + Session (Worker 线程用)
_sync_url = settings.DATABASE_URL.replace("mysql+aiomysql://", "mysql+pymysql://")
sync_engine = sync_create_engine(_sync_url, pool_size=5, max_overflow=5, pool_recycle=3600)
SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入: 获取数据库 Session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
