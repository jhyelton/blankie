# Contributing to blankie

blankie is a solo project that follows team-grade practices. Every change goes through a PR, and `main` only moves when the `ci-ok` check is green. This file describes how that works.

## The OpenSpec lifecycle

Product and tooling changes are planned with [OpenSpec](https://github.com/Fission-AI/OpenSpec) before any code is written. Each change lives in `openspec/changes/<change-name>/` until it's archived.

1. **Explore** (optional): think the idea through with `/opsx:explore`. Nothing is written yet.
2. **Propose**: `/opsx:propose` writes the change's artifacts: `proposal.md`, `design.md`, `specs/` (unless the change sets `skip_specs`) and `tasks.md`.
3. **Plan PR**: commit only the artifacts under `openspec/changes/<change-name>/` and open a PR, titled like `docs(spec): propose <change-name>`. Review and merge it.
4. **Apply**: on a new branch, `/opsx:apply <change-name>` works through `tasks.md` and ticks off each task as it's done.
5. **Implementation PR**: open a second PR with the code and the ticked-off `tasks.md`. Before opening it, run `/code-review` on the branch and fix what it finds. A review caught four async bugs in the audio-spike PR after it was opened; reviewing first keeps those fixes out of the PR's history.
6. **Archive**: the last commit of the implementation PR is `/opsx:archive <change-name>`, which moves the change to `openspec/changes/archive/` and merges its spec deltas into `openspec/specs/`. Only archive a change when every task is done. Tasks that must wait (for example, on time passing) move to a follow-up change.

Useful CLI commands:

```bash
openspec list
openspec status --change repo-guardrails
openspec validate --all --strict
```

`openspec validate --all --strict` is what the CI `openspec` job runs. Run it before pushing any change under `openspec/`.

## Branches and commits

- Branch names contain the change name and what the branch does, e.g. `claude/propose-audio-spike` or `claude/apply-repo-guardrails`. The prefix doesn't matter.
- Commits and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/). Allowed types: `feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `test`, `build`, `perf`. Common scopes: `spec` for OpenSpec artifacts, `app`, `data`, `ci`.
- PRs are **squash-merged**, and the PR title becomes the commit on `main`. The CI `pr-title` job checks the title, so individual commits on a branch aren't checked.

## Reviewing your own PR

GitHub doesn't let you approve your own PR, so the ruleset requires no approvals. The review is a routine instead:

1. Fill in the PR template's checklist honestly.
2. Read the full diff on GitHub, not just in your editor. Look for stray files, debug output, and anything that looks like a URL with a token in it.
3. Wait for `ci-ok` to go green. If `main` has moved, update the branch and let CI run again. The ruleset requires the branch to be up to date.
4. Squash-merge. The branch is deleted automatically.

## Bypassing the rules

The `main` ruleset lets the repository admin bypass its checks, but only when merging a PR, never by pushing directly to `main`.

Use the bypass **only** for PRs opened by bots with `GITHUB_TOKEN` (such as the series-data scraper). GitHub doesn't run CI on those PRs, so `ci-ok` never reports. Before bypassing, check out the bot's branch and run the checks locally:

```bash
openspec validate --all --strict
gitleaks detect --no-banner --config .gitleaks.toml --redact
```

Then merge from the GitHub UI with the bypass option. Never bypass your own PRs; fix what CI reports instead.

## Keeping secrets out

The repository is public. The Patreon feed URL, and every Patreon feed XML file, contain a personal access token. They must never be committed. Test fixtures must be synthetic or redacted, and must not match the patterns in `.gitleaks.toml`: use placeholders like `auth-redacted` or `<creatorId>` instead of realistic values.

Three layers catch leaks:

1. **GitHub push protection** rejects pushes that contain known provider tokens. It doesn't know Patreon URLs.
2. **The CI `secrets` job** runs gitleaks with `.gitleaks.toml` on every PR and push to `main`. By the time it fails, the value is already on a public branch.
3. **The local pre-commit hook** (optional, but recommended) runs the same gitleaks config before each commit, so a leak never leaves your machine.

### Installing the pre-commit hook

```bash
brew install gitleaks pre-commit
pre-commit install
pre-commit run --all-files
```

The hook runs automatically on every `git commit` after that.

### Testing the gitleaks rules

When you change `.gitleaks.toml`, run:

```bash
scripts/test-gitleaks-rules.sh
```

It writes synthetic samples to a temporary directory outside the repo and checks that each Patreon rule fires on a matching sample and stays silent on placeholders.

### If a secret leaks

If the CI `secrets` job fails, or you find a Patreon URL anywhere on GitHub, **treat the token as leaked**. That's true even if you delete the branch right away: the repo is public, and forks, caches and PR refs can keep a copy.

1. **Rotate first.** Reset your private RSS link at Patreon so the old token stops working, then update every podcast app and local config that uses the feed.
2. **Stop the spread.** Close the PR without merging and delete the branch.
3. **Clean up history if the value reached `main`.** Follow GitHub's guide, [Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). It needs a history rewrite and a force push, so the ruleset has to be disabled for the duration. Re-enable it afterwards.
4. **Record what happened** in an issue: what leaked (without the value), how it got past the hook, and what changed to stop it happening again.

Rotation is the step that matters. History cleanup only limits who can still find a token that no longer works.

## CI

All checks live in one workflow, `.github/workflows/ci.yml`, which runs on every PR and every push to `main`. The final `ci-ok` job fails if any other job failed or was cancelled; skipped jobs are fine. `ci-ok` is the only check the ruleset requires.

To add a check, add a job to `ci.yml` and list it under `ci-ok.needs`. If it only matters for some paths, add a filter to the `changes` job and gate the job on its output. Don't add a separate workflow as a required check: a required check from a workflow that path filters skip never reports, and the PR gets stuck.

Third-party actions are pinned to full commit SHAs. Dependabot opens a weekly PR to bump them.

### Bumping the OpenSpec CLI

The `openspec` job pins `@fission-ai/openspec` to an exact version, and Dependabot doesn't track it. To bump it, check the latest release:

```bash
npm view @fission-ai/openspec version
```

Update the version in `ci.yml` and in your global install, run `openspec validate --all --strict`, and open a `ci:` PR.
