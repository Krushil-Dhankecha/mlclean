"""The step and pipeline model: ordered, serializable, replayable."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

# steps that change the number of rows; skipped when a pipeline is replayed
# as a transformer, where X must stay aligned with y
ROW_STEPS = {"remove_duplicates", "drop_unlabeled_rows"}


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

    def apply(
        self, df: pd.DataFrame, *, include_row_steps: bool = True
    ) -> pd.DataFrame:
        """Replay every step on a (copy of a) DataFrame.

        With ``include_row_steps=False``, steps that drop rows are skipped so
        the result keeps one output row per input row.
        """
        from mlclean.cleaning.steps import APPLIERS

        out = df.copy()
        for step in self.steps:
            if not include_row_steps and step.step in ROW_STEPS:
                continue
            out = APPLIERS[step.step](out, step)
        return out
