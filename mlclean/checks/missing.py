"""Missing-value checks."""

from __future__ import annotations

import pandas as pd

from mlclean.issues import HIGH, INFO, MEDIUM, DataIssue


def check_missing(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows == 0:
        return issues

    for column in ctx.feature_columns(df):
        n_missing = int(df[column].isna().sum())
        if n_missing == 0:
            continue
        rate = n_missing / n_rows
        if rate >= ctx.missing_threshold:
            severity, action = HIGH, (
                "Drop the column, impute, or add a missing indicator — at this "
                "rate the raw column carries more absence than signal."
            )
        elif rate >= 0.05:
            severity, action = MEDIUM, (
                "Impute (median for numeric, mode or a 'missing' category for "
                "categorical) and consider a missing indicator."
            )
        else:
            severity, action = INFO, "Impute or let the model's NA handling cover it."
        issues.append(
            DataIssue(
                check="missing_values",
                severity=severity,
                columns=[column],
                message=f"'{column}' is missing in {n_missing:,} rows ({rate:.1%}).",
                recommendation=action,
                details={"missing": n_missing, "rate": round(rate, 4)},
            )
        )

    if ctx.target and ctx.target in df.columns:
        n_target_missing = int(df[ctx.target].isna().sum())
        if n_target_missing:
            issues.append(
                DataIssue(
                    check="missing_target",
                    severity=HIGH,
                    columns=[ctx.target],
                    message=(
                        f"Target '{ctx.target}' is missing in "
                        f"{n_target_missing:,} rows ({n_target_missing / n_rows:.1%})."
                    ),
                    recommendation="Drop unlabeled rows before training; never impute the target.",
                    details={"missing": n_target_missing},
                )
            )
    return issues
