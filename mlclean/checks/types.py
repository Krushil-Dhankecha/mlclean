"""Structural column checks: constants, identifiers, mixed types, text hygiene,
high cardinality."""

from __future__ import annotations

import pandas as pd

from mlclean.issues import INFO, LOW, MEDIUM, DataIssue

QUASI_CONSTANT_THRESHOLD = 0.99


def _is_textual(series: pd.Series) -> bool:
    """True for object and string-dtype columns (pandas 3 uses 'str', not object)."""
    return pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(
        series.dtype
    )


def check_constant_columns(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows == 0:
        return issues

    for column in ctx.feature_columns(df):
        series = df[column]
        n_unique = series.nunique(dropna=False)
        if n_unique <= 1:
            issues.append(
                DataIssue(
                    check="constant_column",
                    severity=MEDIUM,
                    columns=[column],
                    message=f"'{column}' holds a single value — zero signal.",
                    recommendation="Drop it.",
                    details={"unique": int(n_unique)},
                )
            )
            continue
        top_rate = series.value_counts(dropna=False, normalize=True).iloc[0]
        if top_rate >= QUASI_CONSTANT_THRESHOLD:
            issues.append(
                DataIssue(
                    check="quasi_constant_column",
                    severity=LOW,
                    columns=[column],
                    message=(
                        f"'{column}' is {top_rate:.1%} one value — nearly constant."
                    ),
                    recommendation=(
                        "Drop it unless the rare values are exactly what the "
                        "model must catch."
                    ),
                    details={"top_value_rate": round(float(top_rate), 4)},
                )
            )
    return issues


def check_id_columns(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows < 10:
        return issues

    declared = set(ctx.id_columns)
    for column in ctx.feature_columns(df):
        if column in declared:
            continue
        series = df[column].dropna()
        if series.empty:
            continue
        unique_rate = series.nunique() / len(series)
        name = column.lower()
        looks_like_id = name == "id" or name.endswith(("_id", "id")) or "uuid" in name
        # a continuous float measurement is naturally all-unique; only
        # integer-like or textual columns read as identifiers
        identifier_shaped = _is_textual(series) or pd.api.types.is_integer_dtype(
            series
        )
        if (unique_rate == 1.0 and identifier_shaped) or (
            unique_rate > 0.95 and looks_like_id
        ):
            issues.append(
                DataIssue(
                    check="id_column",
                    severity=MEDIUM,
                    columns=[column],
                    message=(
                        f"'{column}' is unique for {unique_rate:.1%} of rows — "
                        "it identifies records rather than describing them."
                    ),
                    recommendation=(
                        "Exclude it from features; models memorize identifiers "
                        "and that memorization is leakage."
                    ),
                    details={"unique_rate": round(float(unique_rate), 4)},
                )
            )
    return issues


def check_mixed_types(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    for column in ctx.feature_columns(df):
        series = df[column].dropna()
        if series.empty or not _is_textual(series):
            continue
        kinds = {type(v).__name__ for v in series.head(1000)}
        if len(kinds) > 1:
            issues.append(
                DataIssue(
                    check="mixed_types",
                    severity=MEDIUM,
                    columns=[column],
                    message=(
                        f"'{column}' mixes Python types ({', '.join(sorted(kinds))}) "
                        "inside one column."
                    ),
                    recommendation="Coerce to one type explicitly before encoding.",
                    details={"types": sorted(kinds)},
                )
            )
            continue
        # numbers stored as strings
        numeric = pd.to_numeric(series, errors="coerce")
        parse_rate = float(numeric.notna().mean())
        if parse_rate >= 0.95 and series.nunique() > 10:
                issues.append(
                    DataIssue(
                        check="numeric_stored_as_text",
                        severity=LOW if parse_rate == 1.0 else MEDIUM,
                        columns=[column],
                        message=(
                            f"'{column}' is text but {parse_rate:.0%} of values "
                            "parse as numbers."
                        ),
                        recommendation=(
                            "Convert with pd.to_numeric; inspect the handful of "
                            "non-numeric values first."
                            if parse_rate < 1.0
                            else "Convert with pd.to_numeric."
                        ),
                        details={"parse_rate": round(parse_rate, 4)},
                    )
                )
    return issues


def check_text_hygiene(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    for column in ctx.feature_columns(df):
        series = df[column].dropna()
        if series.empty or not _is_textual(series):
            continue
        values = series[series.map(lambda v: isinstance(v, str))]
        if values.empty:
            continue
        n_padded = int((values != values.str.strip()).sum())
        if n_padded:
            issues.append(
                DataIssue(
                    check="whitespace_padding",
                    severity=LOW,
                    columns=[column],
                    message=(
                        f"'{column}' has {n_padded:,} values with leading or "
                        "trailing whitespace — ' yes' and 'yes' become two categories."
                    ),
                    recommendation="Strip whitespace before encoding.",
                    details={"padded_values": n_padded},
                )
            )
        lowered = values.str.strip().str.lower()
        n_case_collisions = int(values.str.strip().nunique() - lowered.nunique())
        if n_case_collisions > 0:
            issues.append(
                DataIssue(
                    check="case_inconsistency",
                    severity=LOW,
                    columns=[column],
                    message=(
                        f"'{column}' has {n_case_collisions} categories that "
                        "differ only by letter case."
                    ),
                    recommendation="Normalize case before encoding.",
                    details={"case_collisions": n_case_collisions},
                )
            )
    return issues


def check_high_cardinality(df: pd.DataFrame, ctx) -> list[DataIssue]:
    issues: list[DataIssue] = []
    n_rows = len(df)
    if n_rows == 0:
        return issues
    for column in ctx.feature_columns(df):
        series = df[column]
        if not _is_textual(series) and not isinstance(
            series.dtype, pd.CategoricalDtype
        ):
            continue
        n_unique = int(series.nunique())
        if n_unique > max(50, 0.1 * n_rows) and n_unique < n_rows:
            issues.append(
                DataIssue(
                    check="high_cardinality",
                    severity=MEDIUM if n_unique > 0.5 * n_rows else INFO,
                    columns=[column],
                    message=f"'{column}' has {n_unique:,} distinct categories.",
                    recommendation=(
                        "One-hot encoding will explode; prefer frequency or "
                        "target encoding, or group rare categories."
                    ),
                    details={"unique": n_unique},
                )
            )
    return issues
