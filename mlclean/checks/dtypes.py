"""Columns whose stored type fights their content: several Python types in
one column, or numbers kept as text."""

from __future__ import annotations

import math

import pandas as pd

from mlclean.checks._common import is_textual
from mlclean.issues import LOW, MEDIUM, DataIssue


def _floor_pct(rate: float) -> str:
    """Round a rate down, so a parse rate of 0.9984 never reads '100%' above
    advice to go and inspect the values that didn't parse."""
    if rate >= 1.0:
        return "100%"
    return f"{math.floor(rate * 1000) / 10:g}%"


def check_mixed_types(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    for column in ctx.feature_columns(df):
        series = df[column].dropna()
        if series.empty or not is_textual(series):
            continue
        kinds = {type(v).__name__ for v in series.head(1000)}
        if len(kinds) > 1:
            issues.append(
                DataIssue(
                    check="mixed_types",
                    severity=MEDIUM,
                    columns=[column],
                    message=(
                        f"'{column}' mixes Python types ({', '.join(sorted(kinds))}) "
                        "inside one column."
                    ),
                    recommendation="Coerce to one type explicitly before encoding.",
                    details={"types": sorted(kinds)},
                )
            )
            continue
        # numbers stored as strings
        numeric = pd.to_numeric(series, errors="coerce")
        parse_rate = float(numeric.notna().mean())
        if parse_rate >= 0.95 and series.nunique() > 10:
            unparsed = int(numeric.isna().sum())
            issues.append(
                DataIssue(
                    check="numeric_stored_as_text",
                    severity=LOW if parse_rate == 1.0 else MEDIUM,
                    columns=[column],
                    message=(
                        f"'{column}' is text but {_floor_pct(parse_rate)} of "
                        "values parse as numbers"
                        + (
                            f" ({unparsed:,} of {len(series):,} do not)."
                            if unparsed
                            else "."
                        )
                    ),
                    recommendation=(
                        f"Convert with pd.to_numeric; inspect the {unparsed:,} "
                        "non-numeric values first, since a bare call raises on them."
                        if unparsed
                        else "Convert with pd.to_numeric."
                    ),
                    details={
                        "parse_rate": round(parse_rate, 4),
                        "unparsed": unparsed,
                    },
                )
            )
    return issues
