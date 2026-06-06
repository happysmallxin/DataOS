"""数据清洗 Pipeline 编排器.

对标: DataBrew Recipe + dbt models + DLT Expectations

使用方式:
    from app.services.cleaning import CleaningPipeline

    pipeline = CleaningPipeline()
    report = await pipeline.run(df, stages_config)

架构:
    CleaningPipeline
      ├── ⓪ Profiling (数据画像)
      ├── ① Standardize (格式标准化)
      ├── ② Imputation (缺失值处理, Fit/Transform)
      ├── ③ Dedup (去重)
      ├── ④ Outliers (异常值处理)
      ├── ⑤ BusinessRules (业务规则, 条件执行+三级严重度)
      ├── ⑥ PIIMasking (安全脱敏)
      └── ⑦ QualityGate (质量门控)
"""

import time
from typing import Optional

import pandas as pd

from app.services.cleaning.models import (
    PipelineReport,
    StageResult,
    Severity,
)

# 懒加载阶段类，避免循环导入


class CleaningPipeline:
    """数据清洗 Pipeline 编排器 — 对标 DataWorks 数据开发 DAG."""

    def __init__(self):
        self._registry: dict[str, type] = {}

    def run(self, df: pd.DataFrame, stages: list[dict],
            pipeline_name: str = "", pipeline_version: int = 1) -> PipelineReport:
        """按顺序执行 stages，返回完整报告.

        Args:
            df: 输入 DataFrame
            stages: 阶段定义列表 [{"type":"standardize","config":{...}}, ...]
            pipeline_name: Pipeline 名称
            pipeline_version: 版本号

        Returns:
            PipelineReport: 完整执行报告
        """
        report = PipelineReport(
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            status="running",
        )
        current_df = df.copy()
        results: list[StageResult] = []

        for i, stage_def in enumerate(stages):
            stage_type = stage_def["type"]
            config = stage_def.get("config", {})
            step_num = i + 1

            stage_instance = self._create_stage(stage_type, config)
            if stage_instance is None:
                result = StageResult(
                    stage_name=stage_type,
                    status="failed",
                    rows_in=len(current_df),
                    rows_out=len(current_df),
                    details={"error": f"未注册的阶段类型: {stage_type}"},
                )
                results.append(result)
                report.status = f"failed_at_stage_{step_num}"
                break

            t0 = time.perf_counter()
            try:
                new_df, result = stage_instance.run(current_df)
                result.duration_ms = (time.perf_counter() - t0) * 1000
                result.stage_name = stage_type
                results.append(result)
                current_df = new_df

                # quality_gate 失败 + severity=fail → 阻断
                if stage_type == "quality_gate" and result.status == "failed":
                    on_failure = config.get("on_failure", "error")
                    if on_failure == "error":
                        report.status = "blocked_by_quality_gate"
                        break
            except Exception as e:
                result = StageResult(
                    stage_name=stage_type,
                    status="failed",
                    rows_in=len(current_df),
                    rows_out=len(current_df),
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    details={"error": str(e), "error_type": type(e).__name__},
                )
                results.append(result)
                report.status = f"error_at_stage_{step_num}"
                break

        if report.status == "running":
            report.status = "completed"

        report.stages = results
        report.total_duration_ms = sum(r.duration_ms for r in results)
        report.output_rows = len(current_df)

        return report

    def _create_stage(self, stage_type: str, config: dict):
        """工厂方法 — 根据类型创建阶段实例."""
        # 延迟导入，避免循环依赖
        if stage_type == "standardize":
            from app.services.cleaning.stages.standardize import StandardizeStage
            return StandardizeStage(config)
        if stage_type == "imputation":
            from app.services.cleaning.stages.imputation import ImputationStage
            return ImputationStage(config)
        if stage_type == "dedup":
            from app.services.cleaning.stages.dedup import DedupStage
            return DedupStage(config)
        if stage_type == "outliers":
            from app.services.cleaning.stages.outliers import OutlierStage
            return OutlierStage(config)
        if stage_type == "business_rules":
            from app.services.cleaning.stages.business_rules import BusinessRuleStage
            return BusinessRuleStage(config)
        if stage_type == "pii_masking":
            from app.services.cleaning.stages.pii_masking import PIIMaskingStage
            return PIIMaskingStage(config)
        if stage_type == "quality_gate":
            from app.services.cleaning.stages.quality_gate import QualityGateStage
            return QualityGateStage(config)
        return None

    @staticmethod
    def available_stages() -> list[dict]:
        """返回可用阶段列表."""
        return [
            {"type": "standardize",   "label": "格式标准化",   "description": "trim/大小写/日期解析/类型转换/正则清理"},
            {"type": "imputation",    "label": "缺失值处理",   "description": "删除/常量/均值/中位数/前向填充 (Fit/Transform)"},
            {"type": "dedup",         "label": "去重",        "description": "精确匹配/模糊匹配/复合键"},
            {"type": "outliers",      "label": "异常值处理",   "description": "IQR截断/Z-score标记/IsolationForest"},
            {"type": "business_rules","label": "业务规则校验", "description": "DataFrame.eval 表达式 + 条件执行 + 三级严重度"},
            {"type": "pii_masking",   "label": "PII 安全脱敏", "description": "哈希/掩码/随机替换/数值泛化"},
            {"type": "quality_gate",  "label": "质量门控",    "description": "44+ 规则, 通过率阈值"},
        ]


# 全局单例
cleaning_pipeline = CleaningPipeline()
