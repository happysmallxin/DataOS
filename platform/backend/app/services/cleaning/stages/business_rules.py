"""⑤ 业务规则校验 — 对标 DLT Expectations + dbt tests.

支持: 条件执行 + 三级严重度 (warn/drop/fail)
"""

import pandas as pd
from app.services.cleaning.models import BaseStage, StageResult, Severity


class BusinessRuleStage(BaseStage):
    """业务规则校验阶段 — DataFrame.eval 表达式 + 三级严重度."""

    name = "business_rules"

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
        rules = self.config.get("rules", [])
        on_failure = self.config.get("on_failure", "flag")

        if not rules:
            return df, StageResult(
                stage_name=self.name, status="success",
                rows_in=len(df), rows_out=len(df),
                details={"message": "无规则"}
            )

        result_df = df.copy()
        severity_summary: dict[str, dict] = {"warn": {"rules": 0, "affected_rows": 0},
                                               "drop": {"rules": 0, "dropped_rows": 0},
                                               "fail": {"rules": 0, "triggered": False}}
        rule_results: list[dict] = []
        total_violations = 0
        dropped_indices: set[int] = set()

        for rule in rules:
            name = rule.get("name", "未命名规则")
            condition = rule.get("condition", "")
            severity: Severity = rule.get("severity", "warn")
            rule_type = rule.get("type", "expression")

            try:
                if rule_type == "expression":
                    mask = result_df.eval(condition)
                elif rule_type == "regex":
                    col = rule.get("column", "")
                    pattern = rule.get("pattern", "")
                    mask = result_df[col].astype(str).str.match(pattern, na=False)
                elif rule_type == "in_set":
                    col = rule.get("column", "")
                    values = rule.get("values", [])
                    mask = result_df[col].isin(values)
                else:
                    mask = result_df.eval(condition)

                violated = (~mask).sum()
                total_violations += violated

                if severity == "drop" and violated > 0:
                    drop_idx = result_df[~mask].index.tolist()
                    dropped_indices.update(drop_idx)
                    severity_summary["drop"]["rules"] += 1
                    severity_summary["drop"]["dropped_rows"] += violated

                elif severity == "fail" and violated > 0:
                    severity_summary["fail"]["rules"] += 1
                    severity_summary["fail"]["triggered"] = True

                elif severity == "warn" and violated > 0:
                    severity_summary["warn"]["rules"] += 1
                    severity_summary["warn"]["affected_rows"] += violated

                rule_results.append({
                    "name": name, "condition": condition,
                    "severity": severity, "total": len(result_df),
                    "violated": int(violated), "passed": bool(violated == 0),
                })

            except Exception as e:
                rule_results.append({
                    "name": name, "condition": condition,
                    "severity": severity, "error": str(e), "passed": False,
                })

        # 删除 drop 级别的行
        if dropped_indices:
            result_df = result_df.drop(index=list(dropped_indices))

        # 判断阶段状态
        if severity_summary["fail"]["triggered"]:
            status = "failed"
        elif severity_summary["drop"]["dropped_rows"] > 0 or severity_summary["warn"]["affected_rows"] > 0:
            status = "warning"
        else:
            status = "success"

        return result_df, StageResult(
            stage_name=self.name,
            status=status,
            rows_in=len(df),
            rows_out=len(result_df),
            rows_dropped=len(dropped_indices),
            rows_affected=total_violations,
            details={
                "rules_total": len(rules),
                "rules_passed": sum(1 for r in rule_results if r.get("passed")),
                "rules_failed": sum(1 for r in rule_results if not r.get("passed")),
                "total_violations": total_violations,
                "per_rule": rule_results,
            },
            severity_summary=severity_summary,
        )
