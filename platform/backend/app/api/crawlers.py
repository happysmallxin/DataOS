"""爬虫任务管理 API — P2: 项目级爬虫 CRUD.

对标 DataWorks 数据采集 + Crawlab 执行引擎.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    require_project_role,
    GLOBAL_ADMIN_ROLES,
    get_user_global_roles,
)
from app.core.database import get_db
from app.models.user import User
from app.models.crawler import Crawler
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/api/v1/crawlers", tags=["Crawlers"])


# ---- Pydantic schemas (inline to keep module self-contained) ----
from pydantic import BaseModel, Field
from typing import Optional


class CrawlerCreate(BaseModel):
    project_id: int
    name: str = Field(..., max_length=128)
    target_url: Optional[str] = None
    framework: str = Field(default="Scrapy")
    config: dict = Field(default_factory=dict)
    description: Optional[str] = None


class CrawlerUpdate(BaseModel):
    name: Optional[str] = None
    target_url: Optional[str] = None
    framework: Optional[str] = None
    config: Optional[dict] = None
    description: Optional[str] = None
    status: Optional[str] = None


class CrawlerResponse(BaseModel):
    id: int
    project_id: int
    name: str
    target_url: Optional[str] = None
    framework: str
    config: dict
    description: Optional[str] = None
    status: str
    crawlab_task_id: Optional[str] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    total_runs: int
    total_rows_collected: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CrawlerListResponse(BaseModel):
    items: list[CrawlerResponse]
    total: int


# ============================================================
# CRUD
# ============================================================

@router.post("", response_model=CrawlerResponse, status_code=status.HTTP_201_CREATED)
async def create_crawler(
    req: CrawlerCreate,
    current_user: User = Depends(get_current_user),
    _ = Depends(require_project_role("project_owner", "editor", "developer")),
    db: AsyncSession = Depends(get_db),
):
    """创建爬虫任务 — 归属到项目. 需要 project_owner/editor/developer 角色."""
    existing = await db.execute(
        select(Crawler).where(
            Crawler.project_id == req.project_id,
            Crawler.name == req.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"项目内已存在同名爬虫任务 '{req.name}'")

    crawler = Crawler(
        project_id=req.project_id,
        name=req.name,
        target_url=req.target_url,
        framework=req.framework,
        config=req.config,
        description=req.description,
        created_by=current_user.id,
    )
    db.add(crawler)
    await db.flush()
    await db.refresh(crawler)

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=req.project_id,
        resource="crawler",
        action="create",
        target_id=crawler.id,
        target_name=crawler.name,
        detail={"framework": req.framework, "target": req.target_url},
    ))
    await db.commit()
    return crawler


@router.get("", response_model=CrawlerListResponse)
async def list_crawlers(
    project_id: int = Query(..., description="项目 ID (必填, 项目隔离)"),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目下的爬虫任务列表 — 按项目隔离."""
    stmt = select(Crawler).where(Crawler.project_id == project_id)
    if status:
        stmt = stmt.where(Crawler.status == status)
    stmt = stmt.order_by(Crawler.updated_at.desc())
    result = await db.execute(stmt)
    items = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(Crawler).where(Crawler.project_id == project_id)
    )
    total = count_result.scalar() or 0

    return CrawlerListResponse(items=list(items), total=total)


@router.get("/{crawler_id}", response_model=CrawlerResponse)
async def get_crawler(
    crawler_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个爬虫任务详情."""
    c = await db.get(Crawler, crawler_id)
    if not c:
        raise HTTPException(status_code=404, detail="爬虫任务不存在")
    return c


@router.put("/{crawler_id}", response_model=CrawlerResponse)
async def update_crawler(
    crawler_id: int,
    req: CrawlerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新爬虫任务配置."""
    c = await db.get(Crawler, crawler_id)
    if not c:
        raise HTTPException(status_code=404, detail="爬虫任务不存在")

    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    if not is_admin:
        from app.models.project_member import ProjectMember as PM
        member = await db.execute(
            select(PM).where(PM.project_id == c.project_id, PM.user_id == current_user.id)
        )
        if not member.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="你不是该项目成员")

    if req.name is not None:
        c.name = req.name
    if req.target_url is not None:
        c.target_url = req.target_url
    if req.framework is not None:
        c.framework = req.framework
    if req.config is not None:
        c.config = req.config
    if req.description is not None:
        c.description = req.description
    if req.status is not None:
        c.status = req.status

    await db.commit()
    await db.refresh(c)
    return c


@router.delete("/{crawler_id}")
async def delete_crawler(
    crawler_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除爬虫任务 — 需要 project_owner 角色."""
    c = await db.get(Crawler, crawler_id)
    if not c:
        raise HTTPException(status_code=404, detail="爬虫任务不存在")

    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    if not is_admin:
        from app.models.project_member import ProjectMember as PM
        from app.models.role import Role
        member = await db.execute(
            select(PM, Role).join(Role, Role.id == PM.role_id).where(
                PM.project_id == c.project_id, PM.user_id == current_user.id
            )
        )
        row = member.one_or_none()
        if not row:
            raise HTTPException(status_code=403, detail="你不是该项目成员")
        _, role = row
        if role.name not in ("project_owner",):
            raise HTTPException(status_code=403, detail="需要 project_owner 角色")

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=c.project_id,
        resource="crawler",
        action="delete",
        target_id=crawler_id,
        target_name=c.name,
    ))
    await db.delete(c)
    await db.commit()
    return {"message": f"爬虫任务 '{c.name}' 已删除"}


# ============================================================
# 执行控制 (P2: 通过 Crawlab API 代理)
# ============================================================

@router.post("/{crawler_id}/start")
async def start_crawler(
    crawler_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """启动爬虫任务 — 代理到 Crawlab."""
    c = await db.get(Crawler, crawler_id)
    if not c:
        raise HTTPException(status_code=404, detail="爬虫任务不存在")

    # 权限校验: 需要 crawler:start 权限
    from app.api.deps import get_user_permissions
    perms = await get_user_permissions(current_user.id, db, c.project_id)
    if "crawler:start" not in perms:
        raise HTTPException(status_code=403, detail="需要权限: crawler:start")

    # TODO P2: 调用 Crawlab API 启动任务
    # from app.services.component_proxy import crawlab
    # await crawlab.post(f"/api/spiders/{c.crawlab_task_id}/run")

    c.status = "running"
    c.last_run_at = datetime.now(timezone.utc)
    c.total_runs += 1
    await db.commit()

    return {"message": f"爬虫任务 '{c.name}' 已启动", "crawler_id": crawler_id}


@router.post("/{crawler_id}/stop")
async def stop_crawler(
    crawler_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """停止爬虫任务."""
    c = await db.get(Crawler, crawler_id)
    if not c:
        raise HTTPException(status_code=404, detail="爬虫任务不存在")

    from app.api.deps import get_user_permissions
    perms = await get_user_permissions(current_user.id, db, c.project_id)
    if "crawler:stop" not in perms:
        raise HTTPException(status_code=403, detail="需要权限: crawler:stop")

    c.status = "stopped"
    c.last_status = "stopped_by_user"
    await db.commit()

    return {"message": f"爬虫任务 '{c.name}' 已停止", "crawler_id": crawler_id}
