"""① 格式标准化 — 对标 DataBrew 250+ 内置转换.

支持操作: trim/lowercase/uppercase/parse_date/cast_type/regex_replace/
          strip_html/normalize_unicode/pad_zero/map_values
"""

from datetime import datetime
from typing import Any

import pandas as pd
from dateutil.parser import parse as parse_date_str

from app.services.cleaning.models import BaseStage, StageResult, ColumnLineage


class StandardizeStage(BaseStage):
    """格式标准化阶段 — 对齐列的数据格式."""

    name = "standardize"

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
        operations = self.config.get("operations", [])
        if not operations:
            return df, StageResult(
                stage_name=self.name, status="success",
                rows_in=len(df), rows_out=len(df),
                details={"message": "无操作"}
            )

        result_df = df.copy()
        modified_columns: set[str] = set()
        lineage: list[ColumnLineage] = []
        parse_errors: list[dict] = []
        cast_errors: list[dict] = []
        type_conversions: dict[str, str] = {}

        for op in operations:
            col = op.get("column", "")
            action = op.get("action", "")
            if col not in result_df.columns:
                continue

            # 条件执行 — 对标 DataBrew ConditionExpression
            mask = self._eval_condition(result_df, op.get("where"))

            try:
                if action == "trim":
                    result_df.loc[mask, col] = result_df.loc[mask, col].astype(str).str.strip()
                    modified_columns.add(col)

                elif action == "lowercase":
                    result_df.loc[mask, col] = result_df.loc[mask, col].astype(str).str.lower()
                    modified_columns.add(col)

                elif action == "uppercase":
                    result_df.loc[mask, col] = result_df.loc[mask, col].astype(str).str.upper()
                    modified_columns.add(col)

                elif action == "parse_date":
                    hint = op.get("hint_format", "")
                    result_df[col] = result_df[col].apply(
                        lambda v, h=hint: _safe_parse_date(v, h, parse_errors)
                    )
                    result_df[col] = pd.to_datetime(result_df[col], errors="coerce")
                    type_conversions[col] = "datetime64"
                    modified_columns.add(col)
                    lineage.append(ColumnLineage(
                        source_column=col, target_column=col,
                        transformation=f"parse_date->datetime64", stage_name=self.name
                    ))

                elif action == "cast_type":
                    dtype = op.get("dtype", "str")
                    old_dtype = str(result_df[col].dtype)
                    if dtype == "int" or dtype == "int64":
                        result_df[col] = pd.to_numeric(result_df[col], errors="coerce").astype("Int64")
                    elif dtype == "float" or dtype == "float64":
                        result_df[col] = pd.to_numeric(result_df[col], errors="coerce")
                    elif dtype in ("bool", "boolean"):
                        result_df[col] = result_df[col].astype(str).str.lower().map(
                            {"true": True, "false": False, "1": True, "0": False,
                             "是": True, "否": False, "yes": True, "no": False}
                        )
                    else:
                        result_df[col] = result_df[col].astype(str)
                    type_conversions[col] = f"{old_dtype}->{dtype}"
                    modified_columns.add(col)

                elif action == "regex_replace":
                    pattern = op.get("pattern", "")
                    replacement = op.get("replacement", "")
                    result_df.loc[mask, col] = result_df.loc[mask, col].astype(str).str.replace(
                        pattern, replacement, regex=True
                    )
                    modified_columns.add(col)

                elif action == "strip_html":
                    result_df.loc[mask, col] = result_df.loc[mask, col].astype(str).str.replace(
                        r"<[^>]*>", "", regex=True
                    )
                    modified_columns.add(col)

                elif action == "normalize_unicode":
                    import unicodedata
                    result_df.loc[mask, col] = result_df.loc[mask, col].astype(str).apply(
                        lambda s: unicodedata.normalize("NFKC", s)
                    )
                    modified_columns.add(col)

                elif action == "pad_zero":
                    width = op.get("width", 5)
                    result_df.loc[mask, col] = result_df.loc[mask, col].astype(str).str.zfill(width)
                    modified_columns.add(col)

                elif action == "map_values":
                    mapping = op.get("mapping", {})
                    result_df.loc[mask, col] = result_df.loc[mask, col].map(mapping).fillna(result_df[col])
                    modified_columns.add(col)

            except Exception as e:
                cast_errors.append({"column": col, "action": action, "error": str(e)})

        details: dict = {
            "operations_applied": len(operations),
            "columns_modified": list(modified_columns),
            "type_conversions": type_conversions,
        }
        if parse_errors:
            details["parse_date_errors"] = len(parse_errors)
        if cast_errors:
            details["cast_errors"] = cast_errors

        return result_df, StageResult(
            stage_name=self.name,
            status="success",
            rows_in=len(df),
            rows_out=len(result_df),
            rows_affected=len(result_df) if modified_columns else 0,
            details=details,
            lineage=lineage,
        )


def _safe_parse_date(value: Any, hint_format: str, errors: list) -> Any:
    """安全解析日期 — 支持 20+ 常见格式."""
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (datetime, pd.Timestamp)):
        return value
    try:
        if hint_format:
            return datetime.strptime(str(value), hint_format)
        return parse_date_str(str(value))
    except Exception:
        errors.append({"value": str(value)[:50], "hint": hint_format})
        return pd.NaT
