"""Disguised missing values: sentinels like -999 or 'unknown' standing in
for nulls. They pass every NaN check and then poison statistics and models."""

from __future__ import annotations

import pandas as pd

from mlclean.checks.types import _is_textual
from mlclean.issues import MEDIUM, DataIssue

_NUMERIC_SENTINELS = {
    -1.0, -9.0, -99.0, -999.0, -9999.0, -99999.0,
    9.0, 99.0, 999.0, 9999.0, 99999.0,
}
_TEXT_SENTINELS = {
    "", "na", "n/a", "none", "null", "nan", "nil", "missing",
    "unknown", "undefined", "?", "-", "--", ".",
}


def _detached(value: float, others: pd.Series) -> bool:
    """True when the value sits far outside where the rest of the data lives."""
    q1, q3 = others.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return False
    return value < q1 - 3.0 * iqr or value > q3 + 3.0 * iqr


def check_disguised_missing(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows < 50:
        return issues

    for column in ctx.feature_columns(df):
        series = df[column].dropna()
        if series.empty:
            continue

        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(
            series
        ):
            # only continuous-looking measurements; {-1, 0, 1} codes are not sentinels
            if series.nunique() < 10:
                continue
            suspects = []
            counts = series.value_counts()
            for value, count in counts.head(20).items():
                v = float(value)
                if not v.is_integer() or v not in _NUMERIC_SENTINELS:
                    continue
                if count / len(series) < 0.01:
                    continue
                if v != series.min() and v != series.max():
                    continue
                others = series[series != value]
                if others.nunique() >= 5 and _detached(v, others):
                    suspects.append((v, int(count)))
            if suspects:
                listed = ", ".join(f"{int(v)} (×{c:,})" for v, c in suspects)
                issues.append(
                    DataIssue(
                        check="disguised_missing",
                        severity=MEDIUM,
                        columns=[column],
                        message=(
                            f"'{column}' contains sentinel-looking values far "
                            f"outside its distribution: {listed}. These usually "
                            "encode 'missing', not real measurements."
                        ),
                        recommendation=(
                            "Confirm with the data source, then replace them "
                            "with NaN before imputing — otherwise every mean, "
                            "fence and model sees them as real numbers."
                        ),
                        details={"values": {str(int(v)): c for v, c in suspects}},
                    )
                )
        elif _is_textual(series):
            values = series[series.map(lambda v: isinstance(v, str))]
            if values.empty:
                continue
            lowered = values.str.strip().str.lower()
            hits = lowered[lowered.isin(_TEXT_SENTINELS)]
            if len(hits) and len(hits) / len(values) >= 0.005:
                found = sorted(hits.unique())
                issues.append(
                    DataIssue(
                        check="disguised_missing",
                        severity=MEDIUM,
                        columns=[column],
                        message=(
                            f"'{column}' has {len(hits):,} values "
                            f"({len(hits) / len(values):.1%}) that read as "
                            f"missing but aren't NaN: {', '.join(repr(f) for f in found[:5])}."
                        ),
                        recommendation=(
                            "Replace them with NaN so missing-value handling "
                            "sees them; as text they become ordinary categories."
                        ),
                        details={"tokens": found, "count": len(hits)},
                    )
                )
    return issues
