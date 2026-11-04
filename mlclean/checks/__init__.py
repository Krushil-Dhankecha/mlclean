"""Built-in audit checks. Each check takes the frame and audit context and
returns a list of DataIssue."""

from mlclean.checks.cardinality import check_high_cardinality
from mlclean.checks.constant import check_constant_columns
from mlclean.checks.dtypes import check_mixed_types
from mlclean.checks.duplicates import check_duplicates
from mlclean.checks.identifiers import check_id_columns
from mlclean.checks.imbalance import check_class_imbalance
from mlclean.checks.labels import check_duplicate_column_names
from mlclean.checks.leakage import check_target_leakage
from mlclean.checks.missing import check_informative_missingness, check_missing
from mlclean.checks.outliers import check_outliers
from mlclean.checks.sentinels import check_disguised_missing
from mlclean.checks.text import check_text_hygiene

# name -> check, the names users pass to audit(checks=..., skip=...)
CHECKS = {
    "missing": check_missing,
    "informative_missingness": check_informative_missingness,
    "duplicates": check_duplicates,
    "constant": check_constant_columns,
    "labels": check_duplicate_column_names,
    "ids": check_id_columns,
    "mixed_types": check_mixed_types,
    "text": check_text_hygiene,
    "cardinality": check_high_cardinality,
    "sentinels": check_disguised_missing,
    "outliers": check_outliers,
    "imbalance": check_class_imbalance,
    "leakage": check_target_leakage,
}

ALL_CHECKS = list(CHECKS.values())

__all__ = [
    "ALL_CHECKS",
    "CHECKS",
    "check_class_imbalance",
    "check_constant_columns",
    "check_disguised_missing",
    "check_duplicate_column_names",
    "check_duplicates",
    "check_high_cardinality",
    "check_id_columns",
    "check_informative_missingness",
    "check_missing",
    "check_mixed_types",
    "check_outliers",
    "check_target_leakage",
    "check_text_hygiene",
]
