# Changelog

## Unreleased

- `MLCleaner.transform` now returns the columns `fit` produced, in that order,
  whatever order the incoming frame is in. It raises `ValueError` when a column
  the pipeline needs is absent instead of dropping it and its indicator in
  silence, and drops columns training never saw, listing them in
  `unknown_columns_`. Previously the output column list was whatever the caller
  passed, so a serving frame assembled from a dict or JSON — where column order
  is arbitrary — could be scored in the wrong order with no error raised.
- `MLCleaner` records `feature_names_in_`, `n_features_in_`,
  `feature_names_out_` and `get_feature_names_out()` after fit.
- `MLCleaner.fit` matches a pandas `y` to `X` on the index rather than by
  position. A `y` holding the same labels in a different order previously
  mislabelled rows without raising, which made the leakage and missingness
  checks report on the wrong pairings. A `y` whose index does not cover `X`
  now raises `ValueError`; array and list targets still pair by position.

## 0.2.0 — 2026-11-02

- New check `disguised_missing`: sentinel values standing in for nulls —
  numeric codes like -999 sitting detached from the distribution, and
  NA-like text such as 'unknown' or 'n/a'.
- New check `informative_missingness`: columns whose gaps themselves predict
  the target (total variation distance for classification, standardized mean
  difference for regression).
- `audit()` takes `checks=` and `skip=` to select checks by name.
- A check that raises on unusual data no longer aborts the audit; it is
  reported as a `check_error` finding and every other check still runs.
- `MLCleaner`: a fit/transform transformer that learns the cleaning pipeline
  on the training frame and replays it unchanged — scikit-learn-compatible by
  convention, with no scikit-learn dependency. `transform` never changes the
  number of rows.
- Imputation fill values are now computed when the pipeline is built and
  stored in the serialized steps, so replaying on new data uses the training
  statistics instead of recomputing them. Pipelines saved by 0.1.0 still
  apply (they fall back to computing at apply time).
- `CleaningPipeline.apply(df, include_row_steps=False)` skips row-dropping
  steps for inference-time use.

## 0.1.0 — 2026-11-02

First release.

- `audit()` with checks for missing values, duplicate rows (including duplicates
  hiding behind id columns), constant and quasi-constant columns, identifier
  columns, mixed types, numeric-stored-as-text, whitespace padding, case
  inconsistency, high cardinality, outliers and skew, class imbalance, rare
  classes, and target leakage.
- Cleaning strategies `audit_only`, `safe`, `balanced` and `aggressive`; every
  change is recorded in a JSON-serializable `CleaningPipeline` that replays on
  new data.
- Reports as console text, Markdown and JSON.
- `mlclean audit` CLI with `--fail-on` for CI gates.
