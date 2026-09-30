# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

blankie is a single-show podcast player for *Blank Check with Griffin & David*. It's built for one owner and replaces Pocket Casts for that show. The product context (listening lanes, the two feeds and their quirks, the episode model, series data from the fan wiki) lives in `openspec/config.yaml` under `context:`. Read it before planning anything. The owner is a devops engineer who is new to mobile development, so explain mobile-specific concepts when they come up.

The repo is **public**. The Patreon feed URL and any Patreon feed XML contain a personal access token. They must never be committed, logged, or used in fixtures. `.gitleaks.toml` encodes the patterns; `CONTRIBUTING.md` covers the leak response.

## Layout

- `app/`: the Flutter app (iOS only for now; Android comes in a later change).
- `openspec/`: planning. Active changes are in `openspec/changes/<name>/`; archived specs are merged into `openspec/specs/`.
- `docs/runbooks/ios-device-install.md`: installing on the iPhone with free Apple signing, and the re-install every 7 days.
- `docs/spikes/`: on-device test results, which gate stack decisions.

## Commands

Flutter (run from `app/`):

```bash
flutter pub get
flutter analyze
flutter test                                              # all unit tests
flutter test test/download_state_test.dart                # one file
flutter test --plain-name "reaches 100% at the end"       # one test by name
flutter build ios --no-codesign                           # compile check without signing
```

On-device (the phone must be paired in Xcode and have Developer Mode on):

```bash
flutter devices                              # get the <udid>
flutter run --release -d <udid>              # install and launch
xcrun devicectl device info files --device <udid> --domain-type appDataContainer --domain-identifier com.jhyelton.blankie
```

Always install with `--release`. Flutter debug builds can't launch from the home screen without a debugger attached. If `flutter run` says `Could not run … Runner.app`, the phone usually needs to trust the developer certificate again (runbook section 6).

Repo checks (the same ones CI runs):

```bash
openspec validate --all --strict
gitleaks dir . --no-banner --config .gitleaks.toml --redact
```

## App architecture

The current app is the `audio-spike` proof of concept. `spike_screen.dart` and the hard-coded episode in `episode.dart` are disposable. The audio and download plumbing is what `blankie-v1` builds on.

- **Playback**: `SpikeAudioHandler` is an `audio_service` `BaseAudioHandler` wrapping a `just_audio` `AudioPlayer`.
  - `audio_service` publishes the `MediaItem` and `PlaybackState` to the lock screen and Control Center, and routes remote commands back to the handler. Headphone toggles arrive as `click`.
  - The lock-screen skip intervals (+30 s / −15 s) come from `AudioServiceConfig` in `main.dart`. They feed `SeekHandler.fastForward` and `rewind`.
  - Interruptions and headphone unplugging are handled by `just_audio`'s built-in `handleInterruptions`, on an `audio_session` configured as `AudioSessionConfiguration.speech()`.
- **Position persistence**: goes through the `PositionStore` interface (`shared_preferences` for now, keyed by GUID). v1 is expected to swap in a real database keyed by wiki identity. The handler saves every 10 s while playing, and immediately on any pause, on seek, and on app lifecycle `paused`/`detached`.
- **Downloads**: `EpisodeDownloader` uses `background_downloader`, which runs on a background `URLSession`, so transfers continue while the app is suspended.
  - Files land as `<guid>.mp3.part` and are renamed on completion. Only the renamed file counts as playable.
  - `allowPause` is off on purpose. iOS resume data would hold the expiring signed redirect URL, so every retry has to restart from the original enclosure URL.
  - All state logic lives in `download_state.dart`: pure, plugin-free, and unit-tested. That includes `reconcile`, which works out the state at startup after a download finished in the background.
- **Enclosure URLs** (`traffic.megaphone.fm`) redirect with `302` to signed CDN URLs that expire. Always store and retry from the original URL. The handler reloads the stream from the original URL if playback errors.
- **iOS project**: plugins link through Swift Package Manager, so there is no Podfile. `Info.plist` sets `UIBackgroundModes` to `audio`. `project.pbxproj` holds the owner's free Personal Team (`DEVELOPMENT_TEAM`).

### Async state rules

The audio-spike review found four bugs, all caused by breaking one of these rules:

- **Change guard state before the first `await`.** In a user-triggered action (for example `download()`), set the "busy" state synchronously. Otherwise a second tap arrives during the `await` and passes the guard.
- **Make completion handlers single-flight and idempotent.** Keep the in-flight `Future` in a field and give it to every caller. Treat "already done" as success. At startup the plugin replays events, so the same completion can arrive twice.
- **Commit derived state only after the operation succeeds.** For example, set the source indicator after `setAudioSource` returns, not before.
- **Never persist from a player that hasn't loaded.** Its position is 0 until a source has loaded. Seeded streams such as `playingStream` also emit as soon as you subscribe.
- **No silent fire-and-forget.** `unawaited_futures` and `discarded_futures` are enabled. Use `unawaited(...)` only when the callee handles its own errors.

Only `PositionStore` and the download state logic have unit tests. Background audio, lock-screen controls, interruptions and downloads can only be checked on a real iPhone. Record the results in `docs/spikes/`.

## Workflow

The full process is in `CONTRIBUTING.md`. The parts that affect how you work:

- Every change is planned with OpenSpec (`/opsx:propose`) before any code is written.
- Each change gets two PRs:
  - a plan PR with only the artifacts, titled `docs(spec): propose <change>`
  - an implementation PR (`/opsx:apply`), whose last commit is `/opsx:archive <change>`
- Only archive a change when every task is done. Tasks that have to wait for time to pass go into a follow-up change.
- Commits and PR titles use Conventional Commits, with types `feat fix docs chore ci refactor test build perf` and scopes like `spec`, `app`, `data`, `ci`. PRs are squash-merged.
- **Pre-PR review.** Before opening an implementation PR, or when the owner asks for one, have a subagent (Agent tool) do the review. Never review your own diff in this context: you'd share the implementer's blind spots, and the review output would fill the working context.
  - Give the subagent only pointers: the base (`main`), the branch, and `openspec/changes/<change>/`. Don't pass your summary, your reasoning, or which parts you believe are fine.
  - Ask for correctness bugs only. Each finding needs `file:line`, a concrete failure scenario, and a suggested fix. The subagent should check its claims against the code and the package sources in `~/.pub-cache`, and should apply the async state rules above.
  - When it reports, verify each finding yourself. Then give the owner a verdict per finding (valid, invalid, or overstated) and a fix plan. Don't change or push anything until the owner agrees.
- CI is a single workflow, `.github/workflows/ci.yml`. `ci-ok` is the only required check. To add a check, add a job to that workflow and list it under `ci-ok.needs`; never add a separate required workflow.
