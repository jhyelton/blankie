# Tasks

## 1. Verify against a real expiry

- [ ] 1.1 When blankie stops launching after its free-signing signature expires, record the date, iOS version, and the exact symptom (error dialog text or launch behavior). Verify: the observation is written in the "Signature expired" row of `docs/spikes/audio-spike-results.md`.
- [ ] 1.2 Follow `docs/runbooks/ios-device-install.md` section 4 exactly as written, noting every step that was wrong, missing, or unclear. Verify: blankie launches from the home screen again with the Mac unplugged.
- [ ] 1.3 Compare what actually survived the re-install (playback position, downloaded episode) with what the runbook says. Verify: the observed behavior is recorded next to the runbook's claim in the results file.

## 2. Correct the docs

- [ ] 2.1 Update runbook sections 4 (re-install) and 6 (troubleshooting) with the corrections found in 1.1–1.3. Verify: each correction noted in group 1 is reflected in the runbook, and the section 4 symptoms match what was observed in 1.1.
- [ ] 2.2 Change the "Signature expired" row in `docs/spikes/audio-spike-results.md` from DEFERRED to PASS/FAIL, with notes. Verify: the results file no longer contains a DEFERRED entry.
