"""数据集生成 API — 向导式创建 + 版本管理 (对齐 MES 文档 §6)."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.dataset import Dataset, DatasetVersion
from app.models.model_table import ModelTable, ModelField

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])

# ---- Schemas ----

class DatasetCreate(BaseModel):
    name: str; version: str = "1.0"; description: Optional[str] = None
    domain_id: Optional[int] = None; model_table_ids: list[int] = []
    output_fields: list[dict] = []; update_cycle: str = "once"
    export_format: str = "parquet"; tags: Optional[list[str]] = None

class DatasetUpdate(BaseModel):
    name: Optional[str] = None; description: Optional[str] = None
    output_fields: Optional[list[dict]] = None; update_cycle: Optional[str] = None
    export_format: Optional[str] = None; tags: Optional[list[str]] = None

# ---- CRUD ----

@router.get("")
async def list_datasets(project_id: int = Query(...), domain_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(Dataset).where(Dataset.project_id == project_id)
    if domain_id: stmt = stmt.where(Dataset.domain_id == domain_id)
    result = await db.execute(stmt.order_by(Dataset.created_at.desc()))
    return result.scalars().all()

@router.post("", status_code=201)
async def create_dataset(req: DatasetCreate, project_id: int = Query(...),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ds = Dataset(project_id=project_id, created_by=current_user.id, **req.model_dump())
    db.add(ds); await db.flush(); await db.refresh(ds); await db.commit()
    return {"id": ds.id, "name": ds.name, "version": ds.version}

@router.put("/{ds_id}")
async def update_dataset(ds_id: int, req: DatasetUpdate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    ds = await db.get(Dataset, ds_id)
    if not ds: raise HTTPException(404, "数据集不存在")
    for k, v in req.model_dump(exclude_unset=True).items(): setattr(ds, k, v)
    await db.commit(); return {"message": "已更新"}

@router.delete("/{ds_id}")
async def delete_dataset(ds_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    ds = await db.get(Dataset, ds_id)
    if not ds: raise HTTPException(404, "数据集不存在")
    await db.delete(ds); await db.commit(); return {"message": "已删除"}

# ---- 预览 ----

@router.post("/{ds_id}/preview")
async def preview_dataset(ds_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    ds = await db.get(Dataset, ds_id)
    if not ds: raise HTTPException(404, "数据集不存在")
    # 读取模型表字段信息
    fields_info = []
    for mid in (ds.model_table_ids or []):
        mt = await db.get(ModelTable, mid)
        if mt:
            mfields = (await db.execute(select(ModelField).where(ModelField.model_table_id == mid))).scalars().all()
            fields_info.append({"model": mt.name, "code": mt.code, "field_count": len(mfields), "fields": [f.code for f in mfields[:5]]})
    return {"name": ds.name, "version": ds.version, "output_fields": ds.output_fields, "model_tables": fields_info, "total_models": len(fields_info)}

# ---- 生成 ----

@router.post("/{ds_id}/generate")
async def generate_dataset(ds_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    ds = await db.get(Dataset, ds_id)
    if not ds: raise HTTPException(404, "数据集不存在")

    ds.status = "generating"
    await db.commit()

    try:
        # 从 PG Gold 读取模型表数据并合并
        from app.core.config import settings
        from sqlalchemy import create_engine, text
        import pandas as pd

        total_rows = 0
        engine = create_engine(settings.PG_GOLD_URL, connect_args={"connect_timeout": 10})
        all_data = []
        for mid in (ds.model_table_ids or []):
            mt = await db.get(ModelTable, mid)
            if not mt or not mt.target_gold_table: continue
            try:
                df = pd.read_sql(f"SELECT * FROM {mt.target_gold_table}", engine)
                all_data.append(df)
                total_rows += len(df)
            except Exception: pass
        engine.dispose()

        if all_data:
            import pandas as pd
            result_df = pd.concat(all_data, ignore_index=True)
            # 写入 MinIO Silver
            from app.core.minio_client import write_dataframe
            from app.core.config import settings as s
            date_str = datetime.now().strftime("%Y-%m-%d")
            key = f"datasets/{ds_id}/{date_str}/v{ds.version}_{datetime.now().strftime('%H%M%S')}.parquet"
            r = write_dataframe(result_df, s.MINIO_BUCKET_SILVER, key)
            ds.storage_path = f"{s.MINIO_BUCKET_SILVER}/{key}"
            ds.total_rows = total_rows
            ds.total_size_bytes = r["size_bytes"]
            ds.status = "published"
            ds.published_at = datetime.now(timezone.utc)

            # 创建版本记录
            db.add(DatasetVersion(dataset_id=ds_id, version=ds.version, status="published",
                total_rows=total_rows, total_size_bytes=r["size_bytes"], storage_path=ds.storage_path))
        else:
            ds.status = "draft"
        await db.commit()
        return {"status": ds.status, "total_rows": ds.total_rows, "storage_path": ds.storage_path}
    except Exception as e:
        ds.status = "draft"
        await db.commit()
        raise HTTPException(500, f"生成失败: {e}")

# ---- 发布 ----

@router.post("/{ds_id}/publish")
async def publish_dataset(ds_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    ds = await db.get(Dataset, ds_id)
    if not ds: raise HTTPException(404, "数据集不存在")
    if ds.status != "published": raise HTTPException(400, "只能发布已生成的数据集")
    ds.published_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "数据集已发布", "published_at": str(ds.published_at)}

# ---- 版本 ----

@router.get("/{ds_id}/versions")
async def list_versions(ds_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(DatasetVersion).where(DatasetVersion.dataset_id == ds_id).order_by(DatasetVersion.created_at.desc()))
    return result.scalars().all()
