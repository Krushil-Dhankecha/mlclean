"""The audit entry point."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from mlclean.checks import ALL_CHECKS
from mlclean.issues import DataIssue, sort_issues
from mlclean.report import AuditReport


@dataclass
class AuditContext:
    """Settings shared by every check."""

    target: str | None = None
    task: str | None = None
    id_columns: list[str] = field(default_factory=list)
    ignore_columns: list[str] = field(default_factory=list)
    missing_threshold: float = 0.5

    def feature_columns(self, df: pd.DataFrame) -> list[str]:
        skip = set(self.ignore_columns)
        if self.target:
            skip.add(self.target)
        return [c for c in df.columns if c not in skip]


def _infer_task(df: pd.DataFrame, target: str | None) -> str | None:
    if not target or target not in df.columns:
        return None
    series = df[target].dropna()
    if series.empty:
        return None
    if pd.api.types.is_bool_dtype(series) or series.dtype == object:
        return "classification"
    if pd.api.types.is_numeric_dtype(series):
        n_unique = series.nunique()
        if n_unique <= 20 and (series == series.round()).all():
            return "classification"
        return "regression"
    return "classification"


def audit(
    df: pd.DataFrame,
    target: str | None = None,
    task: str | None = None,
    id_columns: list[str] | None = None,
    ignore_columns: list[str] | None = None,
    missing_threshold: float = 0.5,
) -> AuditReport:
    """Audit a DataFrame for problems that hurt ML training and evaluation.

    Args:
        df: The data to audit.
        target: Name of the label column, if any. Enables imbalance and
            leakage checks.
        task: "classification" or "regression". Inferred from the target
            when omitted.
        id_columns: Columns known to be record identifiers.
        ignore_columns: Columns the checks should skip entirely.
        missing_threshold: Missing-rate at which a column is flagged
            high-severity (default 0.5).

    Returns:
        An AuditReport holding every detected issue, ready to show,
        export, or clean from.
    """
    if target is not None and target not in df.columns:
        raise ValueError(f"target column '{target}' is not in the DataFrame")

    ctx = AuditContext(
        target=target,
        task=task or _infer_task(df, target),
        id_columns=list(id_columns or []),
        ignore_columns=list(ignore_columns or []),
        missing_threshold=missing_threshold,
    )

    issues: list[DataIssue] = []
    for check in ALL_CHECKS:
        issues.extend(check(df, ctx))

    return AuditReport(df=df, context=ctx, issues=sort_issues(issues))
