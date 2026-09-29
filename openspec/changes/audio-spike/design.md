# Design

## Context

- The repo holds only a README, the GPL license, and the OpenSpec scaffolding. There's no app code yet, and the repo is about to become public.
- The development Mac has Xcode 26.6. The Flutter SDK is **not installed**.
- The owner has no mobile development background and has no paid Apple Developer Program membership. Installs use free signing, which expires every 7 days (see `specs/ios-device-install`).
- Test audio comes from the public feed `https://feeds.megaphone.fm/blank-check`. Enclosure URLs from that feed:
  - redirect (`302`) from `traffic.megaphone.fm` to a signed CDN URL whose `timetoken` query parameter expires
  - serve `accept-ranges: bytes` and a real `content-length`, even though the feed's `enclosure length` is `0`
  - are large: *Taxi Driver with Tracy Letts* (GUID `ca63c896-fae9-11f0-9ff5-67d1244352a1`) runs 3h53m and is about 225 MB
- The requirements are in `specs/audio-playback`, `specs/episode-download` and `specs/ios-device-install`. The motivation is in `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Get a pass/fail answer, on the owner's physical iPhone, to the question: "Can Flutter handle blankie's audio and download plumbing?"
- Produce a Flutter project skeleton, dependency set and iOS configuration that `blankie-v1` builds on instead of redoing.
- Leave behind a runbook the owner can follow without help every 7 days.

**Non-Goals:**
- Feed parsing, the Patreon feed, series data, Lane A/Lane B, queues, or any real UI. The spike screen is disposable.
- Android. The Android runner may exist because `flutter create` generates it, but it is not configured or tested here. It gets its own change before the phone migration.
- Choosing blankie's long-term local database. Position persistence here uses the simplest store that meets the spec.
- CarPlay, playback speed, sleep timer, chapters.
- A CI guard against committing Patreon tokens. This change never touches the Patreon feed, so the guard belongs to the first change that does.

## Decisions

### D1. The Flutter project lives at `app/`, not the repo root
The repo will also hold `openspec/`, `docs/` and, later, the series-data scraper and its CI workflow. Keeping the Flutter project in `app/` keeps those concerns apart and gives CI clear path filters. The iOS bundle identifier is `com.jhyelton.blankie`, which has to be unique for free provisioning.
- *Alternative:* a Flutter project at the repo root. That's slightly less typing, but it mixes app, data and ops files together.
- *Alternative:* a separate throwaway `spike/` project. It would be thrown away, and the toolchain, signing and background-mode setup, which is the expensive part, would have to be redone for v1.

### D2. Audio stack: `just_audio` + `audio_service` + `audio_session`
- `just_audio` plays audio (AVPlayer on iOS). It handles redirects, HTTP range seeking and local files.
- `audio_service` connects the player to the OS media session: lock screen, Control Center, headphone and car remote commands, and later the Android media notification.
- `audio_session` sets the iOS audio session to the `playback` category and delivers interruption and route-change events (see the interruption requirement in `specs/audio-playback`).
- *Alternative:* `just_audio_background`, a thin wrapper that's quicker to set up. It was rejected because v1 needs custom queue and command handling, which means `audio_service` anyway. The spike should prove the stack v1 will actually use.
- *Alternative:* `audioplayers`. It has weaker media-session integration and would still need a separate media-session layer.

### D3. Downloads: `background_downloader`
It uses a background `URLSession` on iOS (and WorkManager on Android), so transfers continue while the app is suspended. It reports progress from the HTTP response size and can retry failed downloads.

Because the redirect target is a signed URL that expires, every retry **starts from the original `traffic.megaphone.fm` URL**, never from a cached redirect location. Files download to a temporary name and are renamed on completion, so a partial file is never treated as playable.
- *Alternative:* `dio` or `http` streaming to a file. Those stop when iOS suspends the app, which fails the background-download requirement.

### D4. Position persistence: `shared_preferences`, keyed by episode GUID
The spike stores one position per GUID. It writes every 10 s while playing and immediately on pause, seek, and app lifecycle `paused`/`detached` events. The storage sits behind a small `PositionStore` interface, so v1 can swap in its real database without changing the player code.
- *Alternative:* SQLite (drift/sqflite) now. That's premature. v1 will choose storage alongside the episode model, where positions will be keyed by wiki identity rather than GUID.

### D5. The spike screen plays one hard-coded public episode
The spike uses *Taxi Driver with Tracy Letts*: its enclosure URL, title, show name and artwork URL are hard-coded from the public feed. At 3h53m and 225 MB, it covers both the "≥3 hour" playback scenario and the "≥150 MB" download scenario.

The screen has play/pause, ±skip, a seek bar, position/duration, a download button with progress, and a status line saying whether the source is the stream or the local file. Nothing more.

### D6. Daily-use installs are release builds
Since iOS 14, Flutter **debug** builds can't be launched from the home screen without an attached debugger. The runbook therefore installs with `flutter run --release` (or `flutter build ios --release` followed by an install from Xcode), using the personal team's automatic signing. This is what satisfies "launches without a debugger" in `specs/ios-device-install`.

### D7. The gate is a written results record
`docs/spikes/audio-spike-results.md` lists every scenario from the three spec files with PASS/FAIL, the device, the iOS version and notes.
- **Pass:** every `audio-playback` and `episode-download` scenario passes on the physical iPhone.
- **Fail:** any scenario still failing after the timebox, which is **2 working days** of on-device debugging. A fail triggers re-evaluating the stack (React Native/Expo being the fallback discussed) before `blankie-v1` starts.

The record ends with an explicit **GO / NO-GO** line.

### D8. Runbook location and shape
`docs/runbooks/ios-device-install.md` has these sections:
1. One-time Mac setup: install Flutter via Homebrew, `flutter doctor`, Xcode components, CocoaPods if `flutter doctor` asks for it.
2. One-time iPhone setup: Developer Mode, pairing with Xcode, trusting the developer certificate under *Settings → General → VPN & Device Management*.
3. First install.
4. The every-7-days re-install: symptoms, the exact commands, and what data survives.
5. Limitations of free signing.
6. Troubleshooting, written from errors actually hit during the spike.

Each command in the runbook is one that was actually run during the spike.

## Risks / Trade-offs

- **[Risk] The signed CDN redirect expires mid-stream or mid-download**, causing a failure or a silent stall. → *Mitigation:* always start and retry from the original URL (D3). Explicitly test a seek into hour 3 after the stream has been paused for over 30 minutes.
- **[Risk] The OS terminates the app while it's paused in the background, and the last position is lost.** → *Mitigation:* write the position on pause and on lifecycle events, not only on a timer (D4). The "resume after the app is terminated" scenario covers this.
- **[Risk] A re-install with a different signing identity wipes the app's data container**, losing positions and downloads every 7 days. → *Mitigation:* the spike tests a real re-install and records the result. The runbook states the behavior (a spec requirement). If data is lost, that becomes an input to v1's design, not a spike failure.
- **[Risk] The main audio packages are largely maintained by one person.** → *Accepted.* The playback code sits behind `audio_service`'s handler abstraction, so the underlying player could be replaced. We'll look again if maintenance stops.
- **[Risk] Free provisioning limits** (7-day expiry, limited number of apps per device) → *Accepted* by the owner. Documented in the runbook.
- **[Trade-off] Tests are mostly manual.** Background audio, lock-screen controls and interruptions can't be tested meaningfully in unit tests or the simulator. Automated tests cover only `PositionStore` and the download-state logic. Everything else is checked on the device and recorded in the results file.

## Migration Plan

This is a new project, so there's nothing to migrate. Rollback on a NO-GO means leaving `app/` in place, marking the results file NO-GO, and opening a new change to re-evaluate the stack.
