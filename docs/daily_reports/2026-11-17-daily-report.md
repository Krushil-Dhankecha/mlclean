# mlclean daily report — 2026-11-17

## Executive summary

- **New P0: `clean()` itself raises on a nullable `boolean` column with nulls.** The
  audit passes, then `clean(strategy="balanced")` and `MLCleaner.fit_transform` both die
  with `TypeError: Invalid value '1.0' for dtype 'boolean'`. `convert_dtypes()` and
  `read_parquet` produce that dtype from any boolean column with gaps, so this is an
  ordinary path. Unfiled before today; no fix on any branch.
- **The cleaning path has no crash guard.** `audit()` turns a failing check into a
  `check_error` finding; `clean()` and `MLCleaner` let the exception out. That asymmetry
  is what makes the finding above a P0 rather than a bad fill value.
- **New P1: `CleaningPipeline.to_json()` raises on a datetime, timedelta or period fill
  value.** `clean()` hands back a frame and a pipeline, and then the pipeline cannot be
  written — which is the README's own `# reproducible, auditable` line.
- Reproducibility is the one thing the nine abandoned look-alikes measured on 11-11 do
  not have, so a serialization hole costs more here than its size suggests.
- **New P2: a column of lists silently loses 5 of 12 checks** (`unhashable type: 'list'`
  in `duplicates`, `constant`, `ids`, `cardinality`, `leakage`). The audit reports zero
  findings and reads clean. A new and very ordinary trigger for #23.
- Probed and clean, first time any run has looked: datetime with `NaT` (naive and
  tz-aware), nullable `Int64`/`Float64`, and a categorical with an unused category. No
  crash, no wrong number.
- `main` is still `b48eb32`, fifteen days old. PyPI 0.2.0 equals `main` exactly, so none
  of the 20 open PRs has reached a user.
- Six of the 20 PRs are red live, all on `test (ubuntu-latest, 3.9)`. **#32 is still the
  only PR green against today's runners**, and still the only merge that unblocks the
  rest.
- #44 and #11 re-confirmed live on 0.2.0 by today's Telco run: two of the four findings
  on the project's own demo file argue from a premise the same report rejects.
- Competitive delta: nothing moved but a pyjanitor patch. One line below.

## Repository health

- **Tests:** 51 pass in 0.82s on `main`; 54 pass in 0.93s on `fix/high-cardinality-numeric-text`.
- **Lint:** `ruff check .` clean on both. No `TODO`/`FIXME`/`HACK`/`XXX` anywhere in
  `mlclean/` or `tests/`.
- **Coverage:** 93% on `main` (698 statements, 49 missed). `cleaning.py` at 82% is the
  floor, and both of today's new findings live in that file.
- **CI:** 14 contexts. Six PRs are **FAILURE:2 / SUCCESS:12** — #30, #38, #39, #41, #43,
  #45 — every failure being `test (ubuntu-latest, 3.9)`. The 14 other PRs still advertise
  14/14 from runs dated 2026-11-03, before `ubuntu-latest` rolled to Ubuntu 26.04. Those
  greens are stale, not passing.
- **Open PRs: 20.** Merge order, read off each PR's `baseRefName` today:
  - **#32 first and alone** (`ci/python39-runner-pin` -> `main`). Nothing else can go
    green until it lands.
  - Stack A: **#6** -> **#12** -> **#38**
  - Stack B: **#7** -> **#11** and **#19** (siblings; the second needs a rebase)
  - Stack C: **#32** -> **#33** and **#37**
  - On `main`, independent: #8, #9, #10, #13, #20, #26, #30, #39, #41, #43, #45, and this
    report's PR.
  Six are stacked, so the cost of the queue rises daily rather than staying flat.
- **Open issues: 21.** None stale in the sense of lacking a reproduction — every one
  carries a measured repro. #40 and #34 and #21 and #31 are the four P0s; #31's fix is
  PR #32 and #34's is PR #38, both unmerged.
- **Dependencies:** 0 dependabot alerts, 0 open bump PRs. Workflow actions stay SHA-pinned.
- **Published version vs main:** `0.2.0` on PyPI == `main` at `b48eb32`. Verified today
  from a clean venv: `pip install mlclean` works, `audit()` runs, 12 checks registered.
  Every fix in the 20 open PRs is still absent for anyone installing today.
- **README and CLI:** all four README code blocks and both documented CLI forms run
  against the real Telco file on `main`. `--fail-on high` correctly exits 0 on a
  medium-only report.

## New issues found

### Bugs

- **P0 — `clean()` and `MLCleaner.fit_transform` raise on a nullable `boolean` column
  with nulls.** No fix on any branch. `cleaning.py:216` asks
  `pd.api.types.is_numeric_dtype(report.df[column])`, which is `True` for pandas'
  `BooleanDtype`, so the column joins `numeric_gaps`; line 230 learns
  `report.df[c].median()`, which is `np.float64(1.0)`; `_apply_impute` line 126 then runs
  `out[column].fillna(1.0)` and pandas refuses:
  `TypeError: Invalid value '1.0' for dtype 'boolean'`. Measured on a 400-row frame with
  40 `pd.NA` in a `boolean` column: `audit()` returns its one missing-values finding,
  `clean("safe")` returns `(400, 3)`, and `clean("balanced")`, `clean("aggressive")` and
  `MLCleaner(strategy="balanced").fit_transform` all raise. The mode of that column is
  `True` and would have worked; it is the numeric routing that is wrong, not the fill.
- **P0 (same finding, the reason it is a P0) — the cleaning path has no crash guard.**
  `audit()` wraps every check and emits `check_error`; `CleaningPipeline.apply`,
  `report.clean` and `MLCleaner.transform` wrap nothing. One unexpected dtype takes the
  whole call down after the audit has already told the user the data is fine.
- **P1 — `CleaningPipeline.to_json()` raises on a temporal fill value.** No fix on any
  branch. `_json_scalar` (`cleaning.py:151-153`) converts a value only when it has
  `.item()`. `pd.Timestamp`, `pd.Timedelta` and `pd.Period` have none and pass through
  untouched; `np.datetime64.item()` returns a `datetime.date`, which `json.dumps` also
  refuses. So a datetime, timedelta or period column with gaps gives
  `TypeError: Object of type Timestamp is not JSON serializable` on the README's own
  `pipeline.to_json("cleaning_steps.json")` line. Confirmed for naive datetime, tz-aware
  datetime, timedelta and period; `Int64`, `Float64`, `category`, `float64` and object
  columns all serialize fine. The fix is two-sided — `from_json` has to restore the type,
  or a replayed pipeline will try to fill a datetime column with a string.
- **P2 — a column holding lists silently loses 5 of 12 checks.** `duplicates`,
  `constant`, `ids`, `cardinality` and `leakage` each fail with
  `unhashable type: 'list'`; the audit returns **0 real findings and 5 `check_error`
  findings at INFO**, so the report reads clean. This is a new trigger for the hole
  already filed as **#23** (`check_error` is INFO) rather than a new defect, and it is
  reached by the ordinary route: `groupby().agg(list)` or `json_normalize` on nested
  JSON. Adding it to #23 as evidence, not filing it separately. Worth noting the better
  fix for the checks themselves: skip an unhashable column the way they skip a
  non-textual one, rather than failing.

### Re-confirmed, already filed, still live for users

- **#44 + #11, on the demo file.** Today's Telco run on `main` prints, at the same MEDIUM
  severity: "'TotalCharges' is text but 100% of values parse as numbers" (the true rate
  is 99.84% — 11 blanks) and "'TotalCharges' has 6,531 distinct categories -> prefer
  frequency or target encoding". Two of four findings argue from a premise the same
  report rejects. Fixes exist on PR #11 and PR #45; neither is merged.
- **#31.** The six live-red PRs are all red on `test (ubuntu-latest, 3.9)`, confirmed from
  #45's job log. PR #32 fixes it and is the only PR green against today's runners.

### Not bugs — probed today, do not re-probe

- `datetime64` with 20 `NaT`, naive and tz-aware: `audit()` counts the gaps correctly
  (`Missing cells: 20 (1.67%)`, "missing in 20 rows (5.0%)"), and `clean("balanced")`
  imputes them with a Timestamp and leaves none behind.
- Nullable `Int64` and `Float64` with `pd.NA`: audit, clean and `to_json` all correct.
- `category` with an unused category level: no crash. Nothing reports the unused level
  either, which is a real one-hot trap but a P3 enhancement at most.
- `timedelta64` without gaps: no findings, no crash.

## User-value opportunities

Ranked by impact over effort.

1. **Guard the cleaning path and fix the boolean routing (S).** Helps anyone whose frame
   came from Parquet or `convert_dtypes()`. Changes a `TypeError` traceback into a
   cleaned frame. Two small edits — route by "numeric and not boolean", and wrap each
   applier the way `audit()` wraps each check — plus tests. Highest value today because
   it is the only finding where the library raises in the user's face.
2. **Make `_json_scalar` temporal-aware, both directions (S/M).** Helps anyone with a
   timestamp column, which is most tabular ML data. Protects the reproducibility claim
   that is mlclean's only real differentiator against the nine look-alikes. Slightly
   larger than it looks because `from_json` must restore the type.
3. **Land #32 (S, owner-only).** Unblocks 19 other PRs and turns 14 stale greens into
   real ones. Breaks the tie against anything else of equal size: nothing else in this
   list can reach a user until it happens.
4. **#40, the id-column/duplicate-check hole (S).** A P0 with a one-file reporting half
   that branches off `main` and merges in any order. Still waiting on approval from
   2026-11-12.
5. **Count and print "N of 12 checks could not run" (M).** Closes #23, and today's list
   column is the second independent trigger. Also closes the CI hole where `--fail-on`
   cannot fail a run whose only findings are `check_error`.

## Competitive insights

Nothing moved. **pyjanitor 0.32.79** (2026-11-17) is the only release since yesterday's
delta; it cuts a version per merged PR, so its version alone is no signal. One detail is
worth a line: its bug fix is "grouped `complete` would drop integer group keys or raise
errors when group keys were integers" — the **same class as mlclean PR #19** (non-string
column labels), after pandera shipped three of them on 11-10. Third independent
confirmation that the class is real and that #19 is worth landing. pandera 0.36.0, Great
Expectations 1.25.0, pointblank 1.3.0, ydata-profiling 4.18.4 and cleanlab 2.9.0 are all
unchanged and were counted on 11-11 or 11-14. Next full sweep due **2026-11-18**.

## Recommended work for today

1. **File the two new issues** (nullable-boolean P0, temporal `to_json` P1) and comment
   the list-column evidence onto #23. First step: `gh issue list --state all --search
   "boolean"` and `--search "to_json"` to confirm neither is covered.
2. **Fix the nullable-boolean P0** on a branch off `main` — route the impute split by
   "numeric and not boolean", wrap each applier in `CleaningPipeline.apply` so one bad
   column cannot take down the call, and prove both with tests that fail without the fix.
   First step: ask for approval on the plan below.
3. **Re-state the #32 merge ask** with today's number attached: 6 of 20 PRs red live, 14
   greens stale, 15 days since `main` moved.

## Recommended work for this week

1. **#32.** Unblocks everything else in the queue.
2. **Nullable-boolean P0 + a crash guard on the cleaning path.** Unblocks trust in
   `clean()` on any Parquet-sourced frame.
3. **Temporal `to_json`/`from_json`.** Unblocks the reproducibility claim.
4. **#40's reporting half.** Unblocks the last unaddressed P0 that is not merge-queue.
5. **#23's "N of 12 could not run" line.** Unblocks the CI gate, and retires two separate
   triggers at once.

## Risks

- **The unmerged stack is the dominant risk, and it is a user risk, not housekeeping.**
  Twenty PRs, four of them fixing P0s, none in `main`. Anyone who runs `pip install
  mlclean` today gets `clean()` renumbering their index (#34), `MLCleaner.transform` with
  no column contract (#21), the id-column/duplicate hole (#40) and a CI that cannot pass
  (#31) — all fixed, none shipped.
- **Adoption risk, sharpened.** The 11-11 sweep found nine libraries with mlclean's exact
  pitch, every one stopped at its first or second release. A repo whose `main` has not
  moved in fifteen days with twenty open branches looks like them from the outside. The
  queue is now a positioning problem as well as an engineering one.
- **Technical risk in `cleaning.py` specifically.** Both of today's findings are in that
  file, it has the lowest coverage in the package (82%), and it is the only module whose
  failures reach the user as a traceback instead of a finding. It deserves the next
  hardening pass after the merge queue clears.
- **No security or privacy risk.** 0 dependabot alerts, no network access, no eval, no
  executable content in a serialized pipeline — steps resolve through a fixed applier
  dict, which is the right design and should stay that way.
- **Stale-green risk.** Reading the PR list as "20 ready to merge" is wrong: it is one
  verified-green PR and nineteen unverified ones. Anything merged on the strength of a
  2026-11-03 check run is merged untested.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since the first run |
| Forks | 0 | 0 | |
| Open issues | 21 | 19 | +2 to be filed today |
| Open PRs | 20 | 18 | plus this report |
| Tests | 51 (`main`) | 51 | 0.82s; 54 on PR #45's branch |
| Coverage | 93% | 93% | `cleaning.py` 82% is the floor, and holds both new bugs |
| PyPI version | 0.2.0 | 0.2.0 | `main` at `b48eb32` for 15 days |
| Install from clean venv | yes, 0.2.0, audit runs | not re-tested | 12 checks registered |
| README examples run | yes, all 4 on real Telco | yes, all 4 | all pass on `main` |
| CLI invocations run | yes, both documented forms | yes, both | `--fail-on` exits correctly |
| PRs red against *today's* runners | 6 of 20 | 1 of 18 green | the other 14 greens are stale |
| Findings on demo file with a wrong premise | 2 of 4 | 2 of 4 | unchanged; #11 and #45 unmerged |
| Dtype families probed for crashes | 8 | 0 | 2 new bugs, 4 clean |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | README heading still says v0.1 |
| Dependabot alerts | 0 | 0 | |

## Decision needed from owner

1. **Merge #32 — or grant standing permission to merge green PRs.** Asked 11-10, 11-11,
   11-12, 11-14, 11-16. Today's number: 6 of 20 PRs red live, 14 greens dated 11-03,
   15 days since `main` moved. Options: merge it yourself; or allow `gh pr merge` so the
   daily job can land verified-green PRs. **Recommend merging #32 today**, then letting
   the daily job rebase the rest.
2. **May I fix the nullable-boolean P0?** Plan: branch off `main`; in `cleaning.py` split
   the impute columns by "numeric and not `BooleanDtype`" so a boolean column takes the
   mode branch; wrap each applier call in `CleaningPipeline.apply` so one failing step
   records itself and the rest still run, matching `audit()`'s crash guard; tests for the
   `boolean` column through `clean()` at all three strategies and through
   `MLCleaner.fit_transform`, each proven to fail without the fix; CHANGELOG under
   `## Unreleased`, no version bump. Touches `mlclean/cleaning.py` and
   `tests/test_cleaning.py`, neither of which any open PR moves, so it merges in any
   order. **Recommend yes** — it is the only finding where the library raises at the user.
3. **Scope on the temporal `to_json` fix: serialize as ISO strings, or refuse?** Options:
   (a) write Timestamp/Timedelta/Period as ISO-8601 strings and have `from_json` restore
   them by the step's recorded dtype; (b) keep `to_json` honest and raise a clear
   `TypeError` naming the column, leaving replay unsupported for temporal fills. (a) is
   the real fix and is M-sized; (b) is S and at least stops the confusing pandas error.
   **Recommend (a)**, but it is the second task, not today's.
4. **#40's reporting half — still unanswered from 2026-11-12.** May `check_duplicates`
   see the detected id columns? Branches off `main`, merges in any order.
