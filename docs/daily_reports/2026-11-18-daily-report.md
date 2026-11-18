# mlclean daily report — 2026-11-18

## Executive summary

- **Someone outside the project sent a pull request.** `Theankitmishra` opened
  [#49](https://github.com/Krushil-Dhankecha/mlclean/pull/49) at 08:08Z yesterday,
  fixing issue #47 (the nullable-boolean crash filed by the 11-17 run). First external
  contribution the repo has had, and the fork count went 0 → 1.
- **Their CI never ran.** The run concluded `action_required`: GitHub holds workflows
  from first-time fork contributors until the owner approves. So the first outside
  contributor has waited 25 hours with no feedback of any kind. Approving that run is
  the single most time-sensitive thing on this list.
- I verified #49 locally instead: 55 tests pass, `ruff` clean, and the fix matches the
  root cause #47 describes. It adds no CHANGELOG entry, which is a repo-side gap —
  `CONTRIBUTING.md` never asks for one.
- **A new gap, found by auditing a free-text dataset for the first time.** On 21,214 real
  Amazon reviews, `high_cardinality` fired six times and **four of the six are wrong
  advice**: it tells the user to frequency- or target-encode a column of 84-word review
  paragraphs, and to do the same to two ISO-8601 timestamp columns.
- The free-text half is filed as **#50**, the datetime half as **#51**. Both are the same
  shape as #44: the check reads storage dtype and calls everything textual "a category to
  encode". PR #45 fixes only the numeric case, so both survive the whole open stack.
- Nine daily runs never saw this because Telco has no free-text and no date column. The
  separation in the data is not subtle — 83.8 mean words in `Review Text` against ≤2.0
  in every column that really is categorical.
- **`main` has not moved in 16 days** and now carries 22 open PRs. Every `pip install`
  today still gets #11 and #44 on the demo dataset: two of four findings on Telco argue
  from a premise the same report rejects.
- **#32 is still the gate.** `ubuntu-latest` is Ubuntu 26.04, which has no Python 3.9, so
  every PR branched off `main` shows a red check that has nothing to do with its change.
  #32 is 14/14 green and has been sitting since 11-10.
- Full competitor sweep ran today (due). Nothing moved into mlclean's space. The one
  useful outside data point supports #50: ydata-profiling had to add a separate variable
  type because free text was being treated as categorical.
- Re-measured the nine look-alike libraries from the 11-11 sweep: **not one has released
  since.** mlclean is still the most-downloaded of the group and the only one with a
  second month of commits — in open branches.

## Repository health

- **Tests:** 51 pass on `main` in 0.96s. 54 on PR #45's branch, 55 on #49's.
- **Lint:** `ruff check .` — all checks passed, on `main` and on #49.
- **Coverage:** 93% total. `cleaning.py` is still the floor at 82%, and it is where #47
  and #48 both live.
- **CI:** the matrix is 13 of 14 green on anything off `main`. The one failure is
  `test (ubuntu-latest, 3.9)` with `The version '3.9' with architecture 'x64' was not
  found for Ubuntu 26.04`. Not the code — issue #31, fix open in #32.
- **Open PRs:** 22. Merge order:
  1. **#32** (`ci/python39-runner-pin`, 14/14 green) first — it unblocks #33 and #37,
     which are stacked on its branch, and makes every other PR's CI readable.
  2. **#6** → **#12** → **#38** (`refactor/package-layout` → `fix/clean-converts-numeric-text`
     → `fix/clean-preserves-index`), in that order; #38's base is #12's branch.
  3. **#7** → **#11** and **#19**, both stacked on `refactor/split-type-checks`.
  4. Then the independents off `main`: #8, #9, #10, #45, #49, and the report PRs
     (#13, #20, #26, #30, #39, #41, #43, #46, and this one).
  Stacked PRs break if their parent merges without them being rebased, so 2 and 3 are
  orders, not preferences.
- **Open issues:** 22, now 24 with #50 and #51. Nothing stale enough to close, nothing
  duplicated, every one carries a reproduction. #31 is the only one whose fix is green
  and waiting.
- **Dependencies:** 0 dependabot alerts, 0 open bump PRs. Still pandas + numpy only.
- **Published version vs main:** PyPI has 0.2.0 from 2026-11-02; `main` is `b48eb32`,
  the same commit. Nothing merged in 16 days, so everything in the 22 PRs — including
  two P0 fixes — is invisible to users.

## New issues found

**Bug — [#50](https://github.com/Krushil-Dhankecha/mlclean/issues/50), P1. `high_cardinality`
calls a free-text column a category to encode.** No fix on any branch. Measured on
`Amazon_Reviews.csv` (21,214 rows): `'Review Text' has 20,407 distinct categories →
One-hot encoding will explode; prefer frequency or target encoding, or group rare
categories.` `Review Text` averages 83.8 words and 460.8 characters, 251 words at the
95th percentile. Target-encoding a review paragraph is not a thing a data scientist would
do; the advice should be to vectorize it or drop it. `Review Title` (5.4 words, 31 chars)
is the same finding and the honest borderline case. Survives PR #45, which excludes only
columns that parse as numbers.

**Bug — [#51](https://github.com/Krushil-Dhankecha/mlclean/issues/51), P1. No check
recognises a datetime stored as text, so date columns are reported as high-cardinality
categories.** No fix on any branch. Same dataset: `Review Date` is 100% parseable as a
timestamp and is reported as `21,054 distinct categories` at MEDIUM; `Date of Experience`
is also 100% parseable and reported as `3,640 distinct categories` at INFO. mlclean has
`numeric_stored_as_text` and no datetime equivalent, so the most common feature-engineering
opportunity in a CSV — year, month, day-of-week, recency — is never mentioned, and the
advice given instead is to encode the raw string.

**Documentation — not filed, P3.** `CONTRIBUTING.md` says nothing about logging changes
under `## Unreleased` in `CHANGELOG.md`. PR #49 omitted the entry, which is the
predictable result. One sentence in CONTRIBUTING fixes it; folding it into the #49 review
is cheaper than a separate issue.

**Bug — not filed, P3.** The whitespace finding hardcodes a toy example regardless of
column: `'Review Text' has 865 values with leading or trailing whitespace — ' yes' and
'yes' become two categories.` On an 84-word prose column that illustration is noise.
Worth fixing when #50 is done, since both touch how a textual column is described.

**Not a finding, checked:** `errors` on `CleaningPipeline` in #49 is a dataclass field,
so two pipelines that differ only in a recorded error compare unequal. It is reset at the
start of each `apply()` and excluded from `to_json`, and `report.clean()` returns the
pipeline, so a caller can actually reach `pipeline.errors`. Review note, not a bug.

## User-value opportunities

Ranked by impact over effort.

1. **Approve #49's workflow run, review, merge.** (S) Helps the one person who has
   volunteered work. It costs a click and a read; leaving it costs the contributor. The
   fix is verified green locally.
2. **Merge #32.** (S) Helps every reviewer and contributor, including the outside one,
   who currently cannot tell a real failure from the runner problem. Green since 11-10.
3. **A semantic-type layer behind `high_cardinality`** — free text, datetime-as-text, and
   URL/path, each with its own advice. (M) Helps anyone auditing data with prose or dates
   in it, which is most real datasets. Closes #50, #51 and the fourth of six wrong
   findings on the review dataset, and generalizes #44's one-off fix into the rule it was
   always a case of. Pandas-native: token counts and `to_datetime(errors="coerce")`, no
   new dependency.
4. **Land the #6 → #12 → #38 and #7 → #11/#19 stacks.** (M) Helps every published-version
   user: it is what makes #11's parse-rate fix and #19's label fixes real.
5. **One sentence in CONTRIBUTING about the Unreleased section.** (S) Helps the next
   outside contributor avoid the only thing #49 got wrong.

Tie-break between 3 and 4: 4 fixes claims users see today, 3 fixes claims they will see
tomorrow on their own data. 4 wins on a user-count basis, 3 wins if the goal is that the
next dogfooding run stops finding the same class of bug.

## Competitive insights

Full sweep, which was due today. Versions and dates taken from the PyPI API.

- **Nothing moved into mlclean's space in a week.** Only `soda-core` released since the
  11-11 sweep that had not already been counted: **4.31.0** (11-17). Its changes are
  BigQuery/SQL Server dialect work, Soda Cloud handling and telemetry — **no new check
  types**, so nothing to borrow for the default check set. One item to note and not copy:
  `feat(telemetry): count Python API calls`. mlclean's no-dependencies, no-phone-home
  posture is a selling point against exactly that.
- Already counted and unchanged: pandera 0.36.0 (11-10), Great Expectations 1.25.0
  (11-12), pointblank 1.3.0 (11-12), pyjanitor 0.32.79 (11-17). Did not move at all:
  pandas 3.1.1, Polars 2.1.0, DuckDB 2.0.0, scikit-learn 1.9.1, ydata-profiling 4.18.4,
  cleanlab 2.9.0, deepchecks 0.19.1. Dead end of the list unchanged: openclean-core 0.4.1
  (2021), DataKleaner 0.1.1 (2025-03), `cleanTS` still 404 on PyPI.
- **Outside support for #50, and it is the useful find of the sweep.** ydata-profiling
  introduced a separate variable type specifically because free text was being treated as
  categorical, and its recognised types include Date/Datetime and URL/Path. The library
  with the most profiling users hit this exact problem and had to answer it with a type
  layer, which is the shape #50 and #51 propose. mlclean's type inference currently has
  two states — numeric-ish and textual — and everything textual becomes "a category to
  encode."
- **Re-measure of the nine look-alikes from 11-11: not one has released since.**
  leakage-buster 1.0.2 (2025-09-13), mlleak 0.1.1 (2025-12-24), featureleakagelens 0.2.0
  (2026-05-05), datasentry 1.0.0 (2026-02-22), dfaudit 0.1.0 (2026-05-08), tput 0.1.0
  (2026-04-13), sanipy 0.1.1 (2026-06-26), mlradar 1.0.1 (2026-05-30) — every version and
  date identical to the 11-11 measurement. Weekly downloads: mlclean 7, tput 6,
  leakage-buster 4, featureleakagelens 4, sanipy 4, mlleak 3, datasentry 2, dfaudit 1,
  mlradar 1. mlclean leads the group and the whole group is in the noise band; these
  numbers cannot distinguish a user from a mirror. mlclean's own weekly count fell from
  16 on 11-11 to 7.
- The uncomfortable reading, unchanged from 11-11 and now sharper: what separates mlclean
  from those nine is a second month of maintenance, and a repo whose newest commit is 16
  days old with 22 open branches does not look separate. The outside PR is the first real
  evidence to the contrary and is currently blocked on an approval click.

## Recommended work for today

1. **Approve the workflow run on #49, then review it.** First step:
   `gh api -X POST repos/Krushil-Dhankecha/mlclean/actions/runs/<id>/approve`, or the
   "Approve and run" button on the PR. This is Krushil's call — it runs a fork
   contributor's code in his CI — so I have not done it.
2. **Merge #32.** First step: read the four-line diff on `.github/workflows/ci.yml`, then
   merge. Everything downstream gets readable CI.
3. **Write the `free_text` check** (#50) on a branch off `main`. First step: add
   `_text_shape()` to `checks/_common.py` returning mean token count and mean length, and
   a test asserting `Review Text`-shaped data is not reported as a category. Needs
   approval before I touch code.

## Recommended work for this week

1. **#49 in, with the CHANGELOG line and the CONTRIBUTING sentence.** Unblocks the first
   outside contributor and closes P0 #47.
2. **#32.** Unblocks #33 and #37 and makes every other PR's CI mean something.
3. **The #6 → #12 → #38 stack, then #7 → #11/#19.** Unblocks the parse-rate fix and the
   column-label fixes for published-version users — the two things today's Telco run
   still reproduces.
4. **The semantic-type layer** (#50, #51, and the URL case). Unblocks honest advice on any
   dataset with prose or dates, and retires the class #44 is one instance of.
5. **#48** (`to_json` raises on a datetime fill value). Unblocks the README's own
   `# reproducible, auditable` line on any frame with a datetime column — which, after
   #51 lands, is a frame mlclean will be telling people to parse.

## Risks

- **Adoption, and it is live right now.** The repo's first outside contributor has had no
  CI and no review for 25 hours. Nothing in open source is more reliably fatal to a
  second contribution than silence on the first.
- **The unmerged stack is a user-facing risk, not housekeeping.** 22 PRs, 16 days, two P0
  fixes among them. Anyone who installs mlclean today gets #11 and #44 on the demo
  dataset, and #47 crashes their `clean()` on a nullable boolean column even though a fix
  now exists in two places.
- **Wrong advice is worse than missing advice,** and #50/#51 are wrong advice. A user who
  target-encodes a review-text column because mlclean told them to is worse off than a
  user mlclean said nothing to. Four of six `high_cardinality` findings on a real dataset
  were in this class.
- **Stale green.** Most of the 14-green badges on older PRs were earned on a runner image
  that no longer exists. A PR that reads green is not known to pass today until #32 lands
  and CI re-runs.
- **Product:** mlclean's type model is binary (numeric-ish / textual) and real data has
  more kinds of column than that. #44, #50 and #51 are three symptoms of one design gap,
  and fixing them one at a time means finding the fourth next week.
- **No type checker runs anywhere** although the package ships `py.typed`. Recorded once;
  not re-reported.

## Metrics to watch

| Metric | Today | Previous | Note |
|---|---|---|---|
| Stars | 0 | 0 | unchanged since the first run |
| Forks | 1 | 0 | first outside fork, and it sent a PR |
| Outside contributors | 1 | 0 | `Theankitmishra`, PR #49 |
| Open issues | 24 | 21 | #50 and #51 filed today |
| Open PRs | 22 | 20 | includes one from outside and this report |
| Tests | 51 (`main`) | 51 | 0.96s; 54 on #45, 55 on #49 |
| Coverage | 93% | 93% | `cleaning.py` 82% is still the floor |
| PyPI version | 0.2.0 | 0.2.0 | `main` at `b48eb32` for 16 days |
| Install from clean venv | yes, main imports and audits | yes | fresh venv, pandas 3.1.1 |
| README examples run | yes, all 4 on real Telco | yes, all 4 | pass on `main` |
| CLI invocations run | yes, both documented forms | yes, both | exit 0 on the review dataset |
| Findings on demo file with a wrong premise | 2 of 4 | 2 of 4 | #11 and #45 still unmerged |
| Wrong `high_cardinality` findings on review data | 4 of 6 | not measured | #50 and #51 |
| Datasets dogfooded | 2 (Telco, Amazon reviews) | 1 | first free-text and first date columns |
| Documented vs implemented checks | 12 / 12 | 12 / 12 | no datetime check in either count |
| Dependabot alerts | 0 | 0 | |

## Decision needed from owner

1. **Approve the held workflow run on #49?** The run is `action_required` because GitHub
   gates first-time fork contributors. Options: approve it (CI runs, contributor gets
   feedback), or review and merge on my local verification alone (55 tests, ruff clean,
   fix matches #47's diagnosis). **Recommendation: approve it.** It is the contributor's
   evidence, not just yours, and the matrix covers five Python versions my laptop does
   not. I have not done this myself — it runs outside code in your CI, which is your call.
2. **Merge #32?** 14/14 green since 11-10, four lines, pins the 3.9 job to `ubuntu-24.04`.
   **Recommendation: merge it first, before anything else.** Nothing else in the queue can
   be judged on its CI until it lands.
3. **Then the stacks, in order: #6 → #12 → #38, and #7 → #11, #19?**
   **Recommendation: yes, in that order.** Merging a parent without rebasing its children
   breaks them, and #11 is what stops the demo dataset reading "100% of values parse as
   numbers" when the true rate is 99.84%.
4. **May I write the `free_text` check for #50 this run?** Scope: a `_text_shape()` helper
   in `checks/_common.py`, a `free_text` finding, `high_cardinality` skipping columns it
   claims, tests on review-shaped data, CHANGELOG under `## Unreleased`, no version bump,
   no new dependency. Branch off `main`, independent of the stack.
   **Recommendation: yes, but after #32 and #49**, so the new PR's CI is readable and the
   outside contributor is not queued behind me. #51 is a second PR, not part of this one.
