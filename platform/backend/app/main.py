"""DataOS Platform — 统一平台层入口.

对标 DataWorks + DataLeap 架构：
- 统一入口，路由分发到各 API 模块
- 健康检查串联所有下游组件
- 预留中间件插槽 (认证/限流/审计)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, projects, datasources
from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal

# 确保所有模型被导入 (触发 table metadata 注册)
import app.models.user        # noqa: F401
import app.models.project     # noqa: F401
import app.models.datasource  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理."""
    # 启动时 — 自动建表 + 种子数据 (开发环境, 生产用 Alembic migration)
    from app.core.security import hash_password
    from app.models.user import User
    from sqlalchemy import select

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 创建默认管理员 (如果不存在)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            session.add(User(
                username="admin",
                email="admin@dataos.local",
                hashed_password=hash_password("admin123"),
                display_name="管理员",
                is_active=True,
                is_superuser=True,
            ))
            await session.commit()
            print("👤 默认管理员已创建 (admin / admin123)")

    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"   API Docs: http://0.0.0.0:8001/docs")
    yield
    # 关闭时
    await engine.dispose()
    print("👋 DataOS shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="DataOS — 企业级数据治理平台统一接入层",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS — 允许前端开发服务器
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 注册路由 ----
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(datasources.router)


@app.get("/")
async def root():
    """根路径 — 平台基本信息."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
