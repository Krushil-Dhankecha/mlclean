# Changelog

## Unreleased

- Fixed: the target-leakage check could not fire on a low-cardinality integer
  target. Any numeric non-bool target routed numeric features to Pearson
  correlation, which measures only linear association and is bounded well
  below the 0.95 threshold between two low-cardinality columns — so the check
  was effectively off for 0/1 integer targets, the commonest shape in
  classification. Association now goes to mutual information unless *both*
  columns are genuinely continuous. A deterministic non-monotone relationship
  scored 0.5 by correlation and scores 1.0 by mutual information.
- Fixed: a continuous feature is no longer skipped as identifier-shaped. Such
  a column is near-unique, but it is binned into deciles before scoring, so a
  leaked probability or score column is now reported instead of ignored.
- New finding `target_leakage_suspect` (medium): association at or above 0.70
  but short of the near-perfect range. Previously anything under 0.95 produced
  no output at all, so a feature explaining 78% of the target's entropy was
  reported as nothing.

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
