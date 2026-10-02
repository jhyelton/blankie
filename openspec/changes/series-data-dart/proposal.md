# Proposal

## Why

The series-data tool is written in Python, and the app is Dart. As a result the repository has two toolchains (uv, ruff, pytest next to Flutter), and the matching rules are implemented twice. `series-data-pipeline` accepted the second point as a trade-off ("every rule exists twice"), with the shared test cases as the safety net. `blankie-v1` hasn't started its matcher yet, so now is the cheapest time to change this. If the tool moves to Dart, the matching code can live in one package that both the tool and the app import, and the repository needs one language and one toolchain.

## What Changes

- Add `packages/blankie_series/`: a pure-Dart package (no Flutter, no `dart:io`) that holds the rules both sides need:
  - title normalization and wiki-to-feed matching (`episode-matching`)
  - the feed `pubDate` to calendar-date rule
  - the `series.json` model, with reading, writing and the supported schema version

  It passes `contracts/matching-vectors.json`.
- Rewrite `tools/series-data/` as a Dart command-line package that depends on `blankie_series`. It keeps the same commands (`generate`, `check`, `check-patreon`), flags, exit codes, report and output format. It replaces `mwparserfromhell` with a small wikitext parser written for the table layouts the tool already accepts.
- Prove the port before removing Python. Run the Python and Dart tools on the same saved wiki and feed responses. The output must be byte-identical: `series.json`, the report, and `check` and `check-patreon` results.
- **Remove** the Python package (`pyproject.toml`, `uv.lock`, `.python-version`, `src/`, `tests/`) and the Python lines in `.gitignore`. The test fixtures and golden files stay and move to the Dart test layout.
- Switch the `series-data` CI job and the weekly `series-data update` workflow from uv to the Dart SDK. The `series-data` path filter also covers `packages/**`. Add Dependabot `pub` entries for the two new packages.
- Update `tools/series-data/README.md`, `docs/runbooks/series-data.md`, `contracts/README.md` and `CLAUDE.md` to use the Dart commands.
- Update the `blankie-v1` plan, which hasn't been applied yet, so the app imports `blankie_series` instead of writing `app/lib/core/matching`. This touches its design (D1, D5) and tasks (1.2, 4.2, 4.3, 10.1).

Not changing: the published `series.json` (shape, bytes and URL), `series.schema.json`, `overrides.json`, the shared test cases, the guardrails, the weekly schedule, and the Keychain-based Patreon check.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `episode-matching`: matching becomes one shared implementation used by every consumer. The shared test cases remain the source of truth for that implementation.
- `series-data-validation`: PR validation also runs when the shared matching package changes.

## Impact

- **Code**: new `packages/blankie_series/` and a rewritten `tools/series-data/` (both Dart). About 2,100 lines of Python and 1,900 lines of Python tests are removed. Two workflows change: `.github/workflows/ci.yml` (the `series-data` job and the `changes` filter) and `.github/workflows/series-data-update.yml`. `.github/dependabot.yml` and `.gitignore` change too.
- **Dependencies**: removes `httpx`, `jsonschema`, `mwparserfromhell`, `pytest` and `ruff`. Adds the Dart packages `http`, `xml`, `args`, `path`, `json_schema`, `unorm_dart` (Unicode NFKD, which Dart's core library lacks), `html_unescape`, `test` and `lints`. The app later pulls in `unorm_dart` and `html_unescape` through `blankie_series`.
- **Toolchain**: CI uses the Dart SDK version that ships with the Flutter version the app pins (Dart 3.13.4 with Flutter 3.47.5). Local runs use the Dart that comes with Flutter, so the owner needs no Python or uv.
- **Data**: none. Before merging, the Python and Dart tools are run on the same freshly saved wiki and feed responses, and their outputs must be byte-identical. The wiki changes most weeks, so a PR from the first weekly run after merging is not a failure in itself. Its report should list only real wiki edits.
- **Other changes**: `blankie-v1` loses its own matcher and imports `blankie_series` instead. Its CI filter adds `packages/**`. Its D5 date rule changes from "UTC calendar days" to the contract's rule, the date in the feed's stated offset. Until now the two disagreed.
- **Secrets**: no change. Automation still never sees the Patreon feed.
