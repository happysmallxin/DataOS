"""数据建模 API — 模型表 + 模型字段 CRUD (对齐 MES 文档 §3.3)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.model_table import ModelTable, ModelField

router = APIRouter(tags=["DataModeling"])

# ---- Schemas ----

class ModelTableCreate(BaseModel):
    code: str; name: str; table_type: str = "DIM"; domain_id: int
    process_id: Optional[int] = None; description: Optional[str] = None
    primary_key_field: Optional[str] = None
    source_gold_table: Optional[str] = None; target_gold_table: Optional[str] = None

class FieldCreate(BaseModel):
    code: str; name: str; data_type: str = "VARCHAR"; length: Optional[int] = None
    description: Optional[str] = None; is_primary_key: bool = False
    is_foreign_key: bool = False; ref_table: Optional[str] = None; ref_field: Optional[str] = None
    source_field: Optional[str] = None; category: str = "dimension"
    quality_rule: Optional[str] = None; sort_order: int = 0

# ---- 模型表 CRUD ----

@router.get("/api/v1/projects/{project_id}/model-tables")
async def list_models(project_id: int, domain_id: Optional[int] = Query(None), table_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(ModelTable).where(ModelTable.project_id == project_id)
    if domain_id: stmt = stmt.where(ModelTable.domain_id == domain_id)
    if table_type: stmt = stmt.where(ModelTable.table_type == table_type)
    result = await db.execute(stmt.order_by(ModelTable.table_type, ModelTable.code))
    return result.scalars().all()

@router.post("/api/v1/projects/{project_id}/model-tables", status_code=201)
async def create_model(project_id: int, req: ModelTableCreate,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    e = await db.execute(select(ModelTable).where(ModelTable.project_id == project_id, ModelTable.code == req.code))
    if e.scalar_one_or_none(): raise HTTPException(409, f"模型表 '{req.code}' 已存在")
    m = ModelTable(project_id=project_id, created_by=current_user.id, **req.model_dump())
    db.add(m); await db.flush(); await db.refresh(m); await db.commit()
    return {"id": m.id, "code": m.code, "name": m.name}

@router.put("/api/v1/projects/{project_id}/model-tables/{mid}")
async def update_model(project_id: int, mid: int, req: ModelTableCreate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    m = await db.get(ModelTable, mid)
    if not m: raise HTTPException(404, "模型表不存在")
    for k, v in req.model_dump(exclude_unset=True).items(): setattr(m, k, v)
    await db.commit(); return {"message": "已更新"}

@router.delete("/api/v1/projects/{project_id}/model-tables/{mid}")
async def delete_model(project_id: int, mid: int,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    m = await db.get(ModelTable, mid)
    if not m: raise HTTPException(404, "模型表不存在")
    await db.delete(m); await db.commit(); return {"message": "已删除"}

# DDL 生成
@router.post("/api/v1/projects/{project_id}/model-tables/{mid}/ddl")
async def generate_ddl(project_id: int, mid: int,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    m = await db.get(ModelTable, mid)
    if not m: raise HTTPException(404, "模型表不存在")
    fields = (await db.execute(select(ModelField).where(ModelField.model_table_id == mid).order_by(ModelField.sort_order))).scalars().all()
    if not fields: raise HTTPException(400, "模型表没有字段, 请先添加字段")

    cols = []
    for f in fields:
        col = f'  {f.code} {f.data_type}'
        if f.length: col += f"({f.length})"
        col += " NOT NULL" if not f.nullable else ""
        if f.is_primary_key: col += " PRIMARY KEY"
        cols.append(col)
    for f in fields:
        if f.is_foreign_key and f.ref_table and f.ref_field:
            cols.append(f"  FOREIGN KEY ({f.code}) REFERENCES {f.ref_table}({f.ref_field})")

    target = m.target_gold_table or m.code
    ddl = f"CREATE TABLE IF NOT EXISTS {target} (\n" + ",\n".join(cols) + "\n);"

    # 执行 DDL
    from app.core.config import settings
    from sqlalchemy import create_engine, text
    try:
        engine = create_engine(settings.PG_GOLD_URL, connect_args={"connect_timeout": 5})
        with engine.connect() as c: c.execute(text(ddl)); c.commit()
        engine.dispose()
        return {"ddl": ddl, "executed": True, "table": target}
    except Exception as e:
        return {"ddl": ddl, "executed": False, "error": str(e)}

# 从 Gold 表导入字段
@router.post("/api/v1/projects/{project_id}/model-tables/{mid}/import-fields")
async def import_fields(project_id: int, mid: int,
    source_table: str = Query(...),
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    from app.core.config import settings
    from sqlalchemy import create_engine, inspect
    try:
        engine = create_engine(settings.PG_GOLD_URL, connect_args={"connect_timeout": 5})
        inspector = inspect(engine)
        cols = inspector.get_columns(source_table)
        engine.dispose()
        count = 0
        for i, c in enumerate(cols):
            if c["name"] in ("_cleaned_at", "_archived_at", "_source_table"): continue
            e = await db.execute(select(ModelField).where(ModelField.model_table_id == mid, ModelField.code == c["name"]))
            if e.scalar_one_or_none(): continue
            db.add(ModelField(model_table_id=mid, code=c["name"], name=c["name"],
                data_type=str(c["type"]), nullable=c.get("nullable", True),
                source_field=c["name"], sort_order=i))
            count += 1
        await db.commit()
        return {"imported": count, "source": source_table}
    except Exception as e:
        raise HTTPException(500, f"导入失败: {e}")

# ---- 模型字段 CRUD ----

@router.get("/api/v1/model-tables/{mid}/fields")
async def list_fields(mid: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ModelField).where(ModelField.model_table_id == mid).order_by(ModelField.sort_order))
    return result.scalars().all()

@router.post("/api/v1/model-tables/{mid}/fields", status_code=201)
async def add_field(mid: int, req: FieldCreate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    f = ModelField(model_table_id=mid, **req.model_dump())
    db.add(f); await db.flush(); await db.refresh(f); await db.commit()
    return {"id": f.id, "code": f.code, "name": f.name}

@router.put("/api/v1/model-tables/{mid}/fields/{fid}")
async def update_field(mid: int, fid: int, req: FieldCreate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    f = await db.get(ModelField, fid)
    if not f: raise HTTPException(404, "字段不存在")
    for k, v in req.model_dump(exclude_unset=True).items(): setattr(f, k, v)
    await db.commit(); return {"message": "已更新"}

@router.delete("/api/v1/model-tables/{mid}/fields/{fid}")
async def delete_field(mid: int, fid: int,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    f = await db.get(ModelField, fid)
    if not f: raise HTTPException(404, "字段不存在")
    await db.delete(f); await db.commit(); return {"message": "已删除"}
