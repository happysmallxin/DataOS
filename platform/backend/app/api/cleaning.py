"""数据清洗 Pipeline API — Pipeline CRUD + 执行.

P1 更新: Pipeline 持久化到 cleaning_pipelines 表，支持按项目增删改查 + 存储执行.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_role, GLOBAL_ADMIN_ROLES, get_user_global_roles
from app.api.schemas import PipelineCreate, PipelineUpdate, PipelineResponse, PipelineListResponse
from app.core.database import get_db
from app.models.user import User
from app.models.pipeline import CleaningPipeline as PipelineModel
from app.models.audit_log import AuditLog
from app.services.cleaning import CleaningPipeline as CleaningPipelineEngine

router = APIRouter(prefix="/api/v1/cleaning", tags=["DataCleaning"])

# 全局引擎实例
pipeline_engine = CleaningPipelineEngine()


# ---- 运行时请求/响应 ----

class ProfileRequest(BaseModel):
    data: list[dict] = Field(..., description="待画像的数据 (JSON 行)")
    sample_size: int = Field(default=10000, description="采样大小")


class PipelineRunRequest(BaseModel):
    data: list[dict] = Field(default_factory=list, description="待清洗的数据 (JSON 行), 不传则从 MinIO 读取")
    stages: list[dict] = Field(default_factory=list, description="运行时阶段定义")
    pipeline_id: int | None = Field(default=None, description="持久化 Pipeline ID (自动从 MinIO 读取)")
    pipeline_name: str = Field(default="", description="Pipeline 名称")
    pipeline_version: int = Field(default=1, description="版本号")


# ============================================================
# Pipeline CRUD (P1 新增)
# ============================================================

@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    req: PipelineCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建持久化清洗 Pipeline — 归属到项目."""
    # 手动权限检查: project_id 在 body 中, require_project_role 需要 path param
    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    if not is_admin:
        from app.models.project_member import ProjectMember as PM
        from app.models.role import Role
        member = await db.execute(
            select(PM, Role).join(Role, Role.id == PM.role_id).where(
                PM.project_id == req.project_id, PM.user_id == current_user.id
            )
        )
        row = member.one_or_none()
        if not row:
            raise HTTPException(status_code=403, detail="你不是该项目成员")
        _, role = row
        if role.name not in ("project_owner", "editor", "developer"):
            raise HTTPException(status_code=403, detail="需要 project_owner/editor/developer 角色")

    existing = await db.execute(
        select(PipelineModel).where(
            PipelineModel.project_id == req.project_id,
            PipelineModel.name == req.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"项目内已存在同名 Pipeline '{req.name}'")

    pl = PipelineModel(
        project_id=req.project_id,
        datasource_id=req.datasource_id,
        source_table=req.source_table,
        target_table=req.target_table,
        name=req.name,
        description=req.description,
        stages=req.stages,
        created_by=current_user.id,
    )
    db.add(pl)
    await db.flush()
    await db.refresh(pl)

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=req.project_id,
        resource="pipeline",
        action="create",
        target_id=pl.id,
        target_name=pl.name,
        detail={"stages_count": len(req.stages)},
    ))
    await db.commit()
    return pl


@router.get("/pipelines", response_model=PipelineListResponse)
async def list_pipelines(
    project_id: int = Query(..., description="项目 ID (必填, 项目隔离)"),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目下的 Pipeline 列表 — 按项目隔离."""
    stmt = select(PipelineModel).where(PipelineModel.project_id == project_id)
    if status:
        stmt = stmt.where(PipelineModel.status == status)
    stmt = stmt.order_by(PipelineModel.updated_at.desc())
    result = await db.execute(stmt)
    items = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(PipelineModel).where(PipelineModel.project_id == project_id)
    )
    total = count_result.scalar() or 0

    return PipelineListResponse(items=list(items), total=total)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个 Pipeline 详情."""
    pl = await db.get(PipelineModel, pipeline_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    return pl


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: int,
    req: PipelineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 Pipeline — 版本号自动递增."""
    pl = await db.get(PipelineModel, pipeline_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")

    # 角色校验
    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    if not is_admin:
        from app.models.project_member import ProjectMember as PM
        member = await db.execute(
            select(PM).where(PM.project_id == pl.project_id, PM.user_id == current_user.id)
        )
        if not member.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="你不是该项目成员")

    if req.name is not None:
        pl.name = req.name
    if req.description is not None:
        pl.description = req.description
    if req.stages is not None:
        pl.stages = req.stages
        pl.version += 1  # 阶段变更时版本号递增
    if req.status is not None:
        pl.status = req.status

    await db.commit()
    await db.refresh(pl)
    return pl


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除 Pipeline — 需要 project_owner 或 admin."""
    pl = await db.get(PipelineModel, pipeline_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")

    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    if not is_admin:
        from app.models.project_member import ProjectMember as PM
        from app.models.role import Role
        member = await db.execute(
            select(PM, Role).join(Role, Role.id == PM.role_id).where(
                PM.project_id == pl.project_id, PM.user_id == current_user.id
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
        project_id=pl.project_id,
        resource="pipeline",
        action="delete",
        target_id=pipeline_id,
        target_name=pl.name,
    ))
    await db.delete(pl)
    await db.commit()
    return {"message": f"Pipeline '{pl.name}' 已删除"}


# ============================================================
# 数据画像 + Pipeline 执行
# ============================================================

@router.post("/profile")
async def profile_data(
    req: ProfileRequest,
    _: User = Depends(get_current_user),
):
    """⓪ 数据画像 — 对标 DataBrew Data Profile."""
    import pandas as pd
    from app.services.cleaning.stages.profiling import generate_profile

    df = pd.DataFrame(req.data) if req.data else pd.DataFrame()
    profile = generate_profile(df, req.sample_size)
    return {
        "total_rows": profile.total_rows,
        "total_columns": profile.total_columns,
        "generated_at": profile.generated_at,
        "issues": profile.issues,
        "suggestions": profile.suggestions,
        "columns": [
            {
                "column": c.column, "dtype": c.dtype,
                "null_count": c.null_count, "null_rate": c.null_rate,
                "unique_count": c.unique_count,
                "min": c.min, "max": c.max,
                "mean": c.mean, "median": c.median,
                "std": c.std, "q1": c.q1, "q3": c.q3,
                "iqr": c.iqr, "skew": c.skew,
                "top_values": c.top_values,
                "avg_length": c.avg_length, "max_length": c.max_length,
            }
            for c in profile.columns
        ],
    }


@router.post("/pipelines/run")
async def run_pipeline(
    req: PipelineRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行清洗 Pipeline — 支持三种数据来源:

    1. 直接传 data (运行时模式, 向后兼容)
    2. 传 pipeline_id → 加载持久化 stages 处理直接传的 data
    3. 传 pipeline_id + pipeline 关联了 datasource_id → 自动从 MinIO 读取同步数据
    """
    import pandas as pd

    stages: list[dict] = list(req.stages) if req.stages else []
    pipeline_name = req.pipeline_name or "unnamed"
    pipeline_version = req.pipeline_version
    pl = None
    df = pd.DataFrame()

    if req.pipeline_id:
        pl = await db.get(PipelineModel, req.pipeline_id)
        if not pl:
            raise HTTPException(status_code=404, detail="Pipeline 不存在")
        if not stages:
            stages = pl.stages
        pipeline_name = pl.name
        pipeline_version = pl.version

        # 🔗 Pipeline 关联了数据源 → 从 MinIO 读取同步数据
        if pl.datasource_id and pl.source_table and not req.data:
            from app.core.minio_client import list_objects, read_dataframe, get_bronze_path
            from app.core.config import settings

            # 支持多表: source_table 逗号分隔, 逐表处理
            tables = [t.strip() for t in pl.source_table.split(",") if t.strip()]
            total_rows = 0
            for tbl in tables:
                prefix = get_bronze_path(pl.project_id, pl.datasource_id, tbl)
                objects = list_objects(settings.MINIO_BUCKET_BRONZE, prefix)
                if not objects:
                    continue
                latest = sorted(objects, key=lambda o: o["last_modified"], reverse=True)[0]
                df = read_dataframe(settings.MINIO_BUCKET_BRONZE, latest["key"])
                total_rows += len(df)
                pipeline_engine.run(df=df, stages=stages, pipeline_name=f"{pl.name}/{tbl}", pipeline_version=pl.version)

            # 使用最后一张表的 df 继续写入逻辑
            if not tables:
                raise HTTPException(status_code=400, detail="没有可处理的表")
            # df 已经是最后一个表的 DataFrame

    # 直接传入的数据优先 (向后兼容)
    if df.empty and req.data:
        df = pd.DataFrame(req.data)

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="无数据可处理: 请传入 data, 或关联数据源并先执行同步, 或指定 pipeline_id 加载已同步数据"
        )

    # 执行 Pipeline
    report = pipeline_engine.run(
        df=df, stages=stages,
        pipeline_name=pipeline_name,
        pipeline_version=pipeline_version,
    )

    # 🔗 清洗结果写入 MinIO (Silver) + PostgreSQL (Gold) + 更新 Pipeline
    output_rows = 0
    pg_result = None
    if pl and pl.datasource_id and pl.source_table:
        try:
            from app.core.minio_client import write_dataframe, get_silver_path
            from app.core.config import settings

            output_df = df.copy()
            output_rows = len(output_df)

            # ── MinIO Silver ──
            silver_prefix = get_silver_path(pl.project_id, pl.name)
            silver_key = f"{silver_prefix}clean_{pd.Timestamp.now().strftime('%H%M%S')}.parquet"
            write_dataframe(output_df, settings.MINIO_BUCKET_SILVER, silver_key)

            # ── PostgreSQL Gold ──
            target_table = pl.target_table or f"clean_{pl.name.lower().replace(' ', '_')}"
            try:
                from sqlalchemy import create_engine as sync_create_engine
                pg_engine = sync_create_engine(settings.PG_GOLD_URL, connect_args={"connect_timeout": 10})
                output_df.to_sql(target_table, pg_engine, if_exists="replace", index=False)
                # 确保有主键 (Directus 要求)
                if "id" in output_df.columns:
                    from sqlalchemy import text as sa_text
                    with pg_engine.connect() as conn:
                        conn.execute(sa_text(
                            f"ALTER TABLE {target_table} ADD PRIMARY KEY (id)"
                        ))
                        conn.commit()
                pg_engine.dispose()
                pg_result = {"table": target_table, "engine": "postgresql", "rows": output_rows}
            except Exception as pg_err:
                pg_result = {"table": target_table, "engine": "postgresql", "error": str(pg_err)}

            # 更新 Pipeline 记录
            pl.last_run_at = pd.Timestamp.now()
            pl.last_output_rows = output_rows
            pl.target_table = target_table
            await db.commit()

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Pipeline 结果写入失败: {e}")

    result = report.to_dict()
    result["output_storage"] = {
        "rows": output_rows,
        "pipeline_id": pl.id if pl else None,
        "datasource_id": pl.datasource_id if pl else None,
        "minio_silver": f"{settings.MINIO_BUCKET_SILVER}/{silver_key}" if pl else None,
        "postgresql": pg_result,
    }
    return result


# ---- 清洗规则模板 ----

from app.models.cleaning_template import CleaningTemplate
from pydantic import BaseModel as PydanticBaseModel

class TemplateCreate(PydanticBaseModel):
    name: str; display_name: str; description: str = ""
    stages: list[dict] = []; exclude_columns: list[str] | None = None

@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(CleaningTemplate).order_by(CleaningTemplate.name))
    return result.scalars().all()

@router.post("/templates", status_code=201)
async def create_template(req: TemplateCreate, db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    t = CleaningTemplate(**req.model_dump(), created_by=current_user.id)
    db.add(t); await db.flush(); await db.refresh(t); await db.commit()
    return {"id": t.id, "name": t.name, "display_name": t.display_name}

@router.put("/templates/{tid}")
async def update_template(tid: int, req: TemplateCreate,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    t = await db.get(CleaningTemplate, tid)
    if not t: raise HTTPException(404, "模板不存在")
    t.name = req.name; t.display_name = req.display_name
    t.description = req.description; t.stages = req.stages
    if req.exclude_columns is not None: t.exclude_columns = req.exclude_columns
    await db.commit()
    return {"message": "模板已更新"}

@router.delete("/templates/{tid}")
async def delete_template(tid: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    t = await db.get(CleaningTemplate, tid)
    if not t: raise HTTPException(404, "模板不存在")
    await db.delete(t); await db.commit()
    return {"message": "模板已删除"}

# ---- 批量创建 Pipeline (选表 + 模板) ----

class BatchCreateRequest(PydanticBaseModel):
    datasource_id: int
    table_names: list[str] = []
    template_id: int | None = None
    target_prefix: str = ""

@router.post("/batch-create-pipelines")
async def batch_create_pipelines(
    req: BatchCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """选多张表 + 一个规则模板 -> 创建一个清洗任务 (含多张表)."""
    from app.models.datasource import DataSource as DS
    ds = await db.get(DS, req.datasource_id)
    datasource_id = req.datasource_id
    table_names = req.table_names
    template_id = req.template_id
    target_prefix = req.target_prefix
    if not ds: raise HTTPException(404, "数据源不存在")

    stages = []
    template_name = ""
    if template_id:
        t = await db.get(CleaningTemplate, template_id)
        if t:
            stages = t.stages
            template_name = t.display_name

    if not stages:
        stages = [{"rule_type": "structure_check", "rule_name": "默认检查", "target": "all_columns", "severity": "warning", "action": "check"}]

    # 创建一个清洗任务, source_table 存所有表名(逗号分隔)
    import pandas as pd
    all_tables = req.table_names
    task_name = f"{template_name or '清洗'}_{pd.Timestamp.now().strftime('%H%M%S')}"
    pl = PipelineModel(
        project_id=ds.project_id or 0, datasource_id=req.datasource_id,
        name=task_name, source_table=",".join(all_tables), target_table="",
        description=f"{task_name}: {', '.join(all_tables[:5])}{'...' if len(all_tables)>5 else ''}",
        stages=stages, created_by=current_user.id,
    )
    db.add(pl)
    await db.flush()
    await db.refresh(pl)
    await db.commit()

    # 自动执行清洗 (跳过未同步的表, 单表失败不影响整体)
    run_result = {"tables_done": 0, "total_rows": 0, "skipped": 0, "errors": []}
    for tbl in all_tables:
        try:
            from app.core.minio_client import list_objects, read_dataframe, write_dataframe, get_bronze_path, get_silver_path
            from app.core.config import settings as s
            prefix = get_bronze_path(ds.project_id or 0, req.datasource_id, tbl)
            objects = list_objects(s.MINIO_BUCKET_BRONZE, prefix)
            if not objects:
                run_result["skipped"] += 1
                continue
            latest = sorted(objects, key=lambda o: o["last_modified"], reverse=True)[0]
            df = read_dataframe(s.MINIO_BUCKET_BRONZE, latest["key"])
            pipeline_engine.run(df=df, stages=stages, pipeline_name=f"{pl.name}/{tbl}", pipeline_version=1)

            silver_prefix = get_silver_path(ds.project_id or 0, f"{pl.name}/{tbl}")
            silver_key = f"{silver_prefix}clean_{pd.Timestamp.now().strftime('%H%M%S')}.parquet"
            write_dataframe(df, s.MINIO_BUCKET_SILVER, silver_key)

            try:
                from sqlalchemy import create_engine as sync_ce, text as sa_text
                pg_engine = sync_ce(s.PG_GOLD_URL, connect_args={"connect_timeout":5})
                df.to_sql(tbl, pg_engine, if_exists="replace", index=False)
                if "id" in df.columns:
                    with pg_engine.connect() as c: c.execute(sa_text(f"ALTER TABLE {tbl} ADD PRIMARY KEY (id)")); c.commit()
                pg_engine.dispose()
            except Exception: pass

            run_result["tables_done"] += 1
            run_result["total_rows"] += len(df)
        except Exception as e:
            run_result["errors"].append(f"{tbl}: {str(e)[:50]}")

    pl.last_run_at = pd.Timestamp.now()
    pl.last_output_rows = run_result["total_rows"]
    await db.commit()

    return {"id": pl.id, "name": pl.name, "tables": all_tables, "table_count": len(all_tables), "template": template_name, "run": run_result}


@router.get("/stages")
async def list_stages(
    _: User = Depends(get_current_user),
):
    """获取可用阶段列表 — 对标 DataBrew 配方步骤目录."""
    return pipeline_engine.available_stages()
