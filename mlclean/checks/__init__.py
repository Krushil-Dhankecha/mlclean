"""Built-in audit checks. Each check takes the frame and audit context and
returns a list of DataIssue."""

from mlclean.checks.duplicates import check_duplicates
from mlclean.checks.imbalance import check_class_imbalance
from mlclean.checks.leakage import check_target_leakage
from mlclean.checks.missing import check_missing
from mlclean.checks.outliers import check_outliers
from mlclean.checks.types import (
    check_constant_columns,
    check_high_cardinality,
    check_id_columns,
    check_mixed_types,
    check_text_hygiene,
)

ALL_CHECKS = [
    check_missing,
    check_duplicates,
    check_constant_columns,
    check_id_columns,
    check_mixed_types,
    check_text_hygiene,
    check_high_cardinality,
    check_outliers,
    check_class_imbalance,
    check_target_leakage,
]

__all__ = [
    "ALL_CHECKS",
    "check_class_imbalance",
    "check_constant_columns",
    "check_duplicates",
    "check_high_cardinality",
    "check_id_columns",
    "check_missing",
    "check_mixed_types",
    "check_outliers",
    "check_target_leakage",
    "check_text_hygiene",
]
