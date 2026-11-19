# mlclean daily report — 2026-11-19

## Executive summary

- `clean()` now demonstrably makes a frame worse: on a real 440,833-row churn file it
  returns a frame that fails mlclean's own audit with **ten MEDIUM `constant_column`
  findings that `clean()` itself created**. One empty row at the end of a CSV is enough.
  Filed as **#53** (P1).
- `clean(strategy="balanced")` drops **six of nine columns** on a standard OHLCV minute-bar
  file, including every price column, because the leakage check reads Pearson correlation
  and the balanced tier turns every leakage finding into a drop. The check's own
  recommendation says "verify the business timeline" — nothing verifies anything. Filed as
  **#54** (P1).
- Two new datasets dogfooded, both first-time: 440,833 × 12 Kaggle churn and 2,070,834 × 9
  SPY minute bars. Dogfooding corpus is now four datasets; both of today's P1s came from
  the two new ones and neither was reachable from Telco.
- The datetime gap (**#51**) reproduces on the second dataset: `date` is reported as
  1,432,780 categories to target-encode *and* as CRITICAL leakage, twice wrong for the same
  missing type. Evidence posted on the issue, including the cost constraint the fix needs.
- Report noise is now measured: 11 of 13 findings on the churn file are the same empty row
  seen column by column, each printing "(0.0%)". Filed as **#55** (P2).
- Performance is fine and now has numbers: 15.7s audit on 2.07M × 9, 836 MB peak RSS
  against a 142 MB frame, no O(n²) behaviour. `leakage` alone is 9.7s of the 15.7s.
- **#49, the first outside PR, has been waiting three days for its CI to be approved.** It
  is an owner-only click and it is still the most time-sensitive item in the repo.
- Nothing merged. `main` is still `b48eb32` from 2026-11-02, 23 open PRs, 27 open issues,
  and every fix written in the last 17 days is live-broken for anyone installing 0.2.0.
- Competitive delta: nothing moved in a day. No comparable has released since yesterday's
  full sweep.

## Repository health

- **Tests:** 51 pass on `main` in 0.49s; 54 on `fix/high-cardinality-numeric-text` (#45),
  55 on #49. No failures anywhere.
- **Lint:** `ruff check .` clean on `main` and on #45.
- **Coverage:** 93% on `main` (698 statements, 49 missed). `cleaning.py` at 82% is still
  the floor, and both of today's P1s live in it.
- **CI:** no run today. The last report PR (#52) shows 2 fail / 12 pass, and both failures
  are **#31** — `ubuntu-latest` rolled to 26.04, which has no Python 3.9, so the 3.9 job
  dies inside `actions/setup-python` before mlclean is installed. Only a branch carrying
  #32's commit can go green. Do not read those red marks as test failures.
- **Open PRs:** 23. Merge order, which has not changed:
  `#32` (CI, unblocks everything) → `#7` → `#11`, `#19` → `#6` → `#12` → `#38` → `#33`.
  Stacked PRs and their bases: #38 on `fix/clean-converts-numeric-text`, #37 and #33 on
  `ci/python39-runner-pin`, #19 and #11 on `refactor/split-type-checks`, #12 on
  `refactor/package-layout`. The rest sit on `main`. **#49 is from outside and is not in
  the stack** — it fixes #47 directly off `main`.
- **Open issues:** 27 after today's three. Nothing stale in the sense of being abandoned;
  everything is stale in the sense that no fix has landed. #23 (crashed checks read as
  INFO) remains the oldest P1 with evidence attached and no branch.
- **Dependencies:** 0 dependabot alerts, 0 open bump PRs. Still pandas + numpy only.
- **Published version vs main:** PyPI 0.2.0 == `main` == `b48eb32`, 17 days old. 4
  downloads last week, 122 last month, 0 yesterday. Everything in the 23 open PRs is
  absent from what users install.

## New issues found

**Bug — #53 (P1), no fix on any branch.** `build_pipeline` reads `missing_values`
findings off the input frame, but `_apply_impute` (`mlclean/cleaning.py:120`) adds
`f"{column}_missing"` unconditionally and runs *after* the row steps. When
`drop_unlabeled_rows` has already removed the rows that held the gaps, the indicator comes
out all zero. Measured: churn file 440,833 × 12 → `balanced` → (440,832, 21), ten added
columns, every one `nunique=1, sum=0`; re-auditing that output reports ten MEDIUM
`constant_column` findings. The step list is also internally inconsistent — the impute step
names `CustomerID` while the step before it drops that column.

**Bug — #54 (P1), no fix on any branch.** Leakage flags at `abs(pearson) >= 0.95` and the
balanced tier drops every flagged column with no severity floor and no confirmation. SPY
OHLCV 2.07M × 9: 5 CRITICAL findings → `balanced` and `aggressive` both drop `Unnamed: 0`,
`date`, `open`, `high`, `low`, `average`, leaving 3 of 9 columns. Pearson measures
collinearity, which is ordinary in any table holding a total and its components, two units
of one quantity, or a before/after pair.

**Enhancement — #55 (P2), no fix on any branch.** One empty row produces one
`missing_values` finding per column: 11 of 13 findings on the churn file, all printing
"(0.0%)" because 1/440,833 rounds away. On a 200-column frame it would be 200 findings.

**Performance — measured, not filed.** Per-check timings on 2.07M × 9 (whole audit 15.7s):
`leakage` 9.69s, `text` 2.15s, `constant` 1.64s, `sentinels` 1.52s, `mixed_types` 0.89s,
everything else under 0.7s. The leakage cost is the NMI crosstab against a 1.4M-distinct
column. A full-column `to_datetime(format="mixed")` on that same column is 45.3s on its
own — three times the whole audit — which is the constraint recorded on #51 for the
datetime check: decide on a sample, then confirm.

**Not filed, P3, recorded so they are not re-found.** The outliers message mixes number
formats inside one sentence (`'volume' has 70,093 values (3.38%) outside [-7,159,
1.108e+04]`) and reports a negative lower fence for a count column, where no value can be
negative.

## User-value opportunities

Ranked by impact over effort.

1. **#53, effort S.** The output of the library's headline function fails the library's own
   audit. It is a contained fix in `build_pipeline`, it has a four-test plan, and it is the
   kind of defect that costs a user trust on first contact. Highest value per hour available
   today.
2. **#54, effort M.** Bigger blast radius — a user silently loses most of their feature
   matrix — but the fix needs a product decision (does `balanced` drop leaky columns at
   all?), so it cannot be written before that decision is made. That is the only reason it
   is second.
3. **Land the stack, effort S for #32 and then mechanical.** 23 PRs, 17 days, every fix
   invisible to users. #32 alone turns the whole queue green. Nothing else on this list
   reaches a user until this happens.
4. **#51 + #50 as one semantic-type layer, effort M.** Confirmed on a second dataset today.
   ydata-profiling's variable types are the precedent, and four of six `high_cardinality`
   findings on real review data were wrong advice. Fixing them one at a time means finding
   the fourth face next week.
5. **#55, effort S.** Cheap readability win on the first thing every user sees. Ties with
   #51 on effort; #51 wins the tie because wrong advice beats noisy advice.

## Competitive insights

Nothing moved. Verified today: ydata-profiling 4.18.4 (2026-04-22), pandera 0.36.0
(11-10), cleanlab 2.9.0 (2026-01-13), deepchecks 0.19.1 (2024-12-15), Great Expectations
1.25.0 (11-12) — all identical to yesterday's full sweep. Next full sweep due 2026-11-25.

## Recommended work for today

1. **Approve #49's workflow run.** One click in the Actions tab. The first outside
   contributor has had no feedback for three days, and the fix is already verified locally
   (55 tests pass, ruff clean, the `is_numeric_dtype and not is_bool_dtype` routing matches
   what `outliers.py` and `sentinels.py` already do).
2. **Fix #53** on a branch off `main`. First step: in `build_pipeline`, apply the row steps
   to `report.df` and recompute remaining missingness per candidate column before emitting
   the impute step. Four named tests in the issue; the first fails on current code.
3. **Decide #54's shape** — not write it. The question is whether `balanced` may drop a
   leakage-flagged column at all. One answer unblocks the PR; the wrong order means writing
   a fix twice.

## Recommended work for this week

1. **#32**, then merge the stack in the recorded order. Unblocks every other fix reaching
   a user, and makes CI readable again.
2. **#53**, which is the smallest P1 with a complete test plan.
3. **#54** once its shape is decided.
4. **#51 + #50** as one semantic-type helper (free text, datetime-as-text, URL/path), with
   the sampling constraint measured today.
5. **#23**, so an audit whose checks crashed stops reading as clean. It is the oldest P1
   with evidence and it gates the honesty of every other finding.

## Risks

- **Inaction is the headline risk, and it is now 17 days old.** Everything in 23 PRs —
  including four P0s — is absent from PyPI 0.2.0. Today added two more P1s to the same
  queue. The repo's own history is the evidence: #11 and #44 were re-confirmed live on
  `main` yesterday, 16 days after their fixes were written.
- **Adoption:** #49 is the first external contribution the project has ever had, and the
  signal it sends depends entirely on how fast it gets a response. Three days of silence on
  a first PR is how a contributor decides not to send a second one.
- **Product:** #54 is the uncomfortable one. "Validation that also fixes" is the
  positioning, and today's measurement shows the fixing half deleting legitimate features
  on one real dataset and manufacturing dead ones on another. Both are in `cleaning.py`,
  the module with the lowest coverage.
- **Technical:** `cleaning.py` at 82% coverage is where both of today's P1s live. The
  untested lines are the strategy tiers.
- **Privacy/security:** no change. 0 dependabot alerts, no dependency added, no data
  committed to any repo.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since the first run |
| Forks | 1 | 1 | the fork that sent #49 |
| Outside contributors | 1 | 1 | `Theankitmishra`, #49, CI still unapproved |
| Open issues | 27 | 24 | #53, #54, #55 filed today |
| Open PRs | 23 | 22 | this report |
| Tests | 51 (`main`) | 51 | 0.49s; 54 on #45, 55 on #49 |
| Coverage | 93% | 93% | `cleaning.py` 82% is the floor |
| PyPI version | 0.2.0 | 0.2.0 | `main` at `b48eb32` for 17 days |
| PyPI downloads | 4 week / 122 month | 7 week / 122 month | single digits are noise; watch the month |
| Install from clean venv | yes | yes | fresh venv, pandas 3.1.1, numpy 2.4.6 |
| README examples run | yes, all 4 on real Telco | yes, all 4 | pass on `main` |
| CLI invocations run | yes, both forms | yes, both | exit 1 under `--fail-on medium` on the churn file |
| Datasets dogfooded | 4 | 2 | added Kaggle churn 440,833 × 12 and SPY 2,070,834 × 9 |
| Findings `clean()` creates | 10 MEDIUM on churn | not measured | #53 |
| Columns surviving `balanced` on OHLCV | 3 of 9 | not measured | #54 |
| Audit time, 2.07M × 9 | 15.7s | not measured | 836 MB peak RSS, `leakage` is 9.7s of it |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | still no datetime check in either count |
| Dependabot alerts | 0 | 0 | |

## Decision needed from owner

1. **Approve the workflow run on #49?** Options: approve and let CI report; approve and
   merge once green; leave it. Recommendation: approve now. It is the repo's first outside
   contribution, the fix is verified locally, and it closes #47 (P0). Two non-blocking
   review notes to leave on it: no CHANGELOG entry under `## Unreleased` (and
   `CONTRIBUTING.md` never asks for one, which is a repo-side gap worth its own line), and
   `errors` being a dataclass field makes two pipelines differing only in a recorded error
   compare unequal.
2. **Merge #32, then the stack?** Options: merge the whole order recorded above; merge #32
   alone to get CI green and decide the rest later; keep holding. Recommendation: merge #32
   today and then work down the order. Seventeen days of green-but-unmerged is now the
   repo's single biggest user-facing problem, and today's two P1s are queued behind the same
   gate.
3. **Does `balanced` drop leakage-flagged columns at all (#54)?** Options: (a) leakage
   becomes report-only and `aggressive` may drop; (b) a drop requires a second signal such
   as an exact functional relationship; (c) add an explicit `drop_leaky=` parameter,
   defaulting to off. Recommendation: (a) plus (c) — the check's own text asks the user to
   verify, so the library should not act on it unless the caller says to.
4. **Approve the #53 fix for today's implementation slot?** It is the plan in "Recommended
   work for today", item 2, on a branch off `main`, with the four tests named in the issue.
   Nothing starts until you say so.
