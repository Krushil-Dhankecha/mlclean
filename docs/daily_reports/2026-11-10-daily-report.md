# mlclean daily report — 2026-11-10

## Executive summary

- Nothing has merged since 0.2.0 on 2026-11-02. Eight code PRs, all 14/14 green, now
  eight days old. `main` is still `b48eb32`.
- New bug, found by dogfooding `MLCleaner.fit`: it pairs `y` to `X` **by position** and
  throws away `y`'s index. With a `y` holding the same labels on the same index in a
  different order, 218 of 600 rows were mispaired, the leakage check stopped firing, and
  the fitted pipeline no longer dropped the leaky column. No exception, no warning.
  Filed as #27 (P1).
- `disguised_missing` and `outliers` give opposite advice about the same cells. 165
  `-999` values in one column produce a MEDIUM "these encode missing, not real
  measurements" and a LOW "cap/winsorize only if they are errors, not real extremes".
  Filed as #28 (P2).
- The CLI reaches 3 of `audit()`'s 7 parameters. `checks`, `skip`, `ignore_columns` and
  `missing_threshold` have no flag, which matters because the CLI is the CI surface.
  Filed as #29 (P2).
- Two of the known bugs are still visible in the CLI's own output on the real Telco file:
  it prints "100% of values parse as numbers" directly above "inspect the handful of
  non-numeric values", and "Missing cells: 0 (0.00%)" for a frame with 11 blank strings.
  Both are fixed in PR #11, which has been green and unmerged for a week.
- The stack is getting more expensive to work around, not less. #24 must target #6, #25
  must target #12, and `transformer.py` is now the only interesting file still free of
  the stack — which is where #21 and #27 both live.
- All five README examples still run clean on the real Telco file. 51 tests in 0.81s,
  ruff clean, coverage 93%, 0 dependabot alerts.
- Competitive delta: pointblank 1.2.0 (2026-11-06) added a minimum-dependency-version CI
  job, which is exactly issue #17. pandera 0.36.0 shipped today with a derived-column
  "Decisions" API, narrowing the validate-versus-fix gap from the declarative side, and
  fixed three column-label shape bugs of the same class as PR #19.
- PyPI shows 4 installs in the last day, the first non-zero daily number. Still 0 stars,
  0 forks, 0 watchers.
- Audit is deterministic across repeated runs on the same frame — checked, no sampling
  surprises. Nullable `Int64`/`Float64`/`boolean` targets carrying `pd.NA` survive
  `MLCleaner.fit` with task inference and `missing_target` intact. Neither needs
  re-testing.

## Repository health

- Tests: 51 pass in 0.81s on `main` (py3.13, pandas 3.1.0, numpy 2.5.4). 60 on the #19
  branch.
- Lint: `ruff check .` — all checks passed.
- Coverage: 93%. `cleaning.py` at 82% is still the weakest module; `transformer.py` reads
  98% and the two contract bugs in it are both uncovered behaviour, not uncovered lines.
- CI: all ten open PRs are 14/14 green (py3.9–3.13 Linux, plus macOS and Windows on 3.13).
- Open PRs: 10. Merge order unchanged:
  - `#9` (product audit + roadmap) → `#10` (leakage by mutual information)
  - `#6` (split report/ and cleaning/ into packages) → `#12` (`clean()` converts
    numeric-stored-as-text, `from_json` fix)
  - `#7` (split checks/types.py) → `#11` (floored parse rate, blank sentinels) and
    `#7` → `#19` (column-label shapes); #11 and #19 are siblings, so whichever lands
    second needs a rebase
  - `#8` (memory footprint check) last, since it also touches `checks/__init__.py`
  - `#13`, `#20`, `#26` are the 11-04, 11-05 and 11-06 daily reports, all off `main` and
    independent of the code stack
- Open issues: 13 after today's filings — #14–#18, #21–#25, #27–#29. #14 and #15 are
  closed by #19 and could be closed the moment it merges. Nothing is stale or missing a
  reproduction.
- Dependencies: 0 dependabot alerts, no open bump PRs. Still pandas + numpy only.
- Published version vs main: both 0.2.0 at `b48eb32`. What is on PyPI is exactly what is
  in `main`, which is the problem — all fifteen known bugs ride with it.

## New issues found

**Bug — `MLCleaner.fit(X, y)` pairs `y` positionally and discards its index** (#27, P1,
no fix on any branch). `transformer.py:71` is `frame[name] = np.asarray(y)`. Measured on a
600-row frame with a post-outcome column `exit_survey_sent`: with `y` in order the audit
flags `target_leakage` on it and the balanced pipeline drops it; with the same `y` on the
same index in a different order, 218 of 600 rows are mispaired, the finding disappears,
and the pipeline keeps the leaky column. Plain `frame[name] = y` would have aligned
correctly. Same family as #21 — a silent wrong answer out of the transformer — but the
other end of it: #21 is column order at transform time, #27 is row pairing at fit time.
Both live in `transformer.py`, which no open PR touches.

**Bug — `disguised_missing` and `outliers` contradict each other on the same values**
(#28, P2, no fix on any branch). 5,000 rows, 165 of them `-999` in an `age` column:
`disguised_missing` says MEDIUM, "these usually encode 'missing', not real measurements";
`outliers` says LOW, "cap/winsorize or log-transform only if they are errors, not real
extremes", over the identical 165 cells. Following the second ruins the column. The fix
belongs in `checks/outliers.py` — exclude values the sentinel check already claimed —
not in the renderer.

**Enhancement — the CLI exposes 3 of `audit()`'s 7 parameters** (#29, P2). Reachable:
`--target`, `--task`, `--id-columns`. Not reachable: `checks`, `skip`, `ignore_columns`,
`missing_threshold`. The CLI is the CI surface, so a pipeline that wants to gate on a
subset of checks has no way to say so. Blocked behind #16: the selector vocabulary is
wrong today, and shipping a `--skip` flag before #16 lands would ship the wrong names
into people's CI configs.

**Performance — `summary()` is recomputed on every render** (not filed, P3).
`report.py:33-49` runs `df.duplicated()` and `df.isna().sum().sum()` on each call, and
`to_text`, `to_markdown` and `to_json` each call it. Measured on 1M × 5: the CLI's three
renders cost 0.52s against a 3.74s audit, of which `duplicated()` is 0.14s a time, for
numbers that cannot have changed. Cache the dict on first call.

**Documentation — README check table still headed "Checks (v0.1)"** (not filed, P3).
Unchanged from the 11-04 report. It is one line, but `README.md` is contended by four
open PRs, so it is better bundled into whichever of them lands last.

## User-value opportunities

Ranked by impact over effort.

1. **Land the stack.** Effort S for Krushil, zero for Claude. Helps every current
   installer: fourteen of fifteen known bugs are fixed and sitting in branches. Nothing
   else on this list changes as much per minute spent.
2. **#21 + #27 in one PR off `main`.** Effort M. Helps anyone putting `MLCleaner` in a
   real serving path — the two bugs are the same promise broken at both ends, the file is
   free of the stack, and fixing one without the other leaves the transformer still
   untrustworthy.
3. **#23, the skipped-check count.** Effort S–M. Helps every CI user, and `report.fail_if`
   (P2 on the roadmap) cannot ship before it without inheriting the same hole.
4. **#17's floor CI job.** Effort S. pointblank just shipped the same job, so the bar is
   now visible in a comparable. Also the cheapest way to stop claiming a dependency range
   that cannot resolve.
5. **#28.** Effort S. Small, but it is the product telling a user to do the wrong thing
   with their data, which is the one thing this library cannot afford.

Tie-break between 2 and 3: #21 has a P0 label and a measured silent misprediction, so it
wins on severity. #23 wins on breadth. The decision below recommends 2, because the
visibility wave is already being held on it.

## Competitive insights

A four-day delta rather than a one-day one, since the last run was 2026-11-06. Full sweep
still due 2026-11-11.

- **pointblank 1.2.0 (2026-11-06)** removed its `pandas<3` pin and "a new CI job tests
  minimum dependency versions". That is issue #17, shipped by a comparable, four days
  before this report. It also treats NaN as missing on Polars, PyArrow and DuckDB "as it
  already was on pandas", and extended `get_step_report()` to table-level steps including
  `col_pct_null()` — still the bar for the P4 HTML report.
- **pandera 0.36.0 (2026-11-10, today)** added a `ParsedColumns`/`ParsedField` and
  `pandera.decisions` API: columns derived from other columns through parsers. This is
  pandera stepping toward transformation, which narrows the "validation that also fixes"
  gap — but from the declarative end, where the user still writes the derivation. mlclean's
  claim is the opposite order: it decides what is wrong and proposes the fix. Worth
  watching, not worth repositioning over. Two other things from the same release: it
  carried a security fix for RCE in `tensordict` load (GHSA-vpwq-239f-3cf7), which is a
  concrete argument for the zero-extra-dependency stance, and it fixed three
  column-label shape bugs — non-string labels in unique checks, nested tuple labels, and
  single-level MultiIndex schemas. That is the same class PR #19 fixes, which is
  independent confirmation the class is real and worth landing.
- **soda-core 4.30.0 (2026-11-05)** and **pandas 3.1.1 (2026-11-04)** both moved; neither
  changes anything for mlclean. Local env is pandas 3.1.0 and the suite is green on it.
- **pyjanitor has not moved since 0.32.75 on 2026-11-04**, cleanlab, ydata-profiling,
  deepchecks and Great Expectations all unchanged. Don't re-check before the 11-11 sweep.

## Recommended work for today

1. **Fix #21 and #27 together in one PR off `main`.** First step: add
   `feature_names_in_`/`n_features_in_` and an output-column list recorded at fit, then
   index-align `y` in `fit` before the audit. `transformer.py` and
   `tests/test_transformer.py` are touched by no open PR, so this merges in any order.
   Needs approval before any code is written.
2. **File nothing further; merge something.** The three issues from today are filed. The
   highest-value action left today is Krushil merging #9 → #10 and #6 → #12, which clears
   four of the eight and frees `CHANGELOG.md` and `cleaning/strategies.py`.
3. **Add the pinned floor CI job from #17** if there is time after 1. First step:
   `pip install "pandas==1.5.3" "numpy==1.26.4"` as its own matrix entry in `ci.yml`,
   which no open PR touches. Settled on 2026-11-04 that the suite passes at that floor, so
   this is a job definition, not an investigation.

## Recommended work for this week

1. **Merge the stack in the order above.** Unblocks everything else; every day it waits,
   new fixes get harder to branch.
2. **#21 + #27.** Unblocks the visibility wave, which is being held on exactly this.
3. **#23's skipped-check count.** Unblocks `report.fail_if` (roadmap P2).
4. **#17's floor job plus one README line** saying pandas 1.5–1.x needs `numpy<2`.
   Unblocks an honest dependency claim; do the README half with whichever stacked PR
   lands last.
5. **#28 and #22.** Both small, both in the "the tool told me the wrong thing" class.
   #22 needs to land on #12's chain, #28 is free.

## Risks

- **Inaction is the main risk and it is compounding.** Eight days unmerged. Fourteen of
  fifteen known bugs are fixed in branches and live on PyPI, and the CLI demo on the real
  Telco file still prints two of them. 4 installs yesterday means the first real reader
  may already have arrived.
- **Branch-off points are running out.** `CHANGELOG.md` is contended by seven PRs,
  `README.md` by four, `checks/__init__.py` by three, `report.py` by #6, `cleaning.py` by
  #6 then #12. Only `transformer.py` and `.github/workflows/ci.yml` are free. Today's
  recommended work fits in that gap on purpose; next week's might not.
- **Product: the transformer is the riskiest surface in the library.** #21 and #27 are two
  silent wrong answers in the one component meant for production serving. Of the two,
  #27 is the quieter — sklearn's feature-name check at least raises on #21's reordered
  frame, whereas nothing anywhere notices a mispaired `y`.
- **Adoption: no inbound channel.** Discussions are off, 0 stars, 0 watchers. Every
  finding in this repo's history came from dogfooding, which does not scale and does not
  tell us what anyone else needs.
- **Security: none open.** 0 dependabot alerts, SHA-pinned actions, trusted publisher
  active. pandera's RCE fix this week is a reminder of what the optional-heavy-deps route
  costs; mlclean is not exposed to it.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | Discussions still off, no inbound channel |
| Forks | 0 | 0 | |
| Watchers | 0 | 0 | |
| Open issues | 13 | 10 | #14–#18, #21–#25, #27–#29; three filed today |
| Open PRs | 10 | 10 | all 14/14 green, nothing merged since 2026-11-02 |
| Tests | 51 pass, 0.81s | 51 pass, 0.87s | 60 on the #19 branch |
| Coverage | 93% | 93% | `cleaning.py` 82% still the weakest module |
| Dependabot alerts | 0 | 0 | |
| PyPI version | 0.2.0 | 0.2.0 | `main` identical to it |
| PyPI installs (7d) | 27 | 102 | `last_day` is 4, first non-zero daily figure |
| Install from clean venv | works | works | verified 2026-11-02 |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | README table still headed "v0.1" |
| Telco audit time | 0.26s | 0.26s | 7,043 × 21, 4 findings |
| README examples passing | 5 / 5 | 5 / 5 | re-run today on the real Telco file |
| Audit of 1M × 5 | 3.74s | not measured | plus 0.52s for the CLI's three renders |

## Decision needed from owner

1. **Merge the stack?** Ten PRs, all green, nothing merged in eight days. Claude cannot
   merge — the auto-mode classifier blocks `gh pr merge` as "Merge Without Review".
   Options: merge in the order above yourself; grant the permission; or say what the stack
   is waiting on, so the next run stops leading with it. **Recommend merging #9 → #10 and
   #6 → #12 today.** That clears four of the eight and frees `CHANGELOG.md` and
   `cleaning/strategies.py`, which two filed issues are currently blocked behind.
2. **Which task should Claude implement today?** One task, with approval.
   **Recommend #21 + #27 in a single PR off `main`** — same file, same broken promise at
   both ends, no stack contention, and the visibility wave is already being held on #21.
   The alternative is #23, which is broader but less severe.
3. **#27: should a mispaired `y` raise, or realign?** Options: (a) if `y` is a Series or
   DataFrame, align on the index and raise `ValueError` when the index sets differ, falling
   back to positional only for arrays and lists; (b) warn and keep positional; (c) document
   positional as the contract and change nothing. **Recommend (a)** — it matches what
   pandas would have done with a plain assignment, and (c) leaves a silent wrong answer in
   the one component meant for production.
4. **Hold the visibility wave?** Unchanged recommendation: **hold until #21, #27 and #23
   land.** The reason is now stronger, not weaker — #27 is a second silent wrong answer in
   the same component, and yesterday's 4 installs suggest the window for fixing it quietly
   is closing.
