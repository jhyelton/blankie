# Tasks

## 1. Shared package `blankie_series`

- [ ] 1.1 Create `packages/blankie_series/` (design D1–D3): `pubspec.yaml` with SDK `^3.13.4`, dependencies `unorm_dart` and `html_unescape`, dev dependencies `test` and `lints`; `analysis_options.yaml` with `lints/recommended.yaml` plus `unawaited_futures` and `discarded_futures`; `lib/blankie_series.dart` exporting `lib/src/`. Commit `pubspec.lock`. Verify: `dart pub get --enforce-lockfile`, `dart analyze --fatal-infos` and `dart format --output=none --set-exit-if-changed .` pass.
- [ ] 1.2 Port `normalize()`, `slug()`, `FeedItem`, `matchOutcome()` and `match()` from `matching.py` (design D2). Add `test/matching_vectors_test.dart`, which loads `../../contracts/matching-vectors.json` and runs every normalization and match case, plus unit tests for each `episode-matching` scenario. Verify: `dart test` passes every case, and changing one expected value in a scratch copy of the file makes the named case fail.
- [ ] 1.3 Implement `pubDateToCalendarDate()` (design D5, `pubDate` row). Verify: tests cover both scenarios in the `episode-matching` requirement "Feed publication dates", plus a missing weekday, a 2-digit year, missing seconds, `-0000`, `UT`, `Z`, `EST`/`PDT`, and an unreadable value (which throws `FormatException`).
- [ ] 1.4 Implement the `SeriesDataset` model and `supportedSchemaVersion` (design D2). Verify: a test round-trips `data/series.json` through `fromJson`/`toJson` with deep equality to the decoded file, absent optional fields stay absent, and a missing required field throws `FormatException` naming the field.
- [ ] 1.5 Add a test that scans `lib/` and fails on any `dart:io` or `package:flutter` import, and a `README.md` for the package: what it holds, that the app and the tool both use it, and that `contracts/` is its source of truth. Verify: `dart test` passes, and the test fails when a scratch `import 'dart:io';` is added to a file in `lib/`.

## 2. Dart tool scaffold, feed and fetch

- [ ] 2.1 Create the Dart package in `tools/series-data/` next to the Python files (design D1, D3, D8): `pubspec.yaml` (name `series_data`, executable `series_data`, path dependency on `blankie_series`, plus `http`, `xml`, `args`, `path` and `json_schema`), `analysis_options.yaml` as in 1.1, `bin/series_data.dart`, and `lib/src/paths.dart`, which finds the repository root with `Isolate.resolvePackageUri`. Commit `pubspec.lock`. Verify: `dart run series_data --help` lists `generate`, `check` and `check-patreon` from both `tools/series-data/` and the repository root (`dart run tools/series-data/bin/series_data.dart --help`), and a test asserts `paths.dart` finds `data/series.schema.json`.
- [ ] 2.2 Copy `tests/fixtures/` to `test/fixtures/` unchanged. Verify: `diff -r tests/fixtures test/fixtures` is empty.
- [ ] 2.3 Port `feed.py` to `feed.dart` with `package:xml` and `pubDateToCalendarDate()`. Error messages never include feed content. Verify: ported tests from `test_generate.py`/`test_fetch.py` that cover feed parsing pass, including a missing guid, a missing title or pubDate, invalid XML and an empty feed.
- [ ] 2.4 Port `fetch.py` to `fetch.dart` (`LiveSource`, `OfflineSource`, redirect-chain following, retries with injected sleep, `Retry-After`, the User-Agent, `save()` in the same file layout) using `package:http` (design D5). Verify: every case in `test_fetch.py` is ported with `MockClient` and passes, and a directory saved by the Python tool's `--save-raw` loads in `OfflineSource`.

## 3. Wikitext parser

- [ ] 3.1 Read `mwparserfromhell`'s `__strip__` rules in `tools/series-data/.venv` and write them as the header comment of `lib/src/wiki.dart` (design D4). Verify: the comment covers wikilinks, external links, tags (visible and invisible), templates, entities, comments and whitespace collapsing.
- [ ] 3.2 Implement the parser in `wiki.dart`: comment and quote removal, tables, cells and attributes, `rowspan`, headings and level-3 sections, inline nodes, the plain text of a cell, and an error for a table nested in a cell (design D4). Port `parseEpisodes`, `parseSpecialFeatures`, `parseMiniseries`, `seriesLinks`, `patreonPostId` and `canonicalNumber`, with the same `WikiParseError` messages. Verify: every case in `test_wiki.py` is ported and passes, plus new tests for a nested table, a `||` cell split, a cell that spans several lines, and a `|` inside `[[a|b]]` that must not be read as an attribute separator.

## 4. Series, overrides and pipeline

- [ ] 4.1 Port `series.py` (`SeriesResolver`, `linkTitles`, wiki URL quoting) and `overrides.py` (loading, validation, `canonicalNumber` targets). Verify: the series and override cases from `test_pipeline.py` and `test_generate.py` are ported and pass, including URL quoting of `'`, `!`, `&` and `#` fragments.
- [ ] 4.2 Port `pipeline.py` (`applyOverrides`, `dropSharedPostIds`, `matchPublicFeed` using `blankie_series`, `assignIds`, `assignSeriesIds`, `buildDataset` through the shared model, `consistencyErrors`), and add the `compareCodePoints` helper for every sort that affects output (design D6). Verify: every case in `test_pipeline.py` is ported and passes, plus a test where `compareCodePoints` and `compareTo` disagree (an emoji against U+FF5E).

## 5. Validation, output and `generate`

- [ ] 5.1 Port `schema.py` with `json_schema` in draft-7 mode, removing `$schema` in memory (design D5), and add the keyword-allowlist test. Verify: both cases in `test_schema.py` are ported with every invalid-document mutation they cover, and the allowlist test fails on a scratch schema that adds `prefixItems`. If `json_schema` can't pass the ported cases, stop and bring the failing cases to the owner before choosing another approach.
- [ ] 5.2 Implement `serialize.dart` (design D6). Verify: `serialize(jsonDecode(file))` reproduces `data/series.json` and `test/fixtures/golden/series.json` byte for byte, and tests cover non-ASCII text, control characters, empty lists and objects, and nested key order.
- [ ] 5.3 Port `guardrails.py`, `report.py` and `generate.py` (`generate`, `check`, `stamp`). Verify: the cases in `test_generate.py` are ported and pass, and `golden_test.dart` reproduces `golden/series.json`, `first-run-report.md` and `diff-report.md` byte for byte **without** regenerating them. An `UPDATE_GOLDEN=1` mode exists for later intended changes.

## 6. CLI and `check-patreon`

- [ ] 6.1 Port `cli.py` with `package:args`: the same subcommands, flags, defaults, `error:`/`warning:`/`pending:`/`ok:` lines and exit codes (0, 1, 2). Verify: ported `test_cli.py`, plus tests running each subcommand through `main()` with temporary files and checking the exit codes and the stderr lines.
- [ ] 6.2 Port `patreon.py` (design D9): the Keychain read via an injected `Process.run`, a fetch that replaces every exception with a URL-free message, `acknowledgedIds`, and `buildReport`. Verify: every case in `test_patreon.py` is ported against a local `HttpServer` with a fake token (success, HTTP 403, connection refused, missing Keychain entry without a network request), and each asserts that neither `http` nor the token appears in stdout or stderr and that no file was written.

## 7. Cutover proof on real data

- [ ] 7.1 Run the D7 comparison: save fresh responses with the Python `generate --save-raw` into the scratchpad, run both tools offline on them with `main`'s `data/series.json` as the previous dataset, and `diff` both `series.json` and both reports. Fix the Dart side until they're identical, except `generatedAt` when the wiki changed since `main`. Then compare `check` output from both tools on the committed data. Verify: record the two empty diffs (commands and result) in the implementation PR description, along with the number of wiki rows parsed.
- [ ] 7.2 Owner: run `uv run series-data check-patreon` and `dart run series_data check-patreon` on your Mac and `diff` the two outputs locally. Don't paste the output anywhere; it contains Patreon titles. Verify: the owner confirms in the PR that the diff was empty and both exit codes matched.

## 8. Switch over and remove Python

- [ ] 8.1 Update `.github/workflows/ci.yml` (design D10): add `packages/**` to the `series-data` filter, and replace the uv steps with `dart-lang/setup-dart` pinned to a commit SHA (`sdk: 3.13.4`, with a comment that the pin follows the app's Flutter version) and the `pub get`/format/analyze/test steps for both packages, then `dart run series_data check`. Verify: on the implementation PR the `series-data` job runs and passes and `ci-ok` is green.
- [ ] 8.2 Update `.github/workflows/series-data-update.yml` to `setup-dart` (same pin) and `dart run series_data generate` with the same flags, and update its header comment. Verify: `actionlint` (or a careful read if it isn't installed) shows no errors, no step references `uv`, and the workflow still uses only `GITHUB_TOKEN`.
- [ ] 8.3 Add Dependabot `pub` entries for `/packages/blankie_series` and `/tools/series-data` (weekly, prefix `build`) and update the file's comment. Verify: the YAML parses, and the entries name directories that contain a `pubspec.yaml`.
- [ ] 8.4 Delete `pyproject.toml`, `uv.lock`, `.python-version`, `src/` and `tests/` from `tools/series-data/`, and the Python block in `.gitignore`. Add `.dart_tool/` to `.gitignore` if it isn't already ignored. Verify: `git ls-files tools/series-data | grep -E '\.py$|uv\.lock|pyproject'` is empty, and `git grep -n -E 'uv run|uv sync|pytest|ruff|setup-uv'` finds nothing outside `openspec/changes/archive/`.
- [ ] 8.5 Rewrite `tools/series-data/README.md` for Dart (setup through Flutter's bundled Dart, commands, the module table, golden updates with `UPDATE_GOLDEN=1 dart test`), and update `test/fixtures/README.md`, `contracts/README.md` (the shared package is the one implementation) and `docs/runbooks/series-data.md` (every `uv run series-data` becomes `dart run series_data`). Verify: every command in the runbook and the README runs as written, except `check-patreon` and `security`, which the owner checks in 7.2.
- [ ] 8.6 Update `CLAUDE.md`: add `packages/` and `tools/series-data/` to Layout, and the tool's and package's `dart test` and `dart run series_data check` commands to Commands. Verify: the listed commands run as written.

## 9. Update the `blankie-v1` plan

- [ ] 9.1 Edit `openspec/changes/blankie-v1/design.md` D1 and D5 as described in this change's design D11: drop `core/matching/`, use `package:blankie_series` for matching, publication dates and the `SeriesDataset` model, and replace the "UTC calendar days" line. Verify: `git grep -n "core/matching\|UTC calendar" openspec/changes/blankie-v1` is empty, and `openspec validate --all --strict` passes.
- [ ] 9.2 Edit `openspec/changes/blankie-v1/tasks.md` tasks 1.2, 4.2, 4.3 and 10.1 as described in design D11, and update its proposal's dependency note to say that `series-data-pipeline` is archived and this change provides the matcher. Verify: no `blankie-v1` task asks for a separate matcher, and `openspec validate --all --strict` passes.

## 10. Final checks

- [ ] 10.1 Run every repository check from a clean clone of the branch: `dart pub get --enforce-lockfile`, `dart analyze --fatal-infos` and `dart test` in both packages, `dart run series_data check`, `openspec validate --all --strict`, `gitleaks dir . --no-banner --config .gitleaks.toml --redact`, and `flutter test` in `app/` (unchanged, but it must still pass). Verify: all pass, and the outputs are summarized in the PR description.
