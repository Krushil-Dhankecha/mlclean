"""AuditReport: holds issues, renders them, and builds cleaning pipelines."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from mlclean.issues import SEVERITY_ORDER, DataIssue

if TYPE_CHECKING:
    from mlclean.audit import AuditContext

_SEVERITY_LABEL = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "info": "INFO",
}


@dataclass
class AuditReport:
    df: pd.DataFrame
    context: AuditContext
    issues: list[DataIssue] = field(default_factory=list)

    # ---------------------------------------------------------------- summary
    def summary(self) -> dict:
        n_rows, n_cols = self.df.shape
        missing_cells = int(self.df.isna().sum().sum())
        counts = {s: 0 for s in SEVERITY_ORDER}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return {
            "rows": n_rows,
            "columns": n_cols,
            "target": self.context.target,
            "task": self.context.task,
            "duplicate_rows": int(self.df.duplicated().sum()),
            "missing_cells": missing_cells,
            "missing_cell_rate": round(missing_cells / max(1, n_rows * n_cols), 4),
            "issue_counts": counts,
            "total_issues": len(self.issues),
        }

    # --------------------------------------------------------------- renderers
    def to_text(self) -> str:
        s = self.summary()
        lines = [
            "mlclean audit report",
            "====================",
            "",
            f"Rows: {s['rows']:,}   Columns: {s['columns']:,}",
            f"Target: {s['target'] or '-'}   Task: {s['task'] or '-'}",
            (
                f"Duplicate rows: {s['duplicate_rows']:,}   "
                f"Missing cells: {s['missing_cells']:,} ({s['missing_cell_rate']:.2%})"
            ),
            "",
        ]
        if not self.issues:
            lines.append("No issues found.")
            return "\n".join(lines)

        for severity in SEVERITY_ORDER:
            group = [i for i in self.issues if i.severity == severity]
            if not group:
                continue
            header = f"{_SEVERITY_LABEL[severity]} ({len(group)})"
            lines += [header, "-" * len(header)]
            for n, issue in enumerate(group, 1):
                lines.append(f"{n}. {issue.message}")
                lines.append(f"   -> {issue.recommendation}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def show(self) -> None:
        print(self.to_text())

    def to_markdown(self, path: str | Path | None = None) -> str:
        s = self.summary()
        lines = [
            "# mlclean audit report",
            "",
            f"- **Rows:** {s['rows']:,}",
            f"- **Columns:** {s['columns']:,}",
            f"- **Target:** `{s['target']}`" if s["target"] else "- **Target:** –",
            f"- **Task:** {s['task'] or '–'}",
            f"- **Duplicate rows:** {s['duplicate_rows']:,}",
            f"- **Missing cells:** {s['missing_cells']:,} ({s['missing_cell_rate']:.2%})",
            "",
        ]
        if self.issues:
            lines += [
                "| Severity | Issue | Columns | Recommendation |",
                "|---|---|---|---|",
            ]
            for issue in self.issues:
                cols = ", ".join(f"`{c}`" for c in issue.columns) or "–"
                lines.append(
                    f"| {_SEVERITY_LABEL[issue.severity]} | {issue.message} "
                    f"| {cols} | {issue.recommendation} |"
                )
        else:
            lines.append("No issues found.")
        text = "\n".join(lines) + "\n"
        if path is not None:
            Path(path).write_text(text, encoding="utf-8")
        return text

    def to_json(self, path: str | Path | None = None) -> str:
        payload = json.dumps(
            {"summary": self.summary(), "issues": [i.to_dict() for i in self.issues]},
            indent=2,
            default=str,
        )
        if path is not None:
            Path(path).write_text(payload + "\n", encoding="utf-8")
        return payload

    # ---------------------------------------------------------------- cleaning
    def clean(self, strategy: str = "safe"):
        """Build and apply a cleaning pipeline for this report.

        Returns:
            (clean_df, pipeline) — the cleaned copy and the reproducible
            pipeline that produced it. The original frame is untouched.
        """
        from mlclean.cleaning import build_pipeline

        pipeline = build_pipeline(self, strategy)
        return pipeline.apply(self.df), pipeline
