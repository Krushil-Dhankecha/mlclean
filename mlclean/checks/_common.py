"""Helpers shared by more than one check."""

from __future__ import annotations

import pandas as pd


def is_textual(series: pd.Series) -> bool:
    """True for object and string-dtype columns (pandas 3 uses 'str', not object)."""
    return pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(
        series.dtype
    )
