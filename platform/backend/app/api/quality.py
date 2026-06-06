"""数据质量 API — 规则配置 + 执行校验."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
import pandas as pd

from app.api.deps import get_current_user
from app.models.user import User
from app.services.quality import quality_engine, QualityResult

router = APIRouter(prefix="/api/v1/quality", tags=["DataQuality"])


class QualityRule(BaseModel):
    """质量规则定义."""
    name: str = Field(..., description="规则名称")
    type: str = Field(..., description="规则类型: not_null / range / regex / unique / custom_sql")
    column: str = Field(default="", description="目标列名")
    min: float | None = Field(default=None, description="范围最小值")
    max: float | None = Field(default=None, description="范围最大值")
    pattern: str = Field(default="", description="正则表达式")
    condition: str = Field(default="", description="自定义条件 (DataFrame.eval)")


class QualityCheckRequest(BaseModel):
    """质量检查请求."""
    data: list[dict] = Field(..., description="待检查的数据 (JSON 行)")
    rules: list[QualityRule] = Field(..., description="质量规则列表")


class QualityCheckResponse(BaseModel):
    """质量检查响应."""
    total_rules: int
    passed_rules: int
    failed_rules: int
    overall_pass_rate: float
    results: list[dict]


@router.post("/check", response_model=QualityCheckResponse)
async def run_quality_check(
    req: QualityCheckRequest,
    _: User = Depends(get_current_user),
):
    """执行数据质量检查 — 传入数据和规则，返回检查结果。"""
    # 转换为 DataFrame
    df = pd.DataFrame(req.data) if req.data else pd.DataFrame()

    # 转换规则格式
    rules = [r.model_dump() for r in req.rules]

    # 执行检查
    results: list[QualityResult] = quality_engine.check_dataframe(df, rules)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    return QualityCheckResponse(
        total_rules=total,
        passed_rules=passed,
        failed_rules=total - passed,
        overall_pass_rate=round(passed / total * 100, 2) if total > 0 else 100,
        results=[r.__dict__ for r in results],
    )


@router.get("/rules")
async def list_rule_templates(
    _: User = Depends(get_current_user),
):
    """获取内置规则模板列表 — 对标 DataWorks 37种规则."""
    return [
        {"type": "not_null", "label": "非空校验", "description": "检查指定列是否包含空值", "icon": "stop"},
        {"type": "range", "label": "范围校验", "description": "检查数值是否在指定范围内", "icon": "sliders"},
        {"type": "regex", "label": "格式校验", "description": "正则匹配检查字段格式", "icon": "file-text"},
        {"type": "unique", "label": "唯一性检查", "description": "检查指定列是否有重复值", "icon": "number"},
        {"type": "custom_sql", "label": "自定义规则", "description": "DataFrame.eval 表达式条件", "icon": "code"},
    ]
