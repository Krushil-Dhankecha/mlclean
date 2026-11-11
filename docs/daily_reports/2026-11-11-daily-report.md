# mlclean daily report — 2026-11-11

## Executive summary

- `main` has not moved in nine days. It is still `b48eb32` (0.2.0, 2026-11-02), and the
  one PR that can merge — #32, the CI runner pin — is still open with `mergedAt: null`.
  Yesterday's report recorded it as merged on Krushil's word; it was not, and `origin/main`
  confirms that again today. Everything else in the repo waits behind it.
- New P0, filed as #34: `clean()` throws away the index whenever it drops a row, so
  cleaned rows cannot be matched back to anything held outside the frame. On the real
  Telco file with 300 scattered unlabeled rows, the natural remap mis-mapped 6,718 of
  6,743 ids and 2,765 labels, and raised nothing.
- #34 is the same failure class as #27, reached more easily. #27 needs a reordered `y`;
  #34 needs only a dropped row, which is what every strategy above `audit_only` does.
- New P1, filed as #36: `MLCleaner` passes a serving-time null straight through if that
  column was complete at fit time. Verified on PR #33's branch, so the new column
  contract does not cover it — a frame can satisfy the contract and still carry a NaN.
  Third run in a row this has been recorded; filed rather than carried again.
- New P2, filed as #35: every pipeline serialized by 0.2.0 claims `"version": "0.1.0"`.
  The field is load-bearing — `_apply_impute`'s pre-0.2 fallback is the behaviour it is
  meant to select — so the next schema change has no safe path while it lies.
- Both #34 and #35 survive unchanged to the tip of the stack, so the refactors in flight
  do not quietly fix them.
- #11, #12 and #19 report `CLEAN` but are not mergeable into `main`. They target parent
  branches, where protection does not apply. Only #32 is `CLEAN` against `main`.
- Full competitor sweep (due today) found a quiet week: pyjanitor 0.32.76/0.32.77 and
  soda-core 4.30.0 shipped nothing that touches mlclean's positioning. The real finding
  is elsewhere — nine small libraries now occupy mlclean's exact niche, and all nine are
  one-release projects with single-digit weekly downloads.
- Health is otherwise fine: 51 tests green on `main` in 0.53s, ruff clean, 93% coverage,
  0 dependabot alerts, clean-venv install of 0.2.0 works on pandas 3.1.1, and the suite
  raises no `FutureWarning` or `DeprecationWarning` under pandas 3.1.

## Repository health

- **Tests:** 51 passed in 0.53s on `main`. 66 passed on `fix/transformer-contracts` (#33).
  Run with `-W error::FutureWarning -W error::DeprecationWarning` against pandas 3.1.0:
  still 51 passed, so mlclean is clean against the pandas 3.1 deprecation round.
- **Lint:** `ruff check .` — all checks passed, on `main` and on #33.
- **Coverage:** 93% on `main` (698 statements, 49 missed). 94% on #33. Lowest modules:
  `cleaning.py` 82%, `checks/leakage.py` 88%, `checks/outliers.py` 89%.
- **CI:** #32 and #33 are 14/14 green with `test (ubuntu-24.04, 3.9)` passing, both run
  2026-11-10. Every other PR's green is stale: #6–#10 from 11-03, #11/#12/#19 from 11-04,
  #20 from 11-05, #26 from 11-06. None of them has ever run the fixed workflow, so none
  reports the required `test (ubuntu-24.04, 3.9)` context. #30 is 12/14 — its two failures
  are `test (ubuntu-latest, 3.9)`, the blocker from #31.
- **Open PRs:** 15 including this report. The order has not changed since yesterday and
  still starts in one place:

  1. **#32** (`ci/python39-runner-pin` → `main`) — the only PR that is `CLEAN` against
     `main`. Nothing else can go green until it lands.
  2. **#33** (`fix/transformer-contracts` → `ci/python39-runner-pin`) — #21 + #27.
     GitHub retargets it to `main` when #32 merges.
  3. Then every remaining PR needs `main` merged in (or a rebase) to pick up the fixed
     workflow, because the missing status context comes from each branch's own `ci.yml`.
     `strict: false` does not help: the problem is the workflow file, not staleness.
  4. Only then the original order applies: #9 → #10; #6 → #12; #7 → #11 and #7 → #19
     (siblings, second one needs a rebase); #8 last, since it also touches
     `checks/__init__.py`.
  5. Report PRs #13, #20, #26, #30 and this one are independent of the code stack.

  Worth flagging because it reads backwards: #11, #12 and #19 show `mergeStateStatus:
  CLEAN` while #6, #7, #8, #9, #10 show `BLOCKED`. The three "clean" ones target parent
  branches, which carry no protection rules. They are not closer to landing.
- **Open issues:** 17. Pre-existing: #14–#18, #21–#25, #27–#29, #31. Filed today: #34
  (P0), #35 (P2), #36 (P1). #31 closes when #32 merges. None is stale or missing a
  reproduction. #29 remains blocked behind #16 by design, not by file contention.
- **Dependencies:** 0 dependabot alerts, no open bump PRs. Runtime requirements are still
  pandas and numpy only — a clean-venv install of 0.2.0 pulls 8 packages total.
- **Published version vs main:** both 0.2.0 at `b48eb32`. The gap that matters is not
  version to `main` but `main` to the open branches: every bug in #14–#36 that has a fix
  is fixed only on an unmerged branch, so all of it is live for anyone installing today.
  Re-confirmed on `main` this run: the CLI on Telco still prints "100% of values parse as
  numbers" for a 99.84% parse rate (#3 in the bug log, fixed in #11) and still reports
  "Missing cells: 0 (0.00%)" for a file with 11 blank `TotalCharges` (fixed in #11), and
  `CleaningPipeline.from_json` still raises `OSError: File name too long` on the string
  its own `to_json` returns (fixed in #12).

## New issues found

**Bugs**

- **#34 (P0) — `clean()` renumbers the index, so cleaned rows cannot be matched back to
  anything.** `cleaning.py:92` is `drop_duplicates(ignore_index=True)` and
  `cleaning.py:134` is `dropna(subset=[target]).reset_index(drop=True)`. Both discard the
  surviving row labels, which is the only link from a cleaned frame to data held beside it
  — a separate `y`, `sample_weight`, `groups`, or the id column mlclean's own `id_column`
  finding tells the user to exclude. Measured on Telco (7,043 × 21) with the label missing
  for 300 randomly scattered customers: `ids.loc[clean.index]` returned the wrong id for
  6,718 of 6,743 rows and the wrong label for 2,765, with no exception. The tail case
  hides it — 200 duplicate rows appended to the end gave 0 mis-mapped, because the fresh
  `RangeIndex` coincides with the survivors — so this is invisible to a test that appends
  rather than interleaves. No fix on any branch; both lines are unchanged at the tip of
  `fix/clean-converts-numeric-text`, so it lands on #12.
- **#36 (P1) — `MLCleaner` passes a serving-time null through if the column was complete
  at fit time.** Impute steps are built only from the training audit's `missing_values`
  findings (`cleaning.py:210-236`), so a column with no training gaps gets no learned fill
  and no step. Verified on #33's branch: `age` (gaps in training) is imputed, `income`
  (complete in training) keeps its serving NaN, no warning. sklearn estimators raise on
  it; XGBoost and LightGBM take it as a missing branch and score quietly. This is #21's
  fourth failure, which #21 left as a separate decision; recorded on 11-05, 11-10 and
  again today, so it is now filed. Not fixed by #33, by design.
- **#35 (P2) — every serialized pipeline claims version 0.1.0.** `cleaning.py:44` hardcodes
  `version: str = "0.1.0"` and nothing ever assigns it, while the package is 0.2.0. Not
  cosmetic: `_apply_impute`'s fallback for pipelines "serialized before 0.2" is exactly the
  behaviour the field is supposed to select, so no future release can branch on it safely.
  `from_json` also accepts a future version and fails with a bare `KeyError` from the
  applier lookup. Unchanged at `cleaning/pipeline.py:38` on #12's branch.

**Enhancements, documentation, security, performance**

- Nothing new. 0 dependabot alerts; no new performance regression (Telco audit 0.26s
  unchanged, 1M × 5 at 3.74s from 11-10 not re-measured today).

**Checked and clean** — worth recording so it is not re-tested: `audit()` handles an empty
frame, an empty frame with columns, a single row, an all-null column, naive and tz-aware
datetimes, nullable `Int64`, `Categorical`, `MultiIndex` columns and a non-unique index
without raising. `report.to_json()` round-trips. No `FutureWarning` or `DeprecationWarning`
under pandas 3.1.

## User-value opportunities

Ranked by what a user feels, divided by effort.

1. **Land #32, then #33 (S, owner action).** Two merges turn fourteen branch-only fixes
   into shipped ones, including the #21 column contract and the #27 row contract. Nothing
   else on this list is worth as much per minute spent, and every other item gets cheaper
   once the stack is moving.
2. **#34, the index fix (S).** Helps anyone who holds row-aligned data outside the audited
   frame, which includes everyone following mlclean's own advice to exclude an id column.
   Two lines plus three tests, and it makes `clean()`'s output honest about which rows
   survived.
3. **#36, serving-time nulls (M).** Helps anyone running `MLCleaner` in a prediction
   service — the use case the transformer was built for. Larger than #34 because it needs
   the indicator-schema decision settled, which is why it ranks below it despite being
   the more severe-sounding of the two.
4. **#23, `check_error` severity (M).** Helps teams using the CLI as a CI gate, where
   today a run with eight of twelve checks crashed exits 0 at every `--fail-on` setting.
   Must land before `report.fail_if` or that ships with the same hole.
5. **#16, selector vocabulary (S).** Helps every user who reads a finding name and tries
   to skip it. Also unblocks #29.

#34 over #36 is the tie-break worth stating: both are silent wrong answers, but #34 is two
lines and no open design question, and it damages the training set rather than one request.

## Competitive insights

Full sweep, the first since 2026-11-04. Nothing in the tracked list changes mlclean's
positioning.

- **Moved, immaterial.** pyjanitor 0.32.76 (11-10, contribution-guideline and CI changes
  only) and 0.32.77 (11-11, better handling of the deprecated `by` argument in `expand`
  and `complete`). soda-core 4.30.0 (11-05) — SQL dialect rendering, redaction, workload
  identity federation, and a fix so `count invalid_values` matches when the list contains
  null; no new check types, so nothing to borrow for the default check set.
- **Already counted on 11-10, unchanged.** pandera 0.36.0 and pointblank 1.2.0.
- **Did not move.** pandas 3.1.1 (11-04, a `read_csv`/`to_csv` path-object regression fix),
  Great Expectations 1.24.1, scikit-learn 1.9.1, ydata-profiling 4.18.4, cleanlab 2.9.0,
  deepchecks 0.19.1, Polars 2.1.0, DuckDB 2.0.0. openclean-core is still 0.4.1 from 2021
  and DataKleaner 0.1.1 from 2025-03; cleanTS is no longer resolvable on PyPI. The
  single-purpose-cleaner end of the list is effectively dead, which is evidence about the
  niche rather than about any one tool.
- **The actual finding: mlclean's niche is now crowded with abandoned attempts.** Searching
  for what mlclean does — pre-model, target-aware, pandas, leakage and quality — turns up
  nine libraries that did not exist in the tracked list: `leakage-buster`, `datasentry`,
  `mlradar`, `dfaudit`, `featureleakagelens`, `tput`, `sanipy`, `mlleak`, `peek`. Their
  summaries describe mlclean's pitch almost word for word ("Audit your pandas DataFrame
  before you trust it", "readiness scoring, leakage detection, drift"). Measured traction:

  | package | first release | latest release | downloads/week |
  |---|---|---|---|
  | leakage-buster | 2025-09-13 | 2025-09-13 | 14 |
  | mlleak | 2025-12-24 | 2025-12-24 | 13 |
  | featureleakagelens | 2026-05-05 | 2026-05-05 | 11 |
  | datasentry | 2026-02-12 | 2026-02-22 | 7 |
  | dfaudit | 2026-05-08 | 2026-05-08 | 6 |
  | tput | 2026-04-13 | 2026-04-13 | 4 |
  | sanipy | 2026-06-26 | 2026-06-26 | 4 |
  | mlradar | 2026-05-28 | 2026-05-30 | 3 |
  | **mlclean** | **2026-11-02** | **2026-11-02** | **16** |

  Every one of them stopped at its first or second release, and not one has reached double
  digits in weekly downloads except the two oldest. Two readings, both worth holding:
  the idea is validated — people keep independently building this — and the idea is not
  the moat. What none of them has is a reproducible serializable pipeline, a fit/transform
  transformer with a column contract, or a second month of maintenance. That is the
  differentiation to lead with, and it is also the argument for landing the stack: a repo
  whose newest commit is nine days old and whose fixes sit in fourteen open branches looks
  like the nine, not unlike them.
- **Fits/doesn't fit:** nothing in this sweep suggests a scope change. soda-core's check
  vocabulary stays warehouse-shaped, pandera's `pandera.decisions` work narrows
  validate-versus-fix from the declarative end but still requires users to write rules,
  and the nine new entrants are narrower than mlclean rather than broader. No new
  dependency implied by any of it.

## Recommended work for today

1. **Merge #32, then #33.** Owner action; Claude cannot (`gh pr merge` is blocked by the
   auto-mode classifier). First step: `gh pr merge 32`, then confirm `git fetch && git
   rev-parse origin/main` has actually moved off `b48eb32` before merging #33 — yesterday
   this step was reported done and had not happened.
2. **Fix #34 on #12's branch.** First step: `git checkout -b fix/clean-preserves-index
   origin/fix/clean-converts-numeric-text`, drop `ignore_index=True` at
   `cleaning/steps.py:18` and `.reset_index(drop=True)` at `cleaning/steps.py:71`, and
   write `test_clean_preserves_surviving_index_when_rows_dropped` first so it is seen to
   fail. Needs approval before any code is written.
3. **Nothing else.** Two merges and one two-line fix is the honest capacity of a day whose
   first item is blocked on someone else.

## Recommended work for this week

1. **#32 → #33 → rebase every remaining PR onto the new `main` → land the eight-PR stack
   in order.** Unblocks all of it; nothing below this is worth starting first.
2. **#34** (index preservation, S). Unblocks honest row tracking through `clean()`.
3. **#23** (`check_error` severity, M). Unblocks `report.fail_if` (P2 roadmap) and closes
   the CI gate hole.
4. **#36** (serving-time nulls, M). Needs the indicator-schema decision in its "Proposed
   solution" settled first.
5. **#16** (selector vocabulary, S). Unblocks #29.

## Risks

- **Inaction is the dominant risk, and it compounds.** Fourteen branches hold fixes for
  bugs that are live on PyPI right now, re-confirmed on `main` this run: a parse rate
  printed as 100% when it is 99.84%, a missing-cell count of 0 for a file with 11 blanks,
  and a `from_json` that cannot read its own `to_json` output. PyPI shows 4 downloads
  yesterday and 16 in the last week, so these are being installed while unfixed.
- **The merge order is now the bottleneck, not the work.** Every day the stack sits,
  another fix has to be stacked on a parent instead of branched off `main`. #34 and #35
  both land on #12 for exactly this reason; neither could go on `main` today. The number
  of free branch-off points is down to `transformer.py`, `ci.yml` and `checks/outliers.py`.
- **Reporting risk, demonstrated twice.** A merge was recorded as done on 11-10 and had
  not happened, and the stack's "14/14 green" badges are runs from 11-03 to 11-06 against
  a workflow that no longer passes. Both were caught only by re-reading the source of
  truth. Any status in this file older than today should be re-read, not trusted.
- **Adoption risk, sharpened by the sweep.** Nine abandoned libraries in the same niche
  means a prospective user's prior is that a tool like this is a weekend project. A repo
  with 0 stars, 15 open PRs and no commit in nine days confirms that prior at a glance.
  The visibility wave is still on hold — #21 and #27 are fixed in #33 and #23 is not
  started — and #34 now joins the hold list, since a first careful reader running
  `clean()` on labelled-in-part data would hit it.
- **Security/privacy:** no change. 0 dependabot alerts, no new dependency proposed, no
  data committed to the repo.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since first run |
| Forks | 0 | 0 | |
| Open issues | 17 | 14 | #34, #35, #36 filed today |
| Open PRs | 15 | 14 | this report; nothing merged |
| Tests | 51 (`main`), 66 (#33) | 51 / 66 | |
| Coverage | 93% (`main`), 94% (#33) | 93% / 94% | |
| PyPI version | 0.2.0 | 0.2.0 | `main` unchanged at `b48eb32` for 9 days |
| Install from clean venv | works | works | 0.2.0, pandas 3.1.1, numpy 2.5.4, 8 packages |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | |
| PyPI downloads (day / week) | 4 / 16 | 4 / 27 | week down; day holding at 4 |
| Dependabot alerts | 0 | 0 | |

## Decision needed from owner

1. **Will you merge #32 now?** It is the only PR that is `CLEAN` against `main`, and
   nothing in the repo can go green until it lands. Options: (a) merge it yourself; (b)
   grant Claude permission to run `gh pr merge` so the daily job can land green PRs
   without waiting a day each time. Recommend (a) today and (b) as a standing change,
   because the pattern of the last nine days is that the merge step is where work stops.
   Please confirm by checking `git rev-parse origin/main` has moved, not by recollection.
2. **After #32, merge #33?** It fixes #21 (P0) and #27 (P1) and is 14/14 green including
   the previously failing 3.9 job. One open question inside it is still yours: #21 asked
   for the fitted *output* columns to be exposed as `feature_names_in_`/`n_features_in_`,
   and #33 instead uses `feature_names_in_` for fit's *input* (sklearn's meaning) and
   `feature_names_out_`/`get_feature_names_out()` for the output. Options: (a) keep #33's
   naming; (b) switch to #21's literal naming. Recommend (a) — the class claims sklearn
   compatibility by convention, so matching sklearn's meaning matters more than matching
   the issue text — but both lists exist either way, so nothing is lost by (b).
3. **May Claude implement #34 today?** Two lines in `cleaning/steps.py` plus three tests,
   branched off `fix/clean-converts-numeric-text` and targeting #12. Options: (a) yes;
   (b) no, land the stack first and fix it on `main` afterwards. Recommend (a) — it is a
   silent wrong answer in the main documented entry point, and waiting for the stack is
   what put it on #12's branch instead of `main` in the first place.
4. **#36's indicator-schema question, which blocks its fix.** Learning a fill value for
   every column means deciding whether every column also gets a `_missing` indicator.
   Options: (a) learn fills for all columns, emit indicators only for columns the audit
   flagged, so the fitted schema is unchanged; (b) emit indicators for all of them, which
   is more informative and changes the output width for clean data. Recommend (a). No
   code until you pick.
