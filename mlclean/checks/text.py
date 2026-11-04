"""Text hygiene: padding and letter case that split one category into two."""

from __future__ import annotations

import pandas as pd

from mlclean.checks._common import is_textual
from mlclean.issues import LOW, DataIssue


def check_text_hygiene(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    for column, values in ctx.feature_series(df):
        series = values.dropna()
        if series.empty or not is_textual(series):
            continue
        values = series[series.map(lambda v: isinstance(v, str))]
        if values.empty:
            continue
        n_padded = int((values != values.str.strip()).sum())
        if n_padded:
            issues.append(
                DataIssue(
                    check="whitespace_padding",
                    severity=LOW,
                    columns=[column],
                    message=(
                        f"'{column}' has {n_padded:,} values with leading or "
                        "trailing whitespace — ' yes' and 'yes' become two categories."
                    ),
                    recommendation="Strip whitespace before encoding.",
                    details={"padded_values": n_padded},
                )
            )
        lowered = values.str.strip().str.lower()
        n_case_collisions = int(values.str.strip().nunique() - lowered.nunique())
        if n_case_collisions > 0:
            issues.append(
                DataIssue(
                    check="case_inconsistency",
                    severity=LOW,
                    columns=[column],
                    message=(
                        f"'{column}' has {n_case_collisions} categories that "
                        "differ only by letter case."
                    ),
                    recommendation="Normalize case before encoding.",
                    details={"case_collisions": n_case_collisions},
                )
            )
    return issues
