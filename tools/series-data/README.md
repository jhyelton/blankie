# series-data

Builds [`data/series.json`](../../data/series.json): which Blank Check episodes belong to which miniseries, and in what order. The data comes from the [Blank Check fan wiki](https://blank-check.fandom.com) (CC BY-SA), and each episode is matched against the public podcast feed. The blankie app fetches the result from `main`.

Day-to-day operation (reviewing the weekly PR, overrides, guardrails, the Patreon check) is in [`docs/runbooks/series-data.md`](../../docs/runbooks/series-data.md). This file is about the code.

## Setup

Needs [uv](https://docs.astral.sh/uv/) (`brew install uv`). uv installs Python 3.12 and the locked dependencies into `.venv/` here.

```bash
cd tools/series-data
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
```

CI runs the same commands plus `series-data check` (the `series-data` job in `.github/workflows/ci.yml`) on PRs that touch `tools/series-data/`, `contracts/` or `data/`.

## CLI

```bash
uv run series-data generate [--offline DIR] [--save-raw DIR] [--accept-guardrail-changes] [--report FILE]
uv run series-data check
uv run series-data check-patreon
```

- `generate` fetches the wiki and the public feed, builds the dataset, validates it, compares it with the current `data/series.json` (the guardrails), and writes `data/series.json`. It prints the Markdown report, or writes it to `--report`. `--save-raw DIR` keeps every raw response; `--offline DIR` replays a saved directory without the network. `--output`, `--previous` and `--overrides` change the file paths (useful for experiments).
- `check` validates the committed `data/series.json` against `data/series.schema.json` and checks that every override in `data/overrides.json` resolves. No network.
- `check-patreon` is local only: it checks Special Features matching against your own Patreon feed, read from the macOS Keychain. See the runbook.

Exit codes: 0 on success, 1 on any error (with an `error:` line on stderr), 2 when `check-patreon` has no Keychain entry.

## How `generate` works

Every stage except fetching and writing is a pure function, so each one is tested against committed fixtures.

```
fetch -> parse wiki -> resolve series -> apply overrides -> match public feed
      -> assign IDs -> build dataset -> validate -> guardrails -> report -> write
```

| Module | Stage |
|---|---|
| `fetch.py` | Three `action=parse` requests (Episodes, Blank Check: Special Features, Miniseries), batched `action=query&redirects` lookups for the series link targets (redirect chains are followed to the final page), and the public feed. Sequential, with the `blankie-series-data/<version>` User-Agent, retrying 429 and 5xx with backoff. |
| `wiki.py` | Parses the episode tables with `mwparserfromhell`. Handles `rowspan` on any column and rows that leave out their Guest(s) cell; any other layout raises `WikiParseError`. Bold/italic quotes are removed first, because an unclosed `'''` otherwise swallows the rest of the table. |
| `series.py` | Turns Series-cell links into series. Links are resolved through wiki redirects, so `PodcastFellas` and `Podcastfellas` are one series. A link to the Standalones page (or its "other standalones" section) means no series; any other Standalones section, such as Ben's Choice or Patreon Standalones, is a series of its own. Category and subject come from the Miniseries page; series missing from it get `other`. |
| `overrides.py` | Loads and validates `data/overrides.json`. |
| `matching.py` | Title normalization and wiki-to-feed matching. The rules are defined by [`contracts/matching-vectors.json`](../../contracts/README.md), which the app's Dart matcher must also pass. |
| `pipeline.py` | Applies overrides, matches main-feed episodes to the public feed, assigns stable IDs, and builds the dataset. |
| `schema.py`, `guardrails.py`, `report.py` | Schema validation, the comparison with the published dataset, and the Markdown report. |
| `generate.py` | Wires the stages together for `generate` and `check`. |
| `patreon.py` | `check-patreon`. |

### Stable IDs

An episode's ID is `<air date>:<slug of its title>` when it's first published (`2026-09-27:after-hours`). After that, `assign_ids` carries the ID forward to whichever row it anchors to, trying in order: the wiki number, the Patreon post ID, the matched public GUID, the ID itself (minted from the wiki's title and date), and finally the current title and date. The wiki number and post ID only count when the row's other hints agree, so a renumbered row keeps its own ID instead of taking a neighbour's. So a wiki correction to a title or date never changes the ID, and the app's saved progress survives it. Two rows that would get the same new ID fail the run.

Series IDs are the slug of the wiki page (or Standalones section) name, carried forward by wiki URL.

### Output

`series.json` is written with sorted keys and 2-space indentation, so diffs stay small. When nothing but the timestamp would change, `generatedAt` is kept too: the file is then byte-identical, and the weekly workflow sees no diff.

## Tests and fixtures

- `tests/test_matching_vectors.py` runs every case in `contracts/matching-vectors.json`.
- `tests/test_golden.py` runs `generate` on the fixtures and compares the output with `tests/fixtures/golden/` byte for byte. After an intended change, regenerate with `UPDATE_GOLDEN=1 uv run pytest` and review the diff.
- `tests/test_patreon.py` runs `check-patreon` against a local HTTP server with a fake token, and checks that neither `http` nor the token is ever printed.

Fixtures are wiki excerpts (CC BY-SA, attributed in `tests/fixtures/README.md`), an excerpt of the public feed, and synthetic Patreon-style items. Never add anything from a real Patreon feed.
