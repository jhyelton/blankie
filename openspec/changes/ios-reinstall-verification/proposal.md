# Proposal

## Why

The `audio-spike` change writes the iOS re-install runbook from a re-install done on purpose, but a real free-signing expiry only happens 7 days after install. We need to check the runbook against an actual expiry before trusting it every week. That check can't finish inside the spike, and the spike's GO/NO-GO decision shouldn't wait on it, so it lives here as a small follow-up.

## What Changes

- When the first real 7-day signature expiry happens, follow `docs/runbooks/ios-device-install.md` section 4 exactly, as written.
- Fix anything in the runbook that didn't match: symptoms, commands, and what data survives.
- Update the "Signature expired" row in `docs/spikes/audio-spike-results.md` from DEFERRED to PASS/FAIL.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This change verifies the existing `ios-device-install` requirements (introduced by `audio-spike`) and corrects documentation. No required behavior changes, so the change sets `skip_specs: true`.

## Impact

- **Docs only**: `docs/runbooks/ios-device-install.md` and `docs/spikes/audio-spike-results.md`.
- **Depends on** `audio-spike` being implemented and installed on the iPhone. It can't start until at least 7 days after that install.
- No app code changes are expected. If the runbook can't be made to work without code changes, stop and open a new change instead.
