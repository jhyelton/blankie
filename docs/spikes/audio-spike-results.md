# Audio spike results

Results of the `audio-spike` change: can Flutter handle blankie's audio and download plumbing on a real iPhone? The pass/fail criteria are in design D7 of the change.

## Setup

| | |
|---|---|
| Device | iPhone 12 Pro (iPhone13,3) |
| iOS | 26.6.2 (23G90) |
| Mac | macOS 26.3.1, Xcode 26.6 |
| Flutter | 3.47.5 (Dart 3.13.4) |
| Packages | just_audio 0.10.6, audio_service 0.18.19, audio_session 0.2.4, background_downloader 9.6.3, shared_preferences 2.5.5 |
| Build | release, free Personal Team signing |
| Episode | *Taxi Driver with Tracy Letts*, 3h53m, 225,419,199 bytes (feed `length="0"`) |

## Scenarios

Status is PASS, FAIL, PENDING (not run yet) or DEFERRED (covered by a follow-up change).

### audio-playback

| Scenario | Status | Notes |
|---|---|---|
| Stream a remote episode | PASS | Streams from the original `traffic.megaphone.fm` URL. |
| Play a downloaded episode | PASS | Source indicator switched to "local" once the download finished. |
| Screen locked during playback | PASS | |
| Switching to another app | PASS | Kept playing while Notes/Safari were in front. |
| Long session while locked | PASS | Fresh install (no download), streamed with the phone locked; still playing past the 60-minute mark. |
| Lock screen shows the episode | PASS | Title, show name, artwork, advancing progress bar. |
| Pause and resume from the lock screen | PASS | |
| Skip from the lock screen | PASS | +30 s and −15 s. |
| Scrub from the lock screen | PASS | |
| Bluetooth headphone play/pause | PASS | |
| Phone call interruption | PASS | Paused during an incoming call; resumed on its own after hang-up. |
| Headphones disconnected | PASS | Paused; didn't continue through the speaker. |
| Resume after pausing | PASS | |
| Resume after the app is terminated | PASS | Force-quit from the app switcher mid-playback. |

### episode-download

| Scenario | Status | Notes |
|---|---|---|
| Download completes while backgrounded | PASS | Playback paused (so the app was suspended), phone locked; on reopening it showed "Downloaded" and "Source: local". |
| Feed reports zero length | PASS | Progress rose against the server size ("of 215.0 MB") and ended at "Downloaded" (100%). |
| Offline playback | PASS | Airplane mode, app relaunched: source "local"; play, pause, seek, resume, and locked playback all worked. |
| Network lost mid-download | PASS | Airplane mode at about 20–30%: the download waited and was never marked downloaded. With the network back, the iOS background session resumed it on its own, so the Retry button wasn't needed. The failed-then-retry path is covered by unit tests. |

### ios-device-install

| Scenario | Status | Notes |
|---|---|---|
| Following the runbook from scratch | PASS | Sections 1–3 were written from the first install on this device. |
| Launch while away from the Mac | PASS | Unplugged, launched from the home-screen icon, streamed audio. |
| Signature expired | DEFERRED | Needs a real 7-day expiry; covered by `ios-reinstall-verification`. |
| Owner checks limitations | PASS | Runbook section 5 lists the 7-day expiry and the 3-app limit. |

## Additional checks

| Check | Status | Notes |
|---|---|---|
| Seek into hour 3 after the stream was paused for over 30 minutes (redirect expiry) | PASS | Paused over 30 min after the long session, seeked to about 3:10:00, pressed play: audio started straight away with no hiccup, so the error-reload path wasn't needed. |
| Position survives a re-install | PASS | `flutter run --release` over the installed app, profile still valid. Same position shown after re-install; playback resumed from it. |
| Download survives a re-install | PASS | Same run. `episodes/<guid>.mp3` (215 MB) unchanged in the app container; screen showed "Downloaded" and "Source: local". |

## Findings

- **No progress without `Content-Length`.** On iOS, `background_downloader` emits no progress events when the server sends no `Content-Length`, so there's no byte count to show. The spec was changed to show indeterminate progress in that case. Megaphone always sends the header, so this doesn't affect the spike episode.
- **iOS waits instead of failing on network loss.** The background `URLSession` holds an interrupted download and continues when connectivity returns, instead of reporting a failure. The Retry button only appears if the system gives up (for example after its 4-hour resource timeout) or the server errors.
- **Plugins use Swift Package Manager.** Flutter 3.47 links iOS plugins through Swift Package Manager, so `app/ios` has no Podfile and CocoaPods isn't used.

## Result

| Spec | PASS | FAIL | DEFERRED |
|---|---|---|---|
| audio-playback | 14 | 0 | 0 |
| episode-download | 4 | 0 | 0 |
| ios-device-install | 3 | 0 | 1 |

All three additional checks passed as well: the hour-3 seek after a long pause, and the position and download surviving a re-install.

Design D7 says the spike passes when every `audio-playback` and `episode-download` scenario passes on the physical iPhone. All 18 did, on the first attempt and well inside the 2-day timebox. "Signature expired" is deferred to `ios-reinstall-verification` because it needs a real 7-day expiry. It isn't part of the D7 gate.

Flutter, with `just_audio`, `audio_service`, `audio_session` and `background_downloader`, handles blankie's audio and download plumbing on iOS. `blankie-v1` can start on this stack.

**GO**

## Command log

Commands run during the spike, in order, for checking the runbook against. Device IDs are replaced by `<udid>` and the team ID by `<team>`.

```text
# 1.1 Mac toolchain
xcodebuild -version            # Xcode 26.6 (17F113), preinstalled
brew install --cask flutter    # Flutter 3.47.5 / Dart 3.13.4 -> /opt/homebrew/share/flutter
flutter --disable-analytics
flutter doctor -v              # Flutter OK, Xcode OK (CocoaPods 1.16.2 present), Android ✗ (expected)
  # [✗] Android toolchain: Unable to locate Android SDK.
  # Connected device: Error: Browsing on the local area network for Joshua's iPhone. Ensure the device is
  # unlocked and attached with a cable or associated with the same local area network as this Mac.
  # The device must be opted into Developer Mode to connect wirelessly. (code -27)

# 1.2–1.5 Project skeleton
flutter create --platforms=ios --org com.jhyelton --project-name blankie app
cd app && flutter analyze && flutter test
flutter pub add just_audio audio_service audio_session background_downloader shared_preferences
flutter build ios --no-codesign   # OK; plugins via Swift Package Manager
flutter pub add --dev shared_preferences_platform_interface
flutter test && flutter analyze
flutter build ios --no-codesign
plutil -extract UIBackgroundModes json -o - build/ios/iphoneos/Runner.app/Info.plist   # ["audio"]

# 2.1 First device install
xcrun devicectl list devices      # iPhone 12 Pro listed, state "unavailable" (not connected)
security find-identity -p codesigning -v   # "Apple Development: <apple-id>" already on the Mac
flutter devices                   # after USB + Trust This Computer:
  # Error: Joshua's iPhone is not available because it is unpaired. Pair with the device
  # in the Xcode Devices Window, and respond to any pairing prompts on the device. (code -29)
# Paired in Xcode > Window > Devices and Simulators; turned on Developer Mode.
flutter devices                   # Joshua's iPhone (mobile) • <udid> • ios • iOS 26.6.2 23G90
flutter run --release -d <udid>
  # Automatically signing iOS for device deployment using specified development team in Xcode project: <team>
  # Could not run build/ios/iphoneos/Runner.app on <udid>.
  # Try launching Xcode and selecting "Product > Run" to fix the problem
xcrun devicectl device info apps --device <udid>    # Blankie com.jhyelton.blankie 1.0.0 installed
xcrun devicectl device process launch --device <udid> com.jhyelton.blankie
  # Unable to launch com.jhyelton.blankie because it has an invalid code signature, inadequate
  # entitlements or its profile has not been explicitly trusted by the user.
# Trusted the certificate: Settings > General > VPN & Device Management.
flutter run --release -d <udid>   # Installing and launching... / Flutter run key commands. => launched

# 5.2 Re-install over the existing app (profile still valid)
xcrun devicectl device info files --device <udid> --domain-type appDataContainer --domain-identifier com.jhyelton.blankie
  # before: Library/Application Support/episodes/<guid>.mp3 (215 MB), Library/Preferences/com.jhyelton.blankie.plist
flutter run --release -d <udid>   # Installing and launching... 2,181ms
xcrun devicectl device info files --device <udid> --domain-type appDataContainer --domain-identifier com.jhyelton.blankie
  # after: same two files, same sizes and timestamps => data container kept
# On the phone: same position, "Downloaded", "Source: local"; play resumed from the position.

# "Delete" via Remove App > Remove from Home Screen (by mistake)
xcrun devicectl device info apps --device <udid>   # Blankie still listed
flutter run --release -d <udid>                    # installed over it; episodes/<guid>.mp3 still present

# Real delete (Remove App > Delete App)
xcrun devicectl device info apps --device <udid>   # Blankie not listed
xcrun devicectl device info files --device <udid> --domain-type appDataContainer --domain-identifier com.jhyelton.blankie
  # ERROR: The system failed to get a list of files on the remote device. (CoreDevice.ActionError error 3)
flutter run --release -d <udid>
  # Could not run build/ios/iphoneos/Runner.app on <udid>.
xcrun devicectl device info files ...              # no episodes/, no com.jhyelton.blankie.plist => position and download lost
xcrun devicectl device process launch --device <udid> com.jhyelton.blankie
  # Unable to launch com.jhyelton.blankie because it has an invalid code signature, inadequate
  # entitlements or its profile has not been explicitly trusted by the user.
  # => deleting the only app from the Personal Team also removed the certificate trust
# Trusted again: Settings > General > VPN & Device Management. App opened, Source: stream, 0:00:00.

# 5.1 Long session (no commands; on-device)
# Streamed >60 min locked; paused >30 min; seek to ~3:10:00 + play: started immediately.
```
