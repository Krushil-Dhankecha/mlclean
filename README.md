# mlclean

[![ci](https://github.com/Krushil-Dhankecha/mlclean/actions/workflows/ci.yml/badge.svg)](https://github.com/Krushil-Dhankecha/mlclean/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mlclean)](https://pypi.org/project/mlclean/)
[![Python](https://img.shields.io/pypi/pyversions/mlclean)](https://pypi.org/project/mlclean/)

**ML-aware data quality auditing and cleaning for pandas DataFrames.**

Before you train, `mlclean` answers one question: *what is wrong with this
dataset, what should I fix, and how do I reproduce those fixes?* It finds the
problems that actually damage models — target leakage, identifier columns,
duplicates shared across splits, class imbalance, silent category mismatches —
not just the ones that look untidy.

```text
mlclean audit report
====================

Rows: 10,000   Columns: 24
Target: churn   Task: classification
Duplicate rows: 36   Missing cells: 1,842 (0.77%)

CRITICAL (1)
------------
1. 'cancellation_flag' predicts target 'churn' almost perfectly
   (normalized mutual information = 1.000). Features this strong are
   usually recorded after the outcome or derived from it.
   -> Verify the business timeline: if the value exists only after the
      prediction moment, remove it from the features.
```

## Why not ydata-profiling / Great Expectations / Cleanlab?

- **ydata-profiling** tells you what the data looks like. `mlclean` tells you
  what will go wrong when you train on it.
- **Great Expectations** validates rules you write. `mlclean` is zero-config:
  one call, opinionated ML-specific checks.
- **Cleanlab** digs into label quality with trained models. `mlclean` runs
  before you have a model at all.

## Install

```bash
pip install mlclean
```

## Quickstart

```python
import pandas as pd
from mlclean import audit

df = pd.read_csv("customer_churn.csv")

report = audit(df, target="churn")
report.show()                      # console summary, most severe first
report.to_markdown("REPORT.md")    # for the repo / PR
report.to_json("report.json")      # for CI

clean_df, pipeline = report.clean(strategy="safe")
pipeline.to_json("cleaning_steps.json")   # reproducible, auditable
```

Replay the exact same cleaning anywhere:

```python
from mlclean import CleaningPipeline

pipeline = CleaningPipeline.from_json("cleaning_steps.json")
new_clean = pipeline.apply(new_df)
```

## In a scikit-learn workflow

Cleaning decisions must be learned on the training split only — recomputing
medians on the test set is quiet leakage. `MLCleaner` freezes everything at
fit time: which columns get dropped and the exact fill values.

```python
from mlclean import MLCleaner

cleaner = MLCleaner(strategy="balanced")
X_train_clean = cleaner.fit_transform(X_train, y_train)
X_test_clean = cleaner.transform(X_test)   # same drops, train's medians
```

`transform` never changes the number of rows, so X stays aligned with y
inside pipelines and cross-validation. Deduplicate before splitting, with
`audit(df).clean()`. No scikit-learn dependency — the transformer follows the
convention, it doesn't import the library.

## Checks (v0.1)

| Check | What it catches |
|---|---|
| `target_leakage` | features with near-perfect association to the target |
| `id_column` | identifiers accidentally left in the features |
| `missing_values` / `missing_target` | gaps by column, unlabeled rows |
| `informative_missingness` | gaps whose pattern predicts the target |
| `disguised_missing` | sentinels like `-999` or `'unknown'` standing in for NaN |
| `duplicate_rows` | exact duplicates (and duplicates hiding behind ids) |
| `constant_column` / `quasi_constant_column` | zero-signal columns |
| `class_imbalance` / `rare_classes` | skewed and under-represented labels |
| `outliers` / `skewed_feature` | 3×IQR outliers, heavy skew |
| `high_cardinality` | categorical columns one-hot would explode on |
| `mixed_types` / `numeric_stored_as_text` | dtype traps |
| `whitespace_padding` / `case_inconsistency` | `' yes'` vs `'yes'` categories |
| `memory_footprint` | RAM spent on pandas defaults rather than data |

Run a subset with `audit(df, checks=["leakage", "duplicates"])` or drop noisy
ones with `skip=["outliers"]`. A check that fails on strange data never aborts
the audit — it comes back as a `check_error` finding and the rest still run.

## Cleaning strategies

Never silently destructive — every change is a recorded step with a reason.

- `audit_only` — report, change nothing (default mindset)
- `safe` — strip whitespace, drop exact duplicates and constant columns, drop unlabeled rows
- `balanced` — safe + drop id/leaky columns, impute moderate gaps (with missing indicators)
- `aggressive` — balanced + drop very-high-missing and quasi-constant columns

## Memory

pandas stores every whole number as int64, every decimal as float64 and every
string as a Python object. A column of ages needs one byte per row and gets
eight; a column of `'yes'` and `'no'` stores two distinct strings a million
times over. On the Telco churn dataset that is 6.82 MB of RAM for 0.94 MB of
data — 86% waste, and the reason a dataset that should fit raises
`MemoryError`.

```python
from mlclean import footprint, dtype_plan, optimize_dtypes

footprint(df)                 # measure; converts and copies nothing
small = optimize_dtypes(df)   # one-off: 6.82 MB -> 0.94 MB
```

The usual fix is a downcasting loop copied from a notebook, and it has two
problems. It chooses dtypes from *this* frame's min and max, so training data
and a later batch end up with different dtypes for the same column and the
model is handed a feature type it was never fit on. And it converts float64
to float32 unconditionally, changing values without saying so.

So the unit here is a plan, decided once and replayed:

```python
plan = dtype_plan(train_df)            # decide dtypes on the training data
json.dump(plan, open("dtypes.json", "w"))   # ships beside the model

small_train = optimize_dtypes(train_df, plan)
small_batch = optimize_dtypes(new_batch, plan)   # identical dtypes, guaranteed
```

Only provably lossless conversions are planned by default. float64 becomes
float32 only when every value survives the round-trip exactly; pass
`allow_lossy_float=True` to override. Unsigned integers are opt-in via
`allow_unsigned=True`, because `uint8` halves many 0-based columns but makes a
later subtraction underflow to 255 instead of going negative.

Replay refuses to corrupt data rather than doing it quietly. A value outside
the planned integer range raises instead of wrapping (numpy turns 1000 into
-24 in int8 without complaint), and a category the plan never saw raises
instead of silently becoming NaN at inference time — pass `on_unseen="nan"`
if you want pandas' own behavior.

## CLI

```bash
mlclean audit data.csv --target churn
mlclean audit data.csv --target churn --json report.json --fail-on high   # CI gate
```

## Roadmap

- [x] scikit-learn-style `MLCleaner` transformer (fit on train, transform test)
- [ ] `compare_train_test(X_train, X_test, ...)` — split consistency audit
- [ ] HTML report
- [ ] Correlation / multicollinearity warnings
- [ ] Polars support

## License

MIT © Krushil Dhankecha
