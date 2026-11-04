"""Problems with the column labels themselves, rather than with the values
underneath them."""

from __future__ import annotations

from collections import Counter

import pandas as pd

from mlclean.issues import MEDIUM, DataIssue


def check_duplicate_column_names(df: pd.DataFrame, ctx) -> list[DataIssue]:
    counts = Counter(df.columns)
    repeated = {label: n for label, n in counts.items() if n > 1}
    if not repeated:
        return []

    listed = ", ".join(
        f"'{label}' ×{n}"
        for label, n in sorted(repeated.items(), key=lambda kv: str(kv[0]))
    )
    positions = {
        str(label): [i for i, c in enumerate(df.columns) if c == label]
        for label in repeated
    }
    return [
        DataIssue(
            check="duplicate_column_names",
            severity=MEDIUM,
            columns=sorted(str(label) for label in repeated),
            message=(
                f"{len(repeated)} column label(s) appear more than once: {listed}. "
                "Selecting one by name returns every copy, so anything downstream "
                "that expects a single column gets a frame instead."
            ),
            recommendation=(
                "Rename or drop the copies — a suffixed join or "
                "df.columns = make_unique(df.columns) — before encoding or "
                "training. Until then the duplicates are indistinguishable by "
                "name in any report, including this one."
            ),
            details={"positions": positions},
        )
    ]
