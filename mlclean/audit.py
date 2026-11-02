"""The audit entry point."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from mlclean.checks import CHECKS
from mlclean.issues import INFO, DataIssue, sort_issues
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


def _select_checks(
    checks: list[str] | None, skip: list[str] | None
) -> dict[str, object]:
    for given in (checks, skip):
        if given:
            unknown = sorted(set(given) - CHECKS.keys())
            if unknown:
                raise ValueError(
                    f"unknown check name(s) {', '.join(unknown)}; "
                    f"valid names: {', '.join(CHECKS)}"
                )
    selected = {name: CHECKS[name] for name in checks} if checks else dict(CHECKS)
    for name in skip or []:
        selected.pop(name, None)
    return selected


def audit(
    df: pd.DataFrame,
    target: str | None = None,
    task: str | None = None,
    id_columns: list[str] | None = None,
    ignore_columns: list[str] | None = None,
    missing_threshold: float = 0.5,
    checks: list[str] | None = None,
    skip: list[str] | None = None,
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
        checks: Run only these checks (names from mlclean.checks.CHECKS).
        skip: Run everything except these checks.

    Returns:
        An AuditReport holding every detected issue, ready to show,
        export, or clean from.

    A failing check never aborts the audit: it is reported as a
    ``check_error`` finding and the remaining checks still run.
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
    for name, check in _select_checks(checks, skip).items():
        try:
            issues.extend(check(df, ctx))
        except Exception as err:  # noqa: BLE001 — one bad column must not kill the audit
            issues.append(
                DataIssue(
                    check="check_error",
                    severity=INFO,
                    message=(
                        f"The '{name}' check failed on this data and was "
                        f"skipped ({type(err).__name__}: {err})."
                    ),
                    recommendation=(
                        "The rest of the audit is unaffected. If the data "
                        "looks ordinary, please report this at "
                        "github.com/Krushil-Dhankecha/mlclean/issues."
                    ),
                    details={"check": name, "error": str(err)},
                )
            )

    return AuditReport(df=df, context=ctx, issues=sort_issues(issues))
