# Design

## Context

- **What exists.** `tools/series-data/` is about 2,100 lines of Python in 14 modules, with about 1,900 lines of pytest tests. The stages are pure functions around a thin I/O shell (`series-data-pipeline` design D3):

  ```
  fetch -> parse wiki -> resolve series -> apply overrides -> match public feed
        -> assign IDs -> build dataset -> validate -> guardrails -> report -> write
  ```

  Golden tests (`tests/test_golden.py`) compare `generate`'s output on committed fixtures with `tests/fixtures/golden/` byte for byte. The same commands run in two places: the CI job `series-data` (uv, ruff, pytest, `series-data check`) and the weekly `series-data update` workflow (`series-data generate`).
- **Python libraries the port has to replace:**
  - `mwparserfromhell`: wikitext tables, links, tags and headings, and `strip_code()` for a cell's plain text.
  - `jsonschema` (draft 2020-12): validation against `data/series.schema.json`.
  - `httpx`: HTTP with retries.
  - stdlib `xml.etree` for RSS, `email.utils.parsedate_to_datetime` for `pubDate`, `html.unescape`, and `unicodedata.normalize("NFKD")`.
- **What Dart lacks.** The Dart core libraries have no Unicode normalization, no HTML entity decoding, no RFC 822 date parser that keeps the stated offset (`HttpDate` only handles GMT), and no wikitext parser on pub.dev worth depending on.
- **`json_schema` on pub.dev** (5.2.2) supports drafts up to 7, not 2020-12. `series.schema.json` uses only keywords that mean the same thing in draft 7: `type`, `const`, `enum`, `pattern`, `format`, `minLength`, `required`, `properties`, `additionalProperties`, `propertyNames`, `items`, `uniqueItems`, and `$ref` to JSON-pointer locations under `$defs`.
- **`blankie-v1`** is planned but not applied. Its design D1 puts `normalize()` and `match()` in `app/lib/core/matching/`, and the `SeriesDataset` model in `app/lib/core/catalog/`. Its D5 compares dates "in UTC calendar days, the same as the Python tool". That is not what the Python tool does: `feed.py` takes the calendar date in the offset the feed states, as `contracts/README.md` says.
- **Toolchain.** Flutter 3.47.5, which ships Dart 3.13.4, is installed locally and pinned by `blankie-v1` for CI.

## Goals / Non-Goals

**Goals:**
- One language in the repository, and one implementation of the matching rules (`episode-matching`, as modified here).
- No visible change. `series.json`, the report, the CLI commands and flags, the exit codes and the runbook procedures stay the same. The cutover (D7) proves this on real data before Python is removed.
- The shared package can be imported by a Flutter app, so it uses no Flutter and no `dart:io`.

**Non-Goals:**
- Changing any rule, guardrail, override op or report section. A bug found during the port is fixed in Python first, or written down and fixed in a later change, so that D7 still compares like with like.
- Moving the app to the shared package. `blankie-v1` does that when it is applied. This change only updates that plan.
- A compiled binary (`dart compile exe`). `dart run` is fast enough for a weekly job and for local use.
- A pub workspace (D3).

## Decisions

### D1. Layout

```
packages/blankie_series/        pure Dart, shared by the tool and the app
  lib/blankie_series.dart       exports the public API
  lib/src/normalize.dart        normalize(), slug()
  lib/src/match.dart            FeedItem, MatchOutcome, matchOutcome(), match()
  lib/src/pub_date.dart         pubDateToCalendarDate()
  lib/src/dataset.dart          SeriesDataset, Series, DatasetEpisode, Hints, Source,
                                supportedSchemaVersion; fromJson / toJson
  test/                         matching_vectors_test.dart, pub_date_test.dart, dataset_test.dart
tools/series-data/              Dart package "series_data" (the CLI)
  bin/series_data.dart
  lib/src/                      cli, fetch, feed, wiki, series, overrides, pipeline,
                                guardrails, report, schema, serialize, patreon, paths
  test/                         one test file per module, golden_test.dart
  test/fixtures/                moved unchanged from tests/fixtures/
```

`tools/series-data/` keeps its path, so links from the runbook, the schema's `description` and the workflows stay valid. The Dart package name uses an underscore (`series_data`) because pub requires one; the directory name doesn't have to match.

`contracts/` stays at the repository root. It is the language-neutral contract, and `matching_vectors_test.dart` in the shared package loads it from `../../contracts/`.

### D2. What goes into `blankie_series`

Only the rules both sides need:

| In the package | Why it's shared |
|---|---|
| `normalize()`, `slug()` | Matching, and the tool's IDs (an ID's slug is the normalized title). |
| `FeedItem` (guid, title, publication date), `matchOutcome()` / `match()` | The `episode-matching` rules. The tool matches wiki rows to the public feed, and `check-patreon` matches to the Patreon feed. The app does both on the device. |
| `pubDateToCalendarDate()` | The new `episode-matching` requirement "Feed publication dates". Both feed readers must turn `pubDate` into a date the same way, or a late-evening release falls outside the 3-day window on one side only. |
| `SeriesDataset` model, `supportedSchemaVersion` | The tool writes `series.json` and the app reads it. One model means one definition of the shape. `fromJson` rejects missing required fields with a `FormatException`. `toJson` leaves out absent optional fields (`wikiNumber` and the three hints), as the Python tool does. |

Kept out of the package:
- The RSS parsers. The tool needs three fields. The app's parser in `blankie-v1` also needs the enclosure URL and duration, and has Patreon-specific handling. Each reads its own items and builds a `FeedItem` to match against.
- JSON Schema validation. Only the tool validates. The app checks `schemaVersion` (`blankie-v1` D6), so it doesn't need `json_schema`.
- The `series.json` serializer (D6). Only the tool writes the file.

Dependencies are `unorm_dart` (NFKD, pure Dart, Unicode 17) and `html_unescape` (every HTML5 named entity plus numeric references, like Python's `html.unescape`). The analyzer has no rule that bans an import, so a test scans the package's `lib/` and fails on any `dart:io` or `package:flutter` import.

- *Alternative:* put the whole pipeline in the package. Rejected: the app would pull in the wikitext parser and the overrides logic, which it never runs.

### D3. Path dependencies, one lockfile per package, no workspace

`tools/series-data/pubspec.yaml` depends on `blankie_series: { path: ../../packages/blankie_series }`. `blankie-v1` adds the same dependency with `path: ../packages/blankie_series`. Each package commits its `pubspec.lock`, and CI runs `dart pub get --enforce-lockfile`, so a dependency change always shows up in a PR diff (the same reason the Python tool committed `uv.lock`).

- *Alternative:* a pub workspace (a root `pubspec.yaml` listing `app`, the tool and the package, with one shared lockfile). Rejected for now: it moves `app/pubspec.lock` to the repository root and changes how `flutter pub get` behaves in `app/`, which is extra mobile tooling to learn for little gain with only three packages. It can be adopted later without changing code.

### D4. A wikitext parser for the layouts the tool accepts

There is no maintained Dart equivalent of `mwparserfromhell`. The tool only ever read a small part of wikitext, so `wiki.dart` parses exactly that part and raises `WikiParseError` for anything outside it. That follows the "fail rather than guess" rule from `series-data-pipeline` D14.

- **Before parsing:** remove HTML comments (`<!-- … -->`; upcoming episodes are hidden in them), then remove runs of two or more `'` (bold and italic), as `wiki.py` does.
- **Tables:** line-based. `{|` opens a table and `|}` closes it. `|-` starts a row, `|+` is a caption (ignored). A line starting with `!` holds header cells, split on `!!` and `||`. A line starting with `|` holds data cells, split on `||`. A cell continues onto following lines until the next cell, row or table line. A cell's attributes are the text before its first `|` that isn't inside `[[…]]`, `[…]`, `{{…}}` or a tag. Only `rowspan` is read. A table inside a table cell raises an error, because the real pages have none (D7 checks this).
- **Headings:** `== X ==` lines. A level-3 section runs until the next heading of level 3 or less, like `get_sections(levels=[3])`.
- **Inline nodes in a cell:** wikilinks `[[target#fragment|label]]`, external links `[url label]` and bare URLs, tags (`<x …>…</x>`, `<x/>`, and void `<br>`), templates `{{…}}`, and HTML entities.
- **Plain text of a cell** follows `wiki.py`'s `_text()`, which is built on `mwparserfromhell`'s `strip_code(normalize=True, collapse=True)`:
  - `<ref>` and `<sup>` are dropped with their contents, and `<br>` becomes a space
  - other tags keep their contents, except `mwparserfromhell`'s invisible tags (such as `ref` and `gallery`), which are dropped
  - a wikilink becomes its label, or its target when it has no label
  - a bracketed external link becomes its label, or nothing when it has none; a bare URL stays as text
  - templates are dropped and entities are decoded
  - whitespace collapses to single spaces

  The implementer reads these rules from the installed `mwparserfromhell` source (`.venv/…/mwparserfromhell/nodes/*.py`, the `__strip__` methods) before Python is removed, and lists them in a comment at the top of `wiki.dart`.

The parser is about 300 lines. The Python parser tests, the golden fixtures and the real-data cutover (D7) cover it.

- *Alternative:* fetch rendered HTML (`action=parse&prop=text`) and use `package:html`. Rejected: it changes the inputs. The cutover could then no longer compare like with like, and rendered tables lose the `rowspan` structure the parser depends on (MediaWiki expands it differently in the output).
- *Alternative:* keep a Python parser and call it from Dart. Rejected, because removing Python is the point of the change.

### D5. Other library choices

| Need | Dart package | Notes |
|---|---|---|
| HTTP | `http` | Retries, backoff and `Retry-After` port directly from `fetch.py`, with `sleep` injected for tests. `MockClient` from `package:http/testing.dart` replaces the Python fetch tests' fake transport. |
| RSS | `xml` | Already planned for the app. Reads `channel/item/{guid,title,pubDate}`, as `feed.py` does. |
| `pubDate` | none (in `blankie_series`) | A small RFC 822 parser. It handles an optional weekday, 2- and 4-digit years, optional seconds, numeric offsets, `GMT`/`UT`/`Z`, the US zone names that `email.utils` knows, and `-0000`. It returns the calendar date in the stated offset. |
| CLI | `args` | The same subcommands, flags and defaults as `cli.py`. |
| JSON Schema | `json_schema` | Compiled in draft-7 mode. The `$schema` key is removed from the in-memory copy so the library doesn't reject the 2020-12 URI; the file on disk doesn't change. A test asserts that the schema uses only keywords from an allowlist that mean the same in both drafts. If the schema later needs a 2020-12-only keyword, that test fails instead of the keyword being silently ignored. |
| Paths | `path` | |
| Lints | `lints` (recommended) plus `unawaited_futures` and `discarded_futures` | The same async rules as the app (`CLAUDE.md`). |

### D6. Byte-identical output

`serialize.dart` reproduces `json.dumps(indent=2, sort_keys=True, ensure_ascii=False) + "\n"`:
- keys sorted at every level
- 2-space indentation, `": "` between key and value, and `[]`/`{}` for empty collections
- non-ASCII characters written as themselves
- control characters escaped the same way Python does, and a trailing newline

Python compares strings by code point, while Dart's `compareTo` compares UTF-16 code units. The two differ only for characters above U+FFFF, such as emoji. So every sort that affects output (JSON keys, report lists, the redirect batch order) uses one `compareCodePoints` helper. Other Python-isms to match, each with a test:
- `str.split()` with no arguments, which splits on Unicode whitespace
- `str.isdigit()` in `rowspan`
- `\d` in Python `re`, which matches any Unicode digit; Dart's matches only ASCII. None of the tool's inputs use non-ASCII digits, so `\d` stays, and the cutover would catch a difference.
- `strftime("%Y-%m-%dT%H:%M:%SZ")` for `generatedAt`

The golden files in `test/fixtures/golden/` are reused unchanged. If the Dart golden test passes without regenerating them, the port matches Python on the fixtures.

### D7. Cutover proof on real data

Python stays in the tree until the Dart tool matches it on real data:

1. Save fresh responses with the Python tool: `uv run series-data generate --save-raw <dir> --output /tmp/py.json --report /tmp/py.md`.
2. Run the Dart tool on the same responses: `dart run series_data generate --offline <dir> --output /tmp/dart.json --report /tmp/dart.md`. Both runs use `main`'s `data/series.json` as `--previous`.
3. `diff` both outputs. They must be identical, except `generatedAt` when the wiki changed since `main` (the two runs then stamp different times).
4. Run `check` with both tools on the committed data, and compare the output.
5. The owner runs `check-patreon` with both tools on their Mac and compares the two outputs locally with `diff`. The output contains Patreon episode titles, so it stays on the Mac and is never pasted into a PR.

Then Python is deleted, in the same PR. The saved responses are public wiki and feed data. They go in the scratchpad, not the repository.

### D8. Running the tool, and finding the repository

- **Commands.** From `tools/series-data/`, run `dart run series_data <generate|check|check-patreon> [flags]`. `pubspec.yaml` declares the `series_data` executable. The runbook replaces `uv run series-data` with `dart run series_data` and keeps every flag. `dart pub get` works like `uv sync`.
- **Repository paths.** `paths.dart` finds the repository root from the package's own location (`Isolate.resolvePackageUri` on `package:series_data/`, then up three directories). Like the Python tool, it then works from any working directory.

### D9. `check-patreon` in Dart keeps its redaction guarantees

- The Keychain is read with `Process.run('security', ['find-generic-password', '-s', 'blankie-patreon-feed', '-w'])`, with the runner injected for tests. A missing `security` binary or a non-zero exit means "no URL" (exit 2, no network request).
- `package:http`'s `ClientException` includes the request URI in its `toString()`. So the fetch catches **every** exception, and rethrows one whose message has only the exception type or the HTTP status. The URL is never put in an exception, a log line or a file.
- The test runs the command against a local `HttpServer` (`dart:io`, test only) with a fake-token URL, for success, a 403 and a connection refusal. It captures stdout and stderr and asserts that neither `http` nor the token appears, and that no file was written. This is a port of `test_patreon.py`.

### D10. CI and the weekly workflow

- **`ci.yml`, `changes` job:** the `series-data` filter adds `packages/**`.
- **`ci.yml`, `series-data` job:** `dart-lang/setup-dart` pinned to a commit SHA, with `sdk: 3.13.4`. Then, in both `packages/blankie_series` and `tools/series-data`:
  - `dart pub get --enforce-lockfile`
  - `dart format --output=none --set-exit-if-changed .`
  - `dart analyze --fatal-infos`
  - `dart test`

  Finally `dart run series_data check` in the tool. The job keeps its name, so `ci-ok.needs` doesn't change.
- **`series-data-update.yml`:** `setup-uv` and `uv sync` become `setup-dart` and `dart pub get --enforce-lockfile`, and `uv run series-data generate` becomes `dart run series_data generate`, with the same flags. The rest of the workflow is unchanged.
- **Dependabot:** add `pub` entries for `/packages/blankie_series` and `/tools/series-data`, weekly, with commit prefix `build`. The existing comment in `dependabot.yml` already expects `pub` entries.
- **SDK pin:** both workflows pin Dart 3.13.4, the Dart that ships with the app's Flutter 3.47.5. When `blankie-v1` or a later change bumps Flutter, it bumps these pins too. A comment next to each pin says so.

### D11. Updating the `blankie-v1` plan

This change edits `openspec/changes/blankie-v1/` (planning artifacts only, no app code):
- **D1 layout:** remove `core/matching/`. `core/catalog/` keeps `Catalog` and `CatalogBuilder`, but the `SeriesDataset` model comes from `package:blankie_series`. Add the path dependency.
- **D5:** matching comes from `blankie_series`, which passes the shared test cases in its own tests. The app's tests cover how `CatalogBuilder` uses it, not the rules themselves. Replace "Dates compare in UTC calendar days" with the `episode-matching` requirement "Feed publication dates", via `pubDateToCalendarDate()`.
- **Tasks:**
  - 1.2: the `flutter` job's filter adds `packages/**`.
  - 4.2: build `SeriesDataset` handling on the package's model, keeping the synthetic fixture and the `schemaVersion: 2` rejection test.
  - 4.3: becomes "use `blankie_series` in `core/feeds` and `CatalogBuilder`".
  - 10.1: becomes "confirm the package's vector tests run in CI when `contracts/**` changes".

## Risks / Trade-offs

- **[Risk] The hand-written wikitext parser differs from `mwparserfromhell` on real pages.** → *Mitigation:* the parser raises an error on anything it doesn't recognize, instead of guessing. The golden fixtures cover every known irregularity. D7 compares full real-data output before Python is removed. After that, the guardrails catch drift, as before.
- **[Risk] `unorm_dart` or `html_unescape` behaves differently from Python's `unicodedata` or `html.unescape`** on some input. → *Mitigation:* the shared test cases and D7. `html_unescape` hasn't been updated in 5 years, but the HTML5 entity list is frozen, so that's acceptable. *Trade-off:* the app also bundles these two packages. They are pure Dart and small.
- **[Risk] `json_schema` in draft-7 mode misses a 2020-12 meaning.** → *Mitigation:* the keyword allowlist test (D5), plus a port of `test_schema.py`'s invalid-document cases.
- **[Risk] The weekly bot PR can't be compared with Python after the cutover.** → *Accepted:* D7 is the comparison. Later regressions show up as unexpected entries in the weekly report, and the guardrails still apply.
- **[Trade-off] The tool and the package pin Dart separately from `app/`.** They are separate packages with separate lockfiles (D3), so their dependency versions can drift from the app's. A matching dependency used by both (`unorm_dart`, `html_unescape`) resolves to whatever version each lockfile holds. Dependabot keeps both moving.
- **[Trade-off] `blankie-v1`'s plan changes before it starts.** This is cheaper than changing it after the app's matcher is written. It is also why this change goes first.

## Migration Plan

1. Build the package and the Dart tool next to the Python tool. Port the tests and pass the golden files unchanged.
2. Run the D7 cutover on fresh real data, including the owner's `check-patreon` comparison.
3. In the same PR: switch both workflows and Dependabot, delete the Python package, and update the docs and the `blankie-v1` artifacts.
4. After merging, trigger `series-data update` by hand (without the acceptance option) and confirm it's green. If it opens a PR, the report lists only real wiki edits since the last run. This step isn't in `tasks.md`: it can only run after the PR that holds the archive commit has merged. If it fails, roll back.

**Rollback:** revert the implementation PR. Python, uv and the old workflows come back unchanged, and `series.json` is unaffected either way.
