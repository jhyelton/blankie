# Proposal

## Why

Lane B ("re-listen to a miniseries in order") needs to know which episodes belong to which series. Neither feed carries that information: there is no season/episode metadata, titles never name the series, and new-release episodes air in the middle of miniseries. The community-maintained fan wiki (blank-check.fandom.com) already tracks series membership for every main-feed and Special Features episode, including the tricky cases. blankie needs that knowledge as a clean, validated, versioned dataset that the app can fetch. The dataset shouldn't depend on the app's stack, so this work can start before the `audio-spike` gate is decided.

## What Changes

- Add a Python tool that reads the wiki's *Episodes*, *Blank Check: Special Features* and *Miniseries* pages via the MediaWiki API and produces `data/series.json`: every episode with a stable ID, and every series with its ordered episodes and attribution.
- Match wiki rows to the public feed to attach public GUID/title hints. Include the Patreon post IDs the wiki already links to, so the app can match Patreon episodes exactly.
- Add a hand-edited `data/overrides.json` for fixing wiki typos, pinning matches, and acknowledging known mismatches.
- Define the title-normalization and matching rules once, as shared JSON test cases (`contracts/matching-vectors.json`) that both this Python tool and the future app matcher must pass.
- Add a weekly GitHub Actions workflow (plus manual trigger) that regenerates the data, validates it, and opens or updates a PR listing unmatched items. The workflow fails, and opens no PR, on schema errors or on signs of breakage or vandalism.
- Add an optional local-only command that checks matching against the owner's Patreon feed, reads the feed URL from the macOS Keychain, and prints a redacted report.
- Publish `data/series.json` from `main` at a stable raw GitHub URL for the app to fetch.

## Capabilities

### New Capabilities

- `series-data`: the published dataset. Its content, stable episode IDs, series ordering and membership, feed-match hints, overrides, attribution, where it's published, and how it gets updated.
- `episode-matching`: the platform-neutral rules for normalizing titles and matching wiki episodes to feed items, defined by shared test cases.
- `series-data-validation`: the checks that keep bad data off `main`. That covers schema validation, breakage and vandalism guardrails, unmatched-item reporting, and the local Patreon check with its redaction guarantees.

### Modified Capabilities

None.

## Impact

- **New code**: `tools/series-data/` (Python package, tests), `contracts/matching-vectors.json`, `data/series.schema.json`, `data/series.json`, `data/overrides.json`, `.github/workflows/series-data-update.yml` for the weekly update, and a `series-data` job added to the repository's `ci.yml` for PR validation.
- **New docs**: `tools/series-data/README.md` and `docs/runbooks/series-data.md`, covering how to review the weekly PR, write overrides, and run the local Patreon check.
- **External systems**: reads the fan wiki's MediaWiki API (about 3 requests per week, with an identifying User-Agent) and the public Megaphone feed. Wiki content is CC BY-SA; attribution ships inside `series.json`.
- **Repository settings**: requires the repo to be public for the raw URL to be fetchable without auth, and requires "Allow GitHub Actions to create pull requests" to be enabled.
- **Secrets**: none. The Patreon feed is never used in CI. See `series-data-validation`.
- **Depends on** `repo-guardrails` being applied first. That change creates `ci.yml` with its always-running `ci-ok` aggregate check, the `main` ruleset, and the PR-only admin bypass used to merge this change's bot PRs.
- **Downstream**: `blankie-v1` will depend on the `series-data` contract and the `episode-matching` test cases.
