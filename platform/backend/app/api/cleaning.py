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

            prefix = get_bronze_path(pl.project_id, pl.datasource_id, pl.source_table)
            objects = list_objects(settings.MINIO_BUCKET_BRONZE, prefix)
            if not objects:
                raise HTTPException(
                    status_code=400,
                    detail=f"数据源 {pl.datasource_id} 的表 {pl.source_table} 尚未同步到 MinIO，请先执行数据同步"
                )

            # 读取最新一批同步数据
            latest = sorted(objects, key=lambda o: o["last_modified"], reverse=True)[0]
            df = read_dataframe(settings.MINIO_BUCKET_BRONZE, latest["key"])

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


@router.get("/stages")
async def list_stages(
    _: User = Depends(get_current_user),
):
    """获取可用阶段列表 — 对标 DataBrew 配方步骤目录."""
    return pipeline_engine.available_stages()
