"""Categorical columns with too many distinct values to one-hot encode."""

from __future__ import annotations

import pandas as pd

from mlclean.checks._common import is_textual
from mlclean.issues import INFO, MEDIUM, DataIssue


def check_high_cardinality(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows == 0:
        return issues
    for column, series in ctx.feature_series(df):
        if not is_textual(series) and not isinstance(series.dtype, pd.CategoricalDtype):
            continue
        n_unique = int(series.nunique())
        if n_unique > max(50, 0.1 * n_rows) and n_unique < n_rows:
            issues.append(
                DataIssue(
                    check="high_cardinality",
                    severity=MEDIUM if n_unique > 0.5 * n_rows else INFO,
                    columns=[column],
                    message=f"'{column}' has {n_unique:,} distinct categories.",
                    recommendation=(
                        "One-hot encoding will explode; prefer frequency or "
                        "target encoding, or group rare categories."
                    ),
                    details={"unique": n_unique},
                )
            )
    return issues
