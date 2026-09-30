# Tasks

## 1. Toolchain and project skeleton

- [x] 1.1 Install the Flutter SDK on the Mac via Homebrew and resolve every `flutter doctor` item needed for iOS (Xcode, CocoaPods if requested). Verify: `flutter doctor` shows no errors for Flutter or Xcode; Android warnings are acceptable. Record every command run, for the runbook.
- [x] 1.2 Create the Flutter project at `app/` with iOS as the only platform and bundle identifier `com.jhyelton.blankie` (design D1). Verify: `cd app && flutter analyze` passes and `flutter test` passes the default test.
- [x] 1.3 Check that the generated `.gitignore` files exclude build output, `Pods/` and local Xcode user data. Also add a root `.gitignore` entry for raw feed dumps (`*.rss.xml`, `feeds/`). Verify: `git status` after a build shows no build artifacts.
- [x] 1.4 Add `just_audio`, `audio_service`, `audio_session`, `background_downloader` and `shared_preferences` to `app/pubspec.yaml`. Verify: `flutter pub get` succeeds and `flutter build ios --no-codesign` completes.
- [x] 1.5 Configure iOS for background audio: add `UIBackgroundModes` → `audio` in `Info.plist`, plus whatever `audio_service` and `background_downloader` document for iOS. Verify: the built `Info.plist` contains the `audio` background mode.

## 2. First device install and runbook

- [x] 2.1 Set up Xcode signing with the owner's free Apple ID (personal team), enable Developer Mode on the iPhone, pair it, and trust the developer certificate. Verify: the skeleton app from 1.2 installs with `flutter run --release` and launches from the home screen with the Mac unplugged.
- [x] 2.2 Write `docs/runbooks/ios-device-install.md` sections 1–3 (Mac setup, iPhone setup, first install) and section 5 (free-signing limitations), using the commands actually run in 1.1 and 2.1 (design D6, D8). Verify: every command in those sections appears in the 1.1/2.1 command log, and the limitations section names the 7-day expiry and the app-count limit.

## 3. Playback

- [x] 3.1 Add a `PositionStore` interface with a `shared_preferences` implementation keyed by episode GUID (design D4), with unit tests for save, load, overwrite and missing-key behavior. Verify: `flutter test` passes the new tests.
- [x] 3.2 Implement an `audio_service` `AudioHandler` backed by `just_audio` that loads the hard-coded *Taxi Driver* episode (design D5) from its original enclosure URL and publishes a `MediaItem` with title, show name, artwork and duration. Verify: on the iPhone, the episode streams, and the lock screen shows the title, show name, artwork and an advancing progress bar.
- [x] 3.3 Wire lock-screen / Control Center commands: play, pause, skip forward 30 s, skip back 15 s, and seek. Verify: each "System media controls" scenario in `specs/audio-playback` passes on the device.
- [x] 3.4 Configure `audio_session` for the playback category and handle interruptions (pause, then resume when the OS says to) and route changes (pause when headphones disconnect). Verify: the "Phone call interruption", "Headphones disconnected" and "Bluetooth headphone play/pause" scenarios pass on the device.
- [x] 3.5 Persist the position every 10 s while playing and immediately on pause, seek and app lifecycle `paused`/`detached`. Restore it when the episode loads. Verify: both "Persist and restore playback position" scenarios pass on the device, including force-quitting the app from the app switcher mid-playback.
- [x] 3.6 Build the disposable spike screen: play/pause, ±skip, seek bar, position/duration, and a source indicator (stream vs local). Verify: the screen reflects state changes made from the lock screen within about 1 s.

## 4. Downloads

- [x] 4.1 Implement downloading with `background_downloader`: download to a temporary filename, rename on completion, and always start and retry from the original `traffic.megaphone.fm` URL (design D3). Add unit tests for the download-state logic (not downloaded → downloading → downloaded / failed, and a partial file is never playable). Verify: `flutter test` passes the new tests.
- [x] 4.2 Show download progress using the server-reported content length, falling back to an indeterminate progress indicator when it's unknown. Verify: the "Feed reports zero length" scenario in `specs/episode-download` passes. Progress for the 225 MB episode reaches 100%.
- [x] 4.3 Make the player use the local file when the episode is downloaded. Verify: the source indicator shows "local", and the "Offline playback" scenario passes in airplane mode, including with the screen locked.
- [x] 4.4 Handle interrupted downloads with a retry action. Verify: the "Network lost mid-download" and "Download completes while backgrounded" scenarios pass on the device.

## 5. On-device gate and re-install

- [x] 5.1 Run the long-session checks: 60+ minutes of locked playback (streamed), plus a seek into hour 3 after the stream has been paused for over 30 minutes (design, redirect-expiry risk). Verify: both are recorded in `docs/spikes/audio-spike-results.md` with PASS/FAIL.
- [x] 5.2 Re-install the app the way the runbook will prescribe, after saving a position and downloading the episode. Record whether the position and download survive. Write runbook section 4 (7-day re-install: symptoms, commands, what data survives) from this. Verify: the re-install section matches what was observed.
- [x] 5.3 Write runbook section 6 (troubleshooting) from the errors actually hit during this change. Verify: every error message listed there was seen during the spike.
- [x] 5.4 Fill in `docs/spikes/audio-spike-results.md` with every scenario from `specs/audio-playback`, `specs/episode-download` and `specs/ios-device-install` as PASS/FAIL, plus the device model, iOS version and notes, ending with an explicit GO/NO-GO line according to the criteria in design D7. Mark the "Signature expired" scenario DEFERRED, because it needs a real 7-day expiry and is covered by the follow-up change `ios-reinstall-verification`. Verify: no scenario is missing, and the GO/NO-GO line is present.
