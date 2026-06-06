"""③ 去重 — 对标 Trifacta cluster + DataBrew dedup.

支持策略: exact (精确hash) / fuzzy (编辑距离) / composite (复合键)
"""

import pandas as pd

from app.services.cleaning.models import BaseStage, StageResult


class DedupStage(BaseStage):
    """去重阶段 — 检测并删除重复行."""

    name = "dedup"

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, StageResult]:
        strategy = self.config.get("strategy", "exact")
        match_columns = self.config.get("match_columns", [])
        keep = self.config.get("keep", "first")
        threshold = self.config.get("similarity_threshold", 0.85)
        blocking_key = self.config.get("blocking_key", "")

        if not match_columns:
            match_columns = list(df.columns)

        rows_before = len(df)

        if strategy == "exact":
            result_df = df.drop_duplicates(subset=match_columns, keep=keep)
            duplicates_found = rows_before - len(result_df)

        elif strategy == "fuzzy":
            result_df, dup_groups = self._fuzzy_dedup(df, match_columns, threshold, keep, blocking_key)
            duplicates_found = rows_before - len(result_df)

        elif strategy == "composite":
            # 多列拼成 hash 键
            df_copy = df.copy()
            df_copy["_composite_key"] = df_copy[match_columns].astype(str).apply(
                lambda row: "_".join(row.values), axis=1
            )
            result_df = df_copy.drop_duplicates(subset=["_composite_key"], keep=keep)
            result_df = result_df.drop(columns=["_composite_key"])
            duplicates_found = rows_before - len(result_df)

        else:
            result_df = df
            duplicates_found = 0

        status = "success"
        if duplicates_found > 0:
            status = "warning"

        return result_df, StageResult(
            stage_name=self.name,
            status=status,
            rows_in=rows_before,
            rows_out=len(result_df),
            rows_dropped=duplicates_found,
            details={
                "strategy": strategy,
                "match_columns": match_columns,
                "keep": keep,
                "threshold": threshold if strategy == "fuzzy" else None,
                "duplicates_found": duplicates_found,
            },
        )

    def _fuzzy_dedup(self, df: pd.DataFrame, columns: list[str],
                     threshold: float, keep: str, blocking_key: str
                     ) -> tuple[pd.DataFrame, list[dict]]:
        """模糊去重 — 使用编辑距离匹配相似行."""
        try:
            from Levenshtein import distance as levenshtein
        except ImportError:
            # 回退到纯 Python 实现
            def levenshtein(a: str, b: str) -> int:
                if len(a) < len(b):
                    return levenshtein(b, a)
                if len(b) == 0:
                    return len(a)
                prev = range(len(b) + 1)
                for i, ca in enumerate(a):
                    curr = [i + 1]
                    for j, cb in enumerate(b):
                        curr.append(min(
                            prev[j + 1] + 1, curr[j] + 1,
                            prev[j] + (ca != cb)
                        ))
                    prev = curr
                return prev[-1]

        df = df.copy().reset_index(drop=True)
        n = len(df)

        # Blocking key 优化: O(n²) → O(n × m²)
        if blocking_key and blocking_key in df.columns:
            groups = df.groupby(blocking_key)
            all_indices = []
            for _, group in groups:
                indices = list(group.index)
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        all_indices.append((indices[i], indices[j]))
            pairs = all_indices
        else:
            pairs = [(i, j) for i in range(n) for j in range(i + 1, min(i + 100, n))]

        # 找重复对
        dup_map: dict[int, int] = {}  # idx → group_id
        group_id = 0

        for i, j in pairs:
            if i in dup_map and j in dup_map:
                continue
            str_a = " ".join(str(df.iloc[i][c]) for c in columns)
            str_b = " ".join(str(df.iloc[j][c]) for c in columns)
            max_len = max(len(str_a), len(str_b))
            if max_len == 0:
                continue
            similarity = 1 - levenshtein(str_a, str_b) / max_len
            if similarity >= threshold:
                if i in dup_map:
                    dup_map[j] = dup_map[i]
                elif j in dup_map:
                    dup_map[i] = dup_map[j]
                else:
                    group_id += 1
                    dup_map[i] = group_id
                    dup_map[j] = group_id

        # 保留策略
        if keep == "most_complete":
            df["_completeness"] = df.notna().sum(axis=1)
            for idx in sorted(dup_map.keys(), key=lambda x: df.iloc[x]["_completeness"], reverse=True):
                group = dup_map[idx]
                for other_idx, g in list(dup_map.items()):
                    if g == group and other_idx != idx:
                        dup_map[other_idx] = idx  # 指向最完整的行
            df = df.drop(columns=["_completeness"])

        # 删除重复行
        drop_indices = set()
        seen_groups = set()
        for idx in sorted(dup_map.keys()):
            g = dup_map[idx]
            if g in seen_groups:
                drop_indices.add(idx)
            else:
                seen_groups.add(g)

        return df.drop(index=drop_indices), []
