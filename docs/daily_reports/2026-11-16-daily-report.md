# mlclean daily report — 2026-11-16

## Executive summary

- Nothing merged. `main` is still `b48eb32` from 2026-11-02, now 14 days old, with 18
  open PRs and 19 open issues. Everything PyPI users install is pre-fix.
- The queue's "green" status is misleading, and that is new. Twelve of the eighteen PRs
  report 14/14 passing from check runs dated **2026-11-03**. `ubuntu-latest` has since
  rolled to 26.04, which has no Python 3.9 build, so re-running any of them today fails
  the `test (ubuntu-latest, 3.9)` job. PR **#32** is the only branch whose `ci.yml`
  pins `ubuntu-24.04`, and the only one green against today's runners.
- New finding, from running the audit on the Telco demo file: `check_high_cardinality`
  gates on storage dtype, so `TotalCharges` is reported as a 6,531-category categorical
  with target-encoding advice — in the same report that says it is numeric. Two of the
  four findings on the demo dataset argue from a premise the report itself contradicts.
- Dogfooding re-confirmed #11 is live for users: one finding reads "'TotalCharges' is
  text but 100% of values parse as numbers" and then "inspect the handful of non-numeric
  values first". The rate is 99.84%, rounded up by `:.0%`.
- Every README snippet and both documented CLI invocations run clean against the real
  7,043-row Telco file. `--fail-on` gates correctly: exit 1 at `medium`, exit 0 at `high`.
- 51 tests pass in 0.75s, `ruff check` clean, coverage 93%, no TODO/FIXME markers, zero
  dependabot alerts.
- No competitor moved into mlclean's space. Only pyjanitor bumped (0.32.77 → 0.32.78,
  patch). Full sweep is due 2026-11-18.
- 2026-11-15 had no run, so this report covers two days of drift rather than one.
- Downloads are 0 / 14 / 121 (day / week / month); the week figure is down from 18.
  Stars and forks remain 0.

## Repository health

- **Tests:** 51 passed in 0.75s on `main`. No skips, no warnings surfaced.
- **Lint:** `ruff check .` — all checks passed. (`ruff format` is deliberately not
  enforced here; a format diff is not a finding.)
- **Coverage:** 93% (698 statements, 49 missed). Weakest modules: `cleaning.py` 82%
  (lines 255-272 uncovered), `checks/leakage.py` 88%, `checks/outliers.py` 89%.
- **CI:** 14 jobs per PR (py3.9–3.13 on Linux, plus macOS and Windows on 3.13). Status
  by PR is below, and the distinction between *green today* and *green in November* is
  the thing to read.
- **Open PRs: 18.** Merge order, read off each PR's `baseRefName` today:
  - **#32 first and alone** (`ci/python39-runner-pin` → `main`). 14/14 green against
    current runners. Until it lands, nothing else can be made green.
  - After #32: every other branch needs `main` merged in before its gate can pass.
  - Stack A: **#6** → **#12** → **#38**
  - Stack B: **#7** → **#11** and **#7** → **#19** (siblings; the second needs a rebase)
  - Stack C: **#32** → **#33** and **#32** → **#37**
  - Based on `main`, independent: #8, #9, #10, #13, #20, #26, #30, #39, #41, and this
    report's PR.
  - Genuinely failing right now: #30, #39, #41 (and #38), all on the py3.9 job, all for
    the runner reason above rather than anything in their diffs.
- **Open issues: 19.** Four P0 (#21, #31, #34, #40), eleven P1, four P2. None stale in
  the sense of lacking a reproduction — every one carries a measured example. #31 is the
  CI issue that #32 fixes.
- **Dependencies:** zero dependabot alerts, zero open bump PRs. Still pandas + numpy
  only, which remains the product's distinguishing constraint.
- **Published version vs main:** PyPI `0.2.0` is byte-identical to `main`. Every fix on
  every branch — 19 issues' worth — is unavailable to anyone who installs mlclean today.

## New issues found

**Bug (P1) — `high_cardinality` reads storage dtype, so a numeric-stored-as-text column
is reported as a high-cardinality categorical.** `checks/types.py:199` skips a column
only when it is not textual and not categorical. It never asks whether the values parse
as numbers, which `check_mixed_types` has already established 30 lines above. On the
Telco demo file this produces, in one report: `numeric_stored_as_text` on `TotalCharges`
(MEDIUM, correct) and `high_cardinality` on `TotalCharges` (MEDIUM, "6,531 distinct
categories → prefer frequency or target encoding"). You do not target-encode a currency
amount. `whitespace_padding` compounds it, describing the column's 11 blank strings as
"' yes' and 'yes' become two categories". No fix exists on any branch. Not a duplicate
of #28, which is `disguised_missing` vs `outliers` on the same cells.

**Already filed, re-confirmed live on the published version (no new issue):** #11, the
parse-rate rounding — the same finding says 100% parse and then tells you to inspect the
non-numeric values. #12, `clean(strategy="safe")` leaves `TotalCharges` as text and
`customerID` in the frame, returning all 7,043 rows × 21 columns unchanged. Both have
fixes sitting on unmerged branches.

## User-value opportunities

Ranked by impact over effort.

1. **Land #32, then the stack** (effort S for #32, M for the cascade). Helps every
   current and future user, because it is the gate on all 19 issues' worth of fixes
   reaching PyPI. Nothing else on this list changes what an installed mlclean does.
2. **Fix the wrong-premise findings** (effort S). Helps every new user: the demo dataset
   is the first thing anyone runs, and two of its four findings currently give advice
   that contradicts the report they sit in. The product's claim is that it tells you the
   truth about your data.
3. **Give the checks a shared notion of a column's effective type** (effort M). The
   generalisation of #2 and of #28: `numeric_stored_as_text`, `high_cardinality`,
   `whitespace_padding`, `disguised_missing` and `outliers` each re-derive what a column
   is, and disagree. One resolved type per column, computed once in the audit context,
   removes a whole class of contradictory findings rather than this instance.
4. **Check registry / `register_check`** (effort M). The standing "dynamic so everyone
   can use it" goal; `ALL_CHECKS` is still a static list.

#2 and #3 tie on user impact. The tiebreak is that #2 is finishable today and #3 needs a
design decision about where resolved types live, so #2 ships first and #3 absorbs it.

## Competitive insights

Nothing moved. pyjanitor 0.32.77 → 0.32.78 (2026-11-14) is a patch on a chainable-verbs
API that has never overlapped mlclean's zero-config audit. pandera 0.36.0, Great
Expectations 1.25.0, pointblank 1.3.0 and soda-core 4.30.0 were all counted in the
2026-11-11 sweep; ydata-profiling, cleanlab and deepchecks have not released since
spring. Next full sweep due 2026-11-18.

## Recommended work for today

1. **Fix `high_cardinality` to skip numeric-stored-as-text columns**, with a test on the
   contradictory pair and a CHANGELOG line under `## Unreleased`. First step: extract the
   parse-rate test from `check_mixed_types` into a helper both checks call, so the two
   cannot drift apart. Needs approval before any code is written.
2. **Decide #32.** It is one squash merge and it unblocks the other seventeen PRs. No
   code to write.
3. **Nothing else.** The queue, not the backlog, is what is costing users.

## Recommended work for this week

1. **Merge #32.** Unblocks every other PR's CI.
2. **Merge the three P0 fixes behind it** — #34 (clean() renumbers the index), #21
   (MLCleaner has no column contract), #40 (id column hidden from the duplicate check).
   Unblocks a truthful 0.2.1.
3. **Land stacks A and B in base order**, rebasing the second sibling of #7. Unblocks
   the ten issues those branches close.
4. **Release 0.2.1** in a dedicated version-bump PR once the stack is in. Unblocks every
   fix actually reaching a user — the only step on this list a user can feel.
5. **Resolved column types in the audit context.** Unblocks #28 and the finding above
   being fixed once rather than per check.

## Risks

- **Inaction on the queue is the dominant risk, and it compounds.** Fourteen days of
  drift means six stacked PRs whose parents are further from `main` each day, and the
  rebase that #32 forces grows with them. Meanwhile every `pip install mlclean` ships
  all 19 known defects.
- **Stale green is worse than red.** Twelve PRs advertise 14/14 from 2026-11-03. Anyone
  reading the queue — including a future run of this job — can conclude the stack is
  ready to merge when in fact only #32 would pass today. Record it or re-trigger it, but
  do not trust it.
- **Product risk: contradictory findings cost more credibility than missing ones.** A
  tool whose whole proposition is "tell me the truth about my data" giving two
  mutually-inconsistent recommendations about one column on the canonical demo dataset is
  worse than a tool with fewer checks.
- **Adoption:** 0 stars, 0 forks, 121 downloads/month and a week-over-week dip. Nothing
  has been published or posted. This stays a risk until a release carries a real catch.
- **No type checker runs anywhere** although the package ships `py.typed`. Noted once;
  not re-raised daily.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since the first run |
| Forks | 0 | 0 | |
| Open issues | 19 | 19 | +1 to be filed today |
| Open PRs | 18 | 17 | plus this report |
| Tests | 51 (`main`) | 51 | 0.75s |
| Coverage | 93% | 93% | `cleaning.py` 82% is the floor |
| PyPI version | 0.2.0 | 0.2.0 | `main` at `b48eb32` for 14 days |
| Install from clean venv | not re-tested today | not re-tested | last verified 2026-11-10 |
| README examples run | yes, all 4 on real Telco | yes, all 3 | all pass |
| CLI invocations run | yes, both documented forms | not measured | `--fail-on` exits 1/0 correctly |
| PRs green against *today's* runners | **1 of 18** (new measurement) | not measured | only #32 |
| Findings on demo file with a wrong premise | **2 of 4** (new measurement) | not measured | both about `TotalCharges` |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | README heading still says v0.1 |
| PyPI downloads (day / week / month) | 0 / 14 / 121 | 1 / 18 / 121 | week down from 18 |
| Dependabot alerts | 0 | 0 | |

## Decision needed from owner

1. **Merge #32?** It is green against current runners, fixes P0 #31, and gates the other
   seventeen PRs. Options: merge it now; or keep holding the whole queue.
   *Recommendation: merge it now.* Fourteen days is long enough, and no other PR can be
   verified until it lands.
2. **After #32, land the stack in base order, or rebase everything onto `main` first?**
   Options: merge in dependency order (#6 → #12 → #38, #7 → #11/#19, #32 → #33/#37),
   accepting one rebase for #7's second sibling; or rebase all six stacked branches onto
   `main` up front and merge them flat. *Recommendation: merge in base order.* The
   stacks are already correct and flattening re-tests six branches to save one rebase.
3. **Approve the `high_cardinality` fix for today?** Scope: a shared numeric-parse helper
   in `checks/types.py`, `check_high_cardinality` skipping columns it identifies, one
   regression test on the Telco contradiction, CHANGELOG under `## Unreleased`, no
   version bump. *Recommendation: yes* — it is the smallest change that stops the demo
   dataset arguing with itself.
4. **Does the resolved-column-type refactor get scheduled this week or deferred?**
   Options: schedule it after the stack lands, absorbing the #2 fix and closing #28; or
   defer until a release is out. *Recommendation: defer until 0.2.1 ships.* It touches
   five checks, and nothing should compete with getting fixes to users.
