"""Cleaning strategies and the reproducible pipeline.

Principle: never silently delete data without recording why. Every change is
a CleaningStep with a reason, and the pipeline replays on any DataFrame.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

STRATEGIES = ("audit_only", "safe", "balanced", "aggressive")


@dataclass
class CleaningStep:
    step: str
    reason: str
    columns: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"step": self.step, "reason": self.reason}
        if self.columns:
            payload["columns"] = self.columns
        if self.params:
            payload["params"] = self.params
        return payload


@dataclass
class CleaningPipeline:
    """An ordered, serializable list of cleaning steps."""

    steps: list[CleaningStep] = field(default_factory=list)
    version: str = "0.1.0"

    def to_json(self, path: str | Path | None = None) -> str:
        payload = json.dumps(
            {"version": self.version, "steps": [s.to_dict() for s in self.steps]},
            indent=2,
        )
        if path is not None:
            Path(path).write_text(payload + "\n", encoding="utf-8")
        return payload

    @classmethod
    def from_json(cls, source: str | Path) -> CleaningPipeline:
        path = Path(source)
        text = path.read_text(encoding="utf-8") if path.exists() else str(source)
        data = json.loads(text)
        steps = [
            CleaningStep(
                step=s["step"],
                reason=s.get("reason", ""),
                columns=s.get("columns", []),
                params=s.get("params", {}),
            )
            for s in data["steps"]
        ]
        return cls(steps=steps, version=data.get("version", "0.1.0"))

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replay every step on a (copy of a) DataFrame."""
        out = df.copy()
        for step in self.steps:
            out = _APPLIERS[step.step](out, step)
        return out


def _apply_drop_columns(df: pd.DataFrame, step: CleaningStep) -> pd.DataFrame:
    return df.drop(columns=[c for c in step.columns if c in df.columns])


def _apply_remove_duplicates(df: pd.DataFrame, step: CleaningStep) -> pd.DataFrame:
    return df.drop_duplicates(ignore_index=True)


def _apply_strip_whitespace(df: pd.DataFrame, step: CleaningStep) -> pd.DataFrame:
    out = df.copy()
    for column in step.columns:
        if column in out.columns:
            out[column] = out[column].map(
                lambda v: v.strip() if isinstance(v, str) else v
            )
    return out


def _apply_impute(df: pd.DataFrame, step: CleaningStep) -> pd.DataFrame:
    out = df.copy()
    method = step.params.get("method", "median")
    for column in step.columns:
        if column not in out.columns:
            continue
        if method == "median":
            fill = out[column].median()
        elif method == "mode":
            modes = out[column].mode(dropna=True)
            fill = modes.iloc[0] if not modes.empty else None
        else:
            fill = step.params.get("value")
        if step.params.get("indicator"):
            out[f"{column}_missing"] = out[column].isna().astype("int8")
        if fill is not None:
            out[column] = out[column].fillna(fill)
    return out


def _apply_drop_unlabeled_rows(df: pd.DataFrame, step: CleaningStep) -> pd.DataFrame:
    target = step.params["target"]
    if target not in df.columns:
        return df
    return df.dropna(subset=[target]).reset_index(drop=True)


_APPLIERS = {
    "drop_columns": _apply_drop_columns,
    "remove_duplicates": _apply_remove_duplicates,
    "strip_whitespace": _apply_strip_whitespace,
    "impute": _apply_impute,
    "drop_unlabeled_rows": _apply_drop_unlabeled_rows,
}


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
    numeric_gaps, categorical_gaps = [], []
    for issue in issues_by_check.get("missing_values", []):
        for column in issue.columns:
            rate = issue.details.get("rate", 0)
            if strategy == "balanced" and rate >= report.context.missing_threshold:
                continue  # left for aggressive
            if pd.api.types.is_numeric_dtype(report.df[column]):
                numeric_gaps.append(column)
            else:
                categorical_gaps.append(column)
    if numeric_gaps:
        pipeline.steps.append(
            CleaningStep(
                "impute",
                "missing_values",
                columns=numeric_gaps,
                params={"method": "median", "indicator": True},
            )
        )
    if categorical_gaps:
        pipeline.steps.append(
            CleaningStep(
                "impute",
                "missing_values",
                columns=categorical_gaps,
                params={"method": "mode", "indicator": True},
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
