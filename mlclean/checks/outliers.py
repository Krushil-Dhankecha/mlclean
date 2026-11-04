"""Numeric outlier detection (IQR fences)."""

from __future__ import annotations

import pandas as pd

from mlclean.issues import INFO, LOW, DataIssue


def check_outliers(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows < 20:
        return issues

    for column, series in ctx.feature_series(df):
        if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(
            series
        ):
            continue
        values = series.dropna()
        if values.nunique() < 10:
            continue  # discrete codes, not a continuous measurement
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr == 0:
            continue
        low_fence = q1 - 3.0 * iqr
        high_fence = q3 + 3.0 * iqr
        n_out = int(((values < low_fence) | (values > high_fence)).sum())
        if n_out == 0:
            continue
        rate = n_out / len(values)
        skew = float(values.skew())
        issue = DataIssue(
            check="outliers",
            severity=LOW if rate >= 0.001 else INFO,
            columns=[column],
            message=(
                f"'{column}' has {n_out:,} values ({rate:.2%}) outside "
                f"[{low_fence:,.4g}, {high_fence:,.4g}] (3×IQR fences)."
            ),
            recommendation=(
                "Inspect before touching them — cap/winsorize or log-transform "
                "only if they are errors, not real extremes."
            ),
            details={
                "outliers": n_out,
                "rate": round(rate, 5),
                "low_fence": float(low_fence),
                "high_fence": float(high_fence),
            },
        )
        issues.append(issue)
        if abs(skew) > 3 and (values > 0).all():
            issues.append(
                DataIssue(
                    check="skewed_feature",
                    severity=INFO,
                    columns=[column],
                    message=f"'{column}' is heavily skewed (skew {skew:.1f}).",
                    recommendation=(
                        "A log or sqrt transform helps linear models; tree "
                        "models don't care."
                    ),
                    details={"skew": round(skew, 2)},
                )
            )
    return issues


def iqr_fences(values: pd.Series, k: float = 3.0) -> tuple[float, float]:
    """Return the (low, high) IQR fences used by the outlier check."""
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    return float(q1 - k * iqr), float(q3 + k * iqr)
