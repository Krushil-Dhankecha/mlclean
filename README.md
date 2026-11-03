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
times over. On the Telco churn dataset that is 6.82 MB of RAM holding 0.94 MB
of data — 86% waste.

```python
from mlclean import footprint, dtype_plan, optimize_dtypes

footprint(df)                 # what it costs now vs what it could cost
small = optimize_dtypes(df)   # one-off: 6.82 MB -> 0.94 MB
```

**What this does not do.** It shrinks a frame you can already load; it does
not rescue one you cannot. `optimize_dtypes` runs after pandas has already
materialized those int64 columns, so if a file will not fit in memory,
`read_csv(dtype=...)` or chunked reading is strictly better — run
`footprint()` on a sample to work out what to pass.

### Correctness first

Narrowing dtypes is easy to do and easy to do wrong, and the widely copied
notebook versions do it wrong in ways that are hard to notice:

- **float64 becomes float32 only where every value round-trips exactly.**
  Tolerance-based checks are not enough: `np.allclose` calls `6082025490` and
  `6082025491` equal under float32 at `atol=5e-8`, so a tool gated on
  tolerance will silently merge two distinct IDs. mlclean compares for exact
  equality and leaves the column alone, or you pass
  `allow_lossy_float=True` and own the trade.
- **float16 is never used**, whatever the range of values. It merges distinct
  numbers wholesale — `[50001.0, 50002.0, 50003.0, 50004.0]` all become
  `50016.0`, four ids collapsing into one — and a numpy reduction over a
  float16 array overflows to `inf`. The notebook function that popularized
  downcasting tries float16 *first*, deciding on range alone, which is how
  this reaches so many pipelines.
- **`category` only when it measurably saves bytes.** A column whose values
  are nearly all distinct costs *more* as a category than as text, because
  the categories themselves have to be stored. mlclean estimates the real
  byte cost and declines when it is not a win.
- **Unsigned integers are opt-in** (`allow_unsigned=True`). `uint8` halves
  many 0-based columns, but a later subtraction underflows to 255 instead of
  going negative.
- **Object columns that hold anything but strings are left alone** rather
  than coerced into categories.

### One plan, replayed

Dtypes chosen from whatever frame is at hand diverge between training and
serving, which hands the model a feature type it was never fit on. So the
decision is made once and replayed:

```python
plan = dtype_plan(train_df)
json.dump(plan, open("dtypes.json", "w"))   # plain dict; ships with the model

small_train = optimize_dtypes(train_df, plan)
small_batch = optimize_dtypes(new_batch, plan)   # identical dtypes
```

Replay refuses to corrupt rather than doing it quietly:

- an integer outside the planned range raises instead of wrapping — numpy
  turns `1000` into `-24` in int8 without complaint
- a category the plan never saw raises instead of becoming NaN mid-inference
  (`on_unseen="nan"` for pandas' own behavior)
- a column the plan was built with but that is missing now raises
  (`on_missing="ignore"` to proceed); columns the plan never saw pass through
  untouched

Note that recent XGBoost and LightGBM align `category` dtypes themselves, so
the category half of this matters most for scikit-learn, hand-rolled
`.cat.codes` features, and CSV/parquet round trips — a CSV does not remember
that a column was categorical. Integer and float widths are not replayed by
any of them.

### Hazards worth knowing

- Narrow integers overflow on arithmetic, signed or not: an `int16` column
  times 1000 wraps negative, silently. Narrow what you feed a model, not what
  you still compute with.
- Run this *after* imputation. Assigning one NaN to an `int16` column turns it
  back into float64 and the saving is gone.
- `concat` with an unplanned frame degrades a `category` column back to text.

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
