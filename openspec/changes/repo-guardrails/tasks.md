# Tasks

## 1. Hygiene files

- [x] 1.1 Add a root `.gitignore` with the entries from design D7. Verify: `git check-ignore -v feeds/x.rss.xml .env.local` reports both as ignored.
- [x] 1.2 Add `.gitleaks.toml`, extending the default rules with the three Patreon rules from design D4. Add a test script (`scripts/test-gitleaks-rules.sh`) that writes synthetic matching and non-matching samples to a temporary directory **outside the repo** and runs `gitleaks detect --no-git` against it. Verify: the script reports that each Patreon rule fires on its matching sample and stays silent on placeholder text such as `auth-redacted`.
- [x] 1.3 Add `.pre-commit-config.yaml` with the gitleaks hook using `.gitleaks.toml`. Verify: with `pre-commit install` done, trying to commit a synthetic matching sample is blocked. Unstage the sample afterwards and don't commit it.

## 2. CI workflow

- [ ] 2.1 Add `.github/workflows/ci.yml` per design D1–D4: the `changes` paths job; the `openspec`, `secrets` and `pr-title` jobs; and the `ci-ok` aggregator with `if: always()`. Default permissions are `contents: read`, and every third-party action is SHA-pinned (D6). Verify: on this change's PR, `ci-ok` passes; a PR touching only `README.md` still reports `ci-ok` (with `openspec` skipped).
- [ ] 2.2 Test the failure paths on throwaway branches, closing the PRs without merging:
  - a PR with an invalid spec
  - a PR titled `update stuff`
  - a PR containing a synthetic Patreon-shaped string

  Verify: each makes `ci-ok` fail, with the right job named. Delete the branches afterwards.
- [ ] 2.3 Add `.github/dependabot.yml` for `github-actions` (weekly, grouped). Verify: Insights → Dependency graph → Dependabot lists the configuration without errors.

## 3. Docs and templates

- [ ] 3.1 Add `.github/pull_request_template.md` with the checklist from design D7. Verify: a new PR's description is pre-filled with it.
- [x] 3.2 Write `CONTRIBUTING.md` (design D7), covering: the OpenSpec lifecycle with commands, branch and commit naming, the self-review routine, bypass rules, installing the pre-commit hook, bumping the pinned OpenSpec CLI, and the secret-leak response. Update `README.md` to link to it. Verify: every command in `CONTRIBUTING.md` was actually run in this change.

## 4. Repository settings (owner confirms each `gh api` call before it runs)

- [ ] 4.1 Enable secret scanning, push protection and Dependabot security updates through `gh api -X PATCH repos/jhyelton/blankie` (`security_and_analysis`). Verify: `gh api repos/jhyelton/blankie --jq .security_and_analysis` shows all three `enabled`.
- [ ] 4.2 Set merge options through `gh api -X PATCH repos/jhyelton/blankie`: squash only, PR title/body as the squash commit, `delete_branch_on_merge: true` (design D5). Verify: `gh repo view --json squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed,deleteBranchOnMerge` shows `true,false,false,true`.
- [ ] 4.3 After this change's implementation PR is merged and `ci-ok` has run on `main`, commit `.github/rulesets/main.json` (design D5) in a follow-up PR and apply it with `gh api -X POST repos/jhyelton/blankie/rulesets --input .github/rulesets/main.json`. Verify:
  - `gh api repos/jhyelton/blankie/rulesets` lists `main-protection` as active
  - `git push origin HEAD:main` from a scratch commit is rejected
  - a PR without a green `ci-ok` shows as blocked
- [ ] 4.4 Rebase or update any open plan PRs so they report `ci-ok` under the new rules. Verify: every open PR shows `ci-ok` passing, or a real failure to fix.
