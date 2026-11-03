"""Plain-text rendering for the terminal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mlclean.issues import SEVERITY_LABEL, SEVERITY_ORDER

if TYPE_CHECKING:
    from mlclean.report import AuditReport


def render_text(report: AuditReport) -> str:
    s = report.summary()
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
    if not report.issues:
        lines.append("No issues found.")
        return "\n".join(lines)

    for severity in SEVERITY_ORDER:
        group = [i for i in report.issues if i.severity == severity]
        if not group:
            continue
        header = f"{SEVERITY_LABEL[severity]} ({len(group)})"
        lines += [header, "-" * len(header)]
        for n, issue in enumerate(group, 1):
            lines.append(f"{n}. {issue.message}")
            lines.append(f"   -> {issue.recommendation}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
