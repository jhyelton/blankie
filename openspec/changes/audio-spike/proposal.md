# Proposal

## Why

blankie is going to be a Flutter app that replaces Pocket Casts for daily listening to Blank Check, first on an iPhone and then on Android. The riskiest part of that plan is platform plumbing, not app logic: 2–3 hour episodes have to keep playing with the screen locked, be controllable from the lock screen and headphones, survive interruptions, resume where they left off, and download in the background. Before we build feeds, series data, or the two-lane UI, we need proof on a real iPhone that Flutter can do these reliably. If it can't, we want to know now, while switching stacks is still cheap.

## What Changes

- Create the Flutter project that later changes will build on (iOS target only for now).
- Build a minimal, throwaway spike screen that plays one hard-coded public Blank Check episode, both streamed and downloaded.
- Prove background playback, lock-screen and headphone controls, interruption handling, and position resume on a physical iPhone.
- Prove that a full-length episode downloads in the background and plays offline.
- Write a runbook for installing blankie on an iPhone with a free Apple ID, including the recurring 7-day re-install.
- Record the go/no-go result for the Flutter stack against explicit pass/fail criteria.

## Capabilities

### New Capabilities

- `audio-playback`: playing an episode, controlling it from outside the app (lock screen, Control Center, headphones), handling audio interruptions, and resuming from the last saved position.
- `episode-download`: downloading an episode's audio to the device in the background and playing it without a network connection.
- `ios-device-install`: the documented, repeatable process for installing blankie on the owner's iPhone with free Apple signing and re-installing it when the 7-day signature expires.

### Modified Capabilities

None. No specs exist yet.

## Impact

- **New code**: a Flutter project at `app/` with the iOS runner, audio/background/download dependencies, and the iOS background-audio configuration.
- **New docs**: an iOS device install runbook and a spike results record under `docs/`.
- **Tooling**: the Flutter SDK must be installed on the development Mac (Xcode 26.6 is already present).
- **External**: streams and downloads one episode from the public Megaphone feed. The Patreon feed and its token are not used anywhere in this change.
- **Gate**: `series-data-pipeline` does not depend on this change and can proceed in parallel. `blankie-v1` must not start until this spike records a pass.
