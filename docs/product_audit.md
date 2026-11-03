# mlclean product audit

Audited 2026-11-03 against `main` at v0.2.0. Everything below was read out of
the code or measured, not inferred from the README. Three pull requests are
open and not included in the "current state" sections; they are listed in
[In flight](#in-flight) because they change the file layout the rest of this
document describes.

---

## 1. Features actually implemented

**One entry point.** `audit(df, ...)` runs every registered check over a
DataFrame and returns an `AuditReport`. There is no other analysis path.

**Twelve check selectors** (`mlclean/checks/__init__.py`) producing seventeen
distinct issue types:

| Selector | Issue types emitted |
|---|---|
| `missing` | `missing_values`, `missing_target` |
| `informative_missingness` | `informative_missingness` |
| `duplicates` | `duplicate_rows`, duplicates masked by id columns |
| `constant` | `constant_column`, `quasi_constant_column` |
| `ids` | `id_column` |
| `mixed_types` | `mixed_types`, `numeric_stored_as_text` |
| `text` | `whitespace_padding`, `case_inconsistency` |
| `cardinality` | `high_cardinality` |
| `sentinels` | `disguised_missing` |
| `outliers` | `outliers`, `skewed_feature` |
| `imbalance` | `class_imbalance`, `rare_classes` |
| `leakage` | `target_leakage` |

Selectable with `checks=[...]` / `skip=[...]`. A check that raises is caught
and reported as a `check_error` finding so one bad column cannot abort the run.

**Cleaning.** `report.clean(strategy)` builds a `CleaningPipeline` and applies
it, returning `(clean_df, pipeline)`. Five step kinds exist — `drop_columns`,
`remove_duplicates`, `strip_whitespace`, `impute`, `drop_unlabeled_rows` — in
four tiers: `audit_only`, `safe`, `balanced`, `aggressive`. Imputation fill
values are computed when the pipeline is built and stored in the step, so
replay uses training statistics.

**Reproducibility.** `CleaningPipeline.to_json()` / `.from_json()`; `.apply(df,
include_row_steps=False)` skips row-dropping steps so row counts stay aligned
at inference.

**Transformer.** `MLCleaner` implements `fit` / `transform` / `fit_transform` /
`get_params` / `set_params` by convention, with no scikit-learn dependency, and
exposes `report_` and `pipeline_` after fitting.

### What does **not** exist

No profiling beyond `report.summary()` (eight scalars). No numeric or
categorical distribution summaries. **No datetime handling of any kind** — no
date parsing, no date checks, no invalid-date detection. No validation layer.
No HTML report. No train/test comparison. No encoders, scalers, or splitting.
No PII detection. No fuzzy matching. No logging. No progress reporting. No
file-path input to the library API. No way to produce cleaned data from the
CLI. No service or API mode. No `docs/`, `examples/`, or notebooks.

---

## 2. Public API surface

Six names in `mlclean.__all__`: `audit`, `AuditReport`, `CleaningPipeline`,
`CleaningStep`, `DataIssue`, `MLCleaner`. `py.typed` ships, and type hints are
present throughout.

```
audit(df, target=None, task=None, id_columns=None, ignore_columns=None,
      missing_threshold=0.5, checks=None, skip=None) -> AuditReport

AuditReport.summary() -> dict
           .to_text() / .show() / .to_markdown(path=None) / .to_json(path=None)
           .clean(strategy="safe") -> (DataFrame, CleaningPipeline)
           .issues: list[DataIssue]        .df, .context

DataIssue(check, severity, message, recommendation, columns, details)
         .to_dict()

CleaningPipeline(steps, version).to_json(path) / .from_json(src)
                                .apply(df, include_row_steps=True)
CleaningStep(step, reason, columns, params)

MLCleaner(strategy="balanced", target=None, task=None, id_columns=None,
          ignore_columns=None, missing_threshold=0.5)
```

**CLI — one command.** `mlclean audit <path>` with `--target`, `--task`,
`--id-columns`, `--json PATH`, `--markdown PATH`, `--fail-on
{critical,high,medium,low}`, plus `--version`. `--fail-on` drives the exit code
for CI gating.

**Configuration** is constructor and keyword arguments only; there is no config
file, no environment variables, and no global state. Severity is a bare string
(`"critical"`…`"info"`) with a module-level order list, not an enum.

---

## 3. Input and output formats

| Direction | Supported | Notes |
|---|---|---|
| Library in | `pandas.DataFrame` only | A path raises; there is no loader |
| CLI in | CSV, Parquet | Dispatch is `path.endswith((".parquet", ".pq"))`, else `read_csv` unconditionally |
| Out | stdout text, JSON, Markdown | `to_json` / `to_markdown` take an optional path |
| Cleaned data out | **nothing** | `clean()` returns a frame in Python; no writer, no CLI path |

Two consequences worth naming. An `.xlsx` or `.json` file is handed to
`read_csv` and fails with a pandas parser error that does not mention the
format. And if `pyarrow` is absent, `mlclean x.parquet` raises pandas'
`ImportError` directly — the `parquet` extra is declared in `pyproject.toml`
but nothing checks for it or explains the fix. That line (`cli.py:43`) is one
of the few uncovered statements.

---

## 4. Dependencies and Python support

`pandas>=1.5`, `numpy>=1.23`. Nothing else. Extras: `dev` (pytest, pytest-cov,
ruff), `parquet` (pyarrow). `requires-python = ">=3.9"`, with 3.9–3.13
classifiers.

This is the project's single strongest asset and the audit's main warning: most
of the feature requests in the brief would end it. Competing libraries are
unmaintained or unusable largely because of dependency weight, and a two-package
install is a real differentiator, not a detail.

---

## 5. Tests

51 tests, 692 lines across six files, **93% statement coverage**, enforced in
CI at `--cov-fail-under=90`. Matrix: Ubuntu on 3.9–3.13 plus macOS 3.13 and
Windows 3.13, with `ruff check` on every job. Actions are SHA-pinned and
`persist-credentials: false`.

Quality is good for a library this young: checks are tested against purpose-built
frames, the transformer has its own file, and the CLI exit code is covered.

Weaknesses, by measured coverage:

- `cleaning.py` 82% — the thinnest area, and the one holding destructive logic.
  Lines 255–272 (the whole `aggressive` tier) are untested.
- `leakage.py` 88% — the headline feature. Lines 23–26, 41, 59, 63 uncovered.
- `outliers.py` 89%, `sentinels.py` 94%.
- No messy-data corpus. Every fixture is synthetic and well-formed; nothing
  exercises mixed encodings, ragged rows, Excel artefacts, or stray types deep
  in a column. Two of the five known bugs below only appear on real data.
- No golden-file tests on report output, so text/Markdown/JSON can drift apart.
- No parquet path test, no property-based tests, no benchmark.

---

## 6. Documentation gaps

README is strong — honest positioning against ydata-profiling, Great
Expectations and Cleanlab, real sample output, a quickstart, a check table.
Docstrings are substantive and explain *why*, not just *what*.

Missing: any `docs/` directory (this file is the first), API reference, hosted
docs, per-check reference documenting thresholds and their rationale,
`examples/` directory, runnable notebook, `CODE_OF_CONDUCT.md`, and
documentation of the privacy properties of report output. `CONTRIBUTING.md` is
28 lines and `SECURITY.md` 10.

---

## 7. Security, privacy, performance, scalability

**Security — low risk, by construction.** No `eval`, no `pickle`, no network,
no subprocess. Pipelines serialize to JSON, so loading an untrusted pipeline
cannot execute code; the worst case is a malformed step name raising `KeyError`
from the applier table. Release uses PyPI Trusted Publishing over OIDC with
`id-token: write` scoped to the publish job.

**Privacy — undocumented and the most likely surprise.** Reports embed data,
not just statistics. `disguised_missing` details carry the actual sentinel
tokens found; `mixed_types` carries type names; messages quote column names
throughout. A JSON report committed to a repository or pasted into an issue can
therefore leak column semantics and sample values. This is defensible behaviour
— the findings are useless otherwise — but it is nowhere stated, and there is
no redaction switch.

**Performance — unmeasured.** There is no benchmark in the repo. By inspection:
leakage runs a `pd.crosstab` per feature against the target, so cost grows with
columns × rows; `check_text_hygiene` applies Python-level `map` over full
columns; `_binned` runs `qcut` per column. Nothing samples, nothing chunks,
nothing reports progress, and there is no documented size ceiling. A user
auditing a few million rows has no idea whether to expect seconds or minutes.

**Scalability.** Entirely in-memory pandas. No Polars or DuckDB path.
`AuditReport` holds a reference to the frame (`report.df`), so keeping a report
keeps the dataset alive — relevant when auditing several files in a loop.

**Correctness — five verified defects**, found by running the library against
real datasets rather than fixtures. These matter more than any new feature:

1. **Leakage cannot fire on a 0/1 integer target.** `leakage.py:53` marks any
   numeric non-bool target as numeric, so `leakage.py:79` routes numeric
   features to Pearson correlation — which against a binary target is bounded
   far below the `ASSOCIATION_FLAG = 0.95` threshold. Demonstrated on Criteo: a
   post-outcome column with `P(y=1 | x=0) = 0` over 95,934 rows and normalized
   mutual information of 0.4555 was not flagged, because Pearson came out at
   0.2498. This silently disables the headline check on the commonest target
   shape in classification. Binary-vs-binary must route to mutual information
   regardless of storage dtype.
2. **No severity tier below 0.95.** A dataset whose label is a thresholded
   feature scored NMI 0.7816 and produced no finding at any severity.
3. **`dtypes.py` formats the parse rate with `:.0%`**, so 0.9984 prints as
   "100% of values parse as numbers" directly above its own advice to inspect
   the non-numeric ones. A user who trusts the message runs a bare
   `pd.to_numeric` and gets a `ValueError`.
4. **The sentinel frequency floor hides rare blanks.** `sentinels.py:86`
   requires a 0.5% share; the Telco dataset's eleven `' '` values are 0.156%,
   so `disguised_missing` never fires and the report header prints
   `Missing cells: 0 (0.00%)` for a dataset that has eleven.
5. **`clean()` ignores `numeric_stored_as_text`.** The finding is reported and
   never acted on, so a before/after demonstration does not actually fix the
   problem it opens with.

---

## 8. UX problems

- **The CLI cannot clean.** It audits and exits. The library's second half is
  unreachable from the command line, which is where the brief's target analysts
  live.
- **The library cannot open a file.** `audit()` requires a DataFrame, so every
  user writes their own `read_csv` first.
- **Format dispatch is a guess.** Anything not ending `.parquet`/`.pq` goes to
  `read_csv`.
- **A missing optional dependency produces a library-internal error** rather
  than "install mlclean[parquet]".
- **The crash guard converts bugs into silence.** A failing check becomes an
  `INFO` `check_error` buried under real findings. Bug 3 above reached a user
  as *no memory finding at all* rather than as an error — in a tool whose job
  is to report problems, a check that vanishes is indistinguishable from a
  check that passed.
- **No logging and no progress output.** `logging` is not imported anywhere, so
  a long audit is silent and unobservable.
- **No preview.** `clean()` is non-mutating, which is the right default, but
  there is no way to see the row and column deltas a strategy would produce
  without running it and diffing by hand.
- **Severity is a string.** Typos in `--fail-on` are caught by argparse, but
  `DataIssue(severity="High")` is accepted and then sorts last.

---

## 9. Gap analysis versus comparable tools

| Tool | Does well | Take from it | Do **not** copy | Concrete idea |
|---|---|---|---|---|
| **pandas** | The substrate; `convert_dtypes`, `interpolate`, `to_datetime` already solve much of §C | Delegate, never reimplement. `read_csv(dtype=)` beats post-hoc fixes | Its permissiveness — silent coercion is the problem mlclean names | Use `infer_dtype` / `to_datetime(errors="coerce")` under the hood and report the coercion rate |
| **pyjanitor** | Chainable, memorable verbs; thin wrapper over pandas | Naming discipline; `clean_names` is the canonical column-name normalizer | Method-chaining onto `DataFrame` — monkey-patching the user's namespace conflicts with "explicit configuration" | Ship `standardize_column_names` as a recorded, reversible step |
| **OpenRefine** | Transformation **history** and clustering of near-identical values; undo/redo | The history model is exactly mlclean's pipeline, proven over a decade | Interactivity and the GUI; a server-backed app is a different product | Adopt its clustering vocabulary (key collision, fingerprint) for label normalization — recommend-only |
| **Great Expectations** | Explicit suites, docs, batch validation | Separating validation from cleaning; machine-readable results | Config sprawl and the V2→V3→Fluent→1.0 churn that stranded users | A `rules.yaml` validation layer with **zero** required config to start |
| **Soda Core** | Compact declarative check language; CI/monitoring posture | Terse YAML checks; exit codes designed for pipelines | Warehouse-first assumptions | Reuse `--fail-on` semantics for `mlclean validate` |
| **openclean** | Academic rigour on functional dependencies and outliers | Statistical framing of anomaly detection | Heavy dependency graph; low maintenance | Functional-dependency violations as a check (`city` → `postcode`) |
| **DataKleaner** | Tiny scope, trivially understandable | Nothing beyond "small can be enough" | It auto-treats outliers by default — destructive without consent | — |
| **cleanTS** | Time-series-specific cleaning | That time series need their own split/leakage rules | Scope: time series is a separate product | Keep temporal order out of v1; document the gap honestly |
| **CPClean** | Principled "does cleaning change the prediction?" framing | The impact framing: rank issues by effect on the model | Its compute cost | Report *estimated impact* on a recommendation, which is the brief's "impact" field |
| **scikit-learn preprocessing** | Encoders, scalers, imputers, pipelines — mature, correct, universally known | Fit/transform semantics, already followed by `MLCleaner` | **Reimplementing it.** See roadmap §"What not to build" | Emit a ready-made `ColumnTransformer` spec instead of competing encoders |
| **ydata-profiling** | Breadth of descriptive profiling, HTML report | Report architecture; it prints actual memory per column | Its breadth and dependency weight; it breaks on pandas releases | Profile only what feeds a check. It reports *actual* memory and never *wasted* memory — the delta is unoccupied ground |
| **DuckDB** | Larger-than-memory SQL, zero-config | Out-of-core as an *optional* backend for profiling scans | Making it required | `mlclean profile big.parquet` via DuckDB when the extra is installed |
| **Polars** | Speed, lazy evaluation, strict typing | Strictness as a virtue | A rewrite. Backend abstraction is a Phase 3 decision, not a Phase 1 one | Narwhals-style thin internal layer only once the API is stable |

---

## 10. Prioritized backlog

Effort: **S** ≤ half a day, **M** one to three days, **L** a week or more.
"Value" is adoption impact, not novelty.

### Must precede any visibility push

| # | Item | Effort | Why |
|---|---|---|---|
| 1 | Fix leakage routing for binary integer targets (bug 1) | S | The headline check is silently off for most classification data |
| 2 | Add a MEDIUM association tier below 0.95 (bug 2) | S | 0.78 NMI currently produces nothing |
| 3 | Fix the `:.0%` parse-rate message (bug 3) | S | Self-contradictory advice that leads to a crash |
| 4 | Floor sentinels on count, not rate (bug 4) | S | Report prints "0 missing" for data with missing values |
| 5 | Make `clean()` act on `numeric_stored_as_text` (bug 5) | M | The before/after story does not currently work |
| 6 | Make the crash guard loud — surface `check_error` at WARNING and in the summary header | S | A vanished check must not look like a clean bill of health |

### Phase 1 candidates

| # | Item | Effort | Notes |
|---|---|---|---|
| 7 | File-path input + real format dispatch (CSV/TSV/Parquet/Excel/JSON) with actionable errors | M | Unblocks every CLI story; wire the `parquet` extra properly |
| 8 | `mlclean clean` CLI writing CSV/Parquet output | M | The library's second half is currently unreachable |
| 9 | `profile()` module: numeric, categorical and datetime summaries | M | Genuinely absent; keep it in service of checks, not competing with ydata |
| 10 | Datetime support: parsing, mixed-format detection, invalid and future dates | M | The single largest category gap — no datetime code exists at all |
| 11 | Enrich `DataIssue` with `confidence`, `auto_fixable`, `impact`, `transform_id` | S | Satisfies the brief's "recommendation" object without a parallel system |
| 12 | HTML report | M | Needed for notebooks and any public demo |
| 13 | Messy-data fixture corpus + `examples/` with a small committed dataset | M | Two of five bugs needed real data; no dataset is committed anywhere |
| 14 | `logging` with configurable verbosity; progress on long scans | S | Observability; prerequisite for large-data work |
| 15 | `dry_run` / diff preview of a strategy | S | "Review every transformation" needs a preview, not a rerun |
| 16 | Severity enum replacing bare strings | S | Cheap correctness win |

### Phase 2 candidates

| # | Item | Effort | Notes |
|---|---|---|---|
| 17 | `validate()` + `rules.yaml` validation layer | L | Separate from cleaning, per the brief |
| 18 | `compare_train_test()` | M | Cross-split duplicates, unseen categories, drift |
| 19 | Pipeline provenance: input/output hashes, timestamps, library version, lineage | M | Real differentiator; cheap once steps are stable |
| 20 | YAML pipeline serialization alongside JSON | S | Human-editable |
| 21 | ML-ready export: splitting, feature metadata, data dictionary, writers | L | Must stay leakage-safe |
| 22 | Export a standalone Python script reproducing a pipeline | M | Removes mlclean as a runtime dependency; strong trust signal |
| 23 | Functional-dependency check | M | From openclean |
| 24 | Benchmarks and a documented size ceiling | S | Replaces "unmeasured" with a number |
| 25 | Report redaction mode and a documented privacy posture | S | Reports currently embed sample values undocumented |

### Deferred or declined

See `docs/roadmap.md` for the reasoning. In short: encoders and scalers,
service mode, PII masking, LLM explanations, and a Polars rewrite are all
either outside the stated positioning or liabilities at this stage.

---

## In flight

Three open pull requests, all CI-green, none merged. They change the layout
described above:

- **#6** splits `report.py` into `mlclean/report/` (one module per output
  format) and `cleaning.py` into `mlclean/cleaning/` (`pipeline`, `steps`,
  `strategies`). Pure move.
- **#7** splits `checks/types.py` into `constant`, `identifiers`, `dtypes`,
  `text`, `cardinality`, plus `_common.py`. Pure move. Bugs 3 and 4 above live
  in files this PR moves, so fix them after it lands.
- **#8** adds a `memory_footprint` check plus `footprint()`, `dtype_plan()` and
  `optimize_dtypes()` — dtype narrowing with a plan learned once and replayed.

Both splits exist to make the layout above survive the roadmap: `report/` gains
the HTML renderer as a sibling file, and `cleaning/steps.py` is where new
operations go.
