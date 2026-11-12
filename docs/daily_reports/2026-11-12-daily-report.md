# mlclean daily report — 2026-11-12

## Executive summary

- New P0, filed as #40: mlclean holds two separate notions of "this column is an
  identifier" and they do not agree. The cleaner unions the detected id with the
  declared one (`cleaning.py:197-198`); the duplicate check reads only the declared one
  (`checks/duplicates.py:34`). So on the documented call, 22 exact duplicate rows in the
  Telco file go unreported, and then `clean()` drops `customerID` and hands those 22
  duplicates back as the training set.
- The two findings are mutually exclusive, which is what makes it a trap rather than a
  gap. Without `id_columns=`, you get `id_column` and no duplicate finding. With it, you
  get `duplicate_rows_ignoring_ids` and the `id_column` finding disappears
  (`checks/types.py:69-70` skips declared columns). There is no call that reports both.
- The harm lands in the exact failure mlclean advertises catching. The duplicate check's
  own recommendation reads "deduplicate before splitting — duplicates shared across
  train and test inflate every metric", and the README says to deduplicate with
  `audit(df).clean()`. That instruction does not do it on any dataset with an id column.
- `clean()` is not idempotent on `balanced` or `aggressive`: its output fails its own
  audit, and a second `clean()` silently drops 22 more rows. Measured on Telco.
- No fix on any branch. `ctx.id_columns` is the only id source in `duplicates.py` at the
  tip of all seven open code branches, so none of the refactors in flight touches it.
- Competitive: pointblank shipped **1.3.0 today** and moved straight into mlclean's
  niche — `pb.Ablation`, `check_splits()`, `check_synthetic()`, near-duplicate and
  benchmark-contamination checks, `to_data_card()`. Yesterday's full sweep saw 1.2.0 and
  concluded nothing threatened mlclean's positioning. One day later that is no longer
  true of the phrase "ML-aware pre-model data quality".
- What still distinguishes mlclean is narrower than it was: pointblank is
  validation-first (you write the steps; `Ablation` scores *your* steps), mlclean is
  detection-first (it tells you what is wrong without you writing rules). That holds,
  but it is now the whole differentiation rather than one of several.
- `main` has not moved in ten days, still `b48eb32`. #32 is still open with
  `mergedAt: null` — the third consecutive day this has been the top item.
- Health otherwise unchanged: 51 tests green in 0.89s, ruff clean, 93% coverage,
  0 dependabot alerts, both README examples run end to end against Telco.

## Repository health

- **Tests:** 51 passed in 0.89s on `main`. No TODO/FIXME/HACK/XXX in `mlclean` or
  `tests`.
- **Lint:** `ruff check .` — all checks passed.
- **Coverage:** 93% (698 statements, 49 missed), unchanged. Lowest: `report.py` 98%,
  `transformer.py` 98% by line but the gaps are in the branches this report cares about.
- **CI:** #32 and #37 are fully green, 14/14, including `test (ubuntu-24.04, 3.9)`.
  #38 and #30 fail exactly one job each, `test (ubuntu-latest, 3.9)`, which is #31 —
  they branch from parents that do not carry the workflow fix, so the failure is
  inherited, not theirs. Everything else in the stack has never run the fixed workflow.
- **Open PRs:** 16. Merge order is unchanged from yesterday and still starts in one
  place:
  1. **#32** (`ci/python39-runner-pin` → `main`) — the only PR `CLEAN` against `main`.
  2. **#33** and **#37** (both → `ci/python39-runner-pin`) — GitHub retargets them to
     `main` when #32 lands.
  3. Then every remaining PR needs `main` merged in to pick up the fixed workflow.
  4. Then the original order: #9 → #10; #6 → #12 → #38; #7 → #11 and #7 → #19; #8 last.
  5. Report PRs #13, #20, #26, #30 and this one are independent of the code stack.
- **Open issues:** 18, including #40 filed today. None stale, none missing a reproduction.
  #31 closes when #32 merges.
- **Dependencies:** 0 dependabot alerts, no open bump PRs, still pandas and numpy only.
- **Published version vs main:** both 0.2.0 at `b48eb32`. Re-confirmed on `main` today
  by running the README examples against Telco: the audit still prints "100% of values
  parse as numbers" for a 99.84% parse rate and "Missing cells: 0 (0.00%)" for a file
  with 11 blank `TotalCharges`. Both are fixed only on #11.

## New issues found

**Bugs**

- **#40 (P0) — the detected id column and the id-aware duplicate check do not talk to
  each other.** `check_duplicates` builds `id_like` from `ctx.id_columns` alone
  (`checks/duplicates.py:34`), which holds only what the caller passed. The `id_column`
  check's own detection is never fed back, although `cleaning.py:197-198` unions both
  sources for the drop step — so the cleaner already does the right thing and the
  reporter does not. Measured on Telco (7,043 × 21), renamed `Churn` → `churn`:
  `audit(df, target="churn")` reports `id_column` on `customerID` and no duplicate
  finding; the same call with `id_columns=["customerID"]` reports
  `duplicate_rows_ignoring_ids` with 22 rows and drops the `id_column` finding.
  Ground truth: 0 exact duplicates with `customerID`, 22 without it. Then
  `clean(strategy="balanced")` drops `customerID` and returns a frame whose own audit
  flags `duplicate_rows`, and a second `clean()` removes 22 rows. Not fixed on any
  branch.
- **(folded into #40) `clean()` is not idempotent above `safe`.** `balanced` and
  `aggressive` both return output that fails `audit()`, because the drop-identifier step
  creates duplicates that no earlier step could have seen. Filed as part of #40 rather
  than separately: same root cause, and splitting it would invite fixing the symptom.

**Documentation**

- README's check table is headed "Checks (v0.1)" while the package is 0.2.0 and the
  table lists the 12 current checks including the two added in 0.2.0. Cosmetic, P3, not
  filed — it belongs in whichever PR next touches the README.

**Enhancements, security, performance**

- Nothing new. 0 dependabot alerts. No performance work today; Telco audit timing
  unchanged at 0.26s and not re-measured at scale.

**Checked and clean** — recorded so it is not re-tested: both README python examples run
end to end on Telco (`audit` → `show` → `to_markdown` → `to_json` → `clean` →
`pipeline.to_json`, then `CleaningPipeline.from_json` → `apply`). `MLCleaner` exposes
`get_params` and `set_params`, so sklearn `clone` works; it has no `__sklearn_tags__`,
which matters only for sklearn's own estimator-check suite and not for the documented
`fit_transform`/`transform` use. `safe` is idempotent.

## User-value opportunities

Ranked by what a user feels, divided by effort.

1. **Land #32, then #33 and #37 (S, owner action).** Still the highest value per minute
   in the repo and still not done. Two merges turn fifteen branch-only fixes into
   shipped ones.
2. **#40, the id/duplicate disconnect (S-M).** Helps every user whose data has an id
   column, which is most tabular data. Two parts: make the duplicate check see the
   detected id, and stop `clean()` returning a frame that fails its own audit. The first
   is the reporting bug, the second is the data bug; both are small, and the pattern to
   copy already exists in `cleaning.py`.
3. **A `check_split(train, test)` function (M).** This is the pointblank
   `check_splits()` idea, and it is the right one to take: it needs no model, so it stays
   inside pandas and numpy, and it answers the question #40 exposes — did duplicates or
   drift leak across the split I just made. Nothing else in the comparable set offers
   this without a validation DSL.
4. **#23, `check_error` severity (M).** Unchanged from yesterday. Helps teams using the
   CLI as a CI gate, where today a run with eight of twelve checks crashed exits 0 at
   every `--fail-on` setting. Must land before `report.fail_if`.
5. **#16, selector vocabulary (S).** Helps anyone who reads a finding name and tries to
   skip it. Also unblocks #29.

#40 over #23 is the tie-break worth stating: both are silent wrong answers, but #40
corrupts the training set the user walks away with, while #23 lets a bad run pass a gate
the user can still inspect.

## Competitive insights

Daily delta, not a sweep — the full sweep was 2026-11-11. One thing moved and it matters.

- **pointblank 1.3.0, released today.** Yesterday's sweep recorded 1.2.0 (11-06) as
  "already counted, unchanged". 1.3.0 is explicitly "about the quality of the data used
  to train and evaluate models" and ships: `pb.Ablation`, which retrains the model with
  each validation step's failing rows removed and compares it against dropping the same
  number of random rows, reporting paired intervals with Holm-adjusted helps/hurts/
  inconclusive verdicts; `col_vals_scored()` for validating rows by model scores;
  text checks for low-quality text, near-duplicates, benchmark contamination and PII;
  `check_splits()` and `check_synthetic()`; and `to_data_card()`.
  - **What they do better:** `Ablation` answers a question mlclean cannot currently
    answer at all — is this finding worth acting on. mlclean's severities are
    threshold heuristics (`ASSOCIATION_FLAG = 0.95` and friends); pointblank measures
    the effect against a random-rows control.
  - **What mlclean can still differentiate on:** pointblank is validation-first. You
    write the steps, and `Ablation` scores the steps you wrote. mlclean is
    detection-first: it finds the problems without being told what to look for. That is
    the whole of the differentiation now, where a week ago "ML-aware" was also part of
    it.
  - **Scope fit:** `Ablation` itself does **not** fit, and the reason is worth recording
    so it is not revisited: it needs a model to retrain, which means scikit-learn, which
    costs the pandas-plus-numpy-only property that every competitor's issue tracker says
    is the thing users actually complain about losing. Note the idea, do not adopt the
    dependency. Effort L and declined.
  - **`check_splits()` does fit** and needs no model. Effort M. Ranked 3rd above.
- **Nothing else moved.** pandera 0.36.0 (11-10) and pyjanitor 0.32.77 (11-11) are both
  as recorded yesterday. ydata-profiling 4.18.4, cleanlab 2.9.0, deepchecks 0.19.1,
  Great Expectations 1.24.1 and soda-core 4.30.0 unchanged.

## Recommended work for today

1. **Merge #32, then #33 and #37.** Owner action; `gh pr merge` is blocked here. First
   step: `gh pr merge 32`, then confirm `git rev-parse origin/main` has moved off
   `b48eb32` before merging the other two. This has been the top item for three days and
   was twice reported done when it had not been.
2. **Fix the reporting half of #40.** First step: branch off `origin/main` — nothing
   open touches `checks/duplicates.py` — and make `check_duplicates` take the detected
   id columns as well as the declared ones, with a test that the documented
   `audit(df, target=...)` call reports 22 duplicates on a Telco-shaped frame. Needs
   approval before any code.
3. **Nothing else.** The data half of #40 (`clean()` idempotence) is a separate decision
   about whether the drop-identifier step should force a re-dedup, and it should not be
   bundled into the same change.

## Recommended work for this week

1. **#32 → #33/#37 → rebase the rest onto the new `main` → land the stack in order.**
   Unblocks everything below it.
2. **#40** (id/duplicate disconnect, S-M). Reporting half first, then the `clean()`
   idempotence decision.
3. **#23** (`check_error` severity, M). Unblocks `report.fail_if` and closes the CI gate
   hole.
4. **`check_split(train, test)`** (M). The one idea worth taking from pointblank 1.3.0,
   and the natural follow-on from #40.
5. **#16** (selector vocabulary, S). Unblocks #29.

## Risks

- **Inaction, and it is now compounding visibly.** Fifteen branches hold fixes for bugs
  that are live on PyPI, re-confirmed on `main` today by running the README's own
  examples: a parse rate printed as 100% when it is 99.84%, and a missing-cell count of
  0 for a file with 11 blanks. Three downloads yesterday, 16 in the last week.
- **#40 is the first finding that makes the tool actively misleading rather than
  incomplete.** A user who follows the README gets a training set with duplicates in it
  and an audit that said the data was fine. That is worse for trust than any missing
  check, and it is the kind of thing a first careful reader finds.
- **Competitive risk changed shape today.** pointblank 1.3.0 is a well-funded project
  (Posit) shipping into mlclean's exact space on a weekly cadence, while `main` has not
  moved in ten days. The gap is not features, it is tempo, and the merge queue is the
  reason.
- **Reporting risk.** Status older than today in any of these files should be re-read
  rather than trusted: the #32 merge has now been reported done twice without having
  happened, and yesterday's "nothing threatens positioning" was correct when written and
  wrong a day later.
- **Security/privacy:** no change. 0 dependabot alerts, no new dependency proposed —
  and one explicitly declined above — no data committed to the repo.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since first run |
| Forks | 0 | 0 | |
| Open issues | 18 | 17 | #40 filed today |
| Open PRs | 17 | 15 | #38 and this report (#39) |
| Tests | 51 (`main`) | 51 | |
| Coverage | 93% | 93% | |
| PyPI version | 0.2.0 | 0.2.0 | `main` unchanged at `b48eb32` for 10 days |
| README examples run | yes | yes | both, end to end on Telco |
| `clean()` idempotent | **no** (balanced, aggressive) | not measured | new measurement |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | README heading still says v0.1 |
| PyPI downloads (day / week) | 3 / 16 | 4 / 16 | |
| Dependabot alerts | 0 | 0 | |

## Decision needed from owner

1. **Will you merge #32 now?** Third day running as the top item. It is the only PR
   `CLEAN` against `main` and is 14/14 green. Options: (a) merge it yourself;
   (b) grant permission to run `gh pr merge` so the daily job can land green PRs.
   Recommend (a) today and (b) standing. Confirm with `git rev-parse origin/main`, not
   from memory.
2. **May I implement the reporting half of #40 today?** Make `check_duplicates` see the
   detected id columns, plus a regression test on a Telco-shaped frame. Branches off
   `origin/main` because nothing open touches `checks/duplicates.py`, so it merges in any
   order against the stack. Options: (a) yes; (b) no, land the stack first.
   Recommend (a).
3. **Should `clean()` guarantee its own output passes `audit()`?** This is the data half
   of #40 and it is a design decision, not a bug fix. Options: (a) when the
   drop-identifier step runs, re-check duplicates afterwards and append a
   `remove_duplicates` step — makes `clean()` idempotent, and changes row counts for
   anyone relying on today's behaviour; (b) leave the rows alone and have `clean()` warn
   that its output still has findings; (c) document that `clean()` is a single pass and
   leave it. Recommend (a), because silently returning duplicates is the harm, and the
   step ordering is already the cleaner's job. No code until you pick.
4. **Confirm `pb.Ablation` stays declined.** It is the strongest idea in the comparable
   set and it costs the pandas-plus-numpy-only property. Recommend declining and
   recording it, which is what this report does. Say if you want it reconsidered.
