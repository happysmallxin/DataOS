"""④ 异常值处理 — 对标 DataBrew Outlier 操作.

支持: IQR/Z-score/IsolationForest → flag/cap/remove
"""

import numpy as np
import pandas as pd
from app.services.cleaning.models import BaseStage, StageResult


class OutlierStage(BaseStage):
    """异常值处理阶段."""

    name = "outliers"

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
        method = self.config.get("method", "iqr")
        action = self.config.get("action", "cap")
        columns = self.config.get("columns", [])
        iqr_mult = self.config.get("iqr_multiplier", 1.5)
        zscore_threshold = self.config.get("zscore_threshold", 3.0)
        partition_by = self.config.get("partition_by", "")

        if not columns:
            # 自动选数值列
            columns = [c for c in df.columns if df[c].dtype in ("float64", "int64", "Int64")]

        result_df = df.copy()
        per_column: dict[str, dict] = {}
        total_outliers = 0

        for col in columns:
            if col not in result_df.columns:
                continue

            if partition_by and partition_by in result_df.columns:
                # 分组检测 (对标 DataBrew per_group)
                bounds = {}
                for group, group_df in result_df.groupby(partition_by):
                    col_data = group_df[col].dropna()
                    if len(col_data) < 4:
                        continue
                    if method == "iqr":
                        q1, q3 = col_data.quantile([0.25, 0.75])
                        iqr = q3 - q1
                        lower, upper = q1 - iqr_mult * iqr, q3 + iqr_mult * iqr
                        bounds[group] = (lower, upper)
            else:
                col_data = result_df[col].dropna()
                per_column[col] = {"count": len(col_data)}

                if method == "iqr":
                    q1, q3 = col_data.quantile([0.25, 0.75])
                    iqr = q3 - q1
                    lower = q1 - iqr_mult * iqr
                    upper = q3 + iqr_mult * iqr
                    per_column[col].update({"Q1": q1, "Q3": q3, "IQR": iqr,
                                             "lower_bound": lower, "upper_bound": upper})

                    outlier_mask = (result_df[col] < lower) | (result_df[col] > upper)
                    outliers_found = int(outlier_mask.sum())
                    per_column[col]["outliers_found"] = outliers_found
                    total_outliers += outliers_found

                    if action == "cap":
                        result_df.loc[result_df[col] < lower, col] = lower
                        result_df.loc[result_df[col] > upper, col] = upper
                        per_column[col]["capped_range"] = f"[{lower:.2f}, {upper:.2f}]"

                    elif action == "flag":
                        result_df[f"{col}_is_outlier"] = outlier_mask

                elif method == "zscore":
                    mean, std = col_data.mean(), col_data.std()
                    if std == 0:
                        continue
                    z_scores = np.abs((result_df[col] - mean) / std)
                    outlier_mask = z_scores > zscore_threshold
                    outliers_found = int(outlier_mask.sum())
                    per_column[col].update({"mean": mean, "std": std,
                                             "outliers_found": outliers_found})

                    if action == "cap":
                        upper = mean + zscore_threshold * std
                        lower = mean - zscore_threshold * std
                        result_df.loc[result_df[col] > upper, col] = upper
                        result_df.loc[result_df[col] < lower, col] = lower

        # action=remove: 删除所有有异常值的行
        if action == "remove" and total_outliers > 0:
            outlier_rows = set()
            for col in columns:
                if col not in result_df.columns:
                    continue
                col_data = result_df[col].dropna()
                if len(col_data) < 4:
                    continue
                q1, q3 = col_data.quantile([0.25, 0.75])
                iqr = q3 - q1
                lower, upper = q1 - iqr_mult * iqr, q3 + iqr_mult * iqr
                outlier_rows.update(result_df[(result_df[col] < lower) | (result_df[col] > upper)].index)
            result_df = result_df.drop(index=list(outlier_rows))

        return result_df, StageResult(
            stage_name=self.name,
            status="warning" if total_outliers > 0 else "success",
            rows_in=len(df),
            rows_out=len(result_df),
            rows_affected=total_outliers,
            rows_dropped=(len(df) - len(result_df)) if action == "remove" else 0,
            details={"method": method, "action": action, "columns_checked": columns,
                     "total_outliers": total_outliers, "per_column": per_column},
        )
