# mlclean daily report — 2026-11-14

## Executive summary

- `main` has not moved in twelve days. Every one of the eighteen open issues that has a
  fix has that fix on an unmerged branch, so all of them are still live for anyone who
  installs 0.2.0 today. 121 downloads in the last month.
- #32 is still the only thing standing between seventeen PRs and a green gate. It is
  14/14 green and `CLEAN` against `main`. This is the fourth consecutive report with
  the same top item.
- Re-confirmed on `main` by running the README verbatim against the real Telco file:
  the header prints `Missing cells: 0 (0.00%)` for a file with 11 blanks, the parse-rate
  finding says "100% of values parse as numbers" directly above its own advice to
  "inspect the handful of non-numeric values", and a reloaded pipeline reports
  `version: 0.1.0`. All three have fixes on branches. None is in `main`.
- New finding, and it is a product gap rather than a bug: **mlclean does not notice two
  feature columns holding identical data.** `df.merge(billing, on="customerID")` — the
  ordinary way a training frame gets assembled — made pandas create `tenure_x`/`tenure_y`,
  `Contract_x`/`Contract_y` and `MonthlyCharges_x`/`MonthlyCharges_y`, all three pairs
  byte-identical. The audit reported four findings and named none of them;
  `clean(strategy="aggressive")` kept all six columns.
- `CleaningPipeline.from_json` still cannot read what `to_json` returns: the serialized
  text exceeds the filename limit, `Path(source).exists()` raises
  `OSError: File name too long`, and README block 2 only works because it reads from a
  file. Fixed on PR #12's branch, live on PyPI.
- Two things checked today and **not** broken, recorded so no future run re-spends the
  time: `audit()` leaves the caller's frame untouched (content, dtypes, column order and
  index all identical afterwards on 7,043 x 21), and so does `clean()` at all three
  strategies. `ignore_columns` genuinely excludes a column from every check.
- Competitive delta: nothing moved into mlclean's space. pandera 0.36.0 added
  LLM-delegated derived columns, Great Expectations 1.25.0 added column-to-column row
  conditions. Both are rule-writing surfaces and both widen the distance from
  zero-config rather than closing it.
- No dependency or security change. 0 dependabot alerts, no bump PRs, no data in the
  repo.

## Repository health

- **Tests:** 51 passed in 0.83s on `main`. No failures, no skips.
- **Lint:** `ruff check .` — all checks passed.
- **Coverage:** 93% (698 statements, 49 missed), unchanged.
- **CI:** red on every branch cut from `main`, and it is #31, not the code.
  `test (ubuntu-latest, 3.9)` dies inside `actions/setup-python` with
  `The version '3.9' with architecture 'x64' was not found for Ubuntu 26.04`, before
  mlclean is installed. The other twelve jobs pass. Only a branch carrying #32's commit
  can report the now-required `test (ubuntu-24.04, 3.9)` context.
- **Open PRs:** 17. The merge order, read off each PR's `baseRefName` today rather than
  from memory:
  - **#32 first, alone.** `ci/python39-runner-pin` -> `main`. Nothing else can go green
    until it lands, and every other branch then needs `main` merged in to pick up the
    new workflow file.
  - Stack A: **#6** (`refactor/package-layout`) -> **#12** (`fix/clean-converts-numeric-text`)
    -> **#38** (`fix/clean-preserves-index`).
  - Stack B: **#7** (`refactor/split-type-checks`) -> **#11** and **#19** (both based on it).
  - Stack C: **#32** -> **#33** (`fix/transformer-contracts`) and **#37** (report 11-11).
  - Independent of any stack, based on `main`: #8, #9, #10, #13, #20, #26, #30, #39.
  - A stacked PR whose parent merges without it being rebased will break, so the order
    above is load-bearing, not advisory.
- **Open issues:** 18. Nothing stale in the sense of lacking a reproduction — every one
  carries measured evidence. Four carry P0: #21 and #27 (both fixed on #33), #31 (fixed
  on #32), #34 (fixed on #38) and #40 (no fix on any branch). #29 is blocked behind #16
  by design.
- **Dependencies:** 0 dependabot alerts, no open bump PRs. Still pandas + numpy only.
- **Published version vs main:** PyPI 0.2.0 = `main` at `b48eb32`, unchanged since
  2026-11-02. Nothing on a branch has reached a user.

## New issues found

**Enhancement, P1 — no check for duplicated feature columns.** Two columns holding
identical data produce zero findings. Reproduced on real Telco through a plain merge:
`df.merge(df[["customerID","tenure","MonthlyCharges","Contract"]], on="customerID")`
gives 7,043 x 24 with three byte-identical `_x`/`_y` pairs, and the audit's four findings
name none of them. `clean(strategy="aggressive")` dropped `customerID` and kept all six
duplicated columns. Not covered by anything existing: `duplicate_rows` is the row
analogue, the `duplicate_column_names` check added on PR #19 is about duplicate *labels*,
and this case has distinct labels because pandas renames rather than duplicates them.
`target_leakage` compares features to the target, never to each other. Cost of the
check is not an argument against it: hashing 61 columns x 7,043 rows with
`pd.util.hash_pandas_object` took 0.008s, so hash-then-verify is effectively free and
needs nothing outside pandas. No fix on any branch. **To be filed today.**

**Documentation, P3 — the whitespace finding illustrates every column with the same
wrong example.** On Telco it prints "'TotalCharges' has 11 values with leading or
trailing whitespace — ' yes' and 'yes' become two categories" for a money column.
Carried over unfiled from 2026-11-04; recorded again because it is in the output of the
README's first example, which is the first thing a new user sees. No fix on any branch.

Nothing else new. The other eighteen findings in the backlog were re-confirmed rather
than rediscovered.

## User-value opportunities

Ranked by impact over effort.

1. **Land #32, then the three stacks** — S for #32 itself, M for the rebases. Helps
   every user of 0.2.0, because it is the only thing that converts fifteen branches of
   finished work into a release. Nothing else on this list competes with it; it is not
   a feature, it is the precondition for shipping any of them.
2. **#40's reporting half** — S. Helps anyone who follows the README: today `clean()`
   returns duplicate rows it never reported. Branches off `main` cleanly because nothing
   open touches `checks/duplicates.py`, so it merges in any order. Asked for approval
   yesterday; not yet given.
3. **The duplicated-column check** — M. Helps anyone who builds a training frame from a
   join, which is most people. Changes what they see from "four findings, data looks
   fine" to "three feature pairs are the same column twice". Breaks the tie against #40
   only if the owner would rather add a check than fix one, since #40 is a correctness
   bug and this is an absence.
4. **#23's check-completion count** — S. Helps CI users: today no `--fail-on` setting
   can fail a run whose only findings are crashed checks. Closes the `--fail-on` hole for
   free and unblocks #29.
5. **#24's markdown escaping** — S. Helps anyone whose data contains a pipe; one value
   breaks the whole table. Lands on #6.

## Competitive insights

Daily delta only — the last full sweep was 2026-11-11 and the next is due 2026-11-18.

Two releases landed after that sweep and neither touches mlclean's niche.
**Great Expectations 1.25.0** (2026-11-12) added column-to-column comparisons inside row
conditions and fixed SQL-backend metrics under a row condition. Still a rule-writing DSL,
still warehouse-first. **pandera 0.36.0** (2026-11-10) added `ParsedField`/`ParsedColumn`
and a `pandera.decisions` API that delegates column derivation to a decision model. That
is a schema-authoring surface with an LLM behind it; it moves pandera further from
zero-config and further from pandas-plus-numpy-only, so it widens mlclean's distinction
rather than threatening it. pointblank 1.3.0 and pyjanitor 0.32.77 were already counted
on 2026-11-12 and 2026-11-11. Nothing else moved.

One idea worth taking from GE's release, stripped of its DSL: it is explicit about null
semantics when comparing two columns of the same row. mlclean has no cross-column check
at all, and the duplicated-column finding above is the version of that which needs no
rules from the user.

## Recommended work for today

1. **Merge #32.** Owner's call; the daily job cannot run `gh pr merge`. First step:
   `gh pr merge 32 --squash` after confirming `gh pr view 32 --json mergeable` still
   reads `MERGEABLE`.
2. **File the duplicated-column enhancement** with the merge reproduction above, the
   0.008s cost measurement and the hash-then-verify sketch. First step: `gh issue create`
   with the acceptance criteria and test plan.
3. **#40's reporting half, if approved:** make `check_duplicates` see the detected id
   columns, with a regression test on a Telco-shaped frame that interleaves its
   duplicates rather than appending them.

## Recommended work for this week

1. **#32, then rebase the three stacks onto the new `main`.** Unblocks every other item
   on this list; nothing ships without it.
2. **Release 0.2.1 the moment stacks A and B are in.** Unblocks the whole reason the
   backlog exists: six user-visible bugs reach users only at a release.
3. **#40 both halves** — the reporting fix, then the owner's decision on whether
   `clean()` must return a frame that passes its own audit. Unblocks trusting `clean()`.
4. **#23's completion count.** Unblocks #29 and makes `--fail-on` mean something.
5. **The duplicated-column check.** Unblocks nothing, which is why it is last; it is the
   first new user-facing capability in two weeks and worth starting once the queue moves.

## Risks

- **Inaction is now the dominant risk and it is compounding.** Fifteen branches hold
  fixes for bugs that are live on PyPI, re-confirmed on `main` today by running the
  README's own examples. 121 downloads in the last month, 18 in the last week. A reader
  who tries the quickstart meets a self-contradictory finding in the first screen of
  output.
- **The report itself has become a status risk.** The #32 merge has now been reported as
  the top decision four days running. Anything in these files dated before today should
  be re-read rather than trusted; confirm `main` with `git rev-parse origin/main`.
- **The stacked PRs are a decay risk.** Six of the seventeen are based on another branch.
  Every day they sit, `main` and their parents drift further apart, and the rebase that
  #32 already forces gets larger. The cost of the queue is rising, not flat.
- **Adoption:** 0 stars, 0 forks, no external issue or PR. Nothing on a branch has
  reached a user, so none of the finished work is earning anything yet.
- **Product:** the duplicated-column gap is the first finding in a while that is an
  absence rather than a defect, and absences are what a careful first user compares
  against pyjanitor or a hand-rolled `df.T.duplicated()`.
- **Security/privacy:** no change. 0 dependabot alerts, no new dependency proposed, no
  data committed in any repo.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since the first run |
| Forks | 0 | 0 | |
| Open issues | 18 | 18 | one to be filed today |
| Open PRs | 17 | 17 | plus this report |
| Tests | 51 (`main`) | 51 | |
| Coverage | 93% | 93% | |
| PyPI version | 0.2.0 | 0.2.0 | `main` at `b48eb32` for 12 days |
| Install from clean venv | not re-tested today | — | last verified 2026-11-10 |
| README examples run | yes, all 3 on real Telco | yes | header/body contradiction still visible |
| `audit()` mutates input | **no** (new measurement) | not measured | content, dtypes, order, index all intact |
| `clean()` mutates input | **no** (new measurement) | not measured | all three strategies |
| Duplicate feature columns detected | **no** (new measurement) | not measured | 3 identical pairs, 0 findings |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | README heading still says v0.1 |
| PyPI downloads (day / week / month) | 1 / 18 / 121 | 3 / 16 / — | |
| Dependabot alerts | 0 | 0 | |

## Decision needed from owner

1. **Will you merge #32 now?** Fourth day as the top item, and the only PR `CLEAN`
   against `main`, 14/14 green. Options: (a) merge it yourself; (b) grant standing
   permission to run `gh pr merge` so the daily job can land green PRs itself.
   Recommend (a) today and (b) as a standing arrangement. Confirm the result with
   `git rev-parse origin/main`, not from this report.
2. **May I implement #40's reporting half?** Unchanged from yesterday, still unanswered.
   Branches off `origin/main`, merges in any order against the stack. Options: (a) yes;
   (b) no, land the stack first. Recommend (a).
3. **Should the duplicated-column check go in, and in which form?** Options: (a) a new
   `duplicate_columns` check reporting each group of identical columns at MEDIUM, with
   `clean()` leaving them alone; (b) (a) plus a cleaning step that keeps the first column
   of each group under `balanced` and above; (c) not now. Recommend (a) — reporting is
   the part that cannot be wrong, and dropping a column the user may have meant to keep
   is the kind of decision #25 shows we should not take silently.
4. **Still open from 2026-11-12, unanswered: should `clean()` guarantee its own output
   passes `audit()`?** This is #40's data half and a design call. Options: (a) re-check
   duplicates after the drop-identifier step and append a `remove_duplicates` step,
   making `clean()` idempotent and changing row counts for anyone relying on today's
   behaviour; (b) leave the rows and have `clean()` warn that its output still has
   findings; (c) document that `clean()` is a single pass. Recommend (a). No code until
   you pick.
