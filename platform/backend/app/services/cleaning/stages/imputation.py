"""② 缺失值处理 — 对标 Spark ML Imputer (Fit/Transform 分离).

支持: drop_column/drop_row/constant/mean/median/mode/ffill/bfill/interpolate/flag_only/rolling_average
"""

import pandas as pd
from app.services.cleaning.models import BaseStage, StageResult


class ImputationStage(BaseStage):
    """缺失值处理阶段 — Fit/Transform 模式."""

    name = "imputation"

    def __init__(self, config: dict):
        super().__init__(config)
        self._fitted: dict = {}  # Fit 阶段学习的统计量

    def fit(self, df: pd.DataFrame) -> "ImputationStage":
        """学习填充统计量."""
        col_configs = self.config.get("columns", {})
        for col, cfg in col_configs.items():
            if col not in df.columns:
                continue
            method = cfg.get("method", "constant")
            col_data = df[col].dropna()
            if method == "median":
                self._fitted[f"{col}_median"] = col_data.median()
            elif method == "mode":
                modes = col_data.mode()
                self._fitted[f"{col}_mode"] = modes[0] if len(modes) > 0 else ""
            elif method == "mean":
                self._fitted[f"{col}_mean"] = col_data.mean()
            elif method == "rolling_average":
                self._fitted[f"{col}_window"] = cfg.get("window_size", 5)
        return self

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
        # 自动 Fit
        if not self._fitted:
            self.fit(df)

        global_threshold = self.config.get("global", {})
        drop_col_threshold = global_threshold.get("drop_column_threshold", 0.5)
        drop_row_threshold = global_threshold.get("drop_row_threshold", 0.5)

        result_df = df.copy()
        rows_before = len(result_df)
        columns_dropped: list[str] = []
        filled: dict = {}

        # 全局：删除缺失率过高的列
        for col in list(result_df.columns):
            null_rate = result_df[col].isna().mean()
            if null_rate >= drop_col_threshold:
                result_df = result_df.drop(columns=[col])
                columns_dropped.append(col)

        # 全局：删除缺失过多的行
        if drop_row_threshold > 0:
            min_non_null = int(len(result_df.columns) * (1 - drop_row_threshold))
            result_df = result_df.dropna(thresh=max(1, min_non_null))

        # 逐列填充
        col_configs = self.config.get("columns", {})
        for col, cfg in col_configs.items():
            if col not in result_df.columns:
                continue
            method = cfg.get("method", "constant")
            null_before = int(result_df[col].isna().sum())
            if null_before == 0:
                continue

            try:
                if method == "drop_column":
                    result_df = result_df.drop(columns=[col])
                    columns_dropped.append(col)
                elif method == "drop_row":
                    result_df = result_df.dropna(subset=[col])
                elif method == "constant":
                    value = cfg.get("value", "unknown")
                    result_df[col] = result_df[col].fillna(value)
                    filled[col] = {"method": "constant", "value": value, "filled_count": null_before}
                elif method == "median":
                    med = self._fitted.get(f"{col}_median", result_df[col].median())
                    result_df[col] = result_df[col].fillna(med)
                    filled[col] = {"method": "median", "value_used": med, "filled_count": null_before}
                elif method == "mode":
                    mode_val = self._fitted.get(f"{col}_mode", "")
                    result_df[col] = result_df[col].fillna(mode_val)
                    filled[col] = {"method": "mode", "value_used": mode_val, "filled_count": null_before}
                elif method == "mean":
                    mean_val = self._fitted.get(f"{col}_mean", result_df[col].mean())
                    result_df[col] = result_df[col].fillna(mean_val)
                    filled[col] = {"method": "mean", "value_used": round(float(mean_val), 2), "filled_count": null_before}
                elif method == "ffill":
                    result_df[col] = result_df[col].ffill()
                    filled[col] = {"method": "ffill", "filled_count": int(result_df[col].isna().sum() - null_before + null_before)}
                elif method == "bfill":
                    result_df[col] = result_df[col].bfill()
                    filled[col] = {"method": "bfill", "filled_count": null_before}
                elif method == "interpolate":
                    result_df[col] = result_df[col].interpolate()
                    filled[col] = {"method": "interpolate", "filled_count": null_before}
                elif method == "rolling_average":
                    window = self._fitted.get(f"{col}_window", 5)
                    order_by = cfg.get("order_by", "")
                    if order_by and order_by in result_df.columns:
                        result_df = result_df.sort_values(order_by)
                    result_df[col] = result_df[col].fillna(
                        result_df[col].rolling(window, min_periods=1).mean()
                    )
                    filled[col] = {"method": "rolling_average", "window": window, "filled_count": null_before}
                elif method == "flag_only":
                    result_df[f"{col}_is_missing"] = result_df[col].isna()
                    filled[col] = {"method": "flag_only", "flagged_count": null_before}
            except Exception as e:
                filled[col] = {"method": method, "error": str(e)}

        return result_df, StageResult(
            stage_name=self.name,
            status="success",
            rows_in=rows_before,
            rows_out=len(result_df),
            rows_dropped=rows_before - len(result_df),
            rows_affected=sum(v.get("filled_count", 0) for v in filled.values()),
            details={
                "columns_dropped": columns_dropped,
                "filled": filled,
                "fit_statistics": {k: (round(float(v), 2) if isinstance(v, float) else v)
                                   for k, v in self._fitted.items()},
            },
        )
