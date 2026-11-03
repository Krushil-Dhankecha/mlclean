"""The appliers: one function per step name, dispatched through APPLIERS."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from mlclean.cleaning.pipeline import CleaningStep


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
    # fill values learned when the pipeline was built; falling back to
    # computing them here keeps pipelines serialized before 0.2 replayable
    learned = step.params.get("values", {})
    for column in step.columns:
        if column not in out.columns:
            continue
        if column in learned:
            fill = learned[column]
        elif method == "median":
            fill = out[column].median()
        elif method == "mode":
            modes = out[column].mode(dropna=True)
            fill = modes.iloc[0] if not modes.empty else None
        else:
            fill = step.params.get("value")
        if step.params.get("indicator"):
            out[f"{column}_missing"] = out[column].isna().astype("int8")
        if fill is not None and not pd.isna(fill):
            out[column] = out[column].fillna(fill)
    return out


def _apply_drop_unlabeled_rows(df: pd.DataFrame, step: CleaningStep) -> pd.DataFrame:
    target = step.params["target"]
    if target not in df.columns:
        return df
    return df.dropna(subset=[target]).reset_index(drop=True)


APPLIERS = {
    "drop_columns": _apply_drop_columns,
    "remove_duplicates": _apply_remove_duplicates,
    "strip_whitespace": _apply_strip_whitespace,
    "impute": _apply_impute,
    "drop_unlabeled_rows": _apply_drop_unlabeled_rows,
}
