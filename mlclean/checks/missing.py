"""Missing-value checks."""

from __future__ import annotations

import pandas as pd

from mlclean.issues import HIGH, INFO, MEDIUM, DataIssue

TVD_FLAG = 0.2  # total variation distance at which missingness counts as signal
SMD_FLAG = 0.5  # standardized mean difference, likewise


def check_missing(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows == 0:
        return issues

    for column, series in ctx.feature_series(df):
        n_missing = int(series.isna().sum())
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


def check_informative_missingness(df: pd.DataFrame, ctx) -> list[DataIssue]:
    """Flag columns whose *gaps* predict the target.

    When rows with a missing value have a clearly different target
    distribution than rows without, the missingness is signal — a plain fill
    erases it, and in the worst case the gap exists because the value is
    recorded after the outcome (leakage).
    """
    issues: list[DataIssue] = []
    if not ctx.target or ctx.target not in df.columns or len(df) < 100:
        return issues
    target = df[ctx.target]
    if target.dropna().nunique() < 2:
        return issues

    for column, series in ctx.feature_series(df):
        mask = series.isna()
        n_missing = int(mask.sum())
        if n_missing < 20 or n_missing > 0.95 * len(df):
            continue
        t_missing = target[mask].dropna()
        t_present = target[~mask].dropna()
        if len(t_missing) < 20 or len(t_present) < 20:
            continue

        if ctx.task == "classification":
            p = t_missing.value_counts(normalize=True)
            q = t_present.value_counts(normalize=True)
            classes = p.index.union(q.index)
            tvd = float(
                0.5 * sum(abs(p.get(c, 0.0) - q.get(c, 0.0)) for c in classes)
            )
            if tvd < TVD_FLAG:
                continue
            strength = {"tvd": round(tvd, 4)}
            wording = (
                f"the target distribution shifts by {tvd:.0%} (total variation) "
                "between rows where it is missing and rows where it is not"
            )
        else:
            spread = float(target.dropna().std())
            if spread == 0:
                continue
            smd = abs(float(t_missing.mean()) - float(t_present.mean())) / spread
            if smd < SMD_FLAG:
                continue
            strength = {"standardized_mean_difference": round(smd, 4)}
            wording = (
                f"the target mean differs by {smd:.2f} standard deviations "
                "between rows where it is missing and rows where it is not"
            )

        issues.append(
            DataIssue(
                check="informative_missingness",
                severity=MEDIUM,
                columns=[column],
                message=(
                    f"Whether '{column}' is missing is itself informative: "
                    f"{wording}."
                ),
                recommendation=(
                    "Impute with a missing indicator so the signal survives — "
                    "and ask why the gaps track the outcome: values filled in "
                    "only after the outcome is known are leakage."
                ),
                details={"missing": n_missing, **strength},
            )
        )
    return issues
