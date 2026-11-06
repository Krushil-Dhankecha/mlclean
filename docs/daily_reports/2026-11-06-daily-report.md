# mlclean daily report — 2026-11-06

## Executive summary

- Nothing merged for the fourth day running. `main` is still `b48eb32` from 2026-11-02,
  so every fix in the ten open PRs is still absent from the version on PyPI.
- Two new bugs found, both in code paths no previous run had exercised, both filed.
- `to_markdown()` does not escape `|`, so one pipe in a class label or a column name
  shifts every cell after it. Measured: a 5-cell and a 6-cell row against a 4-cell
  header (issue #24, P1). The CLI's `--markdown` writes exactly the file people paste
  into a CI job summary.
- The `aggressive` strategy imputes a column and then drops it, leaving a
  `<column>_missing` indicator with no column beside it and a dead fill value in the
  serialized pipeline (issue #25, P2). Reproduced on real Telco.
- Issue #23 is worse than it was written up as. `--fail-on` has no `info` setting, so a
  frame where 8 of 12 checks crashed exits 0 at every severity. Evidence posted on #23;
  that makes it the first P1 to land, not the third.
- The crashed-check count is frame-dependent — 7 of 12 on 2026-11-04, 8 of 12 on
  today's all-numeric frame. #23's "N of 12 could not run" has to be counted at audit
  time, not read off a list.
- One theory tested and dead: `to_json()`'s `default=str` does not stringify numbers.
  Every `details` value comes out as a native int or float on both Telco and a frame
  firing eleven checks. Do not re-test this.
- Both new bugs survive PRs #6 and #12 unchanged, so neither is a refactor artifact —
  but both fixes have to stack on those branches rather than branch off `main`.
- First install traffic on PyPI: 102 in the last week, against 0 stars, 0 forks and 0
  watchers. Read it as mirror traffic, not users.
- Competitive delta: nothing moved. pyjanitor is still 0.32.75 from 2026-11-04;
  every other comparable's latest release pre-dates the 2026-11-04 sweep.

## Repository health

- **Tests:** 51 passed in 0.87s on `main`. No failures, no skips.
- **Lint:** `ruff check .` — all checks passed.
- **Coverage:** 93% (698 statements, 49 missed). Weakest: `cleaning.py` 82%,
  `checks/leakage.py` 88%, `checks/outliers.py` 89%.
- **CI:** all ten open PRs at 14/14 SUCCESS across py3.9–3.13 on Linux plus macOS and
  Windows on 3.13.
- **Open PRs:** ten. Two are daily reports off `main` and independent — #13
  (2026-11-04) and #20 (2026-11-05). The eight code PRs need this order:
  - #9 (docs: product audit + roadmap) → #10 (leakage by mutual information)
  - #6 (split `report/` and `cleaning/` into packages) → #12 (`clean()` converts
    numbers-stored-as-text, `from_json` fix)
  - #7 (split `checks/types.py` per concern) → #11 (floored parse rate, blank
    sentinels) and → #19 (column-label shapes), two siblings; whichever merges second
    needs a rebase
  - #8 (memory footprint) last, since it also touches `checks/__init__.py`
- **Open issues:** ten, up from eight. #14–#18 and #21–#25. #14 and #15 are already
  closed by PR #19 and can be closed the moment it merges. Nothing stale, nothing
  duplicated; every one has a reproduction.
- **Dependencies:** 0 dependabot alerts, no open bump PRs. Runtime deps still pandas
  and numpy only.
- **Published version vs main:** identical — `main` is the 0.2.0 tag. Which is the
  problem: the thirteen known bugs fixed on branches are all live for anyone installing
  today.

## New issues found

**Bug — #24, P1.** `to_markdown()` interpolates `message`, `columns` and
`recommendation` into a table row with no escaping (`mlclean/report.py:93-105`). A
class label `trial|free` yields a 5-cell row; a column named `rev|cost` yields 6, both
against a 4-cell header. `to_text()` and `to_json()` are correct on the same report, so
it is the renderer alone. No fix on any branch. PR #6 moves the code to
`mlclean/report/markdown.py` with the formatting unchanged, so the fix belongs on top
of #6.

**Bug — #25, P2.** Under `aggressive`, `build_pipeline` (`mlclean/cleaning.py:196-204`)
guards the impute tier with `if strategy == "balanced" and rate >= missing_threshold`,
so a high-missing column is imputed and then dropped by the tier's own
`high_missing_rate` step. Output keeps `mostly_null_missing` with no `mostly_null`; the
pipeline JSON keeps a median nothing reads. Verified on Telco plus one 80%-null column.
Needs a decision before a fix — keeping the indicator is defensible, but nothing chose
it. No fix on any branch; belongs on top of #12.

**Bug — evidence added to #23, not a new issue.** `--fail-on` accepts only
`critical|high|medium|low` (`mlclean/cli.py:33-37`), and `check_error` is INFO, so a CI
gate cannot fail on a broken audit. On a duplicate-label frame: 8 check_errors, 0 real
findings, exit 0 at all four settings, and nothing in the rendered text states how many
checks completed.

**Not filed, lower priority, carried for tomorrow:**
- `disguised_missing` and `outliers` both report the same 165 `-999` values as separate
  unrelated findings. The outlier check should know a value was already flagged as a
  sentinel.
- `details["rate"]` is rounded to 4 places in `missing.py` and `duplicates.py` but 5 in
  `outliers.py` (`0.03324`). One of them is wrong; pick one.
- Still open from 2026-11-04: `whitespace_padding` illustrates every column with a
  hardcoded `' yes'`/`'yes'`; the header's "Missing cells" counts only NaN; the CLI
  prints raw tracebacks for a missing file or unknown `--target`; `py.typed` ships but
  nothing type-checks; the README check table is still headed "Checks (v0.1)".

## User-value opportunities

Ranked by what a user feels, divided by effort.

1. **Land the stack.** Thirteen fixed bugs reach users the day it merges, and it costs
   no new code. Nothing else on this list competes. Effort S for Krushil, impossible
   for Claude — see Decisions.
2. **#23's skipped-check count.** Turns a silently-clean audit into an honest one and
   closes the CI hole in the same change. Helps anyone whose frame has an unusual
   column shape, which is anyone with duplicate labels, a MultiIndex, or list cells.
   Effort S.
3. **#24's Markdown escaping.** Helps anyone using `--markdown` for a CI summary, which
   is the output most likely to be read by someone other than the person who ran it.
   Effort S.
4. **#21's column contract on `MLCleaner.transform`.** Still the only P0. Silent
   misprediction through XGBoost, torch and ONNX. Effort M, and it is the one new file
   the stack does not touch — `transformer.py` is contended by no open PR.
5. **#16's check-name vocabulary.** `skip=["disguised_missing"]` raises on the name the
   report just printed. First thing a user tries after reading a finding they want to
   mute. Effort S.

Tie-break between 2 and 3, if it matters: #23 fails silently in a pipeline, #24 fails
visibly on a page. Prefer the silent one.

## Competitive insights

Nothing moved. Latest releases: pyjanitor 0.32.75 (2026-11-04), pandera 0.35.0
(2026-10-25), cleanlab 2.9.0 (2026-01-13), ydata-profiling 4.18.4 (2026-04-22),
deepchecks 0.19.1 (2024-12-15). pyjanitor's was already counted in the 2026-11-05
delta; everything else pre-dates the 2026-11-04 sweep. Next full sweep due 2026-11-11.

One thing the new findings touch: patito's pitch of "reports all validation errors at
once" is already how mlclean behaves, and #23 is the reason it cannot be claimed yet —
reporting every error at once is worth nothing if the report does not say which checks
failed to run.

## Recommended work for today

At most three, each finishable today.

1. **#23 — count the checks that could not run and raise the headline.** First step:
   add a `checks_run` / `checks_total` pair to `AuditReport.summary()`, counted in
   `audit()` where the guard already catches the exception. Then have the headline
   severity respect it, which makes `--fail-on` work for free. Branches off `main`;
   `audit.py` is touched only by #19, so expect a small conflict there.
2. **#24 — escape Markdown cells.** First step: a `_cell(text)` helper that replaces
   `|` with `\|` and collapses newlines, applied to the three interpolated fields.
   Branch off `refactor/package-layout` and target #6.
3. **#25 — decide the aggressive tier's indicator question**, then make the one-line
   guard change. First step is the decision, not the code.

Realistically one of these lands today. Recommend 1.

## Recommended work for this week

Ordered.

1. **Merge the eight code PRs in the order above.** Unblocks everything; thirteen bugs
   go from branched to fixed, and the next PR stops conflicting with six others over
   `CHANGELOG.md`.
2. **#21 — the `MLCleaner.transform` column contract.** The only P0. Unblocks any
   honest claim about serving, which the README's sklearn section already implies.
3. **#23**, as above. Unblocks `report.fail_if` (P2), which would otherwise ship with
   the same hole.
4. **#17 — the pandas floor CI job**, pinning both pandas 1.5.3 and `numpy<2`.
   Unblocks saying `pandas>=1.5` out loud, and settles whether the declared floor
   should move up instead.
5. **#16 — accept the check names the report prints.** Unblocks the first thing a user
   does with `skip=`.

## Risks

- **Inaction is the top risk, and it has compounded four days.** Thirteen known bugs are
  fixed in branches and live in `main`. Anyone who installs mlclean today gets a leakage
  check that cannot fire on a 0/1 target, a parse rate that rounds 99.84% up to 100%,
  and an audit that loses seven to eight of twelve checks on a duplicate-label frame.
  Every day the stack sits is a day the published version is worse than the work done.
- **The stack is getting harder to land, not easier.** Both of today's fixes have to
  stack on open PRs rather than branch off `main`, because #6 and #12 own the files.
  `CHANGELOG.md` is contended by seven PRs. This grows.
- **Product: `aggressive` has undecided behaviour.** #25 is cheap now and expensive
  once someone depends on the orphan indicator.
- **Adoption: no inbound channel.** 0 stars, 0 forks, 0 watchers, Discussions off. The
  102 weekly PyPI installs are almost certainly mirrors. The visibility wave is
  unblocked and unstarted, but it should not start while #21 and #23 are open — the
  first careful reader would find them.
- **Quality: `py.typed` still ships with no type checker anywhere.** Unchanged, and the
  longer it ships the more likely someone's `mypy` run blames mlclean.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | Discussions still off, no inbound channel |
| Forks | 0 | 0 | |
| Watchers | 0 | 0 | |
| Open issues | 10 | 8 | #14–#18, #21–#25; #24 and #25 new today |
| Open PRs | 10 | 10 | all 14/14 green, nothing merged since 2026-11-02 |
| Tests | 51 pass, 0.87s | 51 pass, 0.82s | 60 on the #19 branch |
| Coverage | 93% | 93% | `cleaning.py` 82% is the weakest module |
| Dependabot alerts | 0 | 0 | |
| PyPI version | 0.2.0 | 0.2.0 | `main` identical to it |
| PyPI installs (7d) | 102 | not measured | first time measured; read as mirrors |
| Install from clean venv | works | works | verified 2026-11-02 |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | README table still headed "v0.1" |
| Telco audit time | 0.26s | not measured | 7,043 × 21, 4 findings |

## Decision needed from owner

1. **Merge the stack?** Ten PRs, all green, nothing merged in four days. Claude cannot
   merge — the auto-mode classifier blocks `gh pr merge` as "Merge Without Review".
   Options: merge in the order above yourself; grant the permission; or say the stack is
   waiting on something, so the next run stops reporting it as the top risk.
   **Recommend merging #9 → #10 and #6 → #12 today**, which clears four of the eight and
   frees `CHANGELOG.md` and `cleaning/strategies.py`.
2. **Which of today's three should Claude implement?** One task, with approval.
   **Recommend #23** — it closes a silent CI hole, branches off `main`, and the
   skipped-check count is needed before `report.fail_if` can ship.
3. **#25: should `aggressive` keep the missingness indicator for a column it drops?**
   Options: (a) drop cleanly — extend the guard, output loses both; (b) keep the
   indicator deliberately, document it, and emit an indicator-only step. **Recommend
   (a)**, and add (b) later as a named `keep_missingness_indicator=True` option rather
   than as a side effect of step ordering.
4. **Hold the visibility wave?** The portfolio card, Kaggle notebooks and Show HN are
   unblocked. **Recommend holding until #21 and #23 land** — a careful first reader
   finding a silent misprediction costs more than a week of waiting.
