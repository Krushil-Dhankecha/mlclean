"""Measure a DataFrame's memory footprint and shrink it reproducibly.

pandas defaults are generous: every whole number is int64, every decimal
float64, every string a Python object. A column of ages needs one byte per
row and gets eight; a column holding 'yes' and 'no' stores two distinct
strings a million times over. Frames routinely carry three to ten times the
memory they need, which is what turns a dataset that would fit into a
MemoryError.

The usual fix is a downcasting loop copied from a notebook. Two things go
wrong with it. It picks dtypes from *this* frame's min and max, so running it
on training data and again on a later batch produces different dtypes for
the same column — the model then sees a feature type it was not fit on.
And it converts float64 to float32 unconditionally, quietly changing values.

So the unit here is a *plan*: ``dtype_plan`` decides the dtypes once, on the
training frame, and ``optimize_dtypes`` replays that plan on any later frame.
The plan is a plain dict, so it serializes to JSON and ships with the model.
By default only provably lossless conversions are planned.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

__all__ = ["dtype_plan", "footprint", "optimize_dtypes"]

PLAN_VERSION = 1

# above this share of distinct values, `category` costs more than it saves
CATEGORY_MAX_UNIQUE_RATE = 0.5

_SIGNED_LADDER = ("int8", "int16", "int32", "int64")
_UNSIGNED_LADDER = ("uint8", "uint16", "uint32", "uint64")


def _is_text(series: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(
        series.dtype
    )


def _int_target(series: pd.Series, allow_unsigned: bool) -> str | None:
    """Smallest integer dtype that holds every value in the column."""
    values = series.dropna()
    if values.empty:
        return None
    low, high = int(values.min()), int(values.max())
    ladder = _UNSIGNED_LADDER if (allow_unsigned and low >= 0) else _SIGNED_LADDER
    for name in ladder:
        info = np.iinfo(name)
        if low >= info.min and high <= info.max:
            if np.dtype(name).itemsize < series.dtype.itemsize:
                return name
            return None
    return None


def _float_is_exact_in_32(series: pd.Series) -> bool:
    """True when float32 round-trips every value without changing it."""
    values = series.dropna()
    if values.empty:
        return True
    original = values.to_numpy()
    return bool(np.array_equal(original.astype(np.float32).astype(original.dtype), original))


def _category_cost(series: pd.Series) -> tuple[int, int] | None:
    """(distinct values, estimated bytes as a category column).

    Estimated rather than measured: converting a large object column to
    find out what it would cost allocates the very memory the caller is
    short of.
    """
    uniques = pd.Series(series.dropna().unique())
    distinct = len(uniques)
    if distinct == 0:
        return None
    codes_itemsize = 1 if distinct <= 127 else (2 if distinct <= 32767 else 4)
    estimated = int(uniques.memory_usage(deep=True)) + len(series) * codes_itemsize
    return distinct, estimated


def _decide(
    series: pd.Series,
    *,
    allow_unsigned: bool,
    allow_lossy_float: bool,
    allow_category: bool,
) -> dict[str, Any] | None:
    """Pick a cheaper dtype for one column, or None to leave it alone."""
    current = int(series.memory_usage(index=False, deep=True))
    dtype = series.dtype
    n_rows = len(series)

    # pandas extension dtypes (Int64, string, boolean) have their own
    # storage rules and nullability; v1 leaves them as the user set them
    if isinstance(dtype, np.dtype):
        if dtype.kind in "iu":
            target = _int_target(series, allow_unsigned)
            if target:
                return {
                    "dtype": target,
                    "current_bytes": current,
                    "estimated_bytes": n_rows * np.dtype(target).itemsize,
                    "lossy": False,
                }
            return None
        if dtype.kind == "f" and dtype.itemsize > 4:
            exact = _float_is_exact_in_32(series)
            if exact or allow_lossy_float:
                return {
                    "dtype": "float32",
                    "current_bytes": current,
                    "estimated_bytes": n_rows * 4,
                    "lossy": not exact,
                }
            return None

    if allow_category and _is_text(series):
        values = series.dropna()
        # an object column holding non-strings would have to be coerced to
        # become a category, and a silent type change is not a saving
        if not all(isinstance(v, str) for v in values.head(1000)):
            return None
        cost = _category_cost(series)
        if cost is None:
            return None
        distinct, estimated = cost
        if n_rows and distinct / n_rows > CATEGORY_MAX_UNIQUE_RATE:
            return None
        if estimated >= current:
            return None
        return {
            "dtype": "category",
            "categories": sorted(values.unique()),
            "current_bytes": current,
            "estimated_bytes": estimated,
            "lossy": False,
        }
    return None


def footprint(
    df: pd.DataFrame,
    *,
    allow_unsigned: bool = False,
    allow_lossy_float: bool = False,
    allow_category: bool = True,
    ignore_columns: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Measure what the frame costs now and what it could cost.

    Nothing is converted and nothing is copied: object columns are measured
    in place, and the cost of a `category` column is estimated from its
    distinct values.

    Returns:
        A dict with ``current_bytes``, ``optimized_bytes``, ``saved_bytes``,
        ``savings_rate`` and a per-column ``columns`` breakdown.
    """
    skip = set(ignore_columns)
    current_total = 0
    optimized_total = 0
    columns: dict[str, dict[str, Any]] = {}

    for column in df.columns:
        series = df[column]
        current = int(series.memory_usage(index=False, deep=True))
        current_total += current
        if column in skip:
            optimized_total += current
            continue
        decision = _decide(
            series,
            allow_unsigned=allow_unsigned,
            allow_lossy_float=allow_lossy_float,
            allow_category=allow_category,
        )
        if decision is None:
            optimized_total += current
            continue
        optimized_total += decision["estimated_bytes"]
        columns[column] = {
            "from": str(series.dtype),
            "to": decision["dtype"],
            "saved_bytes": max(0, current - decision["estimated_bytes"]),
            "lossy": decision["lossy"],
        }

    saved = max(0, current_total - optimized_total)
    return {
        "current_bytes": current_total,
        "optimized_bytes": optimized_total,
        "saved_bytes": saved,
        "savings_rate": (saved / current_total) if current_total else 0.0,
        "columns": columns,
    }


def dtype_plan(
    df: pd.DataFrame,
    *,
    allow_unsigned: bool = False,
    allow_lossy_float: bool = False,
    allow_category: bool = True,
    ignore_columns: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Decide each column's dtype once, on this frame.

    Build the plan on the training data and keep it. Replaying it with
    ``optimize_dtypes`` gives later frames the same dtypes, which is the
    point: dtypes chosen per-batch are a train/serve skew bug waiting to
    happen.

    Args:
        allow_unsigned: Let non-negative columns become uint8/16/32. Halves
            the width of many 0-based columns, but later subtraction
            underflows to a huge positive number instead of going negative,
            so it is off by default.
        allow_lossy_float: Let float64 become float32 even when that changes
            values. Off by default; float64 columns whose values survive the
            round-trip exactly are downcast either way.
        allow_category: Let low-cardinality text become `category`. Usually
            the largest single saving.
        ignore_columns: Columns to leave exactly as they are.

    Returns:
        A JSON-serializable plan: ``{"version": 1, "columns": {name: spec}}``.
    """
    skip = set(ignore_columns)
    columns: dict[str, dict[str, Any]] = {}
    for column in df.columns:
        if column in skip:
            continue
        decision = _decide(
            df[column],
            allow_unsigned=allow_unsigned,
            allow_lossy_float=allow_lossy_float,
            allow_category=allow_category,
        )
        if decision is None:
            continue
        spec: dict[str, Any] = {"dtype": decision["dtype"]}
        if decision["dtype"] == "category":
            spec["categories"] = decision["categories"]
        if decision["lossy"]:
            spec["lossy"] = True
        columns[column] = spec
    return {"version": PLAN_VERSION, "columns": columns}


def _assert_fits(series: pd.Series, target: str, column: str) -> None:
    """Refuse a conversion that would silently change values.

    numpy casts out-of-range integers by wrapping — 1000 becomes -24 in
    int8, with no error — and overflows floats to inf. A plan built on one
    frame and replayed on a wider one would corrupt the column, so the
    mismatch is raised instead.
    """
    values = series.dropna()
    if values.empty:
        return
    if target.startswith(("int", "uint")):
        info = np.iinfo(target)
        low, high = int(values.min()), int(values.max())
        if low < info.min or high > info.max:
            raise ValueError(
                f"column '{column}' holds values in [{low}, {high}], which do "
                f"not fit {target} (range [{info.min}, {info.max}]). The plan "
                "was built on narrower data; rebuild it on data that covers "
                "this range."
            )
    elif target == "float32":
        numeric = pd.to_numeric(values, errors="coerce").dropna()
        finite = numeric[np.isfinite(numeric)]
        limit = float(np.finfo(np.float32).max)
        if not finite.empty and float(finite.abs().max()) > limit:
            raise ValueError(
                f"column '{column}' holds values larger than float32 can "
                f"represent ({limit:.3e}); converting would overflow them to "
                "infinity. Leave this column as float64."
            )


def optimize_dtypes(
    df: pd.DataFrame,
    plan: dict[str, Any] | None = None,
    *,
    allow_unsigned: bool = False,
    allow_lossy_float: bool = False,
    allow_category: bool = True,
    ignore_columns: tuple[str, ...] = (),
    on_unseen: str = "raise",
) -> pd.DataFrame:
    """Return a copy of the frame using cheaper dtypes.

    Args:
        plan: A plan from ``dtype_plan``. Omit it to plan from this frame —
            fine for a one-off, wrong for anything you will later apply to
            a second frame.
        on_unseen: What to do when a planned `category` column contains a
            value the plan never saw. ``"raise"`` (default) reports the
            column and the offending values; ``"nan"`` takes pandas' own
            behavior and turns them into NaN. The default is loud because
            silently NaN-ing unseen categories at inference time is the bug
            this function exists to prevent.

    Raises:
        ValueError: on an unknown ``on_unseen``, a plan version this release
            cannot read, or an unseen category under ``on_unseen="raise"``.
    """
    if on_unseen not in ("raise", "nan"):
        raise ValueError(f"on_unseen must be 'raise' or 'nan', got '{on_unseen}'")
    if plan is None:
        plan = dtype_plan(
            df,
            allow_unsigned=allow_unsigned,
            allow_lossy_float=allow_lossy_float,
            allow_category=allow_category,
            ignore_columns=ignore_columns,
        )
    version = plan.get("version", PLAN_VERSION)
    if version > PLAN_VERSION:
        raise ValueError(
            f"plan version {version} was written by a newer mlclean; "
            f"this release reads up to version {PLAN_VERSION}"
        )

    out = df.copy()
    for column, spec in plan.get("columns", {}).items():
        if column not in out.columns:
            continue
        target = spec["dtype"]
        if target == "category":
            categories = spec.get("categories", [])
            known = set(categories)
            present = out[column].dropna()
            unseen = sorted({v for v in present[~present.isin(known)]}, key=str)
            if unseen and on_unseen == "raise":
                shown = ", ".join(repr(v) for v in unseen[:5])
                more = f" (and {len(unseen) - 5} more)" if len(unseen) > 5 else ""
                raise ValueError(
                    f"column '{column}' holds {len(unseen)} value(s) the plan "
                    f"never saw: {shown}{more}. The plan was built on different "
                    "data. Rebuild it, add these to the plan's categories, or "
                    "pass on_unseen='nan' to accept them becoming NaN."
                )
            column_values = out[column]
            if unseen:
                # pandas deprecates building a Categorical from values the
                # dtype does not list, so blank them explicitly
                column_values = column_values.where(
                    column_values.isin(known) | column_values.isna(), np.nan
                )
            out[column] = column_values.astype(
                pd.CategoricalDtype(categories=categories)
            )
        else:
            _assert_fits(out[column], target, column)
            out[column] = out[column].astype(target)
    return out
