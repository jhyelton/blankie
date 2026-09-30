# Installing blankie on an iPhone (free Apple ID)

This runbook takes a Mac with Xcode installed to blankie running on your iPhone, using a free Apple ID instead of a paid Apple Developer Program membership. It also covers the re-install you have to repeat every 7 days, when the free signature expires.

Every command here was actually run while writing it. The log is in [`docs/spikes/audio-spike-results.md`](../spikes/audio-spike-results.md#command-log).

**Tested with:** macOS 26.3.1, Xcode 26.6, Flutter 3.47.5, iPhone 12 Pro on iOS 26.6.2.

## Background: why this is different from a normal app install

- **Signing.** iOS only runs apps signed by a certificate it trusts. App Store apps are signed by Apple. Here, Xcode signs blankie with a *development certificate* tied to your Apple ID's free *Personal Team*, plus a *provisioning profile* listing which devices may run it. It's roughly like a self-signed TLS certificate that each device has to trust explicitly.
- **Expiry.** Free provisioning profiles are valid for 7 days. After that, iOS refuses to launch the app until you re-install it from the Mac (section 4).
- **Release builds.** Flutter *debug* builds only run with a debugger attached, so they won't launch from the home screen on their own. Daily-use installs are always *release* builds (`--release`).

## 1. One-time Mac setup

1. Check Xcode is installed:

   ```bash
   xcodebuild -version
   ```

2. Install the Flutter SDK with Homebrew. It lands in `/opt/homebrew/share/flutter`, with `flutter` and `dart` on your `PATH`.

   ```bash
   brew install --cask flutter
   ```

3. Optionally turn off Flutter's usage analytics:

   ```bash
   flutter --disable-analytics
   ```

4. Check the toolchain:

   ```bash
   flutter doctor -v
   ```

   **Flutter** and **Xcode** must show `[✓]`. If Xcode asks for extra components or CocoaPods, follow what `flutter doctor` prints. An `[✗]` for **Android toolchain** is expected and fine: blankie doesn't target Android yet.

5. Add your Apple ID to Xcode: **Xcode → Settings → Accounts → +**. Xcode creates a "*Your Name* (Personal Team)" team and an "Apple Development" certificate for it. You only do this once per Mac.

## 2. One-time iPhone setup

1. Connect the iPhone with a cable and unlock it. Tap **Trust This Computer** and enter the phone's passcode.
2. **Pair the phone in Xcode.** Open **Xcode → Window → Devices and Simulators**, select the iPhone, and accept any prompt on the phone. Trusting the computer in step 1 is *not* enough. Without this step, `flutter devices` reports the phone as unpaired (see section 6).
3. **Turn on Developer Mode** on the phone: **Settings → Privacy & Security → Developer Mode**. The option only appears after Xcode has paired with the phone. The phone restarts; confirm when it asks.
4. Check that Flutter can see the phone:

   ```bash
   flutter devices
   ```

   You should see a line like `Joshua's iPhone (mobile) • <udid> • ios • iOS 26.6.2`. The `<udid>` is the device ID used below.

## 3. First install

1. From a checkout of this repository, build a release build, install it and launch it:

   ```bash
   cd app
   flutter run --release -d <udid>
   ```

   Flutter signs the app automatically with the Personal Team set in the Xcode project. The first build takes about a minute.

2. **The first launch fails**, and that's expected: iOS doesn't trust your developer certificate yet. `flutter run` prints `Could not run build/ios/iphoneos/Runner.app on <udid>`, but the app *is* installed.
3. On the iPhone, open **Settings → General → VPN & Device Management**. Under **Developer App**, tap **Apple Development: *your Apple ID***, tap **Trust**, and confirm.
4. Run the same command again:

   ```bash
   flutter run --release -d <udid>
   ```

   This time it prints `Installing and launching...` followed by `Flutter run key commands.`, and blankie opens on the phone.
5. Press `q` in the terminal to detach, or just close it. The app keeps running.
6. Unplug the phone, swipe blankie away in the app switcher, and open it from its home-screen icon. It should launch normally with no Mac attached.

Trust lasts as long as at least one app signed by your Personal Team stays installed on the phone. Re-installing over the existing app skips steps 2–3. If you delete blankie and it was your only app from that team, iOS also removes the trust, and the next install fails to launch until you trust the certificate again (steps 2–4).

## 4. Every 7 days: re-install

### Symptoms

Seven days after the last install, the free provisioning profile expires and iOS stops launching blankie. Nothing warns you beforehand.

> **Not yet observed.** The spike couldn't wait 7 days. The expected symptom is that tapping the icon opens nothing, or the app flashes open and closes straight away. The follow-up change `ios-reinstall-verification` records the exact behavior and any message iOS shows, and updates this section.

It's easiest to re-install on a fixed day each week, before it expires. Re-installing early is harmless.

### Re-install

1. Connect the iPhone with a cable and unlock it.
2. Check that Flutter sees it:

   ```bash
   flutter devices
   ```

3. From a checkout of this repository, build and install over the existing app:

   ```bash
   cd app
   flutter run --release -d <udid>
   ```

   It prints `Installing and launching...` and then `Flutter run key commands.`, and blankie opens on the phone.
4. Press `q` or close the terminal, then unplug.

You don't need to trust the certificate again, because the installed app keeps the trust in place.

**Do not delete blankie before re-installing.** Install over the existing app.

### What survives

Observed on 2026-09-30 by re-installing over an installed copy (task 5.2):

| Data | Re-install over the existing app | Delete the app, then install |
|---|---|---|
| Playback position | Kept | Lost |
| Downloaded episodes | Kept | Lost |

A re-install over the existing app keeps its data container, because the bundle ID (`com.jhyelton.blankie`) and the team are the same. You can check from the Mac: the files under `Library/Application Support/episodes/` and `Library/Preferences/` have the same sizes and timestamps before and after the install.

```bash
xcrun devicectl device info files --device <udid> --domain-type appDataContainer --domain-identifier com.jhyelton.blankie
```

Deleting the app removes its whole data container. Afterwards the `devicectl` command above fails with `The system failed to get a list of files on the remote device.` Deleting the app also removes the certificate trust if blankie was the only app from your team (see section 3).

> The re-install observed so far happened while the old profile was still valid. `ios-reinstall-verification` repeats it after a real expiry, when Xcode issues a new profile, and confirms the data is kept then too.

**Remove from Home Screen vs Delete App.** Long-pressing the icon and choosing **Remove App → Remove from Home Screen** only hides the icon; the app and its data stay installed. Only **Delete App** removes the data.

## 5. Limitations of free signing

These affect daily use. They are what you give up by not paying for the Apple Developer Program.

- **7-day expiry.** The free provisioning profile expires 7 days after the install. After that, iOS refuses to launch blankie until you re-install from the Mac (section 4). Nothing warns you in advance; the app just stops opening.
- **App-count limit.** A free Personal Team can have at most **3 apps** installed on a device at the same time. Installing a fourth fails in Xcode until you delete one of the others.
- **App ID limit.** A free Personal Team can register at most **10 new App IDs (bundle identifiers) per 7 days**. blankie always uses `com.jhyelton.blankie`, so this only matters if you experiment with other bundle IDs.
- **Needs the Mac.** Every install and re-install needs this Mac and Xcode. Once the phone has been paired, it doesn't have to be on the cable: when the phone and the Mac are on the same Wi-Fi, `flutter devices` lists it as `(wireless)` and `flutter run --release` installs over the network. The phone must be unlocked for the launch.
- **Restricted capabilities.** Free teams can't use capabilities such as push notifications, iCloud, or App Groups. The audio spike uses none of them: background audio and background downloads work with free signing.
- **One Apple ID's devices only.** The app is provisioned for your registered devices. It can't be shared through TestFlight or with other people's phones.

## 6. Troubleshooting

Each entry below was hit during the audio spike. The exact output is in the [command log](../spikes/audio-spike-results.md#command-log).

### `flutter doctor`: `Unable to locate Android SDK.`

The **Android toolchain** line shows `[✗]`. This is expected: blankie doesn't target Android yet. Ignore it, as long as **Flutter** and **Xcode** show `[✓]`.

### `flutter doctor`: `Error: Browsing on the local area network for <name>'s iPhone. … (code -27)`

This appears under **Connected device** when the phone isn't connected by cable, or hasn't been paired and set to Developer Mode yet. It doesn't stop anything. Connect the phone and finish section 2.

### `flutter devices`: `<name>'s iPhone is not available because it is unpaired. … (code -29)`

The phone is connected and trusts the Mac, but Xcode hasn't paired with it. Tapping **Trust This Computer** is not the same as pairing.

**Fix:** open **Xcode → Window → Devices and Simulators**, select the phone, and accept the prompts on the phone. Then turn on Developer Mode if you haven't (section 2, step 3), and run `flutter devices` again.

### `flutter run`: `Could not run build/ios/iphoneos/Runner.app on <udid>.`

The build and install worked, but iOS refused to launch the app. `flutter run` doesn't say why, and it suggests opening Xcode, which you don't need to do. To see the reason, launch the app from the Mac:

```bash
xcrun devicectl device process launch --device <udid> com.jhyelton.blankie
```

During the spike the reason was always the next error.

### `Unable to launch com.jhyelton.blankie because it has an invalid code signature, inadequate entitlements or its profile has not been explicitly trusted by the user.`

The phone doesn't trust your developer certificate. This happens:

- on the very first install, and
- after you delete blankie when it was the only app from your Personal Team, because deleting the app also removes the trust.

**Fix:** go to **Settings → General → VPN & Device Management**, tap **Apple Development: *your Apple ID***, then **Trust**. Then open blankie from its icon, or run `flutter run --release -d <udid>` again.

### I deleted blankie, but it's still installed with all its data

Long-pressing the icon and choosing **Remove App → Remove from Home Screen** only hides the icon. `xcrun devicectl device info apps --device <udid>` still lists Blankie, and a re-install keeps the download and the saved position.

**Fix:** to really delete it, choose **Remove App → Delete App**, or use **Settings → General → iPhone Storage → Blankie → Delete App**. Deleting loses the saved position and the downloads (section 4), so only do it on purpose.

### `Unable to launch com.jhyelton.blankie because the device was not, or could not be, unlocked.`

The install worked, but the phone was locked, so iOS wouldn't open the app. `flutter run` only prints `Could not run build/ios/iphoneos/Runner.app on <udid>.` This one is easy to hit on a wireless install, because the phone isn't in your hand.

**Fix:** unlock the phone and run `flutter run --release -d <udid>` again, or just open blankie from its icon.

### `devicectl … info files`: `The system failed to get a list of files on the remote device.`

This is what you see when blankie isn't installed, so there's no data container to list. After a real delete, it confirms that the app's data is gone.
