"""数据质量规则引擎 — 基于 Great Expectations + 自定义规则.

对标 DataWorks 数据质量 (37种规则模板)，Phase 1 实现 5 种核心校验:
  - not_null: 字段非空
  - range: 数值范围
  - regex: 格式校验
  - unique: 唯一性
  - custom_sql: 自定义 SQL 规则
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd


@dataclass
class QualityResult:
    """单条质量检查结果."""
    rule_name: str
    passed: bool
    total_rows: int
    failed_rows: int
    pass_rate: float
    message: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class QualityEngine:
    """数据质量引擎 — 对标 DataWorks 质量中心.

    使用方式:
        engine = QualityEngine()
        results = engine.check_dataframe(df, rules)
    """

    def check_dataframe(self, df: pd.DataFrame, rules: list[dict]) -> list[QualityResult]:
        """对 DataFrame 执行一组质量规则."""
        results = []
        for rule in rules:
            result = self._run_rule(df, rule)
            results.append(result)
        return results

    def _run_rule(self, df: pd.DataFrame, rule: dict) -> QualityResult:
        """执行单条规则."""
        rule_type = rule.get("type", "custom_sql")
        column = rule.get("column", "")
        name = rule.get("name", f"{rule_type}:{column}")

        try:
            if rule_type == "not_null":
                return self._check_not_null(df, column, name)
            elif rule_type == "range":
                return self._check_range(df, column, rule.get("min"), rule.get("max"), name)
            elif rule_type == "regex":
                return self._check_regex(df, column, rule.get("pattern", ""), name)
            elif rule_type == "unique":
                return self._check_unique(df, column, name)
            elif rule_type == "custom_sql":
                return self._check_custom(df, rule.get("condition", "1=1"), name)
            else:
                return QualityResult(
                    rule_name=name, passed=False, total_rows=len(df),
                    failed_rows=0, pass_rate=0,
                    message=f"未知规则类型: {rule_type}"
                )
        except Exception as e:
            return QualityResult(
                rule_name=name, passed=False, total_rows=len(df),
                failed_rows=0, pass_rate=0,
                message=f"规则执行异常: {str(e)}"
            )

    def _check_not_null(self, df: pd.DataFrame, column: str, name: str) -> QualityResult:
        """非空校验."""
        total = len(df)
        if column not in df.columns:
            return QualityResult(rule_name=name, passed=False, total_rows=total,
                                 failed_rows=total, pass_rate=0, message=f"列 '{column}' 不存在")
        nulls = int(df[column].isna().sum())
        passed = nulls == 0
        return QualityResult(
            rule_name=name, passed=passed, total_rows=total,
            failed_rows=nulls, pass_rate=round((total - nulls) / total * 100, 2) if total > 0 else 100,
            message="通过" if passed else f"发现 {nulls} 行空值"
        )

    def _check_range(self, df: pd.DataFrame, column: str, min_val: Optional[float], max_val: Optional[float], name: str) -> QualityResult:
        """范围校验."""
        total = len(df)
        if column not in df.columns:
            return QualityResult(rule_name=name, passed=False, total_rows=total,
                                 failed_rows=total, pass_rate=0, message=f"列 '{column}' 不存在")
        col = df[column]
        mask = pd.Series(True, index=df.index)
        if min_val is not None:
            mask &= col >= min_val
        if max_val is not None:
            mask &= col <= max_val
        failed = int((~mask).sum())
        passed = failed == 0
        return QualityResult(
            rule_name=name, passed=passed, total_rows=total,
            failed_rows=failed, pass_rate=round((total - failed) / total * 100, 2) if total > 0 else 100,
            message=f"通过 (范围: {min_val or '-∞'} ~ {max_val or '+∞'})" if passed else f"{failed} 行超出范围"
        )

    def _check_regex(self, df: pd.DataFrame, column: str, pattern: str, name: str) -> QualityResult:
        """格式校验."""
        total = len(df)
        if column not in df.columns:
            return QualityResult(rule_name=name, passed=False, total_rows=total,
                                 failed_rows=total, pass_rate=0, message=f"列 '{column}' 不存在")
        invalid = int((~df[column].astype(str).str.match(pattern)).sum())
        passed = invalid == 0
        return QualityResult(
            rule_name=name, passed=passed, total_rows=total,
            failed_rows=invalid, pass_rate=round((total - invalid) / total * 100, 2) if total > 0 else 100,
            message=f"格式校验通过" if passed else f"{invalid} 行格式不匹配"
        )

    def _check_unique(self, df: pd.DataFrame, column: str, name: str) -> QualityResult:
        """唯一性校验."""
        total = len(df)
        if column not in df.columns:
            return QualityResult(rule_name=name, passed=False, total_rows=total,
                                 failed_rows=total, pass_rate=0, message=f"列 '{column}' 不存在")
        dupes = int(df[column].duplicated().sum())
        passed = dupes == 0
        return QualityResult(
            rule_name=name, passed=passed, total_rows=total,
            failed_rows=dupes, pass_rate=round((total - dupes) / total * 100, 2) if total > 0 else 100,
            message="无重复值" if passed else f"发现 {dupes} 行重复"
        )

    def _check_custom(self, df: pd.DataFrame, condition: str, name: str) -> QualityResult:
        """自定义条件校验 (SQL-like expression on DataFrame)."""
        total = len(df)
        try:
            # 使用 pandas query 方法执行条件
            passed_mask = df.eval(condition)
            failed = int((~passed_mask).sum())
            is_pass = failed == 0
            return QualityResult(
                rule_name=name, passed=is_pass, total_rows=total,
                failed_rows=failed, pass_rate=round((total - failed) / total * 100, 2) if total > 0 else 100,
                message=f"条件 '{condition}' 通过" if is_pass else f"{failed} 行不满足条件"
            )
        except Exception as e:
            return QualityResult(
                rule_name=name, passed=False, total_rows=total,
                failed_rows=total, pass_rate=0,
                message=f"条件执行错误: {str(e)}"
            )


# 全局引擎实例
quality_engine = QualityEngine()
