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

## Checks (v0.1)

| Check | What it catches |
|---|---|
| `target_leakage` | features with near-perfect association to the target |
| `id_column` | identifiers accidentally left in the features |
| `missing_values` / `missing_target` | gaps by column, unlabeled rows |
| `duplicate_rows` | exact duplicates (and duplicates hiding behind ids) |
| `constant_column` / `quasi_constant_column` | zero-signal columns |
| `class_imbalance` / `rare_classes` | skewed and under-represented labels |
| `outliers` / `skewed_feature` | 3×IQR outliers, heavy skew |
| `high_cardinality` | categorical columns one-hot would explode on |
| `mixed_types` / `numeric_stored_as_text` | dtype traps |
| `whitespace_padding` / `case_inconsistency` | `' yes'` vs `'yes'` categories |

## Cleaning strategies

Never silently destructive — every change is a recorded step with a reason.

- `audit_only` — report, change nothing (default mindset)
- `safe` — strip whitespace, drop exact duplicates and constant columns, drop unlabeled rows
- `balanced` — safe + drop id/leaky columns, impute moderate gaps (with missing indicators)
- `aggressive` — balanced + drop very-high-missing and quasi-constant columns

## CLI

```bash
mlclean audit data.csv --target churn
mlclean audit data.csv --target churn --json report.json --fail-on high   # CI gate
```

## Roadmap

- [ ] `compare_train_test(X_train, X_test, ...)` — split consistency audit
- [ ] scikit-learn `MLCleaner` transformer (fit on train, transform test)
- [ ] HTML report
- [ ] Correlation / multicollinearity warnings
- [ ] Polars support

## License

MIT © Krushil Dhankecha
