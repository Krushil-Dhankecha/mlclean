"""Memory footprint: how much of the frame's RAM is pandas defaults rather
than data."""

from __future__ import annotations

import pandas as pd

from mlclean.issues import INFO, LOW, MEDIUM, DataIssue
from mlclean.memory import footprint

MB = 1_048_576

# a saving worth interrupting someone over
MIN_BYTES = MB
MIN_SAVINGS_RATE = 0.15
MEDIUM_SAVED_BYTES = 500 * MB
LOW_SAVED_BYTES = 50 * MB

_TOP_COLUMNS = 3


def _severity(saved_bytes: int) -> str:
    if saved_bytes >= MEDIUM_SAVED_BYTES:
        return MEDIUM
    if saved_bytes >= LOW_SAVED_BYTES:
        return LOW
    return INFO


def check_memory_footprint(df: pd.DataFrame, ctx) -> list[DataIssue]:
    if df.empty or not len(df.columns):
        return []

    stats = footprint(df, ignore_columns=tuple(ctx.ignore_columns))
    saved = stats["saved_bytes"]
    if stats["current_bytes"] < MIN_BYTES or saved < MIN_BYTES:
        return []
    if stats["savings_rate"] < MIN_SAVINGS_RATE:
        return []

    ranked = sorted(
        stats["columns"].items(), key=lambda kv: kv[1]["saved_bytes"], reverse=True
    )
    worst = ", ".join(
        f"'{name}' {spec['from']}→{spec['to']} saves {spec['saved_bytes'] / MB:.1f} MB"
        for name, spec in ranked[:_TOP_COLUMNS]
        if spec["saved_bytes"] > 0
    )

    return [
        DataIssue(
            check="memory_footprint",
            severity=_severity(saved),
            columns=[name for name, _ in ranked],
            message=(
                f"This frame holds {stats['current_bytes'] / MB:,.1f} MB; the "
                f"same values fit in {stats['optimized_bytes'] / MB:,.1f} MB "
                f"({stats['savings_rate']:.0%} less). {worst}."
            ),
            recommendation=(
                "Call mlclean.optimize_dtypes(df) for a one-off. For a model, "
                "build the plan once with dtype_plan(train_df), keep it beside "
                "the model, and replay it on every later frame — dtypes chosen "
                "per batch drift apart and the model then sees a feature type "
                "it was not fit on."
            ),
            details={
                "current_bytes": stats["current_bytes"],
                "optimized_bytes": stats["optimized_bytes"],
                "saved_bytes": saved,
                "savings_rate": round(stats["savings_rate"], 4),
                "columns": {
                    name: {
                        "from": spec["from"],
                        "to": spec["to"],
                        "saved_bytes": spec["saved_bytes"],
                    }
                    for name, spec in ranked
                },
            },
        )
    ]
