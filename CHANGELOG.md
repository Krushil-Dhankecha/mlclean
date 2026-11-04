# Changelog

## Unreleased

- Column labels that are not strings no longer break the `id_column` check.
  `pd.read_csv(path, header=None)` and `pd.DataFrame(ndarray)` give integer
  labels, and the name heuristic called `.lower()` on them, which took the
  whole check down as a `check_error`.
- Frames with duplicate column labels are audited properly. Checks now read
  each column by position, because `df[label]` returns a DataFrame when two
  columns share a name — that was failing seven of the twelve checks, and the
  audit still completed, so a report built from the five survivors looked
  like a clean result. Both copies of a duplicated label are now checked
  independently.
- New check `duplicate_column_names` (selector `labels`): repeated labels are
  a data-quality problem in their own right, and the finding lists the
  positions so the copies can be told apart.
- `audit()` refuses a duplicated target column with a clear message instead of
  failing on `AttributeError` outside the crash guard. Which copy is the label
  is not something it should guess.

- Internal restructure: `checks/types.py` is split into one module per
  concern — `constant`, `identifiers`, `dtypes`, `text`, `cardinality` —
  with the shared `is_textual` helper in `checks/_common.py`. No behavior
  change; check names and the `checks=`/`skip=` selectors are unchanged.

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
