"""Target-leakage heuristics.

Flag features whose association with the target is so strong it usually means
the feature is derived from, or recorded after, the outcome.

Association is measured without sklearn, and *which* measure matters more than
it looks. Pearson correlation is only meaningful between two columns that are
genuinely continuous: between two binary columns it is bounded well below 1
however deterministic the relationship, so a correlation threshold can never
fire on a 0/1 target — which is most classification data. Anything that is not
continuous on both sides therefore goes to normalized mutual information,
computed from a contingency table with continuous columns binned by decile.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mlclean.issues import CRITICAL, HIGH, MEDIUM, DataIssue

# almost certainly leakage
ASSOCIATION_FLAG = 0.95
# strong enough to be worth checking the timeline of, not strong enough to
# call a defect: a real feature can legitimately score here
ASSOCIATION_WATCH = 0.70
BINS = 10


def _binned(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series) and series.nunique() > BINS:
        try:
            return pd.qcut(series, BINS, duplicates="drop").astype(str)
        except (ValueError, IndexError):
            return series.astype(str)
    return series.astype(str)


def _is_continuous(series: pd.Series) -> bool:
    """Numeric with enough distinct values for correlation to mean anything.

    The cutoff is the binning threshold on purpose: a numeric column with
    fewer distinct values than that is treated as categorical everywhere in
    this module.
    """
    return (
        pd.api.types.is_numeric_dtype(series)
        and not pd.api.types.is_bool_dtype(series)
        and series.nunique() > BINS
    )


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

    continuous_target = _is_continuous(target)

    for column in ctx.feature_columns(df):
        if column in ctx.id_columns:
            continue
        series = df[column]
        pair = pd.concat([series, target], axis=1).dropna()
        if len(pair) < 50:
            continue
        feature_vals, target_vals = pair.iloc[:, 0], pair.iloc[:, 1]
        n_unique = feature_vals.nunique()
        if n_unique < 2:
            continue
        continuous_feature = _is_continuous(feature_vals)
        # near-unique features (identifiers) make mutual information
        # trivially perfect; they are the id-column check's business. A
        # continuous column is also near-unique but gets binned into deciles
        # first, so its score is meaningful and it must not be skipped —
        # a leaked probability or score column looks exactly like this.
        id_shaped = n_unique > 0.8 * len(pair) and not continuous_feature

        score = None
        measure = None
        if continuous_feature and continuous_target:
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
        elif score >= ASSOCIATION_WATCH:
            issues.append(
                DataIssue(
                    check="target_leakage_suspect",
                    severity=MEDIUM,
                    columns=[column],
                    message=(
                        f"'{column}' is strongly associated with target "
                        f"'{ctx.target}' ({measure} = {score:.3f}) — short of "
                        "the near-perfect range, but more than most honest "
                        "features manage."
                    ),
                    recommendation=(
                        "Check when this value becomes known. Available before "
                        "the prediction moment, it is a good feature; only "
                        "available afterwards, it is leakage."
                    ),
                    details={"score": round(score, 4), "measure": measure},
                )
            )
    return issues
