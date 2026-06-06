"""⑥ PII 安全脱敏 — 对标 DataBrew PII/Security 操作.

支持: hash/mask_range/mask_email/mask_date/random_replace/shuffle/drop_column/round_number
"""

import hashlib
import random

import pandas as pd
from app.services.cleaning.models import BaseStage, StageResult


class PIIMaskingStage(BaseStage):
    """PII 安全脱敏阶段."""

    name = "pii_masking"

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
        operations = self.config.get("operations", [])
        if not operations:
            return df, StageResult(
                stage_name=self.name, status="success",
                rows_in=len(df), rows_out=len(df),
                details={"message": "无操作"}
            )

        result_df = df.copy()
        applied: list[str] = []

        for op in operations:
            col = op.get("column", "")
            action = op.get("action", "")
            applied.append(f"{col}:{action}")

            if action == "drop_column":
                if col in result_df.columns:
                    result_df = result_df.drop(columns=[col])

            elif action == "hash":
                if col in result_df.columns:
                    result_df[col] = result_df[col].astype(str).apply(
                        lambda s: hashlib.sha256(s.encode()).hexdigest()[:16]
                    )

            elif action == "mask_range":
                keep_prefix = op.get("keep_prefix", 3)
                keep_suffix = op.get("keep_suffix", 4)
                if col in result_df.columns:
                    result_df[col] = result_df[col].astype(str).apply(
                        lambda s, p=keep_prefix, sf=keep_suffix:
                        s[:p] + "*" * max(1, len(s) - p - sf) + s[-sf:] if len(s) > p + sf else s
                    )

            elif action == "mask_email":
                if col in result_df.columns:
                    result_df[col] = result_df[col].astype(str).apply(_mask_email)

            elif action == "mask_date":
                if col in result_df.columns:
                    result_df[col] = result_df[col].apply(
                        lambda v: f"{str(v)[:4]}-01-01" if pd.notna(v) else v
                    )

            elif action == "random_replace":
                if col in result_df.columns:
                    unique_vals = result_df[col].dropna().unique()
                    if len(unique_vals) > 0:
                        mapping = {v: f"用户_{random.randint(1000, 9999)}" for v in unique_vals}
                        result_df[col] = result_df[col].map(mapping).fillna(result_df[col])

            elif action == "shuffle":
                if col in result_df.columns:
                    vals = result_df[col].values.copy()
                    random.shuffle(vals)
                    result_df[col] = vals

            elif action == "round_number":
                precision = op.get("precision", -3)
                if col in result_df.columns:
                    result_df[col] = pd.to_numeric(result_df[col], errors="coerce")
                    result_df[col] = result_df[col].apply(
                        lambda v: round(v, precision) if pd.notna(v) else v
                    )

        return result_df, StageResult(
            stage_name=self.name,
            status="success",
            rows_in=len(df),
            rows_out=len(result_df),
            rows_affected=len(df),
            details={"operations_applied": len(operations), "applied": applied},
        )


def _mask_email(email: str) -> str:
    """邮箱掩码: zhang@test.com → z***@test.com."""
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return local[0] + "***" + f"@{domain}"
