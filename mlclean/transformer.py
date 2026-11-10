"""MLCleaner: learn cleaning on the training split, replay it everywhere else.

Follows the scikit-learn transformer convention (fit / transform / get_params)
without importing scikit-learn, so the core dependencies stay pandas and
numpy. transform never changes the number of rows — X stays aligned with y —
and never changes the columns either: it returns exactly the columns fit
produced, in that order, raising rather than quietly handing back a frame
shaped differently from the one the model was trained on.
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


def _align_target(X: pd.DataFrame, y):
    """Put ``y`` in ``X``'s row order before the two are joined.

    A pandas ``y`` carries an index, and that index is the only statement of
    which label belongs to which row. Reading it off positionally instead --
    which is what ``np.asarray(y)`` did -- mislabels every row whenever the
    caller's ``y`` is ordered differently from ``X``, and nothing raises.
    Arrays and lists have no index to go on, so those keep the positional
    path and pandas' own length check.
    """
    if not isinstance(y, (pd.Series, pd.DataFrame)):
        return y

    if isinstance(y, pd.DataFrame):
        if y.shape[1] != 1:
            raise ValueError(
                f"y has {y.shape[1]} columns; pass a single column or a Series."
            )
        y = y.iloc[:, 0]

    if X.index.equals(y.index):
        return y

    unmatched = X.index.difference(y.index)
    extra = y.index.difference(X.index)
    if len(unmatched) or len(extra):
        raise ValueError(
            "y's index does not cover X's rows: "
            f"{len(unmatched)} row(s) of X have no label and "
            f"{len(extra)} label(s) belong to rows not in X. "
            "Align them before fitting, or pass y as an array to pair by "
            "position."
        )
    if not y.index.is_unique:
        raise ValueError(
            "y's index holds duplicate labels, so matching it to X's rows is "
            "ambiguous. Pass y as an array to pair by position instead."
        )
    return y.reindex(X.index)


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

    ``transform`` keeps two contracts. The row count is unchanged, and the
    output columns are exactly ``feature_names_out_``, in that order, whatever
    order the caller's frame arrived in. A column the pipeline needs and the
    frame does not have raises ``ValueError``; a column training never saw is
    dropped and listed in ``unknown_columns_``. ``feature_names_in_`` and
    ``n_features_in_`` describe the frame passed to ``fit``.
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
            frame[name] = np.asarray(_align_target(X, y))
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

        # The output schema is taken from the training frame itself rather than
        # read off the steps: the appliers decide what they add and drop, and a
        # second guess at that here would be a second place to get it wrong.
        self.feature_names_in_ = list(X.columns)
        self.n_features_in_ = X.shape[1]
        fitted_out = self.pipeline_.apply(X, include_row_steps=False)
        self.feature_names_out_ = list(fitted_out.columns)
        produced = set(self.feature_names_out_)
        self.required_columns_ = [c for c in X.columns if c in produced]
        self.unknown_columns_ = []
        return self

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        """The output columns learned at fit time, in order."""
        if not hasattr(self, "feature_names_out_"):
            raise RuntimeError("MLCleaner is not fitted yet; call fit first.")
        return np.asarray(self.feature_names_out_, dtype=object)

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not hasattr(self, "pipeline_"):
            raise RuntimeError("MLCleaner is not fitted yet; call fit first.")

        missing = [c for c in self.required_columns_ if c not in X.columns]
        if missing:
            raise ValueError(
                "transform is missing "
                f"{len(missing)} column(s) the fitted pipeline needs: "
                f"{', '.join(repr(c) for c in missing)}. "
                "Imputing a feature that was never supplied would be a guess, "
                "so this fails instead."
            )
        # Known-but-dropped columns (an id the pipeline removes) are not
        # reported here; only columns training never saw at all.
        known = set(self.feature_names_in_)
        self.unknown_columns_ = [c for c in X.columns if c not in known]

        out = self.pipeline_.apply(X, include_row_steps=False)
        absent = [c for c in self.feature_names_out_ if c not in out.columns]
        if absent:
            raise ValueError(
                "transform could not reproduce "
                f"{len(absent)} fitted output column(s): "
                f"{', '.join(repr(c) for c in absent)}. "
                "Reindexing would fill them with nulls and hide the problem."
            )
        # Reindex on columns only; the index, and so the row count, is untouched.
        return out.reindex(columns=self.feature_names_out_)

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
