# Tasks

## 1. Tooling skeleton and PR checks

- [ ] 1.1 Create `tools/series-data/` as a uv-managed Python 3.12 package `series_data`, with pytest and ruff configured and a `series-data` CLI entry point with `generate`, `check` and `check-patreon` subcommands (stubs for now) (design D1, D2). Verify: `uv run pytest` passes (one placeholder test), `uv run ruff check` is clean, and `uv run series-data --help` lists the three subcommands.
- [ ] 1.2 Add `.github/workflows/series-data-check.yml`, which runs on pull requests that touch `tools/series-data/**`, `contracts/**` or `data/**`, sets up uv, and runs ruff, pytest and `series-data check`. Verify: a pushed branch shows the check passing in the PR's checks list.

## 2. Contracts: schema and shared matching test cases

- [ ] 2.1 Write `data/series.schema.json` (JSON Schema 2020-12) for the shape in design D5, covering every field required by the `series-data` spec "Dataset contents" and "Attribution" requirements. Add schema tests: one valid document and invalid ones (missing air date, bad category, unknown feed value, audio URL present). Verify: `uv run pytest -k schema` passes.
- [ ] 2.2 Create `contracts/matching-vectors.json` with a documented format (normalization cases plus match cases). Include every scenario from `specs/episode-matching` and every real miss from design Context, using synthetic Patreon items (design D11). Verify: the file validates against its own small schema, and a README section explains the format for the future Dart implementation.

## 3. Wiki fetch and parse

- [ ] 3.1 Implement the fetch stage: three sequential MediaWiki `action=parse` requests with the User-Agent and retry/backoff from design D9, plus an `--offline <dir>` mode that reads saved responses. Verify: unit tests using a mocked transport cover success, a retried 503, and a final failure. Offline mode reads a fixture directory.
- [ ] 3.2 Implement parsing of the *Episodes* page with `mwparserfromhell`: skip HTML comments, carry `rowspan` series cells down, strip markup from titles, parse M/D/YYYY dates, and raise an error on rows with unexpected cell counts. Verify: tests against committed wikitext excerpts (with attribution README) cover a rowspan block, a row with no series, a commented-out upcoming row, `<span>` titles, and the 3018 typo row parsed as-is.
- [ ] 3.3 Implement parsing of the *Blank Check: Special Features* page: `SF###` numbers, Patreon post IDs taken from both link forms, and multiple series split on `<br>`. Verify: tests cover SF294 (post ID `158692113`) and SF296 (two series).
- [ ] 3.4 Implement parsing of the *Miniseries* page into series metadata (title, subject, category from the section heading, wiki URL). Verify: tests confirm that "Podcastfellas" → Martin Scorsese / `director` and "The Phantom Podcast" → `star-wars`. A series referenced by an episode but missing from the Miniseries page gets category `other` and is listed in the report.

## 4. Matching

- [ ] 4.1 Implement title normalization per `specs/episode-matching`. Verify: every normalization case in `contracts/matching-vectors.json` passes through a pytest parametrized over that file.
- [ ] 4.2 Implement the matcher (hints first, then a ±3 day window, prefix/leading-"the" rules, tie-breaks, and "no match" on ambiguity). Verify: every match case in `contracts/matching-vectors.json` passes, and an offline run against the saved real public feed matches at least 590 of 600 main-feed rows before overrides.

## 5. Dataset generation

- [ ] 5.1 Implement `apply_overrides` with the ops and required `reason` from design D6, failing on overrides that don't resolve (and treating them as *pending* in `check` mode, design D7). Verify: tests for each op, a stale override error, and a pending wiki-number override.
- [ ] 5.2 Implement `assign_ids` using the previous dataset and the anchor order from design D4, and fail on duplicate IDs. Verify: tests show that an ID survives a title fix ("Podtastic" → "Podcastic") and a date fix, a new row gets `<date>:<slug>`, and a duplicate raises an error naming both rows.
- [ ] 5.3 Implement `build_dataset`: episodes keyed by ID, series ordered by air date including later releases, hints (public GUID/title and Patreon post ID) and attribution, written with sorted keys and 2-space indentation. Verify: a golden-file test on a fixture produces byte-identical output across two runs (ignoring `generatedAt`), and "Disclosure Day" sorts last in its series in the fixture.

## 6. Validation, guardrails and report

- [ ] 6.1 Wire schema validation and the guardrails (row-count drop, disappeared IDs, series losing episodes, more than 5% membership change) into `generate`, with an `--accept-guardrail-changes` flag. When no previous dataset exists (the first run), skip the comparison guardrails and say so in the report. Verify: tests cover each guardrail failing, passing when accepted with the overridden guardrails listed in the report, and a first run with no previous dataset.
- [ ] 6.2 Generate the Markdown report: counts, added/changed episodes, membership changes first, unmatched wiki rows and feed items (minus acknowledged ones), and overridden guardrails. Verify: a golden-file test of the report for a fixture diff.

## 7. Weekly update workflow

- [ ] 7.1 Enable *Settings → Actions → General → Allow GitHub Actions to create and approve pull requests* (the owner does this). Verify: the setting shows as enabled.
- [ ] 7.2 Add `.github/workflows/series-data-update.yml` per design D8: Monday cron plus `workflow_dispatch` with `accept_guardrail_changes`, generation with all checks before any PR step, a no-diff early exit that ignores `generatedAt`, `peter-evans/create-pull-request` on branch `series-data/update` with the report as the PR body, and raw responses uploaded as a 30-day artifact. It must not reference any Patreon secret. Verify: a manual run on a test branch opens a PR, and a second immediate run opens no new PR.

## 8. Local Patreon check

- [ ] 8.1 Implement `series-data check-patreon` per design D10: read the URL from the Keychain, parse in memory, write nothing to disk, and report by title, date and ID only, with URL-free error messages. Verify: tests with a local test HTTP server and a fake token URL confirm that stdout and stderr never contain `http` or the token, a 403 error shows only the status, and a missing Keychain entry exits with setup instructions and makes no request.
- [ ] 8.2 Run `check-patreon` against the owner's real feed (the owner does this on their Mac). Add `ackUnmatchedWiki` or `fix` overrides for any genuine misses. Verify: the report has no unexplained unmatched Special Features episodes.

## 9. First dataset, docs and publication

- [ ] 9.1 Run `generate` against the live wiki and feed. Review every unmatched item and add overrides for the real misses (Space Jam year, Podtastic/Podcastic, Titanic parts, Silence of the Lambs, Furiosa, the trailer, live-only episodes). Commit `data/series.json` and `data/overrides.json`. Verify: the report shows zero unacknowledged unmatched main-feed items, and `series-data check` passes.
- [ ] 9.2 Write `tools/series-data/README.md` (development and CLI usage) and `docs/runbooks/series-data.md`, covering:
  - how to review the weekly PR
  - how to write each override op
  - how to accept guardrail changes
  - how to store the Patreon URL in the Keychain and run `check-patreon`
  - the `GITHUB_TOKEN`/branch-protection caveat from design Risks

  Verify: every command in the runbook was actually run in this change.
- [ ] 9.3 After the repo is public, fetch `https://raw.githubusercontent.com/jhyelton/blankie/main/data/series.json` without credentials. Verify: `curl -sf` returns JSON that validates against `data/series.schema.json`. If the repo is still private, leave this task unchecked and report it as blocked; don't fake it.
