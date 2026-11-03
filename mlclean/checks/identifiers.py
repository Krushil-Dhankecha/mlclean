"""Columns that identify records instead of describing them."""

from __future__ import annotations

import pandas as pd

from mlclean.checks._common import is_textual
from mlclean.issues import MEDIUM, DataIssue


def check_id_columns(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows < 10:
        return issues

    declared = set(ctx.id_columns)
    for column in ctx.feature_columns(df):
        if column in declared:
            continue
        series = df[column].dropna()
        if series.empty:
            continue
        unique_rate = series.nunique() / len(series)
        name = column.lower()
        looks_like_id = name == "id" or name.endswith(("_id", "id")) or "uuid" in name
        # a continuous float measurement is naturally all-unique; only
        # integer-like or textual columns read as identifiers
        identifier_shaped = is_textual(series) or pd.api.types.is_integer_dtype(series)
        if (unique_rate == 1.0 and identifier_shaped) or (
            unique_rate > 0.95 and looks_like_id
        ):
            issues.append(
                DataIssue(
                    check="id_column",
                    severity=MEDIUM,
                    columns=[column],
                    message=(
                        f"'{column}' is unique for {unique_rate:.1%} of rows — "
                        "it identifies records rather than describing them."
                    ),
                    recommendation=(
                        "Exclude it from features; models memorize identifiers "
                        "and that memorization is leakage."
                    ),
                    details={"unique_rate": round(float(unique_rate), 4)},
                )
            )
    return issues
