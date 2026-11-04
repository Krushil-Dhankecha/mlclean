"""Target-leakage heuristics.

v0 strategy: flag features whose association with the target is so strong it
usually means the feature is derived from, or recorded after, the outcome.
Association is measured without sklearn: absolute Pearson correlation for
numeric-vs-numeric, and normalized mutual information computed from a
contingency table for everything else (numerics binned by decile).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mlclean.issues import CRITICAL, HIGH, DataIssue

ASSOCIATION_FLAG = 0.95
BINS = 10


def _binned(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series) and series.nunique() > BINS:
        try:
            return pd.qcut(series, BINS, duplicates="drop").astype(str)
        except (ValueError, IndexError):
            return series.astype(str)
    return series.astype(str)


def _normalized_mutual_information(x: pd.Series, y: pd.Series) -> float:
    joint = pd.crosstab(x, y, normalize=True).to_numpy()
    px = joint.sum(axis=1, keepdims=True)
    py = joint.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = joint * np.log(joint / (px @ py))
    mi = float(np.nansum(terms))
    hx = -float(np.nansum(px * np.log(px)))
    hy = -float(np.nansum(py * np.log(py)))
    denom = min(hx, hy)
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, mi / denom))


def check_target_leakage(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    if not ctx.target or ctx.target not in df.columns:
        return issues
    target = df[ctx.target]
    if target.dropna().nunique() < 2 or len(df) < 50:
        return issues

    numeric_target = pd.api.types.is_numeric_dtype(target) and not (
        pd.api.types.is_bool_dtype(target)
    )

    for column, series in ctx.feature_series(df):
        if column in ctx.id_columns:
            continue
        pair = pd.concat([series, target], axis=1).dropna()
        if len(pair) < 50:
            continue
        feature_vals, target_vals = pair.iloc[:, 0], pair.iloc[:, 1]
        n_unique = feature_vals.nunique()
        if n_unique < 2:
            continue
        # near-unique features (identifiers) make mutual information
        # trivially perfect; they are the id-column check's business
        id_shaped = n_unique > 0.8 * len(pair)

        score = None
        measure = None
        if (
            numeric_target
            and pd.api.types.is_numeric_dtype(feature_vals)
            and not pd.api.types.is_bool_dtype(feature_vals)
        ):
            corr = feature_vals.corr(target_vals)
            if pd.notna(corr):
                score, measure = abs(float(corr)), "absolute Pearson correlation"
        if score is None:
            if id_shaped:
                continue
            score = _normalized_mutual_information(
                _binned(feature_vals), _binned(target_vals)
            )
            measure = "normalized mutual information"

        if score >= ASSOCIATION_FLAG:
            issues.append(
                DataIssue(
                    check="target_leakage",
                    severity=CRITICAL if score >= 0.99 else HIGH,
                    columns=[column],
                    message=(
                        f"'{column}' predicts target '{ctx.target}' almost "
                        f"perfectly ({measure} = {score:.3f}). Features this "
                        "strong are usually recorded after the outcome or "
                        "derived from it."
                    ),
                    recommendation=(
                        "Verify the business timeline: if the value exists only "
                        "after the prediction moment, remove it from the features."
                    ),
                    details={"score": round(score, 4), "measure": measure},
                )
            )
    return issues
