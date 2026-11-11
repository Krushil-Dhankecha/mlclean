# Changelog

## Unreleased

- `clean()` keeps the index of the rows that survive, instead of renumbering
  from zero. Removing duplicates or dropping unlabeled rows used to discard
  the row labels, so a `y`, a weight column or the id column the audit told
  you to exclude could no longer be matched to the cleaned frame —
  `y.loc[clean_df.index]` silently returned the wrong rows. Call
  `.reset_index(drop=True)` yourself if you want contiguous numbering.
  `MLCleaner.transform` is unaffected; it never ran row steps.
- `clean()` now acts on `numeric_stored_as_text` instead of only reporting it.
  A column where every value parses is converted in the `safe` tier (dtype
  only); one where a few values don't is converted in `balanced` and above,
  where the resulting gaps can be imputed with the fit-time median and a
  missing indicator. Telco's `TotalCharges` came out of `clean()` as a
  6,531-category string before this.
- `CleaningPipeline.from_json` accepts the JSON text `to_json` returns. It
  probed the filesystem first, so any pipeline long enough to exceed the
  filename limit raised `OSError` instead of loading.
- Internal restructure: `report.py` is now the `mlclean.report` package
  (one module per output format) and `cleaning.py` the `mlclean.cleaning`
  package (`pipeline`, `steps`, `strategies`). No behavior change; all
  public imports keep working.

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
