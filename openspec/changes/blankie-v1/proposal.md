# Proposal

> **Status: specs only.** `design.md` and `tasks.md` are deliberately not written yet. They will be added with `/opsx:update blankie-v1` after `audio-spike` records GO, so the design can use the spike's results (the stack, and whether app data survives the 7-day re-install). Don't apply this change before then.

## Why

The owner listens to Blank Check through Pocket Casts, where the show is one flat, date-sorted list of about 900 episodes across the public and Patreon feeds. Catching up on the current miniseries while re-listening to an old one means scrolling back years and re-downloading episodes by hand. blankie v1 is the first version the owner can use every day instead of Pocket Casts for this show. It's organized around miniseries, which is how the owner actually thinks about the show.

## What Changes

- **Series-first home screen.** Every miniseries appears with its unplayed count, ordered by most recent episode. Episodes without a series are grouped as Standalones. New episodes that the series data doesn't know about yet appear in a "New, not yet sorted" group until the data catches up.
- **One logical episode per wiki ID.** The public and Patreon feeds are merged using the `series-data` dataset and the `episode-matching` rules. The ad-free copy plays when it's available.
- **Listening state.**
  - Played/unplayed status and resume position are kept per episode.
  - Bulk actions for day one: "Mark series as played" and "Mark everything before this episode as played".
  - "Start re-listen" works through a finished series with its own progress, without erasing play history.
- **Continuous listening.** When an episode finishes, playback advances to the next episode in the same series, or the next in the re-listen. Speed control applies to the whole app.
- **Manual downloads.** You can download one episode, or queue a whole series. The queue downloads a limited number at a time, is Wi-Fi only unless you allow cellular, and deletes played episodes automatically unless you turn that off.
- **Feeds.** The public feed works out of the box. The Patreon feed URL can be added in settings and is stored in the device's secure storage. Feeds and series data refresh when the app opens and on pull-to-refresh, with offline fallbacks.

## Capabilities

### New Capabilities

- `feed-subscription`: adding, storing, refreshing and removing the podcast feeds, including handling the private Patreon feed URL securely.
- `episode-catalog`: merging feed items and series data into one logical episode per wiki ID, choosing the playable source, loading and caching the series dataset, and grouping episodes that aren't in the dataset.
- `series-browser`: the home series list, series detail, the Standalones and "New, not yet sorted" groups, and what they display.
- `listening-state`: played status, resume positions, bulk marking, and re-listen runs.
- `listening-session`: what happens when an episode finishes (auto-advance) and playback speed.
- `download-queue`: downloading single episodes or whole series through a limited-concurrency queue, the network policy, and removing downloads.

### Modified Capabilities

None yet. This change builds on capabilities introduced by in-flight changes that aren't archived yet:
- `audio-playback` and `episode-download` from `audio-spike`: background playback, media controls, interruptions, position persistence, and background download of a single file.
- `series-data` and `episode-matching` from `series-data-pipeline`: the dataset contract and matching rules.

This change adds new behavior on top of them rather than changing their requirements.

## Non-Goals (candidates for later changes)

Search, episode show notes, sleep timer, CarPlay, background refresh, film metadata (TMDB/Letterboxd), exporting or importing listening state, Android support, and any automatic download policy.

## Impact

- **Depends on:**
  - `audio-spike` recording **GO**. Its results decide the design, including whether app data survives the 7-day free-signing re-install.
  - `series-data-pipeline` publishing `data/series.json` at a public URL and `contracts/matching-vectors.json`.
  - The repository being public.
- **Code:** extends the `app/` project created by `audio-spike`. The disposable spike screen is replaced.
- **Data on device:** listening state (played flags, positions, re-listen runs), the download queue and files, cached feeds, and the cached series dataset. All of it is keyed by stable episode IDs from `series-data`. There's no backend.
- **Secrets:** the Patreon URL lives only in the device's secure storage and in requests to Patreon.
