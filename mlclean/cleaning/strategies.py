"""Turn an audit report into a pipeline, by strategy tier."""

from __future__ import annotations

import pandas as pd

from mlclean.cleaning.pipeline import CleaningPipeline, CleaningStep

STRATEGIES = ("audit_only", "safe", "balanced", "aggressive")


def _mode(series: pd.Series):
    modes = series.mode(dropna=True)
    return modes.iloc[0] if not modes.empty else None


def _as_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series
    return pd.to_numeric(series, errors="coerce")


def _json_scalar(value):
    """numpy scalars don't survive json.dumps; plain Python ones do."""
    return value.item() if hasattr(value, "item") else value


def build_pipeline(report, strategy: str) -> CleaningPipeline:
    """Turn a report's issues into a pipeline for the chosen strategy."""
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}, got '{strategy}'")

    pipeline = CleaningPipeline()
    if strategy == "audit_only":
        return pipeline

    issues_by_check: dict[str, list] = {}
    for issue in report.issues:
        issues_by_check.setdefault(issue.check, []).append(issue)

    # -- safe tier: lossless or trivially-justified fixes
    padded = [c for i in issues_by_check.get("whitespace_padding", []) for c in i.columns]
    if padded:
        pipeline.steps.append(
            CleaningStep("strip_whitespace", "whitespace_padding", columns=padded)
        )
    if "duplicate_rows" in issues_by_check:
        pipeline.steps.append(
            CleaningStep("remove_duplicates", "exact_duplicate_rows")
        )
    constant = [c for i in issues_by_check.get("constant_column", []) for c in i.columns]
    if constant:
        pipeline.steps.append(
            CleaningStep("drop_columns", "constant_column", columns=constant)
        )
    if "missing_target" in issues_by_check and report.context.target:
        pipeline.steps.append(
            CleaningStep(
                "drop_unlabeled_rows",
                "missing_target",
                params={"target": report.context.target},
            )
        )

    text_numeric = {
        column: float(issue.details.get("parse_rate", 0.0))
        for issue in issues_by_check.get("numeric_stored_as_text", [])
        for column in issue.columns
    }
    # every value parses, so converting changes the dtype and nothing else
    exact = sorted(c for c, rate in text_numeric.items() if rate >= 1.0)
    if exact:
        pipeline.steps.append(
            CleaningStep("to_numeric", "numeric_stored_as_text", columns=exact)
        )

    if strategy == "safe":
        return pipeline

    # -- balanced tier: drop identifiers and leaky columns, impute moderate gaps
    id_cols = [c for i in issues_by_check.get("id_column", []) for c in i.columns]
    id_cols += [c for c in report.context.id_columns if c in report.df.columns]
    if id_cols:
        pipeline.steps.append(
            CleaningStep(
                "drop_columns", "identifier_column", columns=sorted(set(id_cols))
            )
        )
    leaky = [c for i in issues_by_check.get("target_leakage", []) for c in i.columns]
    if leaky:
        pipeline.steps.append(
            CleaningStep("drop_columns", "possible_target_leakage", columns=leaky)
        )
    dropped = set(constant) | set(id_cols) | set(leaky)
    # a few values don't parse — blanks, placeholders — and become NaN, so this
    # waits for the tier that is allowed to impute
    coerced = sorted(
        c
        for c, rate in text_numeric.items()
        if rate < 1.0 and c not in dropped and c in report.df.columns
    )
    if coerced:
        pipeline.steps.append(
            CleaningStep(
                "to_numeric",
                "numeric_stored_as_text",
                columns=coerced,
                params={"coerced_to_nan": True},
            )
        )

    numeric_gaps, categorical_gaps = [], []
    for issue in issues_by_check.get("missing_values", []):
        for column in issue.columns:
            rate = issue.details.get("rate", 0)
            if strategy == "balanced" and rate >= report.context.missing_threshold:
                continue  # left for aggressive
            # a column converted above is numeric by the time impute runs
            if column in text_numeric or pd.api.types.is_numeric_dtype(
                report.df[column]
            ):
                numeric_gaps.append(column)
            else:
                categorical_gaps.append(column)
    # gaps the conversion above just made visible
    numeric_gaps += [
        c
        for c in coerced
        if c not in numeric_gaps and _as_numeric(report.df[c]).isna().any()
    ]
    if numeric_gaps:
        pipeline.steps.append(
            CleaningStep(
                "impute",
                "missing_values",
                columns=numeric_gaps,
                params={
                    "method": "median",
                    "indicator": True,
                    "values": {
                        c: _json_scalar(_as_numeric(report.df[c]).median())
                        for c in numeric_gaps
                    },
                },
            )
        )
    if categorical_gaps:
        pipeline.steps.append(
            CleaningStep(
                "impute",
                "missing_values",
                columns=categorical_gaps,
                params={
                    "method": "mode",
                    "indicator": True,
                    "values": {
                        c: _json_scalar(_mode(report.df[c])) for c in categorical_gaps
                    },
                },
            )
        )

    if strategy == "balanced":
        return pipeline

    # -- aggressive tier: drop very-high-missing and quasi-constant columns
    very_missing = [
        c
        for i in issues_by_check.get("missing_values", [])
        for c in i.columns
        if i.details.get("rate", 0) >= report.context.missing_threshold
    ]
    if very_missing:
        pipeline.steps.append(
            CleaningStep("drop_columns", "high_missing_rate", columns=very_missing)
        )
    quasi = [
        c for i in issues_by_check.get("quasi_constant_column", []) for c in i.columns
    ]
    if quasi:
        pipeline.steps.append(
            CleaningStep("drop_columns", "quasi_constant_column", columns=quasi)
        )
    return pipeline
