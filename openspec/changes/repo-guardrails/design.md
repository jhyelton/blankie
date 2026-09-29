# Design

## Context

- `jhyelton/blankie` is **public**, on a personal account, with one owner.
  - Current settings: merge commits, squash and rebase are all allowed; branches aren't deleted on merge; secret scanning, push protection and Dependabot security updates are all **disabled**.
  - There's no `.github/` directory yet.
- OpenSpec CLI: `@fission-ai/openspec` 1.13.2, installed globally with npm.
- Patreon URL shapes (seen in a real feed; only the structure is recorded here, not values):
  - feed URL: `https://www.patreon.com/rss/<creatorId>?auth=<token>&show=<id>`
  - enclosure URLs: `https://www.patreon.com/api/rss/u/<per-user-token>/…?sig=<signature>`

  Both carry per-user credentials.
- Pending changes that interact with this one:
  - `series-data-pipeline` (PR #3) plans its own path-filtered check workflow, and a bot that opens PRs with `GITHUB_TOKEN`.
  - `audio-spike` (PR #1) adds an app `.gitignore` and a root entry for feed dumps.

## Goals / Non-Goals

**Goals:**
- Merging to `main` requires a PR with a green aggregate check, even for the owner, apart from an explicit bypass limited to PRs.
- A Patreon URL can't reach the public repo without at least two independent systems failing: push protection or the CI scan, plus the optional local hook.
- Adding checks later means editing one workflow, not changing branch protection.

**Non-Goals:**
- Required reviews or CODEOWNERS. With one person, GitHub can't satisfy them.
- Signed commits, release automation, versioning.
- Language-specific jobs (Flutter, Python). Their changes add those jobs to `ci.yml`.

## Decisions

### D1. One always-running workflow and an aggregate `ci-ok` check
`ci.yml` runs on every `pull_request` and on pushes to `main`, with **no workflow-level path filters**.
- A `changes` job uses `dorny/paths-filter` to work out which areas changed.
- Area jobs (`openspec`, `secrets`, `pr-title`, and later `app` and `series-data`) run conditionally.
- A final `ci-ok` job with `if: always()` needs all area jobs and fails if any of them failed or was cancelled. A skipped job counts as OK.

Only `ci-ok` is required in the ruleset.
- *Why:* a required check from a workflow that path filters skipped **never reports**, which leaves the PR stuck at "Expected — waiting". An aggregate check that always runs avoids that. It also means new jobs don't need ruleset edits.
- *Alternative:* one required check per workflow. That's fragile with path filters and needs ruleset changes for every new job.

### D2. The `openspec` job
Runs when `openspec/**` changes. It installs `@fission-ai/openspec@1.13.2`, pinned and bumped deliberately, then runs `openspec validate --all --strict`.

### D3. The `pr-title` job
`amannn/action-semantic-pull-request` enforces Conventional Commits on the PR title. Squash-merge uses the PR title as the commit message (D5), so this keeps `main`'s history consistent without any commit-message hooks.

Allowed types: `feat, fix, docs, chore, ci, refactor, test, build, perf`.

### D4. Secret scanning in layers
1. **GitHub secret scanning + push protection:** enabled through `gh api` (the `security_and_analysis` settings). It covers known provider tokens. Custom patterns aren't available on personal accounts, so it doesn't know Patreon URLs.
2. **gitleaks in CI** (`secrets` job, runs on every PR): uses `gitleaks/gitleaks-action` with `.gitleaks.toml`, which extends the default rules with:
   - `patreon-rss-feed`: `patreon\.com/rss/\d+\?[^\s"'<>]*\bauth=`
   - `patreon-rss-enclosure`: `patreon\.com/api/rss/u/[A-Za-z0-9_-]{16,}`
   - `patreon-signed-url`: `patreon(?:usercontent)?\.com/[^\s"'<>]*[?&]sig=`

   The job scans the PR's commits, and a finding fails `ci-ok`. Test fixtures must use synthetic values that don't match these patterns (e.g. `…/rss/0?auth=REDACTED` would match `auth=`, so fixtures use `auth-redacted` instead).
3. **Optional local pre-commit hook:** `.pre-commit-config.yaml` runs the same gitleaks config before each commit. It's documented in `CONTRIBUTING.md` and installed with `pre-commit install`. It's optional because it depends on the owner's machine.

A gitleaks finding in CI means the value has **already been pushed to a public branch**. `CONTRIBUTING.md` spells out the response: treat the secret as leaked, rotate it at Patreon, then clean up the history. That's why layers 1 and 3, which block before the push, matter.

- *Alternative:* the `trufflehog` action. Comparable, but gitleaks' TOML custom rules are simpler to read and to test with `gitleaks detect` locally.

### D5. Repository ruleset and merge settings
Applied through `gh api`, with the JSON committed to `.github/rulesets/main.json` so the configuration is reviewable and can be re-applied.

- **Ruleset `main-protection`**, targeting the default branch:
  - `pull_request` (0 required approvals, dismiss stale approvals off)
  - `required_status_checks` (`ci-ok`, strict: branch must be up to date)
  - `non_fast_forward`
  - `deletion`
  - `required_linear_history`
- **Bypass:** the actor `RepositoryRole: admin` with `bypass_mode: pull_request`. The owner can merge a PR whose checks didn't run, which is needed for `series-data-pipeline`'s `GITHUB_TOKEN` bot PRs, but can never push directly to `main`. `CONTRIBUTING.md` says to use the bypass only for bot PRs, and only after re-running the checks locally.
- **Merge settings:**
  - squash only (merge and rebase merges disabled)
  - squash commit title = PR title, message = PR body
  - `delete_branch_on_merge: true`
  - auto-merge left off

- *Alternative:* classic branch protection. Rulesets are newer, can be exported as JSON, and are what GitHub recommends.
- *Alternative:* a GitHub App token for the bot so its PRs trigger CI. That's more setup, and can be revisited if the bypass turns into a habit.

### D6. Supply chain
- Third-party actions are pinned to full commit SHAs, with a trailing `# vX.Y.Z` comment.
- `.github/dependabot.yml` updates `github-actions` weekly, grouped into one PR. Later changes add `pub` and `pip` ecosystems.
- Dependabot security updates are enabled.
- Workflow permissions default to `contents: read`. Jobs raise permissions only where they need to.

### D7. Docs and hygiene
- `CONTRIBUTING.md` covers the OpenSpec lifecycle (explore → propose → plan PR → apply → implementation PR → archive), branch and commit naming, how to review your own PR, when the bypass is acceptable, and what to do if a secret leaks.
- The PR template has a checklist: linked OpenSpec change, `openspec validate` passing, no secrets or feed dumps, and docs updated.
- The root `.gitignore` covers `*.rss.xml`, `feeds/`, `.env*`, `*.local.*` and OS junk. (`audio-spike` task 1.3 overlaps with this. Whichever lands second just confirms the entries are present.)
- The README links to `CONTRIBUTING.md` and the runbooks.

## Risks / Trade-offs

- **[Risk] Owner bypass weakens the gate.** → *Mitigation:* bypass is limited to PRs (never direct pushes). `CONTRIBUTING.md` restricts it to bot PRs, and the ruleset JSON is under review like any other code. *Accepted* for a solo project.
- **[Risk] gitleaks false positives** from the Patreon rules matching legitimate text, such as docs describing URL shapes. → *Mitigation:* docs describe shapes with placeholders that don't match the patterns. `.gitleaks.toml` allowlists paths only when strictly needed, and every allowlist entry is commented.
- **[Risk] A leak reaches a public branch before CI catches it.** → *Mitigation:* push protection and the local hook come first. `CONTRIBUTING.md` has the incident steps.
- **[Risk] A strict "up to date" requirement means rebasing and re-running CI before each merge.** → *Accepted.* Traffic is low, and it prevents semantic merge conflicts.
- **[Trade-off] A pinned OpenSpec CLI version can drift from the owner's local version.** → Dependabot doesn't cover npm-in-workflow pins, so `CONTRIBUTING.md` notes bumping it deliberately.

## Migration Plan

1. Merge this change's implementation PR while the ruleset isn't active yet. It adds the `ci.yml` that produces `ci-ok`.
2. Once `ci-ok` has reported at least once on `main`, apply the ruleset. Applying it earlier would require a check that GitHub has never seen.
3. Rebase open plan PRs (#1, #3, #4, and #2 if still open) so they get `ci-ok`.

**Rollback:** delete or disable the ruleset through `gh api`. The workflow can stay.
