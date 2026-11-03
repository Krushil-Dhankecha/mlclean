"""AuditReport: holds issues, renders them, and builds cleaning pipelines.

The report object lives here; each output format has its own module
(text, markdown, json_io) so new formats can be added without touching
the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from mlclean.issues import SEVERITY_ORDER, DataIssue
from mlclean.report.json_io import render_json
from mlclean.report.markdown import render_markdown
from mlclean.report.text import render_text

if TYPE_CHECKING:
    from mlclean.audit import AuditContext

__all__ = ["AuditReport"]


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
        return render_text(self)

    def show(self) -> None:
        print(self.to_text())

    def to_markdown(self, path: str | Path | None = None) -> str:
        return render_markdown(self, path)

    def to_json(self, path: str | Path | None = None) -> str:
        return render_json(self, path)

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
