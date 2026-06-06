"""数据清洗 Pipeline — 核心数据模型.

对标: DataBrew Recipe + dbt models + DLT Expectations
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


# ============================================================
# 列级血缘 (对标 DataWorks 列血缘 + dbt ref DAG)
# ============================================================
@dataclass
class ColumnLineage:
    """单列的血缘追踪 — 记录输入列→输出列的转换链."""
    source_column: str
    target_column: str
    transformation: str
    stage_name: str


# ============================================================
# 条件执行 (对标 DataBrew ConditionExpressions)
# ============================================================
@dataclass
class Condition:
    """单条条件表达式 — 对标 DataBrew ConditionExpression."""
    column: str
    operator: str  # eq/neq/gt/gte/lt/lte/in/not_in/between/is_null/not_null/contains/starts_with/ends_with/matches
    value: Any = None
    value2: Any = None  # between 操作的第二个值

    def to_expression(self) -> str:
        """转为 pandas eval 表达式."""
        col = f"`{self.column}`" if " " in self.column else self.column
        op = self.operator
        if op == "eq":         return f"{col} == {_quote(self.value)}"
        if op == "neq":        return f"{col} != {_quote(self.value)}"
        if op == "gt":         return f"{col} > {self.value}"
        if op == "gte":        return f"{col} >= {self.value}"
        if op == "lt":         return f"{col} < {self.value}"
        if op == "lte":        return f"{col} <= {self.value}"
        if op == "in":         return f"{col}.isin({self.value})"
        if op == "not_in":     return f"~{col}.isin({self.value})"
        if op == "between":    return f"({col} >= {self.value} and {col} <= {self.value2})"
        if op == "is_null":    return f"{col}.isna()"
        if op == "not_null":   return f"{col}.notna()"
        if op == "contains":   return f"{col}.str.contains({_quote(self.value)}, na=False)"
        if op == "starts_with": return f"{col}.str.startswith({_quote(self.value)}, na=False)"
        if op == "ends_with":  return f"{col}.str.endswith({_quote(self.value)}, na=False)"
        if op == "matches":    return f"{col}.str.match({_quote(self.value)}, na=False)"
        return "True"


def _sanitize(obj: Any) -> Any:
    """将 numpy 类型转为 Python 原生类型，确保 JSON 可序列化."""
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def _quote(v: Any) -> str:
    if isinstance(v, str):
        return repr(v)
    return str(v)


# ============================================================
# 三级严重度 (对标 DLT warn/drop/fail + dbt severity)
# ============================================================
Severity = str  # "warn" | "drop" | "fail"


# ============================================================
# 阶段结果
# ============================================================
@dataclass
class StageResult:
    """单个阶段的执行结果 — 对标 DataBrew RecipeStep 执行报告."""
    stage_name: str
    status: str  # "success" | "warning" | "failed"
    rows_in: int
    rows_out: int
    rows_affected: int = 0
    rows_dropped: int = 0
    duration_ms: float = 0.0
    details: dict = field(default_factory=dict)
    severity_summary: dict = field(default_factory=dict)
    lineage: list[ColumnLineage] = field(default_factory=list)


# ============================================================
# Pipeline 报告
# ============================================================
@dataclass
class PipelineReport:
    """完整 Pipeline 执行报告 — 对标 dbt run_results.json."""
    pipeline_id: str = field(default_factory=lambda: str(uuid4())[:8])
    pipeline_name: str = ""
    pipeline_version: int = 1
    status: str = "pending"  # pending/running/completed/failed/blocked
    total_duration_ms: float = 0.0
    stages: list[StageResult] = field(default_factory=list)
    quality_gate: Optional[dict] = None
    output_rows: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"

    def to_dict(self) -> dict:
        return _sanitize({
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "status": self.status,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "output_rows": self.output_rows,
            "created_at": self.created_at,
            "stages": [
                {
                    "stage_name": s.stage_name,
                    "status": s.status,
                    "rows_in": s.rows_in,
                    "rows_out": s.rows_out,
                    "rows_affected": s.rows_affected,
                    "rows_dropped": s.rows_dropped,
                    "duration_ms": round(s.duration_ms, 2),
                    "details": s.details,
                    "severity_summary": s.severity_summary,
                    "lineage": [
                        {"source": l.source_column, "target": l.target_column,
                         "transformation": l.transformation, "stage": l.stage_name}
                        for l in s.lineage
                    ],
                }
                for s in self.stages
            ],
            "quality_gate": self.quality_gate,
        })


# ============================================================
# 数据画像 (对标 DataBrew Data Profile)
# ============================================================
@dataclass
class ColumnProfile:
    """单列的数据画像."""
    column: str
    dtype: str
    null_count: int
    null_rate: float
    unique_count: int
    # 数值列
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None
    skew: Optional[float] = None
    # 分类型
    top_values: list[dict] = field(default_factory=list)  # [{value, count, rate}]
    # 文本列
    avg_length: Optional[float] = None
    max_length: Optional[int] = None
    empty_string_count: int = 0
    # 日期列
    min_date: Optional[str] = None
    max_date: Optional[str] = None


@dataclass
class DataProfile:
    """完整数据画像报告."""
    total_rows: int
    total_columns: int
    columns: list[ColumnProfile]
    issues: list[dict] = field(default_factory=list)     # 质量问题列表
    suggestions: list[dict] = field(default_factory=list) # 清洗建议
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============================================================
# Pipeline 版本 (对标 DataBrew Recipe Versioning)
# ============================================================
@dataclass
class PipelineVersion:
    """Pipeline 配置快照 — 创建后不可变."""
    pipeline_id: str
    version: int
    name: str
    description: str = ""
    stages: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"


# ============================================================
# 阶段基类
# ============================================================
class BaseStage:
    """清洗阶段抽象基类 — 对标 Spark ML PipelineStage."""

    name: str = "base"

    def __init__(self, config: dict):
        self.config = config

    def run(self, df: "pd.DataFrame") -> tuple["pd.DataFrame", StageResult]:
        """执行阶段，返回 (转换后DataFrame, 阶段报告)."""
        raise NotImplementedError

    def _eval_condition(self, df: "pd.DataFrame", condition: Optional[dict]) -> "pd.Series":
        """将条件配置转为布尔 Series — 对标 DataBrew ConditionExpression."""
        if condition is None or not condition:
            import pandas as pd
            return pd.Series(True, index=df.index)

        col = condition.get("column", "")
        op = condition.get("operator", "not_null")
        value = condition.get("value")
        value2 = condition.get("value2")

        if op == "eq":         return df[col] == value
        if op == "neq":        return df[col] != value
        if op == "gt":         return df[col] > value
        if op == "gte":        return df[col] >= value
        if op == "lt":         return df[col] < value
        if op == "lte":        return df[col] <= value
        if op == "in":         return df[col].isin(value)
        if op == "not_in":     return ~df[col].isin(value)
        if op == "between":    return (df[col] >= value) & (df[col] <= value2)
        if op == "is_null":    return df[col].isna()
        if op == "not_null":   return df[col].notna()
        if op == "contains":   return df[col].astype(str).str.contains(str(value), na=False)
        if op == "starts_with": return df[col].astype(str).str.startswith(str(value), na=False)
        if op == "ends_with":  return df[col].astype(str).str.endswith(str(value), na=False)
        if op == "matches":    return df[col].astype(str).str.match(str(value), na=False)

        import pandas as pd
        return pd.Series(True, index=df.index)
