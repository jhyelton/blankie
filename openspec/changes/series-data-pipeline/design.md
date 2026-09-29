# Design

## Context

What the exploration found by running prototype code against real data on 2026-09-29 (the requirements themselves are in `specs/`; the motivation is in `proposal.md`):

- **Wiki *Episodes* page** (MediaWiki API `api.php?action=parse&page=Episodes&prop=wikitext&format=json`, about 168 KB)
  - Episodes sit in several `wikitable`s, one per block of 50.
  - Each row is `# | '''[[Title]]''' | audio link | guests | length | M/D/YYYY | series`.
  - The series cell uses `rowspan="N"` to cover following rows.
  - Upcoming episodes sit inside HTML comments and must be skipped.
  - Some titles contain HTML, e.g. `<span class="avatar">`.
  - It currently holds 600 numbered rows across 69 distinct series; about 5 rows have no series.
- **Wiki *Blank Check: Special Features* page** (about 100 KB)
  - Same table shape, with `SF###` numbers.
  - The audio column links to Patreon posts (`patreon.com/[blankcheck/]posts/<slug>-<id>`).
  - The series cell can list **several** series separated by `<br>`.
  - The Patreon feed's `<guid>` **is** the Patreon post ID: 319 of the 326 post IDs linked from the wiki appear exactly as GUIDs in a real Special Features feed.
- **Wiki *Miniseries* page**: series metadata tables grouped under `Star Wars`, `Director Filmographies`, `Special Features` and `Other Series` headings, with subject and start date.
- **Prototype matcher** (normalized title prefix plus a ±2 day window) matched 590 of 600 wiki rows to the public feed. The misses were:
  - a wiki typo in the year (3018)
  - a spelling difference ("Podtastic"/"Podcastic")
  - a leading "The" difference
  - subtitle differences (*Furiosa: A Mad Max Saga*)
  - split-episode naming (*Titanic Part One* vs "Titanic with … - Part One")
  - episodes that were never in the public feed (live shows, announcements)
  - feed-only items (the trailer)
- **Fandom** reports the license as CC-BY-SA (`meta=siteinfo&siprop=rightsinfo`, license URL `https://www.fandom.com/licensing`).
- **Repo**: there's no Python code, CI or `.github/` yet. The repo is being made public, and PR #2 adds the project context to `openspec/config.yaml`.

## Goals / Non-Goals

**Goals:**
- A deterministic generator: the same wiki text, feed, overrides and previous dataset always produce byte-identical output, apart from `generatedAt`.
- A review experience where a normal week is either no PR at all or a small PR whose unmatched list is empty or obviously fine.
- Code the owner, who has a devops background and is new to this codebase, can read and debug.

**Non-Goals:**
- Any app code. `blankie-v1` consumes `series.json` and implements the Dart matcher against `contracts/matching-vectors.json`.
- Matching Patreon "(Ad-Free)" copies of main-feed episodes. They aren't in the wiki, and the app matches them to main-feed episodes on the device using the same rules.
- Editing the wiki automatically. Upstream fixes are done by hand, as a courtesy, and are optional.
- Film-level metadata (TMDB, Letterboxd). Maybe later.

## Decisions

### D1. Layout
```
tools/series-data/           Python package "series_data" + tests/
  pyproject.toml, uv.lock
contracts/matching-vectors.json   shared matching test cases (language-neutral)
data/series.schema.json           JSON Schema (draft 2020-12)
data/series.json                  generated, committed, served from main
data/overrides.json               hand-edited
.github/workflows/series-data-update.yml    weekly cron + manual run
.github/workflows/series-data-check.yml     pull_request checks
docs/runbooks/series-data.md
```
`contracts/` sits at the repo root, not under `tools/`, because the app's tests will load it too.

### D2. Python toolchain: `uv` + pytest + ruff, Python 3.12
`uv` gives a lockfile, fast CI installs (`astral-sh/setup-uv`), and one command to run tools (`uv run pytest`).
- Libraries:
  - `mwparserfromhell` for wikitext: tables, links, `<br>`, comments.
  - stdlib `xml.etree` for RSS; the feed is simple, and `feedparser` would hide the GUID handling.
  - `httpx` for HTTP.
  - `jsonschema` for validation.
- *Alternative:* pip + requirements.txt. More familiar, but it has no lockfile unless we add pip-tools.

### D3. Pipeline stages are pure functions around a thin I/O shell
```
fetch (I/O) -> parse_wiki -> apply_overrides -> assign_ids(prev) -> match(public feed)
            -> build_dataset -> validate(schema) -> guardrails(prev) -> report -> write (I/O)
```
Only `fetch` and `write` touch the network or disk. Every other stage takes plain data, which makes each stage testable against committed fixtures.

The CLI offers:
- `series-data generate [--offline <dir>]`
- `series-data check`
- `series-data check-patreon`

`--offline` reads saved wiki and feed responses, for reproducible debugging.

### D4. Stable IDs come from the previous dataset
`assign_ids` loads the current `data/series.json` and carries each existing ID forward to the row it identifies. It anchors in this order:
1. the wiki number (`600`, `SF294`)
2. the Patreon post ID hint
3. the public GUID hint
4. normalized title plus air date

Only rows with no existing anchor get a new ID, `<YYYY-MM-DD>:<slug(normalized title)>`. An episode's ID doesn't change when the wiki later fixes its title or date. See the `series-data` requirement "Stable episode IDs".

Series IDs follow the same idea: a slug of the wiki series page name, carried forward.
- *Alternative:* recompute IDs from scratch every run. Simpler, but any wiki correction would orphan saved playback progress in the app.

### D5. `series.json` shape (formally defined in `data/series.schema.json`)
```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-10-05T09:00:00Z",
  "source": { "name": "Blank Check with Griffin and David Wiki",
              "url": "https://blank-check.fandom.com",
              "license": "CC BY-SA", "licenseUrl": "https://www.fandom.com/licensing" },
  "series": [
    { "id": "podcastfellas", "title": "Podcastfellas", "subject": "Martin Scorsese",
      "category": "director", "wikiUrl": "https://blank-check.fandom.com/wiki/Podcastfellas",
      "episodes": ["2026-08-09:whos-that-knocking-at-my-door-boxcar-bertha", "..."] }
  ],
  "episodes": {
    "2026-09-27:after-hours": {
      "title": "After Hours", "airDate": "2026-09-27", "feed": "main", "wikiNumber": "600",
      "series": ["podcastfellas"],
      "hints": { "publicGuid": "cb353980-fae9-11f0-9ff5-ebf9d6641dd0",
                 "publicTitle": "After Hours with Alison Sivitz" } }
  }
}
```
- `episodes` is keyed by ID, for O(1) lookup on the phone.
- `series[].episodes` holds the order.
- `hints.patreonPostId` is set for Special Features rows.
- Keys are written sorted, with 2-space indentation, so diffs stay small and reviewable.
- `schemaVersion` bumps only for breaking changes, which the app can check.

### D6. Overrides format
`data/overrides.json` is a list of entries shaped `{ "op": ..., "target": ..., ..., "reason": "..." }`. The `op` values are `fix`, `pinPublicGuid`, `addToSeries`, `removeFromSeries`, `exclude`, `ackUnmatchedWiki` and `ackUnmatchedFeed`.

`reason` is required, so a year from now you know why each entry exists. The target is either an episode ID or, for rows that don't have an ID yet, a wiki number. Overrides that don't resolve fail the run (see the `series-data` requirement "Overrides").

### D7. Human override PRs don't regenerate the dataset
A PR that edits `overrides.json` is checked by `series-data-check.yml`: tests, schema validation, and whether every override resolves against the committed `series.json`. It does **not** refetch the wiki. An override that targets a wiki number not yet in the committed dataset is reported as *pending*, not as an error. The generator still fails if it can't resolve that override after fetching the wiki. The new override takes effect on the next scheduled run, or immediately if you trigger the manual run after merging.

This keeps PR checks deterministic and free of network calls, and every change to `series.json` comes from the one automated path.
- *Alternative:* regenerate in the PR. That brings in wiki drift unrelated to the override and makes the check depend on the network.

### D8. Weekly workflow and how its PR is created
`series-data-update.yml` runs on `schedule: cron "0 9 * * 1"` (Mondays 09:00 UTC, after the Sunday release) and on `workflow_dispatch` with the input `accept_guardrail_changes: boolean`.

Steps:
1. Check out the repo and set up uv.
2. `series-data generate`, which runs every validation and guardrail check and **fails the job before any PR step** if they fail.
3. If `git diff` shows no change other than `generatedAt`, stop.
4. Otherwise use `peter-evans/create-pull-request` with the fixed branch `series-data/update`, so one PR is open at a time and gets refreshed each week. The PR body is the generated report: counts, added/changed episodes, unmatched lists, and any guardrails that were overridden.

Permissions are `contents: write` and `pull-requests: write`, using `GITHUB_TOKEN`. That requires turning on the repo setting *Actions → General → Allow GitHub Actions to create and approve pull requests*.

A failed run shows a red X in Actions, and GitHub emails the owner. No issue-bot is needed.

### D9. The Fandom API is used politely
The tool makes three `action=parse` requests per run, sequentially, with the User-Agent `blankie-series-data/<version> (+https://github.com/jhyelton/blankie)`. It retries with backoff on 5xx and 429 and never runs in parallel. Raw responses are kept as a workflow artifact for 30 days to help debug parser failures. Those responses are CC BY-SA text, and the artifact is only visible to people with repo access.

### D10. The local Patreon check uses the macOS Keychain
`series-data check-patreon` runs `security find-generic-password -s blankie-patreon-feed -w` to get the URL. The runbook documents the one-time `security add-generic-password -s blankie-patreon-feed -a "$USER" -w` step; with no value after `-w`, macOS prompts for it, so it never lands in shell history.

The feed is parsed in memory. The report is built only from titles, dates and IDs. Every exception raised by the HTTP layer is caught and replaced with a message that has the status code but no URL.

A unit test runs the command against a local test HTTP server with a fake token URL and checks that neither `http` nor the token text appears in stdout, stderr or any file the command writes.

Since the wiki already provides post IDs for about 98% of Special Features rows, this check is expected to be quiet. Its main job is catching the few rows without post links.

### D11. Fixtures and the shared test cases are built from public data only
Test fixtures are:
- small excerpts of wiki wikitext (CC BY-SA; `tests/fixtures/README.md` gives attribution)
- small excerpts of the public feed
- **synthetic** Patreon-style items with fake numeric GUIDs and no URLs

The first set of `matching-vectors.json` covers every real miss listed in Context, plus the normalization cases from the `episode-matching` spec.

## Risks / Trade-offs

- **[Risk] Wiki formatting drifts** (a new column, a changed date format) and the parser silently misreads it. → *Mitigation:* the row-count and series-loss guardrails fail loudly. Parser tests run against real excerpts, and an unexpected cell count in a row raises an error instead of guessing.
- **[Risk] Vandalism or an honest mass edit** passes the guardrails with small changes, e.g. reassigning a few episodes. → *Mitigation:* every change is reviewed in a PR diff, and the membership-change summary sits at the top of the PR body. *Accepted:* a few wrong assignments until they're noticed are low-impact.
- **[Risk] PRs created with `GITHUB_TOKEN` don't trigger other workflows**, so the `series-data-check` status check won't run on the bot's PR. If branch protection later requires that check, the bot PR can't be merged. → *Mitigation:* the update job runs the same validation itself before opening the PR (D8). When branch protection is set up, either don't require the check on `series-data/update`, or switch the update job to a GitHub App token. That's recorded in the runbook.
- **[Risk] Raw GitHub caching** means the app may see an update a few minutes late. → *Accepted.*
- **[Risk] The repo isn't public yet**, so the raw URL returns 404 without auth. → *Mitigation:* the last task verifies unauthenticated fetch. If the repo is still private at that point, the task is blocked, not faked.
- **[Trade-off] Every rule exists twice**, once in Python and once later in Dart. → *Mitigation:* the shared test case file is the contract, and both suites must pass it (the `episode-matching` spec).

## Migration Plan

This is a new system, so there's nothing to migrate.

**Rollout:**
1. Merge the tool and the first reviewed `series.json` (with its initial overrides) in the implementation PR.
2. Enable the Actions PR setting.
3. Trigger one manual run to confirm that "no changes → no PR" works.

**Rollback:** disable the workflow. The last good `series.json` stays on `main`.
