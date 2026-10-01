# Design

## Context

- **What exists.** `app/` is the `audio-spike` proof of concept: one hard-coded episode (`episode.dart`), a disposable `spike_screen.dart`, and the plumbing v1 builds on:
  - `SpikeAudioHandler`: an `audio_service` handler around `just_audio`, with a speech `audio_session`.
  - `PositionStore`: `shared_preferences`, keyed by GUID.
  - `EpisodeDownloader`: `background_downloader`, a `.part` file renamed on completion, `allowPause: false`, `retries: 3`.
  - `download_state.dart`: pure and unit-tested, including `reconcile`.

  The spike recorded GO on an iPhone 12 Pro (`docs/spikes/audio-spike-results.md`). The async state rules in `CLAUDE.md` came from its review and apply to all of the code below.
- **What the spike proved about data.** Positions (`shared_preferences`) and files in Application Support survive a re-install over the existing app. Deleting the app erases them. Behavior at a real 7-day expiry is still to be checked by `ios-reinstall-verification`.
- **`background_downloader` 9.6.3, as read in `~/.pub-cache`:**
  - Its concurrency limit, `Config.holdingQueue`, is an in-memory array in native code (`HoldingQueue.swift`). It's lost if iOS terminates the app.
  - Changing Wi-Fi rules with the global `requireWiFi(..., rescheduleRunningTasks: true)` pauses running downloads with `cancelByProducingResumeData` (`WiFi.swift`). That uses the resume data `allowPause: false` exists to avoid, because it holds the expiring signed URL.
  - A per-task `requiresWiFi` sets `allowsCellularAccess = false`. iOS then holds the transfer until Wi-Fi returns, the same "wait instead of fail" behavior the spike saw on network loss.
  - It keeps task records, which include the task URL, under Application Support (`backgroundDownloaderTaskRecords`).
  - It can exclude completed files from iCloud backup (`Config.excludeFromCloudBackup`).
- **Upstream inputs.** `series-data-pipeline` is not applied yet. v1 consumes its `data/series.json` (schema version 1, shape in that change's design D5) and `contracts/matching-vectors.json`.
- **Requirements** are in `specs/`. Motivation and scope are in `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Replace the spike with a structure where every rule in the specs lives in **pure Dart that is unit-tested without plugins**. Examples: catalog building, matching, auto-advance choice, re-listen progress, queue scheduling, download reconciliation. Plugins sit behind thin adapters.
- Make every async entry point follow the `CLAUDE.md` async state rules. Add regression tests for the four spike bugs.
- Keep choices that carry over to Android (the end-of-2026 move). Isolate the one iOS-only piece (backup exclusion, D3) behind an interface.

**Non-Goals:**
- A polished visual design. Screens use stock Material 3 widgets. Styling can come later.
- Android configuration or testing. Android gets its own change.
- A background app refresh, and any server. Refresh happens only when the app is open (see proposal Non-Goals).
- Migrating the spike's saved position or downloaded file. There is one of each, on the owner's phone only (see Migration Plan).

## Decisions

### D1. Code layout: a pure core, adapters, then UI

```
app/lib/
  core/          pure Dart, no Flutter or plugin imports
    matching/    normalize(), match(): passes contracts/matching-vectors.json
    catalog/     Catalog, CatalogBuilder, SeriesDataset model and schema check
    feeds/       FeedItem, RSS parser (package:xml)
    listening/   next-episode choice, re-listen run logic, played threshold
    downloads/   DownloadState (from the spike), queue scheduler, reconcile
  data/          drift database, repositories, feed and dataset caches, secure storage
  platform/      adapters: PlayerPort (just_audio), DownloaderPort
                 (background_downloader), BackupExclusion (iOS channel), Connectivity
  playback/      BlankieAudioHandler (replaces SpikeAudioHandler)
  downloads/     DownloadManager (replaces EpisodeDownloader)
  refresh/       RefreshService: feeds + dataset, single-flight
  ui/            screens and widgets
  providers.dart Riverpod wiring
app/assets/series.json   bundled copy of data/series.json
```

The spike's `episode.dart`, `spike_screen.dart` and `SharedPreferencesPositionStore` are deleted. `DownloadState` and its tests move into `core/downloads/` and generalize from one episode to many.
- *Alternative:* grow the spike classes in place. Rejected: they mix plugin calls with logic, so the logic can't be tested. That is exactly why the four review bugs couldn't get tests.

### D2. App state: Riverpod

Riverpod "providers" are named, lazily created objects: the database, the catalog, the audio handler, and so on. Screens *watch* them and rebuild when they change. Tests *override* them with fakes.

Long-lived services (`RefreshService`, `DownloadManager`, the audio handler, repositories) are plain Dart classes that Riverpod constructs and hands out. Screens read derived values, such as a series' unplayed count, from providers that combine the catalog with drift's live queries.

Riverpod is used without its code generator, so drift (D3) is the only code-generation step.
- *Alternative:* `provider` + `ValueNotifier`, closest to the spike. More hand wiring and weaker test overrides as screens grow.
- *Alternative:* constructors + `StreamBuilder`. No package, but services would be threaded through about 6 screens by hand.

### D3. Storage: drift for state, files for caches, Keychain for the secret

| What | Where | Why |
|---|---|---|
| Listening state, re-listen runs, download queue, feed-item links, settings | drift SQLite database `blankie.sqlite` in Application Support | Transactions for bulk marking, schema migrations, live queries for the UI. Backed up normally. |
| Last good feed bodies (public and Patreon) | `feed-cache/` in Application Support, **excluded from backup** | Needed for offline launch. The Patreon body is secret. |
| Last good `series.json` | `feed-cache/series.json` | Same directory, same lifecycle. |
| Episode audio | `episodes/` in Application Support, **excluded from backup** | Large and re-downloadable. Apple's guidance is to keep such files out of backups. |
| Patreon feed URL | Keychain via `flutter_secure_storage`, accessibility `first_unlock_this_device` | `ThisDeviceOnly` items never leave the device in backups. |

drift is a typed SQLite layer. You declare tables in Dart, and `build_runner` generates the query code. The generated `*.g.dart` files are committed, so a plain `flutter test` works without the generator.

drift turns a query into a `Stream` that emits again whenever its tables change. That's how the home screen's unplayed counts stay current without manual refresh calls.

Nothing in the database holds a URL. Download rows store the episode ID and source feed, and the enclosure URL is looked up from the in-memory catalog when a download is submitted.

**Backup exclusion** is a small iOS *platform channel*: a Dart call that runs about 10 lines of Swift in `AppDelegate`, setting `isExcludedFromBackup` on a directory. It runs at startup on `feed-cache/`, `episodes/` and the plugin's `backgroundDownloaderTaskRecords/`. Excluding a directory covers its contents. The Dart side is a `BackupExclusion` interface, so Android can get its own version later.
- *Alternative:* sqflite with hand-written SQL. No codegen, but mapping rows, migrations and change notifications are all manual.
- *Alternative:* JSON files. No transactions, and each save rewrites a file.
- *Alternative:* cache feeds under `Library/Caches` (not backed up) instead of a channel. Rejected: iOS may purge Caches under storage pressure, which would break "offline launch shows the last catalog".

### D4. Episode identity and the catalog

- **IDs.** A dataset episode's ID is `series.json`'s episode ID. A feed item that doesn't match gets `public:<guid>` or `patreon:<guid>`. That's the "identity derived from its feed and GUID" in `episode-catalog`.
- **CatalogBuilder** is a pure function: `(dataset, publicItems, patreonItems?) → Catalog`. It contains:
  - episodes by ID, each with its sources (`public` and/or `patreon`: GUID, enclosure URL, duration) and its series IDs
  - series with only their available episodes, in dataset order
  - the groups: Standalones, "New, not yet sorted" (published after the dataset's newest air date) and Other

  Episodes with no source, and series with no available episodes, are dropped (`episode-catalog`, "Episodes available only in the dataset are hidden"). The playable source is chosen by the rule in `episode-catalog` "Preferred audio source". A local file, if present, is chosen at play time (D9).
- **Matching order for each feed item:**
  1. Patreon GUID equals the dataset's `patreonPostId` hint.
  2. GUID equals the `publicGuid` hint. Older Patreon ad-free copies reuse public GUIDs.
  3. The title and date rules from `episode-matching`, against dataset episodes. "(Ad-Free)" is removed by normalization.
  4. Otherwise the item is unmatched.

  The matcher never guesses. A tie is unmatched.
- **Performance.** About 1,500 feed items against about 900 dataset episodes, bucketed by air date. `CatalogBuilder` runs in `Isolate.run` (a background thread for Dart), so parsing and matching don't make scrolling stutter.
- **Unmatched items that later match.** A `feed_item_links` table records `(feed, guid) → episodeId` from the last build. When a rebuild maps a `(feed, guid)` from a `public:`/`patreon:` ID to a dataset ID, one transaction moves the listening state:
  - played if either ID was played
  - the position with the later `updatedAt`

  It also re-keys any download row. File names don't depend on the episode ID (D11), so no file moves. This covers the "Dataset catches up" scenario.

### D5. Matching in Dart, tested against the shared cases

`core/matching` implements `episode-matching`. `test/matching_vectors_test.dart` loads `../contracts/matching-vectors.json` (the repo root, relative to `app/`) and runs every normalization and match case. This is the conformance requirement.

Dates compare in UTC calendar days, the same as the Python tool.

### D6. Series dataset: bundled, cached, fetched

- **Source.** `https://raw.githubusercontent.com/jhyelton/blankie/main/data/series.json`.
- **Load order at startup:**
  1. `feed-cache/series.json`, if present and supported
  2. otherwise the bundled `assets/series.json`

  Refresh then fetches the published copy, as part of D7.
- **Schema check.** The app supports `schemaVersion == 1`. A fetched copy with any other version is not cached. The app keeps the previous copy and shows "Update blankie for the latest series data" on the home screen.
- **The bundled copy** is a committed copy of `data/series.json`, updated by hand when convenient. It only matters for a first launch with no network, so it being stale is harmless.
- *Alternative:* a symlink from `app/assets/` to `data/`. Rejected: Flutter asset and git symlink handling differs across platforms, and it would tie the build to the repo layout.

### D7. Feeds and refresh

- **RefreshService.refresh()** fetches the public feed, the Patreon feed (if connected) and the dataset in parallel. It rebuilds the catalog from whatever succeeded, merged with cached copies of whatever failed. Each successful body is written to `feed-cache/` only after it parses.
- **Triggers:** app start, `AppLifecycleState.resumed` (the app is brought to the foreground), and pull-to-refresh.
- **Single-flight.** An in-flight refresh `Future` is kept in a field and returned to every caller, per the async rules. A foreground event during a pull-to-refresh doesn't start a second fetch.
- **Status shown.** The UI shows the "last successful refresh" time and an "Offline" banner when the last attempt failed for network reasons. The banner is driven by fetch results, not by `connectivity_plus` guesses.
- **Parsing** uses `package:xml`:
  - `guid`, `title`, `pubDate`, `enclosure@url`, `itunes:duration`
  - the channel image, from the public feed only (D8)

  `enclosure length` is ignored, since it's `0`.
- **HTTP** uses `package:http`. Its exceptions include the request URL in `toString()`, so the fetcher catches everything at its boundary. It returns a sanitized `FeedError(kind: network | http | parse, status?)`.

### D8. The Patreon URL is a secret everywhere

- **Adding the feed.** Settings accepts a pasted URL, then:
  1. Rejects it if it isn't `https`.
  2. Fetches and parses it.
  3. Saves it to the Keychain only if it parses as RSS with at least one item.

  Errors show `FeedError` text only, such as "Couldn't read that feed (HTTP 403)".
- **Display.** Settings shows "Patreon: connected" with a masked identifier (`patreon.com/…••••`) and the date it was connected. None of the URL's path or query is ever shown.
- **Logging.** All app logging goes through one `log()` helper that runs `redactUrls()`, which replaces any `http(s)://…` with `<url>`. A unit test fails if `debugPrint(` or `print(` appears in `lib/` outside that helper. `debugPrint` still writes to the device log in release builds.
- **Player and downloader errors.** `PlayerException.message` and `TaskException.description` are shown only after `redactUrls()`. For Patreon sources the UI shows the HTTP status or a generic reason.
- **Plugin logging.** `background_downloader` logs through `package:logging`, which prints nothing unless someone listens to `Logger.root`. The app never attaches a listener.
- **Media controls.** `MediaItem.id` is the episode ID, never a URL. `artUri` is always the **public** feed's channel image, so no Patreon URL reaches the OS media session.
- **Disconnect** runs in this order:
  1. Delete the Keychain item.
  2. Delete `feed-cache/patreon.xml`.
  3. Rebuild the catalog.
  4. For every download row whose episode is no longer in the catalog, cancel the task and delete the file (`feed-subscription`, "Removing the Patreon feed").

  Listening-state rows are never deleted. This cleanup runs **only** on an explicit disconnect. A failed refresh never removes downloads.
- **Fixtures.** Test feeds are synthetic. The Patreon-shaped fixture uses `https://example.invalid/…` URLs, and gitleaks runs in CI as before.

### D9. Playback: one handler, a playback context, and advancing on completion

- **BlankieAudioHandler** replaces `SpikeAudioHandler`. It keeps the spike's proven behavior:
  - the speech session, `handleInterruptions`
  - ±30/15 s skips
  - the 10 s and on-pause position saves
  - reloading from the original URL on a stream error
  - the local → stream fallback
  - `_loaded` guarding every save

  It goes through `PlayerPort` (D13) instead of `AudioPlayer` directly.
- **Loading an episode** takes `(episodeId, PlaybackContext)`. The context is `series(seriesId)` or `group(kind)`, and it records where playback was started (`listening-session`, "Multi-series episode"). The source is:
  - the downloaded file if one exists, whichever feed it came from (`episode-catalog`)
  - otherwise the preferred stream

  The loaded episode ID and context are saved to settings, so a relaunch restores them.
- **Played threshold.** A position listener marks the episode played once per load, when `position >= duration − 30 s` or on `ProcessingState.completed`. The same event advances a re-listen run if this episode is the run's *next* episode (D10).
- **Auto-advance.** On `ProcessingState.completed`:
  1. The handler calls the pure `chooseNext(catalog, state, runs, context, finishedId)`. It holds every rule in `listening-session`: played episodes skipped, run order, groups stop, unavailable episodes skipped.
  2. If the result isn't downloaded and the last connectivity check says offline, playback stops. The UI and the lock-screen subtitle show "Next episode needs a connection".
  3. Otherwise it loads the result and plays.

  While locked, audio apps keep running as long as their audio session is active. Loading the next item straight from the completion callback keeps the session active. This must be checked on the device, locked, with a streamed next episode.
- **Speed** is `settings.speed` (0.8–2.0 in 0.1 steps). It's applied with `setSpeed` on every load and immediately when changed, and published in `PlaybackState.speed`.
- **Position store.** `PositionStore` stays as the handler's interface. Its implementation becomes a drift repository keyed by episode ID.
- *Alternative:* a `just_audio` playlist that preloads the next episode, for gapless playback. Rejected for now: AVPlayer would resolve the next item's signed redirect ahead of time, and the redirect could expire before it plays. The next episode also depends on state that changes at the end of the current one. It's the fallback if the device check shows iOS suspends the app between episodes.

### D10. Listening state and re-listen runs

- **`episode_state`:** `(episodeId PK, played, positionMs, updatedAt)`. Rows exist only for episodes that were touched, so a missing row means unplayed at 0.
  - "Mark series as played/unplayed" and "Mark everything before this as played" each run as one transaction over the catalog's available episode IDs.
  - "Before" means `airDate` strictly earlier. An unmatched item's air date is its `pubDate`.
- **`relisten_runs`:** `(seriesId PK, episodeIds JSON, nextIndex, startedAt)`.
  - The episode list is a **snapshot** of the series' available episodes when the run starts, so "0/23" doesn't change when a new release joins the series mid-run.
  - Progress is `nextIndex / episodeIds.length`.
  - Finishing the episode at `nextIndex` increments it. Reaching the end deletes the run.
  - A snapshot episode that is unavailable when the run reaches it (for example after a Patreon disconnect) is skipped and counts as passed.
  - "End re-listen" deletes the row. Played flags and positions are never touched (`listening-state`).
- These rules live in `core/listening/` and are unit-tested against every `listening-state` and `listening-session` scenario.

### D11. Download queue: our persistent queue in front of the plugin's holding queue

- **`downloads` table:** `(episodeId PK, sourceFeed, fileName, state: queued | active | failed | downloaded, queuedAt, error)`. It's the source of truth, and it survives termination.
- **File names** are `<feed>-<sanitized guid>.mp3`, with a `.part` suffix until renamed, as in the spike. They're stable when an unmatched episode's ID changes to a dataset ID (D4).
- **Submission.** Every `queued` row is submitted to `background_downloader`, in `queuedAt` order, with `Config.holdingQueue` set to `(2, null, null)`. Each task gets:
  - `retries: 3`
  - `allowPause: false`
  - `requiresWiFi: !settings.allowCellular`
  - the original enclosure URL from the catalog

  The native holding queue starts the next one when one finishes, even while the app is suspended in the background. The Dart side doesn't need to be awake.
- **After termination.** If iOS terminates the app, the holding queue is lost but active `URLSession` transfers continue. At startup, `DownloadManager.init` reconciles each row, using the spike's `reconcile` generalized per episode:
  - a final file exists → `downloaded`
  - the plugin recorded `complete` and the `.part` file exists → finish the rename (single-flight, as the spike's fix does)
  - the plugin has an active record → leave it
  - no record → resubmit
- **Wi-Fi.** "Waiting for Wi-Fi" is iOS holding the task (`allowsCellularAccess = false`). The UI shows it when a row is active, the device is on cellular, and cellular is off.
  - Changing the cellular setting **cancels and resubmits** active tasks, which then restart from zero with the new flag. It deliberately doesn't use the plugin's global `requireWiFi` reschedule, because that produces resume data (see Context).
- **Cancel.** `cancelTaskWithId`, then delete any `.part` and the row. The holding queue starts the next task. "Cancel all" does this for every row.
- **Failure.** After the plugin's 3 retries the row becomes `failed` with a redacted reason. "Retry" resets it to `queued`, at the end of the queue, starting from the original URL.
- **After completion,** the plugin's task record is deleted (`database.deleteRecordWithId`), so enclosure URLs don't pile up in its store.
- **Download series** takes the unplayed available episodes in series order, or the rest of the active run in run order. It skips downloaded and queued episodes and inserts the rest in one transaction.
- **Auto-remove.** A listener on listening-state changes deletes the file and row when the setting is on and the episode:
  - becomes played and is not ahead in an active run, or
  - has just been passed by an active run (`download-queue`, "Removing played downloads").
- **Startup sweep.** After reconcile, a sweep deletes files in `episodes/` that no row refers to. That covers crash leftovers and the spike's `<guid>.mp3`. A `.part` file is deleted only if its task has no active plugin record.
- *Alternative:* only our Dart queue, submitting 2 at a time. Rejected: Dart doesn't reliably run when a transfer finishes in the background, so a 19-episode queue would stall until the app is opened.
- *Alternative:* only the plugin's holding queue. Rejected: it's lost on termination, so "App restarted mid-queue" would fail.

### D12. Screens

Navigation is plain `Navigator` pushes. There are no deep links, so there's no router package.
- **Home:**
  - "New, not yet sorted", then the series and Standalones by newest episode, then Other (`series-browser`)
  - an "Unplayed only" filter chip
  - pull-to-refresh, the last-refreshed time, and the offline or update-needed banners
- **Series detail**, also used for the groups:
  - an app-bar menu: Download series, Mark series played/unplayed, Start/End re-listen
  - an episode list with played, progress, download and "next in re-listen" markers
  - per-episode actions in a bottom sheet: Play, Download/Remove download, Mark played/unplayed, Mark everything before this as played (with a confirmation dialog)
- **Mini-player bar** on every screen, opening a **Player** sheet with seek, skips and speed.
- **Downloads:** the queue in order, with progress or indeterminate progress, cancel, cancel all, and retry.
- **Settings:**
  - Patreon connect/disconnect
  - allow cellular downloads
  - remove played downloads
  - About: the wiki attribution from `series.json` (source, CC BY-SA, license link), as the license requires

### D13. Spike follow-ups: seams, regression tests, CI, format

- **Seams:**
  - `PlayerPort` covers the part of `AudioPlayer` the handler uses. `JustAudioPlayerPort` adapts it.
  - `DownloaderPort` covers `start`, `enqueue`, `cancelTaskWithId`, `updates`, `recordForId` and `deleteRecordWithId`. `FileDownloaderPort` adapts it.
  - File access goes through `package:file`, with `MemoryFileSystem` in tests.
- **Regression tests** target the v1 classes, which replace the spike classes:
  1. `BlankieAudioHandler`: a failing initial `setAudioSource` followed by pause, lifecycle `paused` and `stop` leaves the saved position unchanged.
  2. `DownloadManager`: a startup `init` reconcile plus a replayed `complete` update produce one rename and state `downloaded`.
  3. `BlankieAudioHandler`: a local-file load that throws falls back to the stream at the same position.
  4. `DownloadManager`: two `download()` calls in the same event-loop turn produce one `enqueue`.
- **Format pass.** A first commit runs `dart format lib test`. After that, drift codegen is always followed by `dart format`, so generated files pass the check.
- **CI.** A `flutter` job in `.github/workflows/ci.yml`:
  - Gated by a `changes` filter on `app/**`, `contracts/**` and the workflow file.
  - Uses `subosito/flutter-action`, pinned by SHA, with `flutter-version: 3.47.5`, on `ubuntu-latest`.
  - Runs in `app/`: `flutter pub get`, `dart format --output=none --set-exit-if-changed lib test`, `flutter analyze`, `flutter test`.
  - Is listed under `ci-ok.needs`.

  Ubuntu is enough because no step builds for iOS.

### D14. On-device verification record

Anything unit tests can't reach is checked on the iPhone with a release build: locked auto-advance, queue progress while locked, Wi-Fi waiting, Keychain survival across a re-install, the lock-screen metadata after an advance, and the spike's R1–R5 re-run on v1. Results go in `docs/device-checks/blankie-v1.md`, in the same PASS/FAIL table style as the spike results. That keeps `docs/spikes/` for stack-gating spikes only.

## Risks / Trade-offs

- **[Risk] iOS suspends the app between the end of one episode and the start of the next while locked**, so auto-advance silently stops. → *Mitigation:* load the next episode directly in the completion callback (D9) and verify it on the device (D14). Fallback: preload the next item as a two-item `just_audio` playlist, and accept the redirect-expiry risk for that one item.
- **[Risk] A holding-queue transfer finishes while the app is terminated**, and the next item isn't submitted until the app next opens. → *Accepted.* Active transfers still finish, and startup reconcile resubmits the rest. With 2 slots, at most 2 episodes wait for the next app launch.
- **[Risk] The plugin's task records hold Patreon enclosure URLs on disk.** → *Mitigation:* delete records after completion, exclude their directory from backup, and never log them. The residual copy lives only in the app's sandbox, which is where the Keychain-held URL already lives.
- **[Risk] Changing the cellular setting restarts active downloads from zero.** → *Accepted.* It's rare, and resuming would need the resume data this design avoids.
- **[Risk] `series-data-pipeline` isn't applied**, so there's no `series.json` or matching-vectors file to build against. → *Mitigation:* apply is blocked on it (proposal Impact). Until it lands, a minimal synthetic `series.json` fixture that follows its schema lets the core logic be built and tested.
- **[Risk] Generated drift code conflicts with the format check.** → *Mitigation:* run `dart format` after every codegen (D13). CI's `flutter analyze` catches generated code that is out of date.
- **[Risk] Deleting the app, including by mistake, erases all listening state**, and there's no export (a proposal Non-Goal). → *Accepted by the owner.* The runbook already warns about it. Device backups keep `blankie.sqlite`, because only caches and audio are excluded.
- **[Trade-off] drift adds a code-generation step** (`build_runner`), one more tool for a new mobile developer. The owner accepted it for typed queries, migrations and live queries. Riverpod is used without its generator to keep it the only one.
- **[Trade-off] Parsing about 1,500 items on each foreground refresh.** It costs a few hundred milliseconds in a background isolate. If it's measurably slow on the device, add conditional GET (`ETag`/`If-Modified-Since`) later without changing the design.

## Migration Plan

1. **Spike data.** v1 doesn't read `shared_preferences` or the spike's `episodes/<guid>.mp3`. The startup sweep (D11) deletes the file on first launch. The owner re-marks Taxi Driver's position by hand, if they want it.
2. **Database schema** starts at drift schema version 1. Later changes add numbered migrations. None run in this change.
3. **Install** is the normal runbook flow (`flutter run --release -d <udid>`) over the existing spike app, so the Keychain and container are kept.
4. **Rollback:** reinstall the previous commit's build over v1. The spike build ignores `blankie.sqlite` and v1's downloads. Reinstalling v1 afterwards picks them up again, because the database and files stay in the container.

## Open Questions

- The exact copy and layout of the banners, empty states and error messages. It can be settled during implementation without changing behavior.
- Whether Megaphone and Patreon support conditional GET. It only matters if refresh turns out to be slow (see Risks).
