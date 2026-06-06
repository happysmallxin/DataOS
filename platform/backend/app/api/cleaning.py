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
    data: list[dict] = Field(..., description="待清洗的数据 (JSON 行)")
    stages: list[dict] = Field(default_factory=list, description="运行时阶段定义")
    pipeline_id: int | None = Field(default=None, description="持久化 Pipeline ID (P1: 使用已存储的阶段)")
    pipeline_name: str = Field(default="", description="Pipeline 名称")
    pipeline_version: int = Field(default=1, description="版本号")


# ============================================================
# Pipeline CRUD (P1 新增)
# ============================================================

@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    req: PipelineCreate,
    current_user: User = Depends(get_current_user),
    _ = Depends(require_project_role("project_owner", "editor", "developer")),
    db: AsyncSession = Depends(get_db),
):
    """创建持久化清洗 Pipeline — 归属到项目."""
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
    """执行清洗 Pipeline — 支持运行时 stages 或加载持久化 Pipeline."""
    import pandas as pd

    # P1: 如果指定了 pipeline_id，从 DB 加载 stages
    stages: list[dict] = list(req.stages) if req.stages else []
    pipeline_name = req.pipeline_name or "unnamed"
    pipeline_version = req.pipeline_version

    if req.pipeline_id:
        pl = await db.get(PipelineModel, req.pipeline_id)
        if not pl:
            raise HTTPException(status_code=404, detail="Pipeline 不存在")
        if not stages:
            stages = pl.stages
        pipeline_name = pipeline_name or pl.name
        pipeline_version = pl.version

        # 记录执行
        pl.last_run_at = pd.Timestamp.now()
        await db.commit()

    df = pd.DataFrame(req.data) if req.data else pd.DataFrame()
    report = pipeline_engine.run(
        df=df, stages=stages,
        pipeline_name=pipeline_name,
        pipeline_version=pipeline_version,
    )
    return report.to_dict()


@router.get("/stages")
async def list_stages(
    _: User = Depends(get_current_user),
):
    """获取可用阶段列表 — 对标 DataBrew 配方步骤目录."""
    return pipeline_engine.available_stages()
