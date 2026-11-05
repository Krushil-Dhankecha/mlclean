# mlclean daily report — 2026-11-05

## Executive summary

- `MLCleaner.transform` makes no promise about columns. The output keeps the serving
  frame's column order, drops any column that is absent without a word, and passes
  through any column that was not in the training frame. On the real Telco file, a
  one-row payload built from a dict — the ordinary way a prediction request arrives —
  came back with all 19 columns in a different order than `fit_transform` produced.
  Pushed through an array-consuming model, the same four rows scored 0.53, 0.71, 0.41,
  0.37 in the right order and 0.10, 0.31, 0.17, 0.09 scrambled. Nothing raised. This is
  the day's P0: the library exists to stop train/serve skew and currently adds a new
  kind of it.
- The imputation indicator overwrites an existing column of the same name. Fit on a
  frame that already has `age_missing` holding real values and `transform` replaces it
  with 1/0 flags, no finding, no warning. One line in `_apply_impute`.
- A column with no gaps in training that arrives with nulls at serving time passes
  through unimputed. No step was learned for it, so `transform` has nothing to apply and
  says nothing; the NaN reaches the model. Defensible behaviour, undocumented either way.
- `check_error` is emitted at `INFO` (`audit.py:115`). That settles the design question
  raised on 2026-11-04: a frame where seven of twelve checks crashed reads as a clean
  dataset, because the only evidence is seven INFO lines under a HIGH/MEDIUM-free
  summary. Severity should reflect that the audit is incomplete.
- Good news on the robustness sweep: nullable `Int64`/`boolean`/`string`, `category`,
  datetime, tz-aware datetime, timedelta, `NaT`, all-NaN columns, a 0-row frame, a frame
  with no columns, a single row and a non-unique index all audit without raising.
  Complex dtype and list-valued cells degrade to `check_error`, which is the crash guard
  working as designed.
- PR #19 fixes MultiIndex columns too, which nobody claimed. A 3-column MultiIndex frame
  produces one `check_error` on `ids` on main and zero on that branch. Worth adding to
  the PR body, since it widens what landing it buys.
- Nothing moved in the repo since yesterday's two runs. Main is still `b48eb32`, the same
  nine PRs are open, all nine 14/14 green, 51 tests pass in 0.8s, `ruff` clean, 0
  dependabot alerts. Third day in a row that every fix is one merge away from users and
  still not with them.
- Correction to yesterday's competitive read: **pyjanitor is not dormant.** It has 68
  releases in 2026 and eight in the last four days (0.32.68 → 0.32.75, latest
  2026-11-04), with a release per merged PR. The March 2024 date in my notes was its
  changelog, not its releases, and "the niche doesn't sustain attention" was the wrong
  conclusion to draw from it.
- One useful consequence of that: pyjanitor 0.32.73 aligned its metadata to Python
  3.11–3.13. mlclean supports 3.9–3.13 and tests it, so there is a real install-footprint
  argument on older stacks that did not exist a week ago.

## Repository health

- Tests: 51 passed in 0.82s on `main`. Branches add their own (60 on `fix/awkward-column-labels`).
- Lint: `ruff check .` clean. Formatting is deliberately not `ruff format` clean; CI does
  not check it.
- Coverage: 93%. Thinnest files unchanged — `cleaning.py` 82%, `checks/leakage.py` 88%,
  `checks/outliers.py` 89%. `transformer.py` is 98% by line and 0% by contract: every
  behaviour in the P0 above is covered by a passing test suite that never asserts on the
  output columns.
- CI: green on all nine open PRs, 14/14 checks each (py3.9–3.13 Linux, plus macOS and
  Windows on 3.13).
- Open PRs: 9, unchanged. Merge order:
  - `#9` (docs: product audit + roadmap) → `#10` (leakage by mutual information)
  - `#6` (split `report`/`cleaning` into packages) → `#12` (base `refactor/package-layout`)
  - `#7` (split `checks/types.py`) → `#11` and `#19`, two siblings on the same base;
    whichever merges second needs a rebase
  - `#8` (memory footprint) last, since it also touches `checks/__init__.py`
  - `#13` (2026-11-04 report) is independent of all of it
- Open issues: 5 (#14–#18). None stale, all have reproductions. #14 and #15 are closed
  by #19; #17 has the pandas-floor question settled in a comment and needs only the CI
  job plus a README line.
- Dependencies: 0 dependabot alerts, no open bump PRs. Runtime deps still `pandas>=1.5`
  and `numpy>=1.23`.
- Published version vs main: PyPI has 0.2.0 and `main` is identical to it. Everything
  found since 2026-11-02 is on a branch.
- TODO/FIXME/HACK/XXX in `mlclean/` and `tests/`: none.

## New issues found

**Bug — `transform` has no column contract (P0, no fix on any branch).**
`transformer.py:84` returns `self.pipeline_.apply(X, include_row_steps=False)` and the
appliers only ever add or drop named columns, so the output column list is whatever the
caller passed, in the caller's order. Three separate failures from one cause: column
order follows the input (Telco, 19 columns, single-row dict payload, first mismatches
`gender`/`TotalCharges`, `SeniorCitizen`/`MultipleLines`, `Partner`/`PhoneService`); a
column absent at serving time is dropped silently along with its `_missing` indicator;
a column the training frame never had is kept. The docstring promises "same drops,
train's fill values" and the README promises row alignment, so a reader has every reason
to assume column alignment too. sklearn's own feature-name check would catch the
DataFrame path with a `ValueError`; anything array-shaped — `.to_numpy()`, an XGBoost
`DMatrix`, a torch tensor, a saved ONNX graph — mispredicts in silence.

**Bug — the imputation indicator overwrites a real column (P1, no fix on any branch).**
`cleaning.py:_apply_impute` does `out[f"{column}_missing"] = ...` unconditionally. A
frame carrying both `age` and `age_missing` loses the contents of the second one. Needs a
name collision, so it is narrower than the P0, but the loss is total and silent, and
`<col>_missing` is a common hand-rolled convention in exactly the kind of
already-half-cleaned frame mlclean gets pointed at.

**Bug — nulls arriving in a column that was complete at fit time are left alone (P1).**
Imputation steps are built only from `missing_values` findings on the training frame. Set
one `income` value to NaN in a serving frame whose training column had none and the NaN
survives `transform` untouched and unmentioned. Either learn fill values for every
eligible column or say plainly that `transform` only repairs what training taught it to.

**Bug — `check_error` at INFO hides a broken audit (P1).**
`audit.py:115` fixes the severity at `INFO`. Combined with issue #15, a duplicate-column
frame yields seven crashed checks and a report whose highest severity is INFO. The
decision I would take: `check_error` raises the report's overall severity to at least
MEDIUM and the text summary names how many checks could not run, so "nothing found" and
"nothing ran" stop looking alike.

**Resolved, verified — MultiIndex columns (no action beyond landing #19).**
A frame with `MultiIndex.from_tuples` columns produces one `check_error` on `ids` on main
(tuples have no `.lower()`) and zero on `fix/awkward-column-labels`. The positional
`(label, series)` rework in #19 covers it.

## User-value opportunities

Ranked by impact over effort.

1. **A fitted schema on `MLCleaner`** — S, highest value. Record the output columns at
   fit, reindex to them at transform, raise on a missing column, drop or raise on an
   extra one. Helps anyone who puts mlclean behind an inference endpoint, which is the
   audience the transformer was built for. Also buys `feature_names_in_` and
   `n_features_in_`, which is what sklearn's own `check_is_fitted` conventions expect, so
   the "sklearn-compatible without importing sklearn" claim gets more true.
2. **Land the stack** — S per PR, and it is the only thing that moves any of the six
   known bugs off PyPI. Third day of saying this.
3. **`check_error` raises report severity** — S. Makes every other robustness fix
   visible instead of silent, and it is the cheapest of the four new bugs.
4. **Collision-safe indicator names** — S. `age_missing`, then `age_missing_1`, or an
   explicit `indicator_suffix`. Small, but it is data loss.
5. **`report.fail_if(severity)`** — M, unstarted P2 on the roadmap. The CI-gate story is
   what gets a library into someone's pipeline rather than their notebook, and it pairs
   with 3: a gate that ignores crashed checks is a gate with a hole in it.

Tie-break between 1 and 2: 2 helps people who already installed, 1 helps people who are
about to put it in production. 1 wins on being a defect with no fix anywhere, where 2 is
a fix with no merge.

## Competitive insights

- **pyjanitor is actively released, not dormant** — 142 releases total, 68 in 2026, eight
  between 2026-11-01 and 2026-11-04, cutting a version per merged PR. 1.5k stars, 63 open
  issues. This corrects the note I carried from the 2026-11-04 sweep, which read its
  changelog's last entry (v0.27.0, March 2024) as its last activity. The positioning is
  unaffected — pyjanitor is a method-chaining verb library where the user says what to
  fix, and mlclean decides what is wrong — but "the niche is thin" is not a line to repeat.
- Their 2026-11-03 bugfix, "leave already-numeric columns unchanged in
  `currency_column_to_numeric`", is the same hazard PR #12 handles on the audit side.
  Worth reading their test for cases ours misses; no code or docs copied.
- **pyjanitor 0.32.73 declares Python 3.11–3.13.** mlclean declares and tests 3.9–3.13.
  On a pinned-3.9 enterprise stack mlclean installs and pyjanitor's current release does
  not — a concrete argument for the floor CI job in issue #17, which turns a declared
  range into a tested one.
- No other movement: pandera 0.35.0 (2026-10-25), great-expectations 1.24.1 (2026-10-22),
  soda-core 4.29.0 (2026-10-27), pointblank 1.1.1 (2026-10-15), cleanlab 2.9.0
  (2026-01-13), ydata-profiling 4.18.4 (2026-04-22), deepchecks still 0.19.1 from
  2024-12-15. Nothing released since the last sweep.

## Recommended work for today

1. **Give `MLCleaner` a fitted output schema.** First step: record the transformed column
   list in `fit`, then reindex in `transform` and decide the two error cases (missing
   column, extra column). `transformer.py` and `tests/test_transformer.py` are touched by
   no open PR, so this branches off `main` and merges in any order.
2. **Make `check_error` raise the report's overall severity** and print the count of
   checks that could not run. First step: find where the summary picks its headline
   severity in `report.py:38` and decide whether INFO stays the issue's own severity with
   a separate "incomplete" flag, or the issue itself moves to MEDIUM.
3. **Fix the indicator collision** in `_apply_impute`. First step: write the failing test
   that fits on a frame holding `age` and `age_missing` and asserts the original values
   survive.

## Recommended work for this week

1. Land the stack in order: #9 → #10, #6 → #12, #7 → #11 → rebase #19, then #8. Unblocks
   every one of the six known bugs for PyPI users and clears the file contention that is
   making every new change pick its base carefully.
2. The `MLCleaner` schema fix (today's 1). Unblocks honest documentation of the
   train/serve story, which is the pitch the visibility wave is built on.
3. `check_error` severity plus the indicator collision (today's 2 and 3). Unblocks
   trusting an audit on data nobody has inspected first.
4. Issue #17's floor job: pin `pandas==1.5.3` with `numpy==1.26.4` in a CI job and add
   the one README line about old pandas needing `numpy<2`. `ci.yml` is touched by no open
   PR. Unblocks the 3.9-era install claim the pyjanitor finding just made worth having.
5. `report.fail_if(severity)`. Unblocks the CI-gate use case and starts P2.

## Risks

- **Inaction on the stack, third day.** Six bugs with written, green fixes are live for
  anyone installing 0.2.0. Every day the stack sits, the rebase cost of the two siblings
  on `refactor/split-type-checks` grows and the chance of a conflict in `CHANGELOG.md`
  (six PRs touch it) or `mlclean/checks/__init__.py` (three) goes up.
- **The transformer bug is a credibility risk, not just a defect.** A library whose README
  opens on train/serve leakage, that reorders features between train and serve, is the
  kind of thing a reviewer on Show HN finds in ten minutes. Fix it before the visibility
  wave, not after.
- **Adoption: still 0 stars, 0 forks, 0 watchers, no inbound channel.** Discussions are
  off. Every issue in the tracker is self-filed. There is no signal yet about what real
  users want, so the roadmap is running on dogfooding alone — which is finding real bugs,
  but will not tell us what people would pay attention for.
- **Privacy/security: nothing new.** 0 alerts, no raw data in reports by default, no new
  dependency proposed today. The library still needs only pandas and numpy.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | no inbound channel; Discussions still off |
| Forks | 0 | 0 | |
| Open issues | 5 | 5 | #14–#18; #14/#15 closed by #19 |
| Open PRs | 9 | 9 | all 14/14 green, nothing merged since 2026-11-02 |
| Tests | 51 pass, 0.82s | 51 pass, 1.0s | 60 on the #19 branch |
| Coverage | 93% | 93% | `transformer.py` 98% by line, untested by contract |
| PyPI version | 0.2.0 | 0.2.0 | main identical to it |
| Install from clean venv | works | works | verified 2026-11-02 |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | README table still headed "v0.1" |

## Decision needed from owner

1. **Merge the stack?** Nine PRs, all green, nothing merged in three days. Claude cannot
   do it — `gh pr merge` is blocked as "Merge Without Review". Options: merge in the order
   above yourself; or grant the permission; or tell me to stop reporting it daily and
   treat the branches as a long-lived backlog. Recommend merging in order, starting with
   #9 → #10 since that chain has no siblings to rebase.
2. **Approve the `MLCleaner` schema fix for today?** Scope: record output columns at fit,
   reindex at transform, raise on a missing column. The open question is the extra-column
   case. Raising is too strict for a serving frame that legitimately carries an ID or a
   timestamp alongside the features, and dropping in silence is how this bug happened in
   the first place. Recommend dropping extras and recording which ones on the fitted
   object, so it is visible without being fatal.
3. **Which way on `check_error` severity?** Either the finding itself becomes MEDIUM, or
   it stays INFO and the report carries a separate "N checks could not run" line that
   raises the headline. Recommend the second: it keeps the severity of a finding meaning
   "how bad is this data" rather than "how bad is this run".
