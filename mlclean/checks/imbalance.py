"""Target distribution checks for classification tasks."""

from __future__ import annotations

import pandas as pd

from mlclean.issues import HIGH, MEDIUM, DataIssue


def check_class_imbalance(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    if not ctx.target or ctx.target not in df.columns or ctx.task != "classification":
        return issues

    counts = df[ctx.target].value_counts(dropna=True)
    if len(counts) < 2:
        issues.append(
            DataIssue(
                check="single_class_target",
                severity=HIGH,
                columns=[ctx.target],
                message=f"Target '{ctx.target}' contains a single class.",
                recommendation="A classifier cannot learn from one class; fix the extract.",
                details={"classes": counts.index.astype(str).tolist()},
            )
        )
        return issues

    total = int(counts.sum())
    minority = counts.iloc[-1]
    minority_rate = minority / total
    if minority_rate < 0.10:
        issues.append(
            DataIssue(
                check="class_imbalance",
                severity=HIGH if minority_rate < 0.02 else MEDIUM,
                columns=[ctx.target],
                message=(
                    f"Minority class '{counts.index[-1]}' is {minority_rate:.1%} "
                    f"of {total:,} labeled rows."
                ),
                recommendation=(
                    "Use class weights or stratified splits, and judge the model "
                    "on PR-AUC/F1 — accuracy will lie."
                ),
                details={
                    "distribution": {
                        str(k): int(v) for k, v in counts.head(20).items()
                    },
                    "minority_rate": round(float(minority_rate), 4),
                },
            )
        )

    rare = counts[counts < 10]
    if len(rare) > 0 and len(counts) > 2:
        issues.append(
            DataIssue(
                check="rare_classes",
                severity=MEDIUM,
                columns=[ctx.target],
                message=(
                    f"{len(rare)} target classes have fewer than 10 examples "
                    f"({', '.join(rare.index.astype(str)[:5])}...)."
                    if len(rare) > 5
                    else f"{len(rare)} target classes have fewer than 10 examples "
                    f"({', '.join(rare.index.astype(str))})."
                ),
                recommendation="Merge rare classes or collect more examples; stratified CV will break on them.",
                details={"rare_classes": {str(k): int(v) for k, v in rare.items()}},
            )
        )
    return issues
