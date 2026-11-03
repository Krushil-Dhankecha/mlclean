# Changelog

## Unreleased

- New check `memory_footprint`: reports how much of a frame's RAM is pandas
  defaults rather than data, with the columns responsible. On the Telco churn
  dataset: 6.82 MB holding 0.94 MB of data.
- New `footprint()`, `dtype_plan()` and `optimize_dtypes()`. The dtype plan is
  decided once on the training frame and replayed, so a later batch cannot
  pick its own dtypes and hand the model a feature type it was not fit on.
  The plan is a plain dict and serializes to JSON.
- Only provably lossless conversions are planned by default: float64 becomes
  float32 only where every value round-trips exactly (`allow_lossy_float=True`
  to override), and unsigned integers are opt-in (`allow_unsigned=True`) since
  `uint8` makes later subtraction underflow.
- Replaying a plan raises rather than corrupting: an integer outside the
  planned range would wrap (numpy casts 1000 to -24 in int8), and a category
  the plan never saw would become NaN at inference time. Pass
  `on_unseen="nan"` for pandas' own behavior.
- `footprint()` estimates rather than converts, and tests float32 exactness in
  one-million-row blocks, so the extra memory it needs is bounded by the block
  size instead of the size of the frame: measured flat at 19.1 MB for a float
  column of 22.9 MB and of 91.6 MB.
- Replaying a plan also raises when a column the plan was built with is
  missing from the frame (`on_missing="ignore"` to proceed). Plans record
  every column they saw, not only the ones they change.
- Object columns holding anything other than strings are left alone instead of
  being coerced into categories.

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
