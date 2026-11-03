"""Columns that carry no signal: a single value, or near enough to one."""

from __future__ import annotations

import pandas as pd

from mlclean.issues import LOW, MEDIUM, DataIssue

QUASI_CONSTANT_THRESHOLD = 0.99


def check_constant_columns(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows == 0:
        return issues

    for column in ctx.feature_columns(df):
        series = df[column]
        n_unique = series.nunique(dropna=False)
        if n_unique <= 1:
            issues.append(
                DataIssue(
                    check="constant_column",
                    severity=MEDIUM,
                    columns=[column],
                    message=f"'{column}' holds a single value — zero signal.",
                    recommendation="Drop it.",
                    details={"unique": int(n_unique)},
                )
            )
            continue
        top_rate = series.value_counts(dropna=False, normalize=True).iloc[0]
        if top_rate >= QUASI_CONSTANT_THRESHOLD:
            issues.append(
                DataIssue(
                    check="quasi_constant_column",
                    severity=LOW,
                    columns=[column],
                    message=(
                        f"'{column}' is {top_rate:.1%} one value — nearly constant."
                    ),
                    recommendation=(
                        "Drop it unless the rare values are exactly what the "
                        "model must catch."
                    ),
                    details={"top_value_rate": round(float(top_rate), 4)},
                )
            )
    return issues
