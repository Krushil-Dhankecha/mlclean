"""JSON serialization, for CI artifacts and machine consumers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mlclean.report import AuditReport


def render_json(report: AuditReport, path: str | Path | None = None) -> str:
    payload = json.dumps(
        {"summary": report.summary(), "issues": [i.to_dict() for i in report.issues]},
        indent=2,
        default=str,
    )
    if path is not None:
        Path(path).write_text(payload + "\n", encoding="utf-8")
    return payload
