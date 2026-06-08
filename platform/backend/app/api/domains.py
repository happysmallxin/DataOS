"""数据建模 API — 数据域 + 业务过程 CRUD + Gold表检查 + DDL生成 (对齐 Dataphin OneData)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, GLOBAL_ADMIN_ROLES, get_user_global_roles
from app.core.config import settings
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
    view_sql: Optional[str] = None          # 自定义 SQL 视图定义
    exclude_columns: Optional[list[str]] = None  # 额外排除的列
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


# ---- Gold 表结构检查 ----

@router.get("/api/v1/projects/{project_id}/gold-tables")
async def list_gold_tables(
    project_id: int,
    current_user: User = Depends(get_current_user),
):
    """获取 PG Gold 中清洗后的表列表."""
    from sqlalchemy import create_engine, inspect, text
    try:
        engine = create_engine(settings.PG_GOLD_URL, connect_args={"connect_timeout": 5})
        inspector = inspect(engine)
        tables = [t for t in inspector.get_table_names() if not t.startswith("_") and not t.startswith("directus_")]
        engine.dispose()
        return tables
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无法连接 Gold 数据库: {e}")


@router.get("/api/v1/projects/{project_id}/gold-tables/{table_name}/columns")
async def get_gold_table_columns(
    project_id: int, table_name: str,
    current_user: User = Depends(get_current_user),
):
    """获取 Gold 表的列定义."""
    from sqlalchemy import create_engine, inspect
    try:
        engine = create_engine(settings.PG_GOLD_URL, connect_args={"connect_timeout": 5})
        inspector = inspect(engine)
        cols = [{"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable", True),
                 "default": str(c.get("default")) if c.get("default") else None}
                for c in inspector.get_columns(table_name)]
        engine.dispose()
        return {"table": table_name, "columns": cols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无法读取表结构: {e}")


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
    auto_create_table: bool = Query(True),  # 是否自动创建目标表
):
    domain = await db.get(DataDomain, domain_id)
    if not domain: raise HTTPException(status_code=404, detail="数据域不存在")
    existing = await db.execute(
        select(BusinessProcess).where(BusinessProcess.project_id == project_id, BusinessProcess.name == req.name)
    )
    if existing.scalar_one_or_none(): raise HTTPException(status_code=409, detail=f"业务过程 '{req.name}' 已存在")

    bp = BusinessProcess(project_id=project_id, domain_id=domain_id, **req.model_dump())
    db.add(bp); await db.flush(); await db.refresh(bp)

    result = {"id": bp.id, "name": bp.name, "display_name": bp.display_name, "table_type": bp.table_type, "ddl": None, "pipeline_id": None}

    # 自动创建目标表/视图 + Pipeline
    if auto_create_table and req.source_tables and req.target_tables:
        from sqlalchemy import create_engine, inspect as sa_inspect, text
        try:
            engine = create_engine(settings.PG_GOLD_URL, connect_args={"connect_timeout": 5})
            inspector = sa_inspect(engine)

            source_table = req.source_tables[0]
            src_cols = inspector.get_columns(source_table)
            target_table = req.target_tables[0]

            # 排除敏感字段 + 用户指定排除
            excluded = {"hashed_password", "password", "secret", "token", "api_key", "is_superuser"}
            if req.exclude_columns:
                excluded.update(req.exclude_columns)

            # ---- 视图模式: view_sql 有值 ----
            if req.view_sql:
                view_name = target_table
                # 使用用户自定义 SQL 创建视图
                create_view_sql = f"CREATE OR REPLACE VIEW {view_name} AS {req.view_sql}"
                with engine.connect() as conn:
                    conn.execute(text(create_view_sql))
                    conn.commit()
                result["view_created"] = view_name
                result["view_sql"] = create_view_sql
                bp.view_sql = req.view_sql
                result["ddl"] = create_view_sql

            # ---- 表模式: 自动生成 DDL ----
            else:
                col_defs = []
                for c in src_cols:
                    if c["name"] in excluded:
                        continue
                    col_type = str(c["type"])
                    nullable = "" if c.get("nullable") is False else "NULL"
                    col_defs.append(f'  "{c["name"]}" {col_type} {nullable}')

                if not any("PRIMARY KEY" in d.upper() for d in col_defs) and any("id" in d.lower() for d in col_defs):
                    for i, d in enumerate(col_defs):
                        if d.strip().startswith('"id"'):
                            col_defs[i] = d.replace(" NULL", " NOT NULL") + " PRIMARY KEY"
                            break

                ddl = f'CREATE TABLE IF NOT EXISTS {target_table} (\n' + ",\n".join(col_defs) + "\n);"
                result["ddl"] = ddl
                with engine.connect() as conn:
                    conn.execute(text(ddl))
                    conn.commit()
                result["table_created"] = target_table

            engine.dispose()

            # 自动生成 Pipeline
            from app.models.pipeline import CleaningPipeline
            stages = [{"type": "standardize", "config": {"column": c["name"], "operation": "trim"}}
                      for c in src_cols if "char" in str(c["type"]).lower() or "text" in str(c["type"]).lower()
                      if c["name"] not in excluded][:3]

            pl = CleaningPipeline(
                project_id=project_id, name=f"{bp.name}_pipeline",
                description=f"自动生成: {source_table} -> {target_table}",
                source_table=source_table, target_table=target_table,
                stages=stages if stages else [{"type": "standardize", "config": {"column": "id", "operation": "trim"}}],
                created_by=current_user.id, status="draft",
            )
            db.add(pl)
            await db.flush()
            result["pipeline_id"] = pl.id
            result["pipeline_name"] = pl.name

        except Exception as e:
            result["ddl_error"] = str(e)

    await db.commit()
    return result


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


@router.post("/api/v1/projects/{project_id}/processes/{process_id}/create-view")
async def create_process_view(
    project_id: int, process_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    view_sql: Optional[str] = None,
):
    """为业务过程创建/刷新 PG 视图."""
    bp = await db.get(BusinessProcess, process_id)
    if not bp: raise HTTPException(status_code=404, detail="业务过程不存在")

    sql = view_sql or bp.view_sql
    if not sql and bp.source_tables:
        # 自动生成排除敏感字段的视图
        from sqlalchemy import create_engine, inspect
        excluded = {"hashed_password", "password", "secret", "token", "api_key", "is_superuser"}
        engine = create_engine(settings.PG_GOLD_URL, connect_args={"connect_timeout": 5})
        inspector = inspect(engine)
        src = bp.source_tables[0]
        cols = [c["name"] for c in inspector.get_columns(src) if c["name"] not in excluded]
        engine.dispose()
        target = bp.target_tables[0] if bp.target_tables else f"v_{bp.name}"
        sql = f"SELECT {', '.join(cols)} FROM {src}"

    if not sql:
        raise HTTPException(status_code=400, detail="无可用 SQL, 请提供 view_sql 或 source_tables")

    view_name = bp.target_tables[0] if bp.target_tables else f"v_{bp.name}"
    create_sql = f"CREATE OR REPLACE VIEW {view_name} AS {sql}"

    from sqlalchemy import create_engine as sync_ce, text
    engine = sync_ce(settings.PG_GOLD_URL, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        conn.execute(text(create_sql))
        conn.commit()
    engine.dispose()

    bp.view_sql = sql
    await db.commit()
    return {"view": view_name, "sql": create_sql}


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
