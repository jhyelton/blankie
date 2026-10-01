# Tasks

## 1. Groundwork

- [ ] 1.1 Run the one-time `dart format lib test` over the spike code as its own commit (design D13). Verify: `dart format --output=none --set-exit-if-changed lib test` exits 0 in `app/`.
- [ ] 1.2 Add the `flutter` job to `.github/workflows/ci.yml` (design D13): a `changes` filter on `app/**`, `contracts/**` and the workflow file; `subosito/flutter-action` pinned by SHA with `flutter-version: 3.47.5`; then `flutter pub get`, the format check, `flutter analyze` and `flutter test` in `app/`. List it under `ci-ok.needs`. Verify: on the implementation PR the `flutter` job runs and passes and `ci-ok` is green; a docs-only PR shows the job as skipped and `ci-ok` still green.
- [ ] 1.3 Add dependencies: `drift`, `drift_flutter`, `flutter_riverpod`, `http`, `xml`, `flutter_secure_storage`, `connectivity_plus`, `file`, `path_provider`; dev: `build_runner`, `drift_dev`. Verify: `flutter pub get` succeeds and `flutter build ios --no-codesign` completes.
- [ ] 1.4 Create the `lib/` layout from design D1 (`core/`, `data/`, `platform/`, `playback/`, `downloads/`, `refresh/`, `ui/`, `providers.dart`). Verify: `flutter analyze` passes.
- [ ] 1.5 Add the `log()` helper with `redactUrls()`, and a test that fails if `print(` or `debugPrint(` appears in `lib/` outside the helper (design D8). Move the spike's `debugPrint` calls onto `log()`. Add `installErrorLogging()`, which sets `FlutterError.onError` and `PlatformDispatcher.instance.onError` to report through `log()`, and call it first in `main()`. Verify: `flutter test` passes; the redaction test turns `https://x.invalid/a?token=1` into `<url>`; and a test shows an uncaught error whose message holds a URL is logged with `<url>` instead.

## 2. Platform adapters (test seams)

- [ ] 2.1 Add `PlayerPort` and `JustAudioPlayerPort`, covering what the handler uses from `AudioPlayer`, plus a `FakePlayerPort` in `test/fakes/` that can be scripted to fail loads (design D13). Verify: `flutter analyze` passes and a smoke test drives the fake through load, play, pause and seek.
- [ ] 2.2 Add `DownloaderPort` and `FileDownloaderPort` (`start` with `doRescheduleKilledTasks: true`, `enqueue`, `cancelTaskWithId`, `updates`, `recordForId`, `deleteRecordWithId`, holding-queue and `resourceTimeout` config), plus a `FakeDownloaderPort` that can replay updates, including late ones after a cancel. Verify: a smoke test enqueues on the fake and receives a scripted `complete` update.
- [ ] 2.3 Add the `BackupExclusion` interface and its iOS platform channel: Dart calls a Swift handler in `AppDelegate` that sets `isExcludedFromBackup` on a directory (design D3). Verify: a unit test with a mocked method channel checks the call and arguments, and `flutter build ios --no-codesign` completes. The exclusion flag can't be read back with `devicectl`, so there is no on-device check.
- [ ] 2.4 Add a `Connectivity` adapter over `connectivity_plus` that exposes online/offline and Wi-Fi/cellular, plus a fake. Verify: `flutter analyze` passes and the fake is used by a smoke test.

## 3. Storage

- [ ] 3.1 Define the drift database `blankie.sqlite` at schema version 1 with the `episode_state`, `relisten_runs`, `downloads`, `feed_item_links` and `settings` tables (design D3, D4, D10, D11). Generate the code, run `dart format`, and commit the generated files. Verify: a test opens an in-memory database and round-trips one row per table, and `flutter analyze` passes.
- [ ] 3.2 Add a drift `PositionStore` keyed by episode ID, alongside the spike's `SharedPreferencesPositionStore`, which 9.1 deletes. Port the spike's position tests (save, load, overwrite, missing key). Verify: `flutter test` passes the ported tests and `flutter analyze` passes.
- [ ] 3.3 Add a settings repository for speed, allow cellular, remove played downloads (on by default), now-playing episode and context, Patreon connected date, and last successful refresh. Verify: unit tests cover defaults and persistence across database reopen.
- [ ] 3.4 Add the Patreon URL store over `flutter_secure_storage` with accessibility `first_unlock_this_device`, plus a fake (design D8). Verify: a unit test with the fake covers save, read and delete; the adapter passes the `first_unlock_this_device` option (checked in the test).
- [ ] 3.5 Create `feed-cache/` and `episodes/` in Application Support at startup and apply `BackupExclusion` to them and to the plugin's `backgroundDownloaderTaskRecords/`, `backgroundDownloaderResumeData/` and `backgroundDownloaderPausedTasks/` (design D3). Verify: a unit test with `MemoryFileSystem` and a fake `BackupExclusion` checks that all five paths are created and excluded.

## 4. Feeds, dataset and catalog (pure core)

- [ ] 4.1 Implement the RSS parser in `core/feeds/` (design D7), with synthetic fixtures for the public feed and a Patreon-shaped feed using `https://example.invalid/…` URLs. Verify: tests cover tab characters in titles, `enclosure length="0"`, missing `itunes:duration`, and channel-image extraction; `gitleaks dir . --no-banner --config .gitleaks.toml --redact` reports nothing.
- [ ] 4.2 Implement the `SeriesDataset` model and the schema-version check (design D6), with a small synthetic `test/fixtures/series.json` that follows `series-data`'s schema. Verify: tests cover loading the fixture and rejecting `schemaVersion: 2`.
- [ ] 4.3 Implement `normalize()` and `match()` in `core/matching/` per `episode-matching` (design D5). Verify: unit tests cover every scenario in that spec (ad-free suffix, punctuation and tab variants, markup, distinct editions, guest suffix, leading article, date window, ambiguity, hint precedence). The shared test cases are added in 10.1.
- [ ] 4.4 Implement `CatalogBuilder`: hint matching, then per-feed `match()` for each dataset episode, items claimed twice left unmatched, pairing of unmatched public and Patreon items, IDs for unmatched items, groups, hidden episodes and series, and preferred source (design D4). Verify: unit tests cover every `episode-catalog` scenario except dataset loading, including "New episode in both feeds" and "Public and ad-free copies merge" for an episode with no GUID hints (proving the two copies don't tie).

## 5. Refresh and feed subscription

- [ ] 5.1 Implement the feed fetcher over `package:http`, returning a sanitized `FeedError(kind, status?)` (design D7). Verify: tests with `MockClient` for HTTP 403, a socket error and invalid XML show that neither the error nor its `toString()` contains `http`.
- [ ] 5.2 Implement the dataset loader: cached copy, then bundled asset; fetch, check schema, cache, and set the update-needed flag (design D6). Verify: tests cover "First launch offline" and "Unsupported schema version" from `episode-catalog`.
- [ ] 5.3 Implement `RefreshService.refresh()`: fetch in parallel, fall back to cache per source, write the cache only after a successful parse, run `CatalogBuilder` in `Isolate.run`, and record the last-success time and the offline flag. Make it single-flight, triggered by start, `resumed` and pull (design D7). Verify: tests show two concurrent calls share one fetch, and a failed fetch keeps the cached catalog with the offline flag set (`feed-subscription` "Offline launch"). Tests with `MockClient` also cover "First launch" (the public feed with no setup) and "New episode appears".
- [ ] 5.4 Record `feed_item_links` on each build and move listening state when an unmatched item gets a new ID (a dataset ID, or a paired `public:` ID): played if either is played, position from the newer `updatedAt` (design D4). Verify: tests cover "Dataset catches up", including a pair of unsorted public and Patreon items that both move to one dataset episode.
- [ ] 5.5 Add the `feedGeneration` guard to `RefreshService` and implement connecting Patreon: an `https` check, fetch and parse, save to the Keychain only on success, increment the generation, then run a new refresh (design D7, D8). Verify: tests cover the "Valid Patreon URL" and "Invalid URL" scenarios, that error messages contain no `http`, and that connecting while a refresh is in flight ends with a catalog that includes Patreon.
- [ ] 5.6 Implement disconnecting Patreon in the design D8 order: increment the generation, delete the Keychain item and `feed-cache/patreon.xml`, then rebuild the catalog. Download cleanup is added in 8.8. Verify: tests cover "Disconnect" (Patreon-only episodes gone, listening state kept), "Reconnect keeps history", and a disconnect during an in-flight refresh that leaves no `patreon.xml` and no Patreon episodes once that refresh finishes.

## 6. Listening state

- [ ] 6.1 Implement the played threshold (on crossing only), the position reset to 0 when an episode finishes, manual played/unplayed (keeping position), "Mark series as played/unplayed" and "Mark everything before this as played" as single transactions (design D10). Verify: tests cover every `listening-state` scenario except re-listen runs, including "State follows the episode, not the feed" and "Playing a finished episode again".
- [ ] 6.2 Implement re-listen runs: snapshot at start, advance only when the next episode finishes, skip unavailable episodes, end early, complete, and one run per series (design D10). Verify: tests cover every re-listen scenario in `listening-state`, including "Episode outside the run order".
- [ ] 6.3 Implement the pure `chooseNext()` (design D9). Verify: tests cover every `listening-session` auto-advance scenario, including "Multi-series episode" and "Started from a group".

## 7. Playback

- [ ] 7.1 Implement `BlankieAudioHandler` over `PlayerPort`. Port the spike behavior (session, interruptions, skips, position saves, stream-error reload, `_loaded` guard). Add `load(episodeId, context)` with the downloaded-file-first source choice, `MediaItem.id` set to the episode ID, and `artUri` set to the public channel image (design D8, D9). Verify: regression tests 1 (a failed initial load never overwrites the saved position) and 3 (a local-file failure falls back to the stream at the same position) pass with `FakePlayerPort`. A test also shows that a downloaded public copy plays from the file after Patreon is connected (the first half of "Downloaded before Patreon was connected"; the rest is in 8.4).
- [ ] 7.2 Wire the played threshold, run advance and auto-advance on completion (design D9): on completion stop the save timer and save 0, then await the single-flight mark-and-advance before `chooseNext`. Include the offline stop with the "Next episode needs a connection" message. Verify: tests with the fakes cover "Next unplayed in series", "Re-listen order" and "Offline, next not downloaded"; a re-listen of episodes that were all played to their end plays each from 0 and advances the run once per episode; and `chooseNext` never returns the episode that just finished.
- [ ] 7.3 Apply speed from settings on every load and immediately on change, and publish it in `PlaybackState` (design D9). Verify: tests cover "Speed persists" and "Change during playback".
- [ ] 7.4 Restore the saved now-playing episode and context at launch without autoplay. Verify: a test reopens the handler and finds the same episode loaded at its saved position.

## 8. Downloads

- [ ] 8.1 Add per-episode `DownloadState` and `reconcile` in `core/downloads/`, alongside the spike's `download_state.dart`, which 9.1 deletes. Cover every plugin status in reconcile (design D11). Add the pure FIFO scheduler. Verify: the ported spike `download_state` tests pass, new tests map `paused`, `canceled`, `failed` and `notFound` to resubmit, scheduler tests cover ordering, and `flutter analyze` passes.
- [ ] 8.2 Implement `DownloadManager` on `DownloaderPort`: the `downloads` table, holding queue `(2, null, null)`, `resourceTimeout` of 7 days, submission in `queuedAt` order with `retries: 0`, `allowPause: false`, `requiresWiFi` and a task ID per attempt, `<feed>-<guid>.mp3.part` naming, a single-flight rename, our own 3 retries as fresh attempts, deleting the plugin record after completion, and redacted errors (design D11). Verify: regression tests 2 (concurrent completions rename once and end `downloaded`) and 4 (two quick `download()` calls enqueue once) pass, plus "Download one episode", "Large series queued", a failure retried 3 times as new attempts before `failed`, and `resume()` never called.
- [ ] 8.3 Implement startup reconcile against each row's current attempt, resubmission, and the orphan sweep (design D11). Verify: tests with `MemoryFileSystem` cover "App restarted mid-queue", a force-quit leaving `paused` and `canceled` records that are resubmitted in queue order, and the sweep deleting a spike-style `<guid>.mp3` while keeping an active `.part`.
- [ ] 8.4 Implement cancel, cancel all, retry and manual "Remove download" (design D11). Verify: tests cover "Cancel" (partial file removed, next starts), a failed row returning to the end of the queue on retry, removing a download keeps listening state, removing the loaded episode's file reloads it from the stream at the same position, and "Downloaded before Patreon was connected" (remove, then download again, uses the Patreon source).
- [ ] 8.5 On a change to the cellular setting, cancel active tasks and resubmit them with the new `requiresWiFi` flag (design D11). Verify: a test shows the active tasks are cancelled and re-enqueued as new attempts with the new flag, a late `canceled` update for the old attempt leaves the new one untouched, and the plugin's global `requireWiFi` is never called.
- [ ] 8.6 Implement "Download series" for both unplayed and re-listen runs. Verify: tests cover "Queue unplayed episodes" and "Queue a re-listen".
- [ ] 8.7 Implement the auto-remove listener (design D11). Verify: tests cover "Auto-remove after playing", "Still playing" (deletion waits until the episode is unloaded), "Re-listen moves past a download", "Setting off", and an episode ahead in a run that is never deleted.
- [ ] 8.8 Connect the Patreon disconnect to download cleanup: cancel and delete downloads whose episode left the catalog, only on an explicit disconnect (design D8). Verify: a test shows a Patreon-only download deleted on disconnect, and kept when a Patreon refresh merely fails.

## 9. App shell and screens

- [ ] 9.1 Rewrite `main.dart`: `ProviderScope`, `AudioService.init` with `BlankieAudioHandler`, and the startup order: error logging, directories and exclusion, database, a catalog built from the cached dataset and feeds, download reconcile (which needs that catalog's enclosure URLs), then refresh. Delete `spike_screen.dart`, `episode.dart`, `spike_audio_handler.dart`, `episode_downloader.dart`, the spike's `download_state.dart`, the `shared_preferences` store and its dependencies. Update the "App architecture" section of `CLAUDE.md` to describe the v1 layout. Verify: `flutter analyze` and `flutter test` pass, `flutter build ios --no-codesign` completes, and `grep -r shared_preferences app/lib` finds nothing.
- [ ] 9.2 Build the home screen: ordering, the unplayed or re-listen badge, the "Unplayed only" filter, pull-to-refresh, last-refreshed time, and the offline and update-needed banners (design D12). Verify: widget tests cover "Airing series on top", "Unplayed badge", "Re-listen shown instead of unplayed" and "Filter on".
- [ ] 9.3 Build series and group detail with the series menu and the episode action sheet, including the confirmation for "Mark everything before this as played". Verify: widget tests cover "Later release in order", "Episode in several series", and confirm vs "Cancelled".
- [ ] 9.4 Build the mini-player and the player sheet with seek, skips and a 0.8–2.0× speed control in 0.1 steps. Verify: a widget test shows the speed control offers exactly 13 values and calls the handler on change.
- [ ] 9.5 Build the downloads screen: queue order, determinate or indeterminate progress, "Waiting for Wi-Fi", cancel, cancel all, retry. Verify: widget tests cover each row state.
- [ ] 9.6 Build settings: Patreon connect and disconnect with the masked identifier, allow cellular, remove played downloads, and About with the dataset's attribution (design D8, D12). Verify: widget tests cover "Viewing settings" (the rendered text contains no URL) and attribution showing source, CC BY-SA and the license link.

## 10. Real series data (needs `series-data-pipeline` applied)

- [ ] 10.1 Add `test/matching_vectors_test.dart`, which loads `../contracts/matching-vectors.json` and runs every case (design D5). Fix any differences in `core/matching/`. Verify: `flutter test` passes, and the CI `flutter` job runs when `contracts/**` changes.
- [ ] 10.2 Copy `data/series.json` to `app/assets/series.json` and register it as an asset (design D6). Verify: a test loads the bundled asset and finds a supported schema version with at least one series.

## 11. On-device verification and review

- [ ] 11.1 Install a release build over the spike app (`flutter run --release -d <udid>`) and record each check as PASS/FAIL in a new `docs/device-checks/blankie-v1.md` (design D14):
  - the spike's `<guid>.mp3` is gone after first launch
  - the public catalog appears grouped by series
  - connecting Patreon merges the ad-free copies, and the lock screen shows no URL
  - locked auto-advance into a streamed next episode works, and the lock screen then shows the new episode. If it fails, implement the design D9 playlist fallback and re-check.
  - a 3-episode series queue, started with playback paused and the phone then locked (so the app is suspended): note how it progresses; PASS if no more than 2 are ever active and all 3 finish with at most one app open
  - force-quitting the app with downloads active and queued, then reopening it: every download restarts and the queue finishes
  - downloads wait on cellular and resume on Wi-Fi
  - offline launch shows the cached catalog
  - the spike's R1–R5 checks pass

  Verify: every listed check has a status, and none is FAIL.
- [ ] 11.2 Re-install over v1 and check that listening state, re-listen runs, downloads and the Patreon connection survive. Update `docs/runbooks/ios-device-install.md` section 4 with what survives. Verify: the result is recorded in `docs/device-checks/blankie-v1.md`, and the runbook matches it.
- [ ] 11.3 Run the pre-PR review with a subagent, as `CLAUDE.md` describes (base `main`, this branch, `openspec/changes/blankie-v1/`). Verify each finding, then agree fixes with the owner before pushing. Verify: each finding has a valid, invalid or overstated verdict, and the agreed fixes are committed with `flutter test` passing.
