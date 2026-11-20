# mlclean daily report — 2026-11-20

## Executive summary

- **`id_columns` silently ignores any name it cannot match.** A leading space, a trailing
  space, the wrong case or a typo all degrade to "no id columns at all", with no warning.
  On the Telco file that loses a real finding: `--id-columns customerID` reports **22
  additional duplicate rows**, and `--id-columns " customerID"` reports none. New, P1,
  no fix on any branch.
- A space after a comma is the normal way to write a list, so `--id-columns "a, b"`
  drops `b`. This is the failure mode a user is most likely to hit and least likely to
  notice, because the audit still succeeds and still prints findings.
- **The CLI returns exit code 1 for two unrelated things**: the `--fail-on` quality gate
  tripping, and being unable to read the file at all. A CI job that gates on
  `mlclean audit data.csv --fail-on high` cannot tell "your data has problems" from
  "your path was wrong". New, P2.
- `--help` offers Parquet, but the package declares no Parquet engine, so a `.parquet`
  path exits with a 17-line pandas traceback about pyarrow. New, P2, docs or dependency
  decision.
- Everything else on `main` is healthy: 51 tests pass in 1.1s, `ruff` clean, 93% coverage,
  no dependabot alerts, all three README blocks and both documented CLI forms run against
  the real Telco file.
- **CI is still red on every PR, and it is still only the Python 3.9 job on
  `ubuntu-latest`** (issue #31). The fix is PR #32, open for 10 days. Until it merges,
  every PR in the stack shows a red X, which is the single biggest obstacle to anything
  merging.
- **Nothing has merged in 18 days.** `main` is still `b48eb32` (0.2.0, 2026-11-02) and
  PyPI serves that. 24 open PRs now, 27 open issues. Every one of the 31 recorded bugs
  that has a fix has that fix only on an unmerged branch, so all of them are live for
  anyone installing today.
- **#49 has waited three days for its workflow run to be approved.** It is the repo's
  first outside pull request, from `Theankitmishra`, and the approval is a single click
  only the owner can make. Three days is already long enough to lose a first-time
  contributor.
- Competitive: nothing moved since the 11-18 sweep.

## Repository health

- **Tests:** 51 passed in 1.09s on `main`. No failures, no skips.
- **Lint:** `ruff check .` — all checks passed.
- **Coverage:** 93% overall. Floor is `cleaning.py` at 82%, then `leakage.py` at 88% and
  `outliers.py` at 89%.
- **CI:** the matrix is green except `test (ubuntu-latest, 3.9)`, which fails on every
  branch. Six of seven jobs pass (macOS 3.13, Windows 3.13, Ubuntu 3.10–3.13). This is
  issue #31 and PR #32 fixes it by pinning that job to `ubuntu-24.04`.
- **Open PRs: 24.** The stack and the order it has to merge in:
  - Independent of everything, mergeable in any order: #32 (CI pin), #6, #7, #8, #9, #10,
    #45, #49, and the eleven daily reports (#13, #20, #26, #30, #39, #41, #43, #46, #52,
    #56, plus today's).
  - Stacked, and each breaks if its base merges without it being rebased:
    **#11 and #19 → base `refactor/split-type-checks` (#7)**;
    **#12 → base `refactor/package-layout` (#6)**;
    **#38 → base `fix/clean-converts-numeric-text` (#12)**, so #6 → #12 → #38;
    **#33 and #37 → base `ci/python39-runner-pin` (#32)**.
  - Practical order: **#32 first** (it unblocks CI for everything and is the base of #33
    and #37), then #7 → #11, #19, then #6 → #12 → #38.
- **Open issues: 27.** Four P0 (#21, #31, #34, #40), fifteen P1, the rest P2. None stale
  in the sense of being unreproducible; all of them are waiting on a merge, not on
  information. #44 and #50 overlap enough to be worth reading together — both are
  `high_cardinality` misclassifying a column — but they are genuinely different causes
  and #45 fixes only the first.
- **Dependencies:** 0 dependabot alerts, 0 open bump PRs. Workflow actions stay SHA-pinned.
- **Published version vs main:** PyPI serves 0.2.0, built from `b48eb32`, which is what
  `main` still points at. 122 downloads in the last month, 2 in the last week. So the
  gap is not "PyPI is behind main" — it is that main itself is 18 days behind the work.

## New issues found

**Bug — `id_columns` silently drops any name that does not match a column exactly (P1,
no fix on any branch).** `audit(df, id_columns=[...])` and `mlclean audit --id-columns`
both take the names on trust and never check them against the frame. Measured on
`WA_Fn-UseC_-Telco-Customer-Churn.csv` (7,043 × 21, target `Churn`):

| `id_columns` | duplicate-rows finding | id_column warning |
|---|---|---|
| `[]` | no | yes |
| `["customerID"]` | **yes — 22 additional rows** | no |
| `[" customerID"]` | no | yes |
| `["customerID "]` | no | yes |
| `["CustomerID"]` | no | yes |
| `["nosuchcol"]` | no | yes |

Every spelling that does not match behaves exactly like passing nothing. The user asked
mlclean to ignore an identifier, mlclean did not, and the report came back with fewer
problems than the data has. For a library whose whole job is telling people the truth
about their data, under-reporting on a parameter the user explicitly set is the bad
direction to fail in. The CLI makes it worse than the API, because `--id-columns "a, b"`
is the natural way to write a list and silently loses `b`.

Fix shape: validate the names against `df.columns` in `audit()`, strip surrounding
whitespace in `cli.py:51`, and emit a finding (not an exception) for a name that still
does not match — the library's own rule is that nothing aborts the audit.

**Bug — the CLI overloads exit code 1 (P2, no fix on any branch).** `cli.py` returns 1
when `--fail-on` trips, and an unreadable file escapes `pd.read_csv` as an uncaught
exception, which also exits 1. argparse already uses 2 for usage errors, so the
convention is there to follow. Measured: `--fail-on medium` on Telco exits 1; a path that
does not exist exits 1 with a 26-line traceback; a `.parquet` path with no engine
installed exits 1 with a 17-line traceback. CI cannot distinguish them. The README sells
`--fail-on high` as the CI gate, so this is on the documented path.

**Documentation — Parquet is advertised and not supported (P2).** `cli.py:23` says "CSV
or Parquet file to audit" and `cli.py:43` calls `pd.read_parquet`, but `pyproject.toml`
declares neither pyarrow nor fastparquet, and neither is a transitive dependency of
pandas. A user following the help text gets pandas' ImportError traceback. Three honest
options, in order of preference: catch it and print "Parquet needs pyarrow or fastparquet
— `pip install mlclean[parquet]`"; add a `parquet` extra and keep the core at pandas+numpy;
or drop Parquet from the help text. Adding pyarrow to the core install is the one option
to avoid — the library's selling point is that it needs only pandas and numpy, and pyarrow
is a ~40MB wheel.

**Not filed, recorded so it is not re-derived.** Audit is exception-clean on the edge
cases that break competitors: no target, a single row, zero rows with columns, an empty
frame, an all-NaN column, a multiclass target, a continuous target, and a frame that is
nothing but the target all return a report rather than raising. A target column that is
not in the frame raises `ValueError` with a clear message, which is right.

## User-value opportunities

1. **Merge PR #32 (S).** Helps everyone, including the outside contributor. It turns a
   red X into a green tick on 24 PRs, which is the difference between a stack that looks
   reviewable and one that looks abandoned. Nothing else on this list is worth doing
   before it.
2. **Approve #49's workflow run (S, one click).** Helps the first outside contributor.
   Three days of silence on a first PR is how a repo gets a reputation.
3. **Validate `id_columns` (S).** Helps anyone using the parameter, which is the one
   parameter the CLI does expose. Small, self-contained, and the test is three lines.
4. **Land the `high_cardinality` pair, #44 via PR #45 then #50 (M).** Helps every user
   with a text or numeric-stored-as-text column, which on the Telco file is the single
   most-reported column. #45 is written and waiting.
5. **Separate the CLI's exit codes (S).** Helps CI users specifically, and there is no
   way to know how many of the 122 monthly installs are CI until it is right.

Tie-break between 3 and 5 if only one fits: **3**, because it changes the report's
content and 5 only changes how a failure is classified.

## Competitive insights

Nothing moved. The last full sweep was 2026-11-18 and the next is due 2026-11-25; today's
delta checked the six closest comparables and every current release predates that sweep —
pandera 0.36.0 (11-10), pointblank 1.3.0 (11-12), Great Expectations 1.25.0 (11-12),
ydata-profiling 4.18.4 (April), cleanlab 2.9.0 (January), deepchecks 0.19.1 (last year).

## Recommended work for today

1. **Merge PR #32.** First step: read the one-line diff pinning the 3.9 job to
   `ubuntu-24.04`, confirm the job goes green on its own branch, merge. Everything else
   today is cheaper afterwards.
2. **Approve the workflow run on #49** so its CI can report, then review it. First step:
   open #49 and click the approval on the held run.
3. **Fix `id_columns` validation.** First step: add a test asserting that
   `audit(df, id_columns=["nosuchcol"])` produces a finding naming the unmatched column,
   watch it fail, then validate in `audit()` and strip whitespace in `cli.py:51`.

## Recommended work for this week

1. **PR #32.** Unblocks honest CI signal on all 24 PRs.
2. **The refactor bases, #7 and #6, in that order.** Unblocks #11, #19, #12 and then #38 —
   four fixes that cannot merge until their bases do.
3. **PR #45** (`high_cardinality` on numeric-stored-as-text). Unblocks issue #44 and makes
   the Telco report stop contradicting itself in two adjacent findings.
4. **The four P0s: #21, #34, #40, and #31 via #32.** Unblocks any claim that 0.2.0 is safe
   to use in a pipeline.
5. **A release PR once the stack is down.** Unblocks users actually receiving any of this;
   31 recorded bugs are fixed-on-a-branch and live on PyPI.

## Risks

- **The unmerged stack is the dominant risk and it compounds daily.** 18 days, 24 PRs, 31
  recorded bugs. Anyone running `pip install mlclean` today gets 0.2.0 with every one of
  them, including four P0s. "Fixed on a branch" is not fixed, and the gap between what the
  repo knows and what users have is now the project's main liability.
- **The stacked PRs rot.** #38 sits on #12 sits on #6. The longer #6 waits, the more likely
  a rebase of #12 and #38 conflicts, and that cost falls on whoever merges, not on whoever
  wrote them.
- **Adoption: the first outside contributor is being ignored.** #49 has waited three days
  for a click. Stars 0, forks 1, and that one fork is the contributor's.
- **Product: silent under-reporting is worse than a crash.** Today's `id_columns` finding
  is the second of this shape in a week (#53 was the first). A check that misreports costs
  more trust than a check that is missing, because the user has no signal that anything
  went wrong.
- **Risk of inaction on CI:** red CI on every PR trains everyone, including the owner, to
  ignore red CI. The day a test genuinely breaks, nobody will notice.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since the first run |
| Forks | 1 | 1 | the fork that sent #49 |
| Outside contributors | 1 | 1 | `Theankitmishra`, #49, CI unapproved for 3 days |
| Open issues | 27 | 27 | none filed today before this report |
| Open PRs | 24 | 23 | this report |
| Tests | 51 (`main`) | 51 | 1.09s; 54 on #45, 55 on #49 |
| Coverage | 93% | 93% | `cleaning.py` 82% is still the floor |
| CI jobs green | 6 of 7 | 6 of 7 | only `ubuntu-latest, 3.9` fails |
| PyPI version | 0.2.0 | 0.2.0 | `main` at `b48eb32` for 18 days |
| PyPI downloads | 2 week / 122 month | 4 week / 122 month | weekly is noise; the month is flat |
| Install from clean venv | yes | yes | repo `.venv`, pandas 3.1.1 |
| README examples run | yes, all 3 blocks | yes, all 4 | on real Telco, plus both CLI forms |
| CLI invocations run | yes, both forms | yes, both | exit 1 under `--fail-on medium` on Telco |
| Datasets dogfooded | 1 (Telco) | 4 | edge-case probing instead of new files today |
| Documented vs implemented checks | 12 rows / 18 names documented, 12 implemented | same | the 18 printed names map onto 12 functions; `checks=` takes neither (#16) |

## Decision needed from owner

1. **Merge PR #32?** It is a one-line runner pin that makes CI able to pass. Options:
   merge it now; or decide to drop Python 3.9 from the matrix instead, which is a bigger
   call with a user-facing consequence. **Recommendation: merge #32 now**, and treat
   dropping 3.9 as a separate question for the next release.
2. **Approve the held workflow run on #49?** Only you can. **Recommendation: yes, today.**
3. **Merge the refactor bases #7 and #6 this week?** Four other PRs are stacked on them
   and rot while they wait. **Recommendation: yes, #7 then #6**, each on its own, so a
   conflict is isolated.
4. **Parquet: extra, message, or drop it from the help text?** **Recommendation: a clear
   error message now and a `parquet` extra later.** Do not put pyarrow in the core
   install — pandas+numpy only is the thing that distinguishes this library.
5. **Should I fix `id_columns` validation today?** It is small, self-contained, and the
   test fails before and passes after. **Recommendation: yes** — say the word and it goes
   on its own branch off `main`, independent of the stack.
