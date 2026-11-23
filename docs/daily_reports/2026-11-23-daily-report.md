# mlclean daily report — 2026-11-23

## Executive summary

- Three known bugs are visible in **six consecutive lines** of the published CLI's output
  on the demo dataset. Running `mlclean audit Telco.csv --target Churn` against 0.2.0
  prints "100% of values parse as numbers" immediately above "inspect the handful of
  non-numeric values", calls a money column 6,531 categories, and illustrates whitespace
  on that same money column with a hardcoded `' yes'`/`'yes'`. Every one has a fix
  written. None is merged.
- **New P1, from dogfooding real data at scale: the outlier check flags a quarter of a
  concentrated column, then goes silent when the column gets worse.** Filed as
  [#60](https://github.com/Krushil-Dhankecha/mlclean/issues/60). On 2M rows of the real
  Criteo file it reports `'f2' has 488,134 values (24.41%) outside [8.183, 8.256]` and
  recommends winsorizing them.
- The `iqr == 0` guard in `checks/outliers.py:30` is a cliff, not a slope. A synthetic
  zero-inflated column flags 9.45% at 70% zeros, 24.99% at 75%, and **nothing at 76%**,
  because the IQR reaches exactly zero and the guard fires. The check is loudest where
  its answer means least.
- PR #32 has been `MERGEABLE`/`CLEAN` with **14 of 14 green for 13 days**. It is the only
  thing standing between this repo and a working merge queue, and only Krushil can merge it.
- Every other PR reads `BLOCKED` for the reason recorded on 2026-11-10 and re-verified
  today: their branches carry the old `ci.yml`, so the required `test (ubuntu-24.04, 3.9)`
  context never reports. #6 and #7 still show 14 green checks **dated 2026-11-03** — stale,
  and they pre-date the ubuntu roll. Do not read them as passing.
- `main` has not moved since **2026-11-02**, 21 days. 25 PRs and 30 issues are open behind it.
- Scale is not a problem and this is the first run to prove it: `audit()` on 2,000,000 × 16
  real rows finished in **4.1s with a 419 MB Python peak**, no crash, no degraded check.
- Tests 51/51 in 0.82s, `ruff check` clean, coverage 93%, zero dependabot alerts, zero
  TODO/FIXME markers. The code is healthy; the *process* is the problem.
- Competitive delta: nothing moved into mlclean's space. Full sweep due 2026-11-25.
- No new work was started on the library today. With 30 issues open and 25 fixes unmerged,
  the marginal value of a 31st finding is far below the value of landing one PR.

## Repository health

- **Tests**: 51 passed, 0 failed, 0.82s on `main` (`b48eb32`).
- **Lint**: `ruff check .` — All checks passed. (`ruff format --check` is deliberately not
  clean here and is not a finding.)
- **Coverage**: 93% overall. Floor is `cleaning.py` at 82% (24 statements missed,
  `255-272` the largest block); `checks/leakage.py` 88% and `checks/outliers.py` 89%.
  Unchanged from 11-20.
- **CI**: 6 of 7 jobs green on every branch. The failure is always
  `test (ubuntu-latest, 3.9)` — Ubuntu 26.04 has no Python 3.9 build. Last failures
  measured today: #57 at 2026-11-20T03:52Z, #45 at 2026-11-16T03:57Z. Issue
  [#31](https://github.com/Krushil-Dhankecha/mlclean/issues/31), fix in PR #32.
- **Open PRs**: 25. Merge order, by `baseRefName`:
  1. **#32** (`ci/python39-runner-pin` → `main`) — **first, alone, and nothing else can
     merge until it does.** 14/14 green, `CLEAN`.
  2. Then every other branch needs `main` merged in (or a rebase) to pick up the new
     workflow, or its gate waits on a job its branch does not define.
  3. Roots: #6 (`refactor/package-layout`), #7 (`refactor/split-type-checks`).
  4. Stacked on #7: #11, #19. Stacked on #6: #12. Stacked on #12: #38.
     Stacked on #32: #33, #37.
  5. Independent of the stack: #8, #9, #10, #45, #49, and the 11 report PRs.
- **Open issues**: 30 (29 at the start of the run, plus #60). Nothing stale without a
  reproduction — every open issue carries measured numbers. #29 is explicitly blocked
  behind #16, and #25 still needs a product decision before it can be fixed.
- **Dependencies**: zero dependabot alerts. Two dependabot runs succeeded on `main` today
  (pip and github_actions), which is the only thing that has touched `main` in 21 days.
- **Published version vs main**: PyPI serves 0.2.0 built from `b48eb32` (2026-11-02).
  `main` is still that commit. So everything in the 25 open PRs — including all four P0s
  — is live for anyone who installs today.

## New issues found

**Bug / P1 — [#60](https://github.com/Krushil-Dhankecha/mlclean/issues/60): the outlier
check flags a quarter of a concentrated column, then goes silent when it gets worse.**
No fix on any branch. `checks/outliers.py:26-32` applies Tukey's 3×IQR rule guarded only
by `if iqr == 0: continue`. On a column whose middle 50% is packed and whose tail is wide,
the IQR collapses and ordinary values fall outside the fences.

Real-world evidence, first 2M rows of `criteo.csv.gz`, `target="conversion"`:

```
[low]  outliers: 'f2' has 488,134 values (24.41%) outside [8.183, 8.256] (3×IQR fences).
[low]  outliers: 'f8' has 228,802 values (11.44%) outside [3.906, 4.021] (3×IQR fences).
[info] outliers: 'f6' has 814 values (0.04%) outside [-22.93, 14.95] (3×IQR fences).
```

`f2` holds 438,723 distinct values across a range of 0.838, but its 1st, 5th and 50th
percentiles are all 8.2144 — over half the column is a single value. `IQR = 0.0105`, so
the fences span **8.8% of the column's range**. `f6` is the control: a well-spread column,
fences wider than its range, 0.04% flagged, correctly INFO.

The cliff, on a synthetic zero-inflated `spend` column (10,000 rows, *k*% exact zeros,
remainder `uniform(1, 100)` — nothing in it is an error):

| share at 0.0 | IQR | reported |
|---|---|---|
| 50% | 50.3 | *nothing* |
| 60% | 37.7 | *nothing* |
| 70% | 17.2 | 945 values (9.45%) |
| 74% | 4.32 | 2,155 values (21.55%) |
| 75% | 0.255 | **2,499 values (24.99%)** |
| 76% | 0 | *nothing* |
| 90% | 0 | *nothing* |

The printed number is arithmetically correct; the conclusion is not. "Outlier" is defined
to be rare — at 24.99% the fences are the artifact, not the data. The recommendation
("cap/winsorize or log-transform") would destroy 488,134 genuine measurements on `f2`.

**Re-confirmed, not new.** Criteo at 2M rows reproduces the leakage gap recorded as bug 1
in the known-bugs memory: `visit` and `exposure` are post-outcome columns and
`target_leakage` fired on neither. Fixed in PR #10, unmerged, so still live on PyPI.

**Not filed, P3, carried.** `whitespace_padding` illustrates every column with a hardcoded
`' yes'`/`'yes'` — on Telco it says that about `TotalCharges`, a money column. Visible in
today's CLI output. It belongs in whichever stacked PR touches that check last.

## User-value opportunities

Ranked by impact over effort. The ranking is lopsided today and that is the finding.

1. **Merge PR #32, then the stack.** Impact: it is the only action that moves any of the
   4 open P0s, 14 P1s and 25 written fixes from "exists" to "shipped". Effort: **S** —
   one click, then rebases. Nothing else on this list is comparable, and nothing else can
   start until it does.
2. **#60's concentration check.** Helps anyone auditing a zero-inflated or capped feature,
   which is most real ML tables. Changes a harmful recommendation into a useful finding,
   and no competitor in the tracked list reports concentration in its own right. Effort:
   **M** — detection and ceiling are small, but a new check name touches the selector
   vocabulary (#16), the README table and `checks/__init__.py`.
3. **#23, the crashed-check count.** Still the cheapest correctness win on the board: it
   makes `--fail-on` work at all, since today no setting of the flag can fail a run whose
   only findings are crashed checks. Effort: **S**.
4. **#16, the selector vocabulary.** Unblocks #29 and stops the CLI shipping the wrong
   names into people's CI configs. Effort: **S**.

Tie-break between 3 and 4: #23 wins because it is a wrong answer and #16 is a confusing
one. A wrong answer in a tool whose whole job is telling the truth about data outranks
a usability snag.

## Competitive insights

Daily delta, not a sweep — the last full sweep was 2026-11-18 and the next is due
2026-11-25. Versions checked against that sweep: pandera 0.36.0, ydata-profiling 4.18.4,
cleanlab 2.9.0, deepchecks 0.19.1, Great Expectations 1.25.0, pointblank 1.3.0 all
unchanged. pyjanitor moved 0.32.78 → 0.32.81 (11-22), which the memory already records as
no signal on its own — it patch-releases every few days on a chainable-verbs API that has
never overlapped the zero-config audit. soda-core reads 4.31.0 (11-17) against the 4.30.0
recorded on 11-20; it is warehouse-first SQL rules either way. **Nothing moved into
mlclean's space.**

One targeted search, run because #60 raised a design question rather than as part of a
sweep: DataRobot's data-quality checks treat excess zeros as a **two-condition** test,
flagging a column only when the frequency of zero is itself unusual, explicitly to cut
false positives. Separately, work on zero-inflated count data argues Tukey's fences stop
being applicable on such columns at all. Both support #60's recommendation to detect the
concentration directly rather than retune `k`, and are recorded on the issue.

## Recommended work for today

1. **Merge #32.** Owner-only. One click, and the rest of this list stops being theoretical.
2. **Rebase one blocked PR onto the new `main` and confirm its gate goes green** — #7 is
   the right probe, since #11 and #19 both stack on it. This proves the 11-10 merge-order
   theory on a real branch before eight more are rebased on the strength of it.
3. **Nothing else.** No new code, no 31st issue. See the risks section.

## Recommended work for this week

1. **Land #32, then #6 and #7**, rebasing each. Unblocks the five PRs stacked on them.
2. **Land #10 and #45.** Both are independent of the stack and both fix findings visible
   in the published CLI's own output today.
3. **Decide #25** (aggressive imputes then drops a column, orphaning the indicator). It
   has been waiting on a product decision since 2026-11-06 and blocks nothing else, which
   is exactly why it keeps being skipped.
4. **Implement #23**, which closes `--fail-on` for free.
5. **Then #60.** Deliberately last: it is new, it needs a naming decision, and shipping a
   new check while 25 fixes sit unmerged would make the backlog worse, not better.

## Risks

- **Inaction is the dominant risk and it is compounding.** `main` has not moved in 21 days.
  Four P0s — #21 (no transform column contract), #34 (clean() renumbers the index), #40
  (id column hidden from the duplicate check), #47 (nullable boolean crashes
  `fit_transform`) — are live for every `pip install mlclean` today. The fixes exist. The
  gap between "written" and "shipped" is now the project's single largest liability.
- **Adoption risk, and it is measurable.** 123 downloads in the last month, 2 in the last
  week, 0 stars. Anyone who tries the demo dataset today meets a self-contradictory
  finding in the first screen of output. That is the first impression the published
  version makes.
- **Process risk: the stale-green trap.** #6 and #7 display 14 green checks dated
  2026-11-03. Anyone merging on that signal is merging an untested branch. Every PR needs
  a fresh run after #32 lands, not a glance at the badge.
- **Correctness risk from #60 specifically.** A user who follows the recommendation
  winsorizes a quarter of a real feature. Of all open findings this is the one where
  mlclean's advice actively damages data, rather than failing to warn about it.
- **Product risk, small and worth naming.** #60's fix adds a check name. With #16
  unresolved, a new selector shipped now would be a second vocabulary to migrate later.
  That is the stated reason it is fifth on the week's list rather than second.
- **No security or privacy risk.** Zero dependabot alerts, no network calls, no telemetry,
  pandas and numpy only.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since the first run |
| Forks | 1 | 1 | the fork that sent #49 |
| Outside contributors | 1 | 1 | `Theankitmishra`, #49, CI still unapproved — 6 days |
| Open issues | 30 | 27 | #58, #59 filed 11-20; #60 filed today |
| Open PRs | 25 | 24 | this report |
| Tests | 51 (`main`) | 51 | 0.82s |
| Coverage | 93% | 93% | `cleaning.py` 82% is still the floor |
| CI jobs green | 6 of 7 | 6 of 7 | only `ubuntu-latest, 3.9` fails |
| PyPI version | 0.2.0 | 0.2.0 | `main` at `b48eb32` for **21 days** |
| PyPI downloads | 2 week / 123 month | 2 week / 122 month | flat |
| Install from clean venv | yes | yes | repo `.venv`, pandas 3.1.1 |
| README examples run | yes, all 4 blocks | yes, all 3 | on real Telco, incl. both selector forms |
| CLI invocations run | yes | yes | exit 0 on Telco with no `--fail-on` |
| Datasets dogfooded | 2 (Telco, Criteo 2M) | 1 | first scale run on record |
| Largest frame audited | 2,000,000 × 16 | 1,000,000 × 5 (synthetic) | 4.1s, 419 MB peak, real data |
| Documented vs implemented checks | 12 rows / 18 names documented, 12 implemented | same | `checks=` takes neither (#16) |

## Decision needed from owner

1. **Merge PR #32?** It has been green and `CLEAN` for 13 days and it gates all 24 other
   PRs. Options: (a) merge it now and rebase the stack behind it; (b) keep waiting.
   **Recommend (a)** — there is no argument for (b) on the table, and the cost of (b) is
   another day with four P0s live on PyPI. I cannot merge it; `gh pr merge` is blocked
   here by the auto-mode classifier.
2. **After #32, do you want me to rebase the eight blocked PRs onto the new `main`?**
   Options: (a) I rebase all eight and report which gates go green; (b) I rebase #7 only,
   you confirm the theory, then the rest; (c) you do it. **Recommend (b)** — one probe
   costs almost nothing and proves the merge-order model before it is applied eight times.
3. **#60: add a new `concentrated_feature` check name, or suppress the bad finding
   without replacing it?** Options: (a) new check name, honest finding, but a new public
   selector while #16 is unresolved; (b) just cap the outlier rate so the wrong finding
   stops, and add the new check after #16 lands. **Recommend (b)** — it removes the
   harmful recommendation this week and defers the vocabulary question to the PR that
   is already about vocabulary.
4. **#25 still needs the product decision** it has been waiting on since 2026-11-06:
   under `aggressive`, should a column be imputed and then dropped, leaving its indicator
   behind? Options: (a) extend the guard to both tiers so it is never imputed-then-dropped;
   (b) keep the indicator deliberately and document it. **Recommend (a)**, with a named
   `keep_missingness_indicator` flag later if the behaviour turns out to be wanted.
