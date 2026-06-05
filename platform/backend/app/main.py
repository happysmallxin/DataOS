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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理."""
    # 启动时
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"   API Docs: http://0.0.0.0:8000/docs")
    yield
    # 关闭时
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
