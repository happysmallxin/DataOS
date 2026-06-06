"""⓪ 数据画像 — 对标 DataBrew Data Profile + DataLeap 数据探查.

自动分析数据特征，生成质量报告和清洗建议.
"""

import pandas as pd
import numpy as np
from app.services.cleaning.models import DataProfile, ColumnProfile


def generate_profile(df: pd.DataFrame, sample_size: int = 10000) -> DataProfile:
    """生成数据画像报告.

    Args:
        df: 输入 DataFrame
        sample_size: 采样大小 (大数据集只采样前 N 行)

    Returns:
        DataProfile: 完整画像报告
    """
    if len(df) > sample_size:
        df = df.head(sample_size)

    total_rows = len(df)
    columns: list[ColumnProfile] = []
    issues: list[dict] = []
    suggestions: list[dict] = []

    for col in df.columns:
        col_data = df[col]
        null_count = int(col_data.isna().sum())
        null_rate = round(null_count / total_rows, 4) if total_rows > 0 else 0.0
        unique_count = int(col_data.nunique())

        profile = ColumnProfile(
            column=col,
            dtype=str(col_data.dtype),
            null_count=null_count,
            null_rate=null_rate,
            unique_count=unique_count,
        )

        # 数值列
        if col_data.dtype in ("float64", "int64", "Int64"):
            numeric = pd.to_numeric(col_data, errors="coerce").dropna()
            if len(numeric) > 0:
                profile.min = round(float(numeric.min()), 4)
                profile.max = round(float(numeric.max()), 4)
                profile.mean = round(float(numeric.mean()), 4)
                profile.median = round(float(numeric.median()), 4)
                profile.std = round(float(numeric.std()), 4)
                q1 = float(numeric.quantile(0.25))
                q3 = float(numeric.quantile(0.75))
                profile.q1 = round(q1, 4)
                profile.q3 = round(q3, 4)
                profile.iqr = round(q3 - q1, 4)
                if len(numeric) > 2:
                    profile.skew = round(float(numeric.skew()), 4)

                # 异常值候选
                if profile.iqr and profile.iqr > 0:
                    lower = q1 - 1.5 * profile.iqr
                    upper = q3 + 1.5 * profile.iqr
                    outlier_count = int(((numeric < lower) | (numeric > upper)).sum())
                    if outlier_count > 0:
                        issues.append({
                            "column": col, "type": "outliers",
                            "detail": f"{outlier_count} 个 IQR 异常值 (范围 [{lower:.2f}, {upper:.2f}])",
                            "severity": "warning"
                        })
                        suggestions.append({
                            "column": col, "action": "outliers",
                            "method": "iqr", "suggested_action": "cap",
                            "reason": f"发现 {outlier_count} 个 IQR 异常值, 建议 cap 或检测"
                        })

                # 偏态
                if profile.skew and abs(profile.skew) > 2:
                    issues.append({
                        "column": col, "type": "skewed",
                        "detail": f"偏度 {profile.skew:.2f}, 高度偏态",
                        "severity": "info"
                    })

        # 分类型
        if col_data.dtype == "object" or col_data.dtype == "string" or unique_count < 50:
            value_counts = col_data.value_counts().head(10)
            profile.top_values = [
                {"value": str(v), "count": int(c),
                 "rate": round(c / total_rows, 4) if total_rows > 0 else 0}
                for v, c in value_counts.items()
            ]

        # 文本列
        if col_data.dtype in ("object", "string"):
            text_data = col_data.dropna().astype(str)
            if len(text_data) > 0:
                lengths = text_data.str.len()
                profile.avg_length = round(float(lengths.mean()), 1)
                profile.max_length = int(lengths.max())
                profile.empty_string_count = int((text_data == "").sum())

        # 日期列
        if "datetime" in str(col_data.dtype):
            dt_data = pd.to_datetime(col_data, errors="coerce").dropna()
            if len(dt_data) > 0:
                profile.min_date = str(dt_data.min())
                profile.max_date = str(dt_data.max())

        # 质量问题
        if null_rate >= 0.5:
            issues.append({
                "column": col, "type": "high_null",
                "detail": f"缺失率 {null_rate:.1%} ≥ 50%",
                "severity": "error"
            })
            suggestions.append({
                "column": col, "action": "imputation",
                "method": "drop_column",
                "reason": f"缺失率 {null_rate:.1%}, 建议删除此列"
            })
        elif null_rate > 0:
            issues.append({
                "column": col, "type": "has_null",
                "detail": f"缺失率 {null_rate:.1%}",
                "severity": "warning"
            })

        # 常量列
        if unique_count <= 1 and total_rows > 1:
            issues.append({
                "column": col, "type": "constant_column",
                "detail": "常量列 (只有一个值)",
                "severity": "info"
            })

        # 高基数
        if unique_count / max(total_rows, 1) > 0.9 and col_data.dtype not in ("float64", "int64"):
            issues.append({
                "column": col, "type": "high_cardinality",
                "detail": f"高基数列 (唯一值/总行数 = {unique_count/total_rows:.1%})",
                "severity": "info"
            })

        # trim 建议
        if col_data.dtype in ("object", "string"):
            sample = col_data.dropna().head(100).astype(str)
            has_whitespace = sample.str.contains(r"^\s|\s$").any()
            if has_whitespace:
                suggestions.append({
                    "column": col, "action": "standardize", "operation": "trim",
                    "reason": "检测到前后空格"
                })

        columns.append(profile)

    return DataProfile(total_rows=total_rows, total_columns=len(df.columns),
                       columns=columns, issues=issues, suggestions=suggestions)
