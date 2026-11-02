"""MLCleaner: learn cleaning on the training split, replay it everywhere else.

Follows the scikit-learn transformer convention (fit / transform / get_params)
without importing scikit-learn, so the core dependencies stay pandas and
numpy. transform never changes the number of rows — X stays aligned with y —
which is what makes it safe inside sklearn pipelines and cross-validation.
Row-level cleanup (deduplication, dropping unlabeled rows) belongs before the
split; do it with ``audit(df).clean()``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mlclean.audit import audit
from mlclean.cleaning import build_pipeline

_PARAM_NAMES = (
    "strategy",
    "target",
    "task",
    "id_columns",
    "ignore_columns",
    "missing_threshold",
)
_FALLBACK_TARGET = "__mlclean_target__"


class MLCleaner:
    """Audit the training frame at fit time and freeze the cleaning pipeline.

    Example:
        cleaner = MLCleaner(strategy="balanced")
        X_train = cleaner.fit_transform(X_train, y_train)
        X_test = cleaner.transform(X_test)   # same drops, train's fill values

    The target can be passed either as ``y`` (a column of X is never needed)
    or by naming a column of X with ``target=``. Passing ``y`` enables the
    leakage and imbalance checks on the training data.

    After fitting, ``report_`` holds the full audit of the training frame and
    ``pipeline_`` the frozen CleaningPipeline, which serializes with
    ``pipeline_.to_json()``.
    """

    def __init__(
        self,
        strategy: str = "balanced",
        target: str | None = None,
        task: str | None = None,
        id_columns: list[str] | None = None,
        ignore_columns: list[str] | None = None,
        missing_threshold: float = 0.5,
    ):
        self.strategy = strategy
        self.target = target
        self.task = task
        self.id_columns = id_columns
        self.ignore_columns = ignore_columns
        self.missing_threshold = missing_threshold

    def fit(self, X: pd.DataFrame, y=None) -> MLCleaner:
        frame = X
        target = self.target
        if y is not None:
            name = getattr(y, "name", None)
            if not isinstance(name, str) or name in X.columns:
                name = _FALLBACK_TARGET
            frame = X.copy()
            frame[name] = np.asarray(y)
            target = name
        report = audit(
            frame,
            target=target,
            task=self.task,
            id_columns=self.id_columns,
            ignore_columns=self.ignore_columns,
            missing_threshold=self.missing_threshold,
        )
        self.report_ = report
        self.pipeline_ = build_pipeline(report, self.strategy)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not hasattr(self, "pipeline_"):
            raise RuntimeError("MLCleaner is not fitted yet; call fit first.")
        return self.pipeline_.apply(X, include_row_steps=False)

    def fit_transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        return self.fit(X, y).transform(X)

    # scikit-learn compatibility ------------------------------------------
    def get_params(self, deep: bool = True) -> dict:
        return {name: getattr(self, name) for name in _PARAM_NAMES}

    def set_params(self, **params) -> MLCleaner:
        for name, value in params.items():
            if name not in _PARAM_NAMES:
                raise ValueError(
                    f"unknown parameter '{name}'; valid: {', '.join(_PARAM_NAMES)}"
                )
            setattr(self, name, value)
        return self
