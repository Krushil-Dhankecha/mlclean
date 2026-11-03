"""Markdown rendering, for READMEs and CI job summaries."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mlclean.issues import SEVERITY_LABEL

if TYPE_CHECKING:
    from mlclean.report import AuditReport


def render_markdown(report: AuditReport, path: str | Path | None = None) -> str:
    s = report.summary()
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
    if report.issues:
        lines += [
            "| Severity | Issue | Columns | Recommendation |",
            "|---|---|---|---|",
        ]
        for issue in report.issues:
            cols = ", ".join(f"`{c}`" for c in issue.columns) or "–"
            lines.append(
                f"| {SEVERITY_LABEL[issue.severity]} | {issue.message} "
                f"| {cols} | {issue.recommendation} |"
            )
    else:
        lines.append("No issues found.")
    text = "\n".join(lines) + "\n"
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text
