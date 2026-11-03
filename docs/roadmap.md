# mlclean roadmap

Written 2026-11-03 against the product brief, informed by
[`product_audit.md`](product_audit.md). This document is
opinionated on purpose, and it declines several items from the brief with
reasons.

## Status

Approved 2026-11-03 with three decisions, all as recommended below:

1. **Scope** — the decline list stands. No encoders or scalers, no service
   mode, no PII masking beyond detect-and-flag, no LLM explanations, no Polars
   rewrite.
2. **API shape** — module-level `profile()` / `clean()` / `validate()` beside
   the existing `audit()`. `MLCleaner` stays as it is, a fit/transform
   estimator.
3. **Phase 1 order** — bugs before reach.

Work started: leakage routing and the MEDIUM association tier (items 1 and 2
of Phase 1a).

---

## Positioning, sharpened

> mlclean tells you what will go wrong when you train on this data, recommends
> the fix, and records exactly what it changed so you can run it again.

Three words carry the product: **ML-aware** (it ranks problems by damage to a
model, not by untidiness), **explainable** (every finding states the evidence
and every change states the reason), **reproducible** (the pipeline is data,
serializable, replayable).

It is not a profiler, not a validation framework, and not a preprocessing
library. Each of those already has a better answer than mlclean will ever
build. What nobody owns is the opinionated layer between them.

---

## Four things in the brief that need deciding before any code

These are genuine tensions, not quibbles. Each one changes what Phase 1 means.

### 1. The brief asks for scikit-learn's preprocessing module

Section 3 says mlclean "should not try to replace pandas, Polars,
scikit-learn". Section C then asks for one-hot, ordinal, frequency and target
encoding, standard/min-max/robust scaling, and class-imbalance handling. That
is `sklearn.preprocessing` plus `ColumnTransformer`, which is mature, correct,
universally known, and would have to be reimplemented here without a
scikit-learn dependency.

**Recommendation: decline.** mlclean's edge is knowing *what* should be done to
a column and why. Re-encoding that knowledge as a worse `OneHotEncoder` costs a
permanent maintenance burden and invites a comparison we lose. Instead, ship
`report.to_sklearn()` emitting a ready-built `ColumnTransformer` specification
— the recommendation becomes executable without us owning the execution. One
exception worth keeping: **target encoding with leakage protection**, because
the leakage-safety part is genuinely our subject matter and the common
implementations get it wrong.

### 2. The example API collides with the existing `MLCleaner`

The brief's example uses `MLCleaner()` as a stateless façade with `.profile()`,
`.recommend()`, `.clean()` and `.apply_pipeline()`. But `MLCleaner` already
exists as a fit/transform transformer following the scikit-learn convention,
with `get_params`/`set_params` and fitted `report_`/`pipeline_` attributes. An
object that is simultaneously a stateful estimator and a stateless service
breaks the estimator contract and confuses both uses.

**Recommendation:** keep `MLCleaner` as the transformer, exactly as it is, and
put the façade at module level beside the existing `audit()`:

```python
from mlclean import profile, audit, clean, validate, apply_pipeline

prof   = profile(df)                       # describe
report = audit(df, target="churn")         # predict damage; issues carry recommendations
clean_df, pipeline = clean(df, report=report, dry_run=False)
pipeline.save("cleaning_pipeline.yaml")
new_df = apply_pipeline(raw_df, "cleaning_pipeline.yaml")
```

This matches the library's existing style, keeps one obvious way to do each
thing, and leaves `MLCleaner` free to be a well-behaved sklearn citizen.

### 3. "Recommendations" already exist under a different name

The brief specifies a `recommend()` returning objects with issue type, affected
columns and rows, severity, recommended action, confidence, a reversible
transform id, and a plain-English explanation. `DataIssue` already carries
check, severity, columns, message, recommendation and details. Building a
second parallel object means two sources of truth that will disagree.

**Recommendation:** extend `DataIssue` with `confidence`, `auto_fixable`,
`impact` (rows and columns affected) and `transform_id`, and expose
`recommend()` as a thin view over `report.issues` filtered to actionable
findings. Cheaper, and the report and the recommendations can never drift.

### 4. `inverse_transform` is mostly not possible

The brief asks for reversibility "where feasible" and also lists
`inverse_transform`. Honestly: dropping a column, removing duplicates,
imputing a missing value and dropping unlabeled rows are all irreversible —
the information is gone. Only scaling and some encodings invert.

**Recommendation:** do not advertise general reversibility. Mark each step
`reversible: true|false` in the pipeline, implement `inverse_transform` only
for the steps that genuinely support it, and raise a clear error naming the
first irreversible step otherwise. A tool whose selling point is trust should
not claim an undo it cannot deliver.

---

## Phase 1 — correctness and reach

The brief's Phase 1 lists fourteen items. Measured against the code, **seven
already exist**: duplicate detection, dtype inference, string and categorical
normalization, outlier detection, recommendations (as issues), JSON and
Markdown reports, and per-operation unit tests. So the real Phase 1 is smaller
and sharper than the brief assumes, and it starts with repair rather than
construction.

### 1a. Fix what is broken (all S, do first)

Five verified defects, detailed in the audit. They come first because every one
of them misfires on the dataset any demo would use, and because a visibility
push that lands on bug 1 costs more than it gains.

1. Route binary-vs-binary targets to mutual information, not Pearson — the
   leakage check is currently silent on 0/1 integer targets.
2. Add a MEDIUM association tier below the 0.95 threshold.
3. Fix the `:.0%` parse-rate message that contradicts its own advice.
4. Floor the sentinel check on count rather than rate.
5. Make `clean()` act on `numeric_stored_as_text`.
6. Make `check_error` loud — surface it in the summary header, not only as an
   INFO finding. A check that vanished must never look like a check that
   passed.

One design decision is needed here: fixing (1) alone still will not catch the
Criteo case, which scores 0.4555 NMI. Catching that needs either the new MEDIUM
tier set low, or a separate one-sided-leakage measure for features that
perfectly *exclude* a class. My recommendation is a MEDIUM tier at 0.70–0.95
plus one-sided leakage as its own check rather than stretching the threshold.

### 1b. Make it reachable (M)

7. **Loaders and format dispatch.** `audit("data.csv")` should work. Support
   CSV, TSV, Parquet, Excel and JSON by content and extension, raise actionable
   errors naming the format and the fix, and gate `pyarrow`/`openpyxl` behind
   extras with a message that names the extra.
8. **`mlclean clean`.** The CLI cannot currently produce cleaned data at all.
   `mlclean clean data.csv --strategy balanced --output clean.parquet
   --pipeline out.yaml --dry-run`.
9. **`logging` and progress.** Configurable verbosity; a progress indicator on
   scans over large frames. Nothing in the codebase imports `logging` today.
10. **Dry-run diff.** Row and column deltas a strategy *would* produce, without
    applying it.

### 1c. Fill the real feature holes (M)

11. **Datetime support.** The largest category gap: there is no datetime code
    in the library at all. Parsing, mixed-format detection, invalid dates,
    implausible future dates, and datetime feature splitting as an opt-in
    cleaning step.
12. **`profile()`.** Numeric summaries (min/max/mean/median/quantiles/std,
    zeros, negatives), categorical summaries (unique, top-n, rare categories),
    datetime coverage. Deliberately narrower than ydata-profiling: profile what
    feeds a check, and report *wasted* memory alongside actual, which nothing
    else prints.
13. **Enriched `DataIssue`** per decision 3 above.
14. **HTML report**, as a sibling module to the existing text/Markdown/JSON
    renderers. No template engine; one self-contained file.
15. **Messy fixture corpus and `examples/`.** Two of the five bugs only showed
    up on real data. No dataset is committed anywhere in the repo, so examples
    need either a small committed fixture or a download script.
16. **Severity enum** replacing bare strings.

Phase 1 exit criteria: every bug above closed, CLI covers profile/audit/clean,
coverage still ≥90%, `examples/` runs end to end on a committed dataset, and
the README quickstart matches reality.

---

## Phase 2 — the differentiator

Reproducibility and validation are where mlclean can be genuinely better than
the alternatives rather than merely lighter.

1. **Pipeline provenance** (M): input and output hashes, timestamps, library
   version, step order, and `reversible` flags per step. Cheap now that steps
   are stable, and it is the backbone of every trust claim.
2. **YAML serialization** beside JSON (S) — human-editable and reviewable in a
   pull request.
3. **Exported standalone script** (M): generate plain pandas code reproducing a
   pipeline with no mlclean at runtime. Strong trust signal, and it makes the
   audit trail legible to someone who does not use the library.
4. **`validate()` and `rules.yaml`** (L): required columns, null expectations,
   ranges, allowed values, unique keys, regex, date ordering, schema
   consistency across batches. Must start with zero required config — Great
   Expectations' config burden is the thing to avoid.
5. **`compare_train_test()`** (M): duplicates shared across splits, unseen
   categories, per-column drift. This is the item the audit's competitor table
   suggests has the clearest unserved demand.
6. **ML-ready export** (L): stratified splitting, feature metadata (origin
   column, transformation, dtype, role), data dictionary, writers for
   CSV/Parquet/JSON/Excel/SQLite, and `report.to_sklearn()` per decision 1.
7. **Functional-dependency check** (M), from openclean: `city` → `postcode`
   violations.
8. **Benchmarks and a documented size ceiling** (S): replace "unmeasured" with
   a number users can plan against.
9. **Privacy posture** (S): document that reports embed sample values, and add
   a redaction mode. Currently undocumented and the most likely user surprise.

---

## Phase 3 — only if Phase 2 lands and is used

1. **Optional DuckDB backend for profiling scans**, behind an extra, for
   larger-than-memory files. Profiling is the one workload where out-of-core
   genuinely helps; cleaning still needs the frame.
2. **Plugin system** (`register_check`) so users add checks without forking.
   The static `ALL_CHECKS` list is the current blocker.
3. **Narwhals-style internal layer** for Polars — *after* the public API has
   stopped moving, never before.

---

## What not to build, and why

Declining things is most of the value in this roadmap.

| Item | Verdict | Reason |
|---|---|---|
| Encoders and scalers | **Decline** | It is `sklearn.preprocessing`. Emit a `ColumnTransformer` spec instead; keep leakage-safe target encoding only |
| Class-imbalance resampling | **Decline** | `imbalanced-learn` owns this, and resampling belongs after the split, inside cross-validation, where mlclean does not sit. Keep the *warning* we already emit |
| FastAPI service mode | **Defer indefinitely** | This converts a two-dependency library into a hosted service needing auth, rate limits, temp storage with expiry, malformed-file scanning, audit logs and deletion controls. That is a product company's surface area, and the users most likely to care about data quality are the least likely to upload their data to a third party. If an API is ever wanted, ship it as a separate `mlclean-serve` package and never make it the default story |
| PII masking | **Downgrade to detect-and-flag** | Regex PII detection has a high false-positive rate, and masking by default is destructive and irreversible. Flag candidates, never auto-mask, and state plainly that it is a heuristic and not a compliance control |
| LLM-assisted explanations | **Decline in core** | Adds network calls, API keys and nondeterminism to a library whose entire pitch is determinism and two dependencies. The brief already forbids an LLM touching data; I would go further and keep it out of the package |
| Fuzzy label matching | **Recommend-only, optional extra** | Needs `rapidfuzz`, and merging categories is a semantic judgement. Cluster and suggest; never merge by default |
| Polars/DuckDB rewrite | **Not now** | Premature. An abstraction layer locks in an API that is still changing |
| General `inverse_transform` | **Scope down** | Per decision 4: per-step flags and honest errors beat a promised undo that cannot work |
| Time-series cleaning | **Out of scope for v1** | A separate product with its own split and leakage rules (see cleanTS). Document the gap rather than half-building it |

---

## Sequencing against the open pull requests

Three PRs are open and CI-green: #6 and #7 restructure `report.py`,
`cleaning.py` and `checks/types.py` into packages; #8 adds the memory
footprint check. **Merge all three before Phase 1 starts.** Bugs 3 and 4 live
in files #7 moves, and Phase 1 adds a renderer (`report/html.py`) and new steps
(`cleaning/steps.py`) that the splits exist to accommodate. Starting Phase 1 on
the old layout means doing the merge conflicts twice.

---

## Engineering standards

Already met: tests alongside features, non-mutating operations, explicit
configuration with no global state, destructive tiers opt-in via `strategy`,
minimal dependencies with heavy ones as extras, CI for lint and tests across
seven platform/version combinations, SHA-pinned actions, Trusted Publishing,
`py.typed` with hints throughout, a changelog.

To add: type checking in CI (mypy or pyright — currently neither runs), a
package-build job, golden-file tests on report output so the three renderers
cannot drift, a messy-data fixture corpus, and benchmarks.

Versioning follows the project's existing convention: changes accumulate under
`Unreleased` in the changelog and a version is cut for a batch, not per pull
request. Phase 1 as scoped here is a 0.3.0.
