"""Duplicate-row checks."""

from __future__ import annotations

import pandas as pd

from mlclean.issues import HIGH, MEDIUM, DataIssue


def check_duplicates(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows == 0:
        return issues

    n_exact = int(df.duplicated().sum())
    if n_exact:
        rate = n_exact / n_rows
        issues.append(
            DataIssue(
                check="duplicate_rows",
                severity=HIGH if rate >= 0.01 else MEDIUM,
                message=f"{n_exact:,} exact duplicate rows ({rate:.1%}).",
                recommendation=(
                    "Deduplicate before splitting — duplicates shared across "
                    "train and test inflate every metric."
                ),
                details={"duplicates": n_exact, "rate": round(rate, 4)},
            )
        )

    # duplicates ignoring id columns: same observation recorded twice under
    # different identifiers
    id_like = [c for c in ctx.id_columns if c in df.columns]
    if id_like:
        feature_cols = [c for c in df.columns if c not in id_like]
        if feature_cols:
            n_near = int(df.duplicated(subset=feature_cols).sum())
            if n_near > n_exact:
                issues.append(
                    DataIssue(
                        check="duplicate_rows_ignoring_ids",
                        severity=MEDIUM,
                        columns=id_like,
                        message=(
                            f"{n_near - n_exact:,} additional rows are identical "
                            f"once id columns ({', '.join(id_like)}) are ignored."
                        ),
                        recommendation="Check whether the same record was ingested more than once.",
                        details={"duplicates_ignoring_ids": n_near},
                    )
                )
    return issues
