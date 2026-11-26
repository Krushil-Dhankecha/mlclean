# mlclean daily report — 2026-11-26

## Executive summary

- **New bug, and it sits on the default setting: `MLCleaner()` hands back a frame with
  nulls still in it.** A column above `missing_threshold` is skipped by the `balanced`
  imputer at `cleaning.py:214-215` with the comment "left for aggressive", and `balanced`
  returns at `cleaning.py:250` before the aggressive dropper ever runs. So nothing touches
  it. `Pipeline([("clean", MLCleaner()), ("clf", LogisticRegression())]).fit(df, y)` raises
  `ValueError: Input X contains NaN`. Filed as **#62, P1**.
- That bug lands on the two paths most users take: `balanced` is `MLCleaner`'s default, and
  the README's third example is the sklearn one. The class docstring claims the transformer
  is "safe inside sklearn pipelines and cross-validation", which is the claim this breaks.
- The audit raises a **HIGH** finding on that column and recommends three fixes — "Drop the
  column, impute, or add a missing indicator" — and the cleaner then does none of the three.
  The library disagreeing with its own advice is worse than either half alone.
- **`main` has not moved in 24 days.** Still `b48eb32` from 2026-11-02. 26 open PRs, 30 open
  issues, and every one of those issues is live for anyone who `pip install`s today.
- **The project's only outside contributor has waited 9 days.** #49 (`Theankitmishra`,
  opened 11-17) still reports **zero checks** because a first-time-contributor workflow run
  needs an approval only Krushil can give. This is the adoption risk on the list that gets
  worse by itself.
- Re-measured on the published 0.2.0 today and still wrong: #11 (parse rate rounded to
  "100%" directly above "inspect the handful of non-numeric values"), #44 (a money column
  called a 6,531-category categorical) and #12 (`clean()` leaves the numeric text as text).
  Three of the four findings on the library's own demo dataset.
- #25 confirmed live too, from the serialized pipeline rather than by reading: under
  `aggressive` the steps are `impute(mostly_missing, median=0.0645)` followed by
  `drop_columns(mostly_missing)` — a fill value computed, serialized, and thrown away.
- Health is otherwise clean: 51 tests pass in 0.78s, `ruff` clean, 93% coverage, no
  dependabot alerts, no TODO/FIXME markers in `mlclean/` or `tests/`, all four README blocks
  and both CLI forms run against the real Telco file.
- Weekly competitor sweep done (was 8 days overdue). **Nothing moved into mlclean's space.**
  Four tools released; the only one worth a sentence is Polars, and it argues *for* mlclean.
- PyPI is slightly up: 129 downloads/month and 7/week against 123 and 2 on 11-23.

## Repository health

- **Tests:** 51 passed in 0.78s on `main` (`.venv/bin/python -m pytest -q`).
- **Lint:** `ruff check .` — all checks passed. No `ruff format --check` run; the repo is
  deliberately not format-clean.
- **Coverage:** 93% (698 statements, 49 missed). `cleaning.py` remains the floor.
- **CI:** 6 of 7 matrix jobs green. `test (ubuntu-latest, 3.9)` still fails because
  `ubuntu-latest` rolled to 26.04, which ships no Python 3.9 (issue #31). The fix is
  **PR #32**, unmerged, and it is the parent of #33 and #37.
- **Open PRs: 26** before this report, 27 with it. Four independent stacks, and the bases
  matter because a parent merging without its children rebased breaks them:
  - `main` ← **#6** ← **#12** ← **#38**
  - `main` ← **#7** ← **#11**, **#19** (two children on one parent)
  - `main` ← **#32** ← **#33**, **#37**
  - directly on `main`: #8, #9, #10, #13, #20, #26, #30, #39, #41, #43, #45, #46, #49, #52,
    #56, #57, #61
  Merge order that works: **#32 first** (it makes CI pass, which unblocks judging everything
  else), then #6 → #12 → #38, then #7 → #11 → #19, then the flat ones in any order.
- **Open issues: 30.** No duplicates found; every one has a reproduction. Five are P0 — #21
  (fix in #33), #31 (#32), #34 (#38), #47 (#49) and **#40, which has no fix on any branch**.
- **Dependencies:** `dependabot/alerts` returns `[]`. No open bump PRs. Core is still
  pandas + numpy only, which is the claim worth protecting.
- **Published version vs main:** PyPI has **0.2.0** (2026-11-02); `main` is the same commit.
  So the published version and `main` agree, and both are 24 days behind the work.

## New issues found

**Bug — P1 — filed as #62, no fix on any branch.**
`balanced` leaves a column above `missing_threshold` neither imputed nor dropped, so
`MLCleaner()` emits nulls. Evidence, on published 0.2.0 with sklearn 1.9.1 and pandas 3.1.1:

```
audit: [high] 'last_login_days' is missing in 80 rows (80.0%).
       -> Drop the column, impute, or add a missing indicator — ...

MLCleaner() (default strategy='balanced') -> (100, 2) ['age', 'last_login_days']
  NaN remaining: {'last_login_days': 80}

Pipeline([('clean', MLCleaner()), ('clf', LogisticRegression())]).fit(df, y):
  ValueError: Input X contains NaN.
```

The same frame under the other two tiers: `safe` leaves it as well (correct — `safe` is
lossless by design and imputes nothing anywhere), `aggressive` handles it properly
(`['age', 'last_login_days_missing']`, no nulls). So `balanced` is the only tier that both
promises to impute gaps and silently skips this one. Cause is two lines working against
each other: `cleaning.py:214-215` skips the column "left for aggressive", and
`cleaning.py:250` returns before the aggressive tier exists. Distinct from #25 (the
*aggressive* side of the same guard: impute-then-drop) and from #36 (columns *complete* at
fit time getting no fill value). Effort **S**.

One honest caveat recorded on the issue: **the repro is synthetic.** None of the eight real
local datasets has a column above 50% missing — the only one with any nulls at all is the
Kaggle churn file at 0.00% (one empty trailing row in 440,833). That absence is probably
why six weeks of dogfooding on Telco and Criteo never hit this, and it is also why the
default `missing_threshold=0.5` makes the bug rarer than it looks. It is not exotic, though:
an optional field that most records leave empty is ordinary, and any user who lowers
`missing_threshold` to something like 0.1 widens the trap considerably.

**Nothing else new.** No new documentation, security or performance findings. Scale, crash
resistance, the README blocks and the `--fail-on` ordering were all audited clean on 11-20
and 11-23 and were not re-chased.

## User-value opportunities

Ranked by what it changes for a user, divided by effort.

1. **Merge the stack.** Effort **M** (review time, not code). Helps every user: it is the
   only action that converts ~20 written-and-tested fixes into something a `pip install`
   delivers. Nothing else on this list competes, because every other item is already done
   and just undelivered.
2. **Approve #49's workflow run.** Effort **S** — one click. Helps the one outside
   contributor the project has. Nine days of silence on a first PR is how a project teaches
   people not to send a second one.
3. **Fix #62.** Effort **S**. Helps anyone using `MLCleaner` in sklearn, which is the
   README's own integration story.
4. **Fix #11 and #44 together.** Effort **S** each, already written as #11 and #45. Helps
   every new user, because those two findings are 50% of what the demo dataset prints.
5. **#60's concentration check.** Effort **M**, and blocked on a naming decision while #16
   is open. Highest ceiling of the unwritten work — nobody in the tracked field reports
   column concentration as a finding of its own.

Tie-break between 3 and 4: #11/#44 are already written and only need merging, so they cost
less than #62, which still needs code. #62 ranks above them only if the stack stays unmerged.

## Competitive insights

Full weekly sweep run (last was 2026-11-18, so this was 8 days overdue). Versions read from
the PyPI JSON API rather than release-note pages, which lag it. **Nothing moved into
mlclean's space.**

Four of the sixteen tracked packages released since 11-18:

- **soda-core 4.32.0** (11-25). The docs site still documents only 4.31.0, whose single core
  change made `CheckSelector` importable from `soda_core.contracts`. Still a YAML/contract
  rule language, still warehouse-first. No overlap with a zero-config pandas audit.
- **Polars 2.2.0** (11-24), on top of 2.0 in October. **This one argues for mlclean rather
  than against it:** 2.0 made the streaming engine the default, and streaming does not
  guarantee row order unless the user passes `maintain_order=True`. mlclean's open work on
  keeping the index intact (#34, #38) is the same property, and pandas gives it for free.
  Worth remembering the next time a Polars backend is proposed — it would import that
  problem.
- **duckdb 2.0.1** (11-20). An engine, not an auditor. Unchanged relevance.
- **pyjanitor 0.32.81** (11-22). The patch cadence already on record as no signal.

Unchanged and not worth re-checking before the next sweep: pandera 0.36.0, Great
Expectations 1.25.0, pointblank 1.3.0, ydata-profiling 4.18.4, cleanlab 2.9.0, deepchecks
0.19.1, openclean 0.2.1, DataKleaner 0.1.1, scikit-learn 1.9.1, pandas 3.1.1. `cleanTS` now
404s on PyPI — worth dropping from the tracked list rather than re-querying it weekly.

One thing the sweep surfaced that is not competitive at all: **pandas is at 3.1.1 and
mlclean's own venv already runs it with all 51 tests green.** `checks/types.py:15` handles
the new string dtype through `is_string_dtype`, and `_infer_task` survives it by falling
through to its final `return "classification"` rather than by intent (`audit.py:37` tests
`series.dtype == object`, which is now False for a text target). It works, but it works by
accident, and the declared floor of `pandas>=1.5` is still untested either way (#17).

## Recommended work for today

1. **Approve the workflow run on #49.** One click, nine days overdue, and it is the only
   item here with another person waiting at the other end.
2. **Merge PR #32.** It makes CI green across the matrix, which is the precondition for
   trusting any other PR's status. Then the stack can be judged on its contents instead of
   on a red check every PR shares. First step: `gh pr view 32` and merge it.
3. **Approve the fix for #62** (plan in "Decision needed", option A). Small, and it closes
   the gap between what the audit recommends and what the cleaner does.

## Recommended work for this week

1. **#32, then the two code stacks in base order** (#6 → #12 → #38, then #7 → #11 → #19).
   Unblocks: everything, and turns 24 days of unshipped fixes into a release.
2. **Release 0.3.0 once the stack is in.** Unblocks: users actually receiving the fixes;
   also clears #35 (every serialized pipeline claiming 0.1.0), which only a release fixes.
3. **#62 plus #25 in one PR.** Unblocks: nothing, but they are the two halves of one broken
   guard and splitting them means touching `cleaning.py:214` twice.
4. **Decide #60's shape** (new check name versus capping the existing finding). Unblocks:
   the concentration work, which is the strongest differentiator left unwritten.
5. **Put a type checker in CI.** Unblocks: nothing immediately — the package ships
   `py.typed` and nothing verifies it, so this is the gap that silently widens. Noted once
   before; still true.

## Risks

- **Inaction is the main risk, and it is compounding.** 24 days, 26 open PRs, 30 open
  issues, four of them P0 with fixes already written. Every day this holds, the published
  library is wrong in ways the repository already knows how to fix. The demo dataset is the
  sharpest version: three of the four findings a new user sees on Telco are affected by
  unmerged work.
- **Adoption:** #49 is nine days unapproved. One fork, one outside contributor, zero stars.
  The cost of ignoring a first contribution is not the PR, it is the next one.
- **Product:** #62 and #54 are both cases of the cleaner acting against the audit's own
  advice — one by doing nothing, one by over-dropping. A user who stops trusting `clean()`
  has no reason to keep the library, because the audit alone is the easy half to replace.
- **Technical:** the stacked PRs rot. Four stacks, three with children; any parent merged
  without rebasing its children breaks them. This risk is purely a function of elapsed time.
- **Security/privacy:** nothing. No alerts, no data committed, core stays pandas + numpy.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since the first run |
| Forks | 1 | 1 | the fork that sent #49 |
| Outside contributors | 1 | 1 | `Theankitmishra`, #49, CI unapproved — **9 days** |
| Open issues | 31 | 30 | #62 filed today |
| Open PRs | 27 | 25 | this report; 26 before it |
| Tests | 51 (`main`) | 51 | 0.78s |
| Coverage | 93% | 93% | `cleaning.py` still the floor |
| CI jobs green | 6 of 7 | 6 of 7 | only `ubuntu-latest, 3.9` fails (#31, fix in #32) |
| PyPI version | 0.2.0 | 0.2.0 | `main` at `b48eb32` for **24 days** |
| PyPI downloads | 7 week / 129 month | 2 week / 123 month | up |
| Install from clean venv | yes | yes | throwaway venv, 0.2.0 + sklearn 1.9.1 + pandas 3.1.1 |
| README examples run | yes, all 4 blocks | yes, all 4 | on real Telco |
| CLI invocations run | yes | yes | exit 0 on Telco with no `--fail-on` |
| Datasets dogfooded | 2 (Telco; 8 scanned for nulls) | 2 (Telco, Criteo 2M) | no real file has a >50%-missing column |
| Largest frame audited | 2,000,000 × 16 (11-23) | 2,000,000 × 16 | not re-run |
| Competitor sweep | full, 4 of 16 moved | delta, none moved | next due 2026-12-03 |
| Documented vs implemented checks | 12 rows / 18 names documented, 12 implemented | same | `checks=` takes neither (#16) |

## Decision needed from owner

1. **Merge PR #32?** It fixes CI for the whole repo (#31). Recommendation: **yes, first,
   before anything else** — every other PR carries the same red check, so nothing else can
   be judged on its own merits until this lands. It has no children that a merge would
   break if #33 and #37 are rebased after.
2. **Merge the two code stacks, in base order?** #6 → #12 → #38, then #7 → #11 → #19.
   Recommendation: **yes**, in that order, rebasing each child after its parent. This is the
   decision the report has repeated for three weeks; the alternative is to close some of
   them, which at least makes the backlog honest.
3. **Approve the workflow run on #49?** Recommendation: **yes, today.** It is one click, the
   contributor has waited nine days, and the fix addresses a P0 (#47).
4. **Fix #62, and how?** Options:
   - **A (recommended):** under `balanced`, impute the above-threshold column like any other
     and add its indicator — the audit's own third recommendation, and the tier already does
     exactly this for every column below the threshold. One guard clause, one test.
   - **B:** drop it under `balanced` too, which makes `balanced` and `aggressive` agree on
     these columns and leaves them differing only on quasi-constants.
   - **C:** leave the behavior and document it, i.e. `balanced` deliberately defers
     above-threshold columns to the user.
   A is recommended because C contradicts the HIGH finding the audit prints, and B deletes a
   column the user may want — dropping on the user's behalf is what #54 is already a
   complaint about. Fix #25 in the same PR; it is the other side of the same guard.
5. **Drop `cleanTS` from the tracked competitor list?** It 404s on PyPI and time series is
   already out of scope by an earlier decision. Recommendation: **yes** — it costs a query a
   week and has never produced a finding.
