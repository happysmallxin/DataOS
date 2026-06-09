"""数据标准 API — 字段标准 + 字段映射 + 编码字典 CRUD."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.data_standard import DataStandard, FieldMapping, CodeDictionary

router = APIRouter(tags=["DataStandards"])

# ---- Schemas ----

class StandardCreate(BaseModel):
    code: str; name: str; description: Optional[str] = None
    data_type: str = "VARCHAR"; length: Optional[int] = None
    category: str = "dimension"; domain_id: Optional[int] = None
    scope: str = "project"; quality_rule: Optional[str] = None  # project/global

class MappingCreate(BaseModel):
    datasource_id: Optional[int] = None; source_table: str; source_field: str
    standard_id: int; transform_rule: str = "direct"

class DictCreate(BaseModel):
    name: str; code: str; source_value: str; standard_value: str

# ---- 字段标准 CRUD ----

@router.get("/api/v1/projects/{project_id}/standards")
async def list_standards(project_id: int, category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    # 项目标准 + 公司级全局标准
    stmt = select(DataStandard).where(
        (DataStandard.project_id == project_id) | (DataStandard.scope == "global")
    )
    if category: stmt = stmt.where(DataStandard.category == category)
    result = await db.execute(stmt.order_by(DataStandard.scope.desc(), DataStandard.category, DataStandard.code))
    return result.scalars().all()

@router.post("/api/v1/projects/{project_id}/standards", status_code=201)
async def create_standard(project_id: int, req: StandardCreate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    e = await db.execute(select(DataStandard).where(DataStandard.project_id == project_id, DataStandard.code == req.code))
    if e.scalar_one_or_none(): raise HTTPException(409, f"标准字段 '{req.code}' 已存在")
    s = DataStandard(project_id=project_id, **req.model_dump())
    db.add(s); await db.flush(); await db.refresh(s); await db.commit()
    return {"id": s.id, "code": s.code, "name": s.name}

@router.delete("/api/v1/projects/{project_id}/standards/{sid}")
async def delete_standard(project_id: int, sid: int,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    s = await db.get(DataStandard, sid)
    if not s: raise HTTPException(404, "标准字段不存在")
    await db.delete(s); await db.commit()
    return {"message": "删除成功"}

# ---- 字段映射 CRUD ----

@router.get("/api/v1/projects/{project_id}/mappings")
async def list_mappings(project_id: int, datasource_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(FieldMapping).where(FieldMapping.project_id == project_id)
    if datasource_id: stmt = stmt.where(FieldMapping.datasource_id == datasource_id)
    result = await db.execute(stmt.order_by(FieldMapping.source_table, FieldMapping.source_field))
    return result.scalars().all()

@router.post("/api/v1/projects/{project_id}/mappings", status_code=201)
async def create_mapping(project_id: int, req: MappingCreate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    e = await db.execute(select(FieldMapping).where(
        FieldMapping.project_id == project_id, FieldMapping.source_table == req.source_table,
        FieldMapping.source_field == req.source_field))
    if e.scalar_one_or_none(): raise HTTPException(409, "该字段已有映射")
    m = FieldMapping(project_id=project_id, **req.model_dump())
    db.add(m); await db.flush(); await db.refresh(m); await db.commit()
    return {"id": m.id, "source_field": m.source_field, "standard_id": m.standard_id}

@router.post("/api/v1/projects/{project_id}/mappings/auto")
async def auto_map_fields(project_id: int, datasource_id: int,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """自动映射: 源表字段名与标准字段code模糊匹配."""
    from app.core.config import settings
    from sqlalchemy import create_engine as sync_ce, inspect as sa_inspect
    from app.models.datasource import DataSource as DS

    ds = await db.get(DS, datasource_id)
    if not ds: raise HTTPException(404, "数据源不存在")

    standards = (await db.execute(select(DataStandard).where(DataStandard.project_id == project_id))).scalars().all()
    if not standards: raise HTTPException(400, "项目无数据标准, 请先创建标准字段")

    try:
        engine = sync_ce(settings.PG_GOLD_URL, connect_args={"connect_timeout": 5})
        inspector = sa_inspect(engine)
        tables = inspector.get_table_names()
        mappings_created = 0
        for table in tables:
            if table.startswith("_"): continue
            for col in inspector.get_columns(table):
                col_name = col["name"].lower()
                for std in standards:
                    if std.code.lower() == col_name or std.name.lower() == col_name or col_name in std.code.lower():
                        e = await db.execute(select(FieldMapping).where(
                            FieldMapping.project_id == project_id, FieldMapping.source_table == table,
                            FieldMapping.source_field == col["name"]))
                        if not e.scalar_one_or_none():
                            db.add(FieldMapping(project_id=project_id, datasource_id=datasource_id,
                                source_table=table, source_field=col["name"], standard_id=std.id))
                            mappings_created += 1
        engine.dispose()
        await db.commit()
        return {"mappings_created": mappings_created, "total_standards": len(standards)}
    except Exception as e:
        raise HTTPException(500, f"自动映射失败: {e}")

# ---- 编码字典 CRUD ----

@router.get("/api/v1/projects/{project_id}/code-dicts")
async def list_code_dicts(project_id: int,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(CodeDictionary).where(CodeDictionary.project_id == project_id).order_by(CodeDictionary.code, CodeDictionary.sort_order))
    return result.scalars().all()

@router.post("/api/v1/projects/{project_id}/code-dicts", status_code=201)
async def create_code_dict(project_id: int, req: DictCreate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    d = CodeDictionary(project_id=project_id, **req.model_dump())
    db.add(d); await db.flush(); await db.refresh(d); await db.commit()
    return {"id": d.id, "code": d.code, "source_value": d.source_value, "standard_value": d.standard_value}
