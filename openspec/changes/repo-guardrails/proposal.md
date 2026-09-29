# Proposal

## Why

blankie is a solo project that follows team-grade practices. Every change goes through a PR that the owner reviews and merges. Without automated gates, that discipline depends entirely on memory. The repository is now public, and the owner's private Patreon feed URL, a personal access token, is handled on this machine during development, so a single accidental commit would publish it. This change adds the guardrails before any implementation PRs land: CI that always reports, protection on `main`, secret scanning tuned for Patreon URLs, and a documented workflow.

## What Changes

- Add one always-running CI workflow with a single aggregate required check. It validates OpenSpec changes and specs, checks that PR titles follow Conventional Commits, and scans for secrets, including custom Patreon feed and enclosure URL patterns. Later changes add their jobs to this workflow rather than creating separately required workflows.
- Protect `main` with a repository ruleset:
  - changes only through PRs (no required approvals, since GitHub doesn't allow approving your own PR)
  - the aggregate check must pass
  - no force pushes or deletion
  - linear history
- Set merge options: squash-merge only, use the PR title as the commit message, and delete branches after merge.
- Enable GitHub secret scanning and push protection, which are free for public repositories.
- Add Dependabot for GitHub Actions updates, with third-party actions pinned to commit SHAs.
- Add a pull request template, a `CONTRIBUTING.md` that describes the OpenSpec plan-PR → implementation-PR → archive workflow, a root `.gitignore` for feed dumps and local secrets, and an optional local pre-commit secret scan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is repository tooling and process with no product behavior, so the change sets `skip_specs: true`.

## Impact

- **New files:** `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.github/pull_request_template.md`, `.gitleaks.toml`, `.gitignore`, `.pre-commit-config.yaml`, `CONTRIBUTING.md`, and a README update.
- **Repository settings** (changed through `gh api` with the owner's confirmation): the ruleset on `main`, merge options, and secret scanning and push protection.
- **Other changes:**
  - `series-data-pipeline` currently plans a separate path-filtered `series-data-check.yml`. It should instead add jobs to `ci.yml`, because a required check that path filters skip never reports and blocks merges.
  - `series-data-pipeline`'s bot PRs (opened with `GITHUB_TOKEN`) don't trigger CI. The ruleset's owner bypass, limited to PRs, is how those get merged.
- **Ordering:** apply this before any implementation PR, so every implementation PR is gated from the start.
