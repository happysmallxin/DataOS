"""数据建模 API — 数据域 + 业务过程 CRUD (对齐 Dataphin OneData)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, GLOBAL_ADMIN_ROLES, get_user_global_roles
from app.core.database import get_db
from app.models.user import User
from app.models.data_domain import DataDomain, BusinessProcess
from app.models.audit_log import AuditLog

router = APIRouter(tags=["DataModeling"])


# ---- Pydantic schemas ----

class DomainCreate(BaseModel):
    name: str = Field(..., max_length=128)
    display_name: str = Field(..., max_length=256)
    parent_id: Optional[int] = None
    description: Optional[str] = None
    sort_order: int = 0


class DomainUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class DomainResponse(BaseModel):
    id: int; project_id: int; parent_id: Optional[int] = None
    name: str; display_name: str; description: Optional[str] = None
    sort_order: int; created_at: str; updated_at: str
    children: list["DomainResponse"] = []
    model_config = {"from_attributes": True}


class ProcessCreate(BaseModel):
    name: str = Field(..., max_length=128)
    display_name: str = Field(..., max_length=256)
    description: Optional[str] = None
    source_tables: Optional[list[str]] = None
    target_tables: Optional[list[str]] = None
    table_type: str = "DWD"
    schedule_cron: Optional[str] = None


class ProcessUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    source_tables: Optional[list[str]] = None
    target_tables: Optional[list[str]] = None
    table_type: Optional[str] = None
    schedule_cron: Optional[str] = None


class ProcessResponse(BaseModel):
    id: int; project_id: int; domain_id: int
    name: str; display_name: str; description: Optional[str] = None
    source_tables: Optional[list] = None; target_tables: Optional[list] = None
    table_type: str; schedule_cron: Optional[str] = None
    created_at: str; updated_at: str
    model_config = {"from_attributes": True}


# ---- 数据域 CRUD ----

@router.post("/api/v1/projects/{project_id}/domains", status_code=201)
async def create_domain(
    project_id: int, req: DomainCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建数据域."""
    existing = await db.execute(
        select(DataDomain).where(DataDomain.project_id == project_id, DataDomain.name == req.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"数据域 '{req.name}' 已存在")

    d = DataDomain(project_id=project_id, **req.model_dump())
    db.add(d)
    await db.flush(); await db.refresh(d)
    await db.commit()
    return {"id": d.id, "name": d.name, "display_name": d.display_name}


@router.get("/api/v1/projects/{project_id}/domains")
async def list_domains(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """数据域列表 (树形结构)."""
    result = await db.execute(
        select(DataDomain).where(DataDomain.project_id == project_id).order_by(DataDomain.sort_order, DataDomain.id)
    )
    domains = result.scalars().all()

    # 构建树形结构
    domain_map = {}
    roots = []
    for d in domains:
        node = {"id": d.id, "project_id": d.project_id, "parent_id": d.parent_id,
                "name": d.name, "display_name": d.display_name, "description": d.description,
                "sort_order": d.sort_order, "created_at": str(d.created_at), "updated_at": str(d.updated_at), "children": []}
        domain_map[d.id] = node
    for d in domains:
        node = domain_map[d.id]
        if d.parent_id and d.parent_id in domain_map:
            domain_map[d.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


@router.put("/api/v1/projects/{project_id}/domains/{domain_id}")
async def update_domain(
    project_id: int, domain_id: int, req: DomainUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    d = await db.get(DataDomain, domain_id)
    if not d: raise HTTPException(status_code=404, detail="数据域不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    await db.commit()
    return {"message": "更新成功"}


@router.delete("/api/v1/projects/{project_id}/domains/{domain_id}")
async def delete_domain(
    project_id: int, domain_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    d = await db.get(DataDomain, domain_id)
    if not d: raise HTTPException(status_code=404, detail="数据域不存在")
    # 检查子域
    children = await db.execute(select(func.count()).select_from(DataDomain).where(DataDomain.parent_id == domain_id))
    if children.scalar() > 0: raise HTTPException(status_code=400, detail="存在子域, 请先删除子域")
    # 检查业务过程
    procs = await db.execute(select(func.count()).select_from(BusinessProcess).where(BusinessProcess.domain_id == domain_id))
    if procs.scalar() > 0: raise HTTPException(status_code=400, detail="存在业务过程, 请先删除")
    await db.delete(d); await db.commit()
    return {"message": "删除成功"}


# ---- 业务过程 CRUD ----

@router.post("/api/v1/projects/{project_id}/domains/{domain_id}/processes", status_code=201)
async def create_process(
    project_id: int, domain_id: int, req: ProcessCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    domain = await db.get(DataDomain, domain_id)
    if not domain: raise HTTPException(status_code=404, detail="数据域不存在")
    existing = await db.execute(
        select(BusinessProcess).where(BusinessProcess.project_id == project_id, BusinessProcess.name == req.name)
    )
    if existing.scalar_one_or_none(): raise HTTPException(status_code=409, detail=f"业务过程 '{req.name}' 已存在")
    bp = BusinessProcess(project_id=project_id, domain_id=domain_id, **req.model_dump())
    db.add(bp); await db.flush(); await db.refresh(bp)
    await db.commit()
    return {"id": bp.id, "name": bp.name, "display_name": bp.display_name, "table_type": bp.table_type}


@router.get("/api/v1/projects/{project_id}/processes")
async def list_processes(
    project_id: int,
    domain_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(BusinessProcess).where(BusinessProcess.project_id == project_id)
    if domain_id: stmt = stmt.where(BusinessProcess.domain_id == domain_id)
    stmt = stmt.order_by(BusinessProcess.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/api/v1/projects/{project_id}/processes/{process_id}")
async def update_process(
    project_id: int, process_id: int, req: ProcessUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bp = await db.get(BusinessProcess, process_id)
    if not bp: raise HTTPException(status_code=404, detail="业务过程不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(bp, k, v)
    await db.commit()
    return {"message": "更新成功"}


@router.delete("/api/v1/projects/{project_id}/processes/{process_id}")
async def delete_process(
    project_id: int, process_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bp = await db.get(BusinessProcess, process_id)
    if not bp: raise HTTPException(status_code=404, detail="业务过程不存在")
    await db.delete(bp); await db.commit()
    return {"message": "删除成功"}
