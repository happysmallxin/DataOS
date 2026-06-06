"""数据清洗 Pipeline API — 对标 DataBrew Recipe API.

端点:
  POST   /api/v1/cleaning/profile         数据画像
  POST   /api/v1/cleaning/pipelines/run   执行清洗 Pipeline
  GET    /api/v1/cleaning/stages          可用阶段列表
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.cleaning import CleaningPipeline
from app.services.cleaning.stages.profiling import generate_profile

router = APIRouter(prefix="/api/v1/cleaning", tags=["DataCleaning"])

pipeline = CleaningPipeline()


class ProfileRequest(BaseModel):
    data: list[dict] = Field(..., description="待画像的数据 (JSON 行)")
    sample_size: int = Field(default=10000, description="采样大小")


class PipelineRunRequest(BaseModel):
    data: list[dict] = Field(..., description="待清洗的数据 (JSON 行)")
    stages: list[dict] = Field(..., description="阶段定义列表")
    pipeline_name: str = Field(default="", description="Pipeline 名称")
    pipeline_version: int = Field(default=1, description="版本号")


@router.post("/profile")
async def profile_data(req: ProfileRequest):
    """⓪ 数据画像 — 对标 DataBrew Data Profile.

    返回每列的统计特征、质量问题和清洗建议。
    """
    import pandas as pd
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
                "column": c.column,
                "dtype": c.dtype,
                "null_count": c.null_count,
                "null_rate": c.null_rate,
                "unique_count": c.unique_count,
                "min": c.min, "max": c.max,
                "mean": c.mean, "median": c.median,
                "std": c.std, "q1": c.q1, "q3": c.q3,
                "iqr": c.iqr, "skew": c.skew,
                "top_values": c.top_values,
                "avg_length": c.avg_length,
                "max_length": c.max_length,
            }
            for c in profile.columns
        ],
    }


@router.post("/pipelines/run")
async def run_pipeline(req: PipelineRunRequest):
    """执行清洗 Pipeline — 对标 DataBrew Recipe Job.

    按顺序执行 stages，返回包含每阶段详细报告的 PipelineReport。
    """
    import pandas as pd
    df = pd.DataFrame(req.data) if req.data else pd.DataFrame()

    report = pipeline.run(
        df=df,
        stages=req.stages,
        pipeline_name=req.pipeline_name or "unnamed",
        pipeline_version=req.pipeline_version,
    )
    return report.to_dict()


@router.get("/stages")
async def list_stages():
    """获取可用阶段列表 — 对标 DataBrew 配方步骤目录."""
    return pipeline.available_stages()
