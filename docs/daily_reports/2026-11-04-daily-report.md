# mlclean daily report — 2026-11-04

## Executive summary

- Seven PRs are open, all CI-green, nothing merged since #5 on 2026-11-02. Six
  user-visible bugs have fixes sitting in that stack, so all six are still live for
  anyone who installs 0.2.0 from PyPI today. This is the day's only P0.
- Two new bugs found by auditing frames with awkward column labels. Integer column
  names break the `id_column` check outright, and duplicate column names break seven
  of twelve checks. Both come back as `check_error` findings, so the audit survives and
  quietly reports almost nothing.
- The names in findings are not the names `checks=` and `skip=` accept. A user who
  reads `disguised_missing` in the report and writes `skip=["disguised_missing"]` gets
  a `ValueError`. The README's one example, `skip=["outliers"]`, happens to be a name
  that works in both places, which is why this has gone unnoticed.
- Every README example still runs, verified end to end against the real Telco file:
  quickstart, markdown/JSON export, pipeline save, replay, and the `MLCleaner`
  fit/transform path.
- The audit's own output on the demo dataset is still wrong in two visible ways
  ("Missing cells: 0" when there are 11, "100% of values parse" above advice to inspect
  the ones that don't). PR #11 fixes the finding text; the header's missing-cell count
  is a separate counter and still only counts NaN.
- `pandas>=1.5` is an untested claim. CI installs an unpinned `.[dev]`, so each Python
  version gets the newest pandas that supports it — pandas 2.x on 3.9, 3.1 on 3.13.
  Nothing anywhere exercises the declared floor.
- pandas 3.0 shipped in January 2026 and changed the default string dtype from `object`
  to `str`. mlclean already handles it (`_is_textual` tests both), and the matrix
  covers pandas 2 and 3 by accident of resolution. No action; worth knowing it is safe.
- Performance at 1M × 8 is 5.9s for an audit, 4.1s of which is three checks making
  separate Python-level passes over the same string columns. Peak RSS is 2.5× the
  frame, and nothing is printed while the user waits.
- CLI error handling is raw: a missing file or an unknown target column prints a
  pandas or mlclean traceback. Exit codes are correct (1), which is what the CI gate
  depends on, so this is cosmetic but it is the first thing a new user sees when they
  typo a filename.
- Competitive position got better without any work: openclean's last release was 2021,
  pyjanitor's last changelog entry is March 2024, and Soda Core 4.x replaced its checks
  language with data contracts — more rules to write, which is the thing mlclean is
  positioned against.

## Repository health

- Tests: 51 passed in 1.0s on `main`. Branches add their own (57 on the leakage branch,
  55 on #11's, 54 on #12's).
- Lint: `ruff check .` clean. Formatting is deliberately not `ruff format` clean and CI
  does not check it.
- Coverage: 93% overall on `main`. Thinnest: `cleaning.py` 82%, `checks/leakage.py` 88%,
  `checks/outliers.py` 89%.
- CI: green on every open PR, across py3.9–3.13 on Linux plus macOS and Windows on 3.13.
- Open PRs: 7. Merge order, with the stacked ones named:
  - `#9` (docs: product audit + roadmap) → `#10` (leakage by mutual information; base
    `main` but contains #9's commit, so #9 first keeps history clean)
  - `#6` (split `report`/`cleaning` into packages) → `#12` (base `refactor/package-layout`)
  - `#7` (split `checks/types.py` per concern) → `#11` (base `refactor/split-type-checks`)
  - `#8` (memory footprint check) last — it also touches `checks/__init__.py`
  - `#11` and `#12` are based on their parents, not `main`. If a parent merges, its
    child needs a rebase before it can go in.
- Open issues: 0. None have ever been filed. Discussions are disabled, so there is no
  inbound channel at all right now.
- Dependencies: 0 dependabot alerts, no open bump PRs. Runtime deps are still
  `pandas>=1.5` and `numpy>=1.23` only.
- Published vs main: PyPI has 0.2.0 (the only release). `main` is identical to it
  except for nothing — every change since is on a branch.
- TODO/FIXME/HACK/XXX in `mlclean/` and `tests/`: none.

## New issues found

**Bug — integer column names break the `id_column` check (P1).**
`mlclean/checks/types.py:75` does `name = column.lower()`. A frame whose columns are
integers — `pd.DataFrame(ndarray)`, or `pd.read_csv(path, header=None)` — raises
`AttributeError: 'int' object has no attribute 'lower'`, and the crash guard turns the
whole check into one `check_error` finding. Reproduced on a 60 × 3 numeric frame. Same
line lives at `checks/identifiers.py:25` after #7.

**Bug — duplicate column names break seven of twelve checks (P1).**
With `columns=["a", "a"]`, `df[column]` returns a DataFrame, not a Series, and
`missing`, `constant`, `ids`, `mixed_types`, `text`, `cardinality` and `sentinels` all
fail (`AttributeError: 'DataFrame' object has no attribute 'dtype'` and friends). The
audit completes and shows seven `check_error` findings, so a user gets a clean-looking
report built from five checks. Excel exports and un-suffixed joins produce this
constantly.

**Enhancement — `checks=`/`skip=` reject the names the report prints (P1).**
Findings are named `disguised_missing`, `missing_values`, `id_column`,
`whitespace_padding`; the selectors accept `sentinels`, `missing`, `ids`, `text`. So
`audit(df, skip=["disguised_missing"])` raises `ValueError: unknown check name(s)`. The
error message does list the valid names, which softens it, but the natural guess is
wrong and the documented example hides the mismatch.

**Enhancement — nothing tests the declared pandas floor (P1).**
`pyproject.toml` promises `pandas>=1.5`; CI resolves the newest pandas per Python
version, so the floor had never run. It does now, locally: 60 tests pass on pandas 1.5.3
with numpy 1.26.4 under Python 3.11, pandas' own numpy DeprecationWarnings aside. So the
code is fine and the claim is loose rather than false — `pandas>=1.5` with `numpy>=1.23`
describes combinations that break, because `pip install "pandas==1.5.3"` alone resolves
numpy 2.x and the 1.5.3 wheel was built against numpy 1.x headers:
`ValueError: numpy.dtype size changed`. Wants a CI job pinning both, and a README line
saying old pandas needs `numpy<2`.

**Bug — the leakage check misses one-sided exclusion (P1, carried).**
A feature that perfectly *excludes* a class scores 0.47 NMI and escapes every
threshold, including the new medium band in #10. Symmetric mutual information is the
wrong instrument for "this value never co-occurs with that label"; it wants a one-sided
measure as its own check rather than a lower threshold.

**Bug — `whitespace_padding` illustrates every column with `' yes'` vs `'yes'` (P2).**
On Telco the message reads "'TotalCharges' has 11 values with leading or trailing
whitespace — ' yes' and 'yes' become two categories", about a money column whose
offending values are blanks. The example should come from the column's own values.

**Bug — the header's missing-cell count disagrees with the findings below it (P2).**
"Missing cells: 0 (0.00%)" prints directly above a finding reporting 11 blank values in
the same dataset. PR #11 makes `disguised_missing` fire on those blanks, which makes
the contradiction louder rather than quieter: the header counts only NaN.

**Performance — three checks each walk the string columns in Python (P2).**
1M × 8 audit, measured: `text` 1.63s, `sentinels` 1.37s, `mixed_types` 1.08s, `leakage`
0.72s, everything else under 0.5s; 5.9s total, and 0.1s for `clean(strategy="balanced")`.
Peak RSS 483MB against a 194MB frame. The three string checks each do their own
`.map(isinstance)` or `.str.strip().str.lower()` pass over the same columns; one shared
normalized pass, or sampling for the type probe, would take most of that back. Nothing
is printed during the wait.

**Documentation — CLI tracebacks, and a stale heading (P2/P3).**
`mlclean audit missing.csv` prints a 25-line pandas traceback; a bad `--target` prints a
`ValueError` traceback from `audit.py:97`. Both exit 1 correctly. Separately, the README
check table is still headed "Checks (v0.1)" while listing v0.2 checks.

## User-value opportunities

Ranked by what they change for a user per unit of work.

1. **Land the seven-PR stack (S, owner action).** Six bugs are fixed and waiting. Until
   they merge and a release goes out, every one of them is what a new user actually
   meets. Nothing else on this list is worth more.
2. **Make the audit survive awkward column labels (S).** Integer and duplicate column
   names are not exotic; both fail silently-ish via `check_error`, which is the worst
   failure mode — the user reads a report that looks fine. One PR covers both, since
   both are "treat a column label as a label, and a selection as possibly a frame".
3. **Accept the printed names in `checks=`/`skip=` (S).** Pure papercut removal: an
   alias table and a test. Anyone who tries to silence a noisy check hits it.
4. **Pin the pandas floor in CI, or raise it (S).** Either the claim becomes true or it
   stops being made. The cost of being wrong here is an install that imports and then
   breaks on real data.
5. **One-sided leakage measure as its own check (M).** This is the library's headline
   claim — "finds what damages models" — and the current instrument misses a whole shape
   of leakage. Worth doing properly rather than by threshold.
6. **Shared string pass across the text checks (M).** 4s of a 6s audit, and the fix is
   structural rather than clever. Matters more as file sizes grow; pairs naturally with
   progress output on long runs.
7. **Column-specific examples in finding messages (S).** Cheap, and the credibility cost
   of a message that describes the wrong kind of data is higher than its size suggests.

## Competitive insights

Full sweep (the previous research pass covered a different six libraries; this one
covers the list mlclean is actually measured against). What changed and what it means:

- **pandas 3.0 (January 2026)** made `str` the default dtype for text instead of
  `object`, and made copy-on-write unconditional. mlclean's `_is_textual` already tests
  both dtypes, and because CI resolves pandas per Python version it is in fact testing
  pandas 2.x on 3.9 and 3.1 on 3.13. Fits scope, no work needed; the related risk is the
  untested 1.5 floor, not the new ceiling.
- **Soda Core 4.x** replaced its checks language with data contracts — a breaking change
  that asks users to write more declarative rules. This sharpens rather than threatens
  mlclean's pitch: the gap it serves is people who do not want to write rules at all.
  Their contract check vocabulary (missing, invalid, duplicate, aggregate, failed rows,
  metric) is worth reading as a checklist of what people expect to be checkable.
- **openclean looks abandoned** (last release 0.2.1, August 2021; copyright notices stop
  at 2021), and **pyjanitor's last changelog entry is v0.27.0, March 2024**. The
  "Python library that actually cleans" niche is thinner than it looks, which is the
  opening mlclean is walking into. Not a reason to relax: it is also evidence that the
  niche does not sustain attention on its own.
- **The Polars validation space is crowded and moving** — pandera, patito, pointblank,
  dataframely, validoopsie — and every one of them validates rather than fixes. Two
  specifics worth keeping: patito's selling point is reporting all validation errors at
  once instead of failing on the first, which is already how mlclean behaves and should
  be said out loud in the README; and pointblank's interactive HTML reports are the bar
  for the P4 HTML report item, not a plain static page.
- Nothing here changes scope. Time series (cleanTS) stays rejected, a validation DSL
  stays out, and a Polars backend stays deferred — though the Polars-side activity is
  the first weak signal that "pandas only" has a ceiling.

## Recommended work for today

1. **Decide the merge order and land what you can** — the stack is the P0 and it is
   owner action, not engineering.
2. **One PR for both column-label bugs**: `column.lower()` on a non-string label, and
   `df[column]` returning a DataFrame under duplicate names. Tests for an
   integer-column frame and a duplicate-column frame that assert zero `check_error`
   findings.
3. **Alias the selector names to the printed check names**, with a test that
   `skip=["disguised_missing"]` works.

## Recommended work for this week

1. Land the stack and cut 0.3.0 — six fixes plus two refactors is a release, and the
   version policy says a batch is exactly when to bump.
2. The column-label fixes and the selector aliases (today's 2 and 3, if they slip).
3. A pinned `pandas==1.5.3` + `numpy==1.26.4` CI job, so the floor stays proven rather
   than proven once by hand.
4. One-sided leakage measure as its own check, with the Criteo case as its test.
5. Make the header's missing-cell count include disguised blanks once #11 is in, so the
   summary line and the findings agree.

## Risks

- **Technical.** Fixes exist only on branches. Rebases get harder as the stack ages, and
  #11 and #12 are stacked on refactors that touch file layout — the window where they
  rebase cleanly is now, not next month.
- **Technical.** The `check_error` guard is good design doing quiet harm: a check that
  cannot run looks like a check that found nothing. Worth considering whether
  `check_error` findings should raise the report's overall severity so they cannot be
  skimmed past.
- **Product.** The library's headline is that it catches what damages models; two known
  gaps (one-sided leakage, and the published version's leakage check on 0/1 integer
  targets) sit directly under that headline.
- **Adoption.** 0 stars, 0 forks, 0 issues, discussions disabled. There is no feedback
  loop, so every finding in this report comes from dogfooding rather than from users.
  That is sustainable for a while and then it isn't.
- **Privacy.** None today: nothing phones home, no data is committed, and the audit
  prints column names and counts rather than values. Worth re-checking whenever a
  finding's message starts quoting data — the whitespace and sentinel messages already
  print example values, which is right for a local CLI and would be wrong in a hosted
  report.
- **Security.** No service mode exists, so the surface is a library plus a CLI reading
  local files. Workflows are SHA-pinned, `permissions: contents: read`, trusted
  publishing on a `pypi` environment. Nothing outstanding.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | visibility push is gated behind the stack |
| Forks | 0 | 0 | |
| Watchers | 0 | 0 | |
| Open issues | 0 | 0 | 5 filed today by this run |
| Open PRs | 7 | 5 (2026-11-03) | #11, #12 added |
| Tests (main) | 51 | 51 | 54–57 on branches |
| Coverage (main) | 93% | 93% | `cleaning.py` 82% is the floor |
| PyPI version | 0.2.0 | 0.2.0 | released 2026-11-02 |
| Dependabot alerts | 0 | 0 | |
| README examples run | 5 of 5 | not measured | verified on the real Telco file |
| Audit, 1M × 8 rows | 5.9s | not measured | first baseline |
| Suite on declared floor | 60 pass | never run | pandas 1.5.3 + numpy 1.26.4, py3.11 |
| Peak RSS vs frame | 2.5× | not measured | 483MB on a 194MB frame |

## Decision needed from owner

1. **Merge the stack.** `gh pr merge` is blocked for Claude by the auto-mode classifier,
   so this needs you. Recommended order: #9, #10, then #6, #12, then #7, #11, then #8,
   rebasing each child after its parent lands. Say the word and I will instead add a
   permission rule so the merges can run from here.
2. **Cut 0.3.0 once the stack is in?** Six user-visible fixes plus two refactors is the
   "accumulated batch" the version policy reserves a release for. Recommended: yes, in a
   dedicated release PR, right after #8.
3. **Should `check_error` raise the report's severity?** Today a check that cannot run is
   invisible in the summary. Recommended: yes, surface it at medium — a report built
   from five of twelve checks should not look like a clean bill of health.
4. **Which of today's three tasks should I implement?** Decided: the column-label bugs,
   shipped as #19 (stacked on #7). It also adds a `duplicate_column_names` check and
   makes `audit()` refuse a duplicated target instead of failing on `AttributeError`.
