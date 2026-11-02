"""Core issue model shared by every check."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CRITICAL = "critical"
HIGH = "high"
MEDIUM = "medium"
LOW = "low"
INFO = "info"

SEVERITY_ORDER = [CRITICAL, HIGH, MEDIUM, LOW, INFO]


@dataclass
class DataIssue:
    """One detected data-quality problem.

    Attributes:
        check: Machine name of the check that produced the issue.
        severity: One of ``critical``, ``high``, ``medium``, ``low``, ``info``.
        columns: Columns involved (empty for dataset-level issues).
        message: Human-readable description of what was found.
        recommendation: What the user should do about it.
        details: Check-specific numbers backing the finding.
    """

    check: str
    severity: str
    message: str
    recommendation: str
    columns: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity,
            "columns": self.columns,
            "message": self.message,
            "recommendation": self.recommendation,
            "details": self.details,
        }


def sort_issues(issues: list[DataIssue]) -> list[DataIssue]:
    """Order issues most severe first, stable within a severity."""
    rank = {name: i for i, name in enumerate(SEVERITY_ORDER)}
    return sorted(issues, key=lambda issue: rank.get(issue.severity, len(rank)))
