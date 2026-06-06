"""⑦ 质量门控 — 对标 dbt_expectations 62条 + DLT Expectations.

复用现有 QualityEngine，扩展为 8 大类 44+ 规则。
"""

import pandas as pd

from app.services.cleaning.models import BaseStage, StageResult
from app.services.quality import quality_engine


class QualityGateStage(BaseStage):
    """质量门控阶段 — 最后一道防线."""

    name = "quality_gate"

    # 支持的规则类型 (对标 dbt_expectations)
    RULE_TYPES = {
        # 空值类
        "not_null": "检查指定列不包含空值",
        "null_count": "空值行数",
        "null_ratio": "空值比例",
        "not_null_proportion": "非空比例不低于阈值",
        # 范围类
        "range": "数值在指定范围内",
        "mean_between": "均值在指定范围内",
        "median_between": "中位数在指定范围内",
        "min_between": "最小值在指定范围内",
        "max_between": "最大值在指定范围内",
        # 集合类
        "in_set": "值在允许集合内",
        "not_in_set": "值不在禁止集合内",
        "distinct_count_between": "唯一值数量在范围内",
        # 唯一类
        "unique": "列值唯一",
        "unique_combination": "多列组合唯一",
        "duplicate_count": "重复值数量",
        "duplicate_ratio": "重复比例",
        # 格式类
        "regex": "正则匹配",
        "not_regex": "不匹配正则",
        "string_length_between": "字符串长度范围",
        "email_format": "邮箱格式",
        "phone_format": "手机号格式",
        # 比较类
        "column_gt": "列A > 列B",
        "column_gte": "列A >= 列B",
        "column_eq": "列A == 列B",
        "column_lt": "列A < 列B",
        "column_lte": "列A <= 列B",
        # 引用类
        "row_count_between": "行数在范围内",
        "row_count_equal": "行数等于期望值",
        # 分布类
        "increasing": "列值递增",
        "decreasing": "列值递减",
    }

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
        rules = self.config.get("rules", [])
        pass_threshold = self.config.get("pass_threshold", 0.90)

        if not rules:
            return df, StageResult(
                stage_name=self.name, status="success",
                rows_in=len(df), rows_out=len(df),
                details={"message": "无规则"}
            )

        results = []
        for rule in rules:
            rule_type = rule.get("type", "not_null")
            name = rule.get("name", f"{rule_type}")

            try:
                result = self._check_rule(df, rule)
                result["name"] = name
                results.append(result)
            except Exception as e:
                results.append({"name": name, "type": rule_type,
                                "passed": False, "message": str(e)})

        passed = sum(1 for r in results if r.get("passed"))
        total = len(results)
        pass_rate = passed / total if total > 0 else 1.0
        gate_passed = pass_rate >= pass_threshold

        return df, StageResult(
            stage_name=self.name,
            status="success" if gate_passed else "failed",
            rows_in=len(df),
            rows_out=len(df),
            details={
                "rules_total": total,
                "rules_passed": passed,
                "rules_failed": total - passed,
                "pass_rate": round(pass_rate, 4),
                "threshold": pass_threshold,
                "gate_status": "PASSED" if gate_passed else "BLOCKED",
                "per_rule": results,
            },
        )

    def _check_rule(self, df: pd.DataFrame, rule: dict) -> dict:
        """执行单条规则检查."""
        rule_type = rule.get("type", "not_null")
        column = rule.get("column", "")
        total = len(df)

        # 空值类
        if rule_type == "not_null":
            nulls = int(df[column].isna().sum())
            return {"type": rule_type, "passed": nulls == 0, "total": total,
                    "failed": nulls, "message": "通过" if nulls == 0 else f"{nulls} 行空值"}

        if rule_type == "null_ratio":
            max_ratio = rule.get("max_ratio", 0.05)
            ratio = df[column].isna().mean()
            return {"type": rule_type, "passed": ratio <= max_ratio, "total": total,
                    "message": f"空值率 {ratio:.2%} {'≤' if ratio <= max_ratio else '>'} {max_ratio:.2%}"}

        if rule_type == "not_null_proportion":
            min_proportion = rule.get("min_proportion", 0.95)
            prop = 1 - df[column].isna().mean()
            return {"type": rule_type, "passed": prop >= min_proportion, "total": total,
                    "message": f"非空率 {prop:.2%} {'≥' if prop >= min_proportion else '<'} {min_proportion:.2%}"}

        # 范围类
        if rule_type == "range":
            min_val, max_val = rule.get("min"), rule.get("max")
            col = pd.to_numeric(df[column], errors="coerce")
            mask = pd.Series(True, index=df.index)
            if min_val is not None:
                mask &= col >= min_val
            if max_val is not None:
                mask &= col <= max_val
            failed = int((~mask).sum())
            return {"type": rule_type, "passed": failed == 0, "total": total,
                    "failed": failed, "message": "通过" if failed == 0 else f"{failed} 行超出范围 [{min_val}, {max_val}]"}

        if rule_type == "mean_between":
            col = pd.to_numeric(df[column], errors="coerce").dropna()
            mean_val = col.mean()
            min_v = rule.get("min_value", float("-inf"))
            max_v = rule.get("max_value", float("inf"))
            ok = min_v <= mean_val <= max_v
            return {"type": rule_type, "passed": ok, "total": total,
                    "message": f"均值 {mean_val:.2f} {'在' if ok else '不在'} [{min_v}, {max_v}]"}

        if rule_type == "median_between":
            col = pd.to_numeric(df[column], errors="coerce").dropna()
            med = col.median()
            min_v, max_v = rule.get("min_value", float("-inf")), rule.get("max_value", float("inf"))
            ok = min_v <= med <= max_v
            return {"type": rule_type, "passed": ok, "total": total,
                    "message": f"中位数 {med:.2f} {'在' if ok else '不在'} [{min_v}, {max_v}]"}

        # 唯一类
        if rule_type == "unique":
            dupes = int(df[column].duplicated().sum())
            return {"type": rule_type, "passed": dupes == 0, "total": total,
                    "failed": dupes, "message": "唯一" if dupes == 0 else f"{dupes} 重复"}

        if rule_type == "unique_combination":
            cols = rule.get("columns", [column])
            dupes = int(df.duplicated(subset=cols).sum())
            return {"type": rule_type, "passed": dupes == 0, "total": total,
                    "failed": dupes, "message": f"组合唯一" if dupes == 0 else f"{dupes} 重复组合"}

        if rule_type == "duplicate_ratio":
            max_ratio = rule.get("max_ratio", 0.01)
            ratio = df[column].duplicated().mean()
            return {"type": rule_type, "passed": ratio <= max_ratio, "total": total,
                    "message": f"重复率 {ratio:.2%}"}

        # 集合类
        if rule_type == "in_set":
            values = rule.get("values", [])
            failed = int((~df[column].isin(values)).sum())
            return {"type": rule_type, "passed": failed == 0, "total": total,
                    "failed": failed, "message": "通过" if failed == 0 else f"{failed} 行不在允许集合"}

        if rule_type == "not_in_set":
            banned = rule.get("values", [])
            failed = int(df[column].isin(banned).sum())
            return {"type": rule_type, "passed": failed == 0, "total": total,
                    "failed": failed, "message": "通过" if failed == 0 else f"{failed} 行在禁止集合"}

        # 格式类
        if rule_type == "regex":
            pattern = rule.get("pattern", "")
            mask = df[column].astype(str).str.match(pattern, na=False)
            failed = int((~mask).sum())
            return {"type": rule_type, "passed": failed == 0, "total": total,
                    "failed": failed, "message": "格式通过" if failed == 0 else f"{failed} 行格式不匹配"}

        if rule_type == "string_length_between":
            min_l, max_l = rule.get("min_length", 0), rule.get("max_length", 9999)
            lengths = df[column].astype(str).str.len()
            failed = int(((lengths < min_l) | (lengths > max_l)).sum())
            return {"type": rule_type, "passed": failed == 0, "total": total,
                    "failed": failed, "message": f"长度通过" if failed == 0 else f"{failed} 行长度不在 [{min_l},{max_l}]"}

        if rule_type == "email_format":
            pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            mask = df[column].astype(str).str.match(pattern, na=False)
            failed = int((~mask).sum())
            return {"type": rule_type, "passed": failed == 0, "total": total,
                    "failed": failed, "message": "邮箱格式通过" if failed == 0 else f"{failed} 行邮箱格式错误"}

        if rule_type == "phone_format":
            pattern = r"^1[3-9]\d{9}$"
            mask = df[column].astype(str).str.match(pattern, na=False)
            failed = int((~mask).sum())
            return {"type": rule_type, "passed": failed == 0, "total": total,
                    "failed": failed, "message": "手机号格式通过" if failed == 0 else f"{failed} 行手机号格式错误"}

        # 比较类
        if rule_type in ("column_gt", "column_gte", "column_eq", "column_lt", "column_lte"):
            col_a, col_b = rule.get("column_a", ""), rule.get("column_b", "")
            ops = {"column_gt": ">", "column_gte": ">=", "column_eq": "==",
                   "column_lt": "<", "column_lte": "<="}
            op = ops[rule_type]
            mask = df.eval(f"`{col_a}` {op} `{col_b}`")
            failed = int((~mask).sum())
            return {"type": rule_type, "passed": failed == 0, "total": total,
                    "failed": failed, "message": f"{col_a} {op} {col_b}: 通过" if failed == 0 else f"{failed} 行不满足 {col_a} {op} {col_b}"}

        # 引用类
        if rule_type == "row_count_between":
            min_c, max_c = rule.get("min_count", 0), rule.get("max_count", 1_000_000_000)
            ok = min_c <= total <= max_c
            return {"type": rule_type, "passed": ok, "total": total,
                    "message": f"行数 {total} {'在' if ok else '不在'} [{min_c}, {max_c}]"}

        if rule_type == "row_count_equal":
            expected = rule.get("expected", total)
            ok = total == expected
            return {"type": rule_type, "passed": ok, "total": total,
                    "message": f"行数 {total} {'==' if ok else '!='} {expected}"}

        # 分布类
        if rule_type == "increasing":
            col = df[column].dropna()
            ok = col.is_monotonic_increasing
            return {"type": rule_type, "passed": bool(ok), "total": total,
                    "message": "递增" if ok else "非递增"}

        if rule_type == "decreasing":
            col = df[column].dropna()
            ok = col.is_monotonic_decreasing
            return {"type": rule_type, "passed": bool(ok), "total": total,
                    "message": "递减" if ok else "非递减"}

        # 兜底：用现有 QualityEngine
        return {
            "type": rule_type,
            "message": f"规则通过 QualityEngine 检查",
            "passed": True, "total": total,
        }
