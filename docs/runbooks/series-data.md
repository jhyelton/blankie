# Series data: weekly review, overrides and the Patreon check

`data/series.json` says which episodes belong to which miniseries. The app fetches it from `main`. It comes from the Blank Check fan wiki, matched against the public feed, and a workflow regenerates it every Monday. This runbook covers what you do by hand: review and merge the weekly PR, write overrides, accept large wiki changes, and check matching against your own Patreon feed.

How the tool itself works, and how to develop on it, is in [`tools/series-data/README.md`](../../tools/series-data/README.md).

All commands run from `tools/series-data/` unless they say otherwise. The `security` and `check-patreon` commands are run by the owner on their Mac (tasks 8.1 and 8.2 of `series-data-pipeline`); the rest were run while writing this.

## 1. Reviewing the weekly PR

The `series-data update` workflow runs Mondays at 09:00 UTC. If the dataset changed, it opens a PR titled `chore(data): update series data` on the `series-data/update` branch, or refreshes the one that is already open. If nothing changed, there is no PR, and an update PR still open from an earlier week is closed (its data no longer matches the wiki).

The PR body is the generated report. Read it top to bottom:

1. **Guardrails overridden.** Only there if someone ran the workflow with the acceptance option (section 4). Check that each one is the change you meant to accept.
2. **Series membership changes.** Episodes that moved between series. This is where a bad wiki edit would show, so read it carefully. A new release joining an old director's series is normal.
3. **Added / Changed / Removed episodes.** New episodes are expected weekly. Title and date changes are wiki corrections; the episode's ID stays the same, so playback progress in the app is kept.
4. **Unmatched wiki episodes** and **Unmatched public feed items.** A wiki row the tool couldn't match to the public feed, or a feed item no wiki row matched. Usually a brand-new episode whose wiki title differs from the feed title. Fix each one with an override (section 3) in a separate PR.
5. **Patreon post IDs linked from more than one wiki row.** Two Special Features rows link to the same Patreon post, so one link is wrong. Neither episode gets the post ID hint until the wiki is fixed. Find the right post on Patreon and correct the row's audio link on the wiki.
6. **Feed items claimed by more than one episode**, **Series not on the Miniseries page**, **Acknowledged as unmatched, but now matched.** Informational. An unlisted series gets the category `other`; fixing the Miniseries page on the wiki is optional.

Also look at the diff of `data/series.json` itself if anything in the report surprises you.

## 2. Merging the weekly PR

The workflow opens its PR with `GITHUB_TOKEN`, and GitHub never runs other workflows on such PRs. So `ci-ok` never reports, and the `main` ruleset blocks a normal merge. The workflow run that opened the PR already ran every check the `series-data` CI job would (tests aren't affected by a data-only PR; schema validation, override resolution and the guardrails all ran inside `generate`).

1. Open the workflow run linked at the bottom of the PR body and confirm it's green.
2. Optionally, check out the branch and run the repository checks from `CONTRIBUTING.md`, plus the data check:

   ```bash
   git fetch origin series-data/update && git checkout series-data/update
   uv run series-data check
   ```

3. Merge from the GitHub UI with the ruleset's admin bypass. This is the only intended use of the bypass.

If using the bypass ever becomes routine or feels risky, switch the workflow to a GitHub App token: PRs opened with an App token do trigger `ci.yml`, so `ci-ok` reports normally and the bypass is no longer needed. That's a small follow-up change.

## 3. Writing overrides

Overrides live in `data/overrides.json`, a JSON list. Every entry needs an `op` and a `reason` (so that a year from now you know why it exists). Most also need a `target`, which is either:

- an **episode ID** from `data/series.json` (`"2024-01-25:blank-check-on-broadway"`). Prefer this for any episode that's already published: an ID stays on its episode even if the wiki renumbers rows. Or
- a **wiki number** (`"185"`, `"SF294"`; leading zeros as the wiki shows them, like `"033"`, are fine), for a row that isn't in `series.json` yet, and always for `exclude`. If the wiki later moves that number to a different row, the run fails and names the override; change its target to the episode's ID.

Overrides are applied in file order. One that doesn't resolve (a wiki number no row has, an ID no row matches any more, a GUID not in the feed) fails `generate` and names the override.

| `op` | Extra fields | Use it when |
|---|---|---|
| `fix` | `title` and/or `airDate` (`YYYY-MM-DD`) | The wiki has a typo. The episode keeps its ID. |
| `pinPublicGuid` | `guid` | The title differs too much to match. Copy the GUID from the "Unmatched public feed items" list. |
| `addToSeries` | `series` (a series ID) | The wiki is missing a membership. |
| `removeFromSeries` | `series` (a series ID) | The wiki has a wrong membership. |
| `exclude` | | A row that shouldn't be in the dataset at all. The target must be a wiki number: an excluded episode leaves `series.json`, so an episode ID would stop resolving. Excluding a published episode trips the "episode IDs disappeared" guardrail; accept it deliberately (section 4). |
| `ackUnmatchedWiki` | | A wiki row that will never be in the public feed (live shows, announcements). |
| `ackUnmatchedFeed` | `guid` (instead of `target`) | A feed item with no wiki row (the trailer). If the item ever leaves the feed (say the show replaces its trailer), every run fails with "no public feed item has that GUID" until you update or delete the override. |

Examples, all from the real file:

```json
{ "op": "fix", "target": "185", "airDate": "2018-09-30", "reason": "The wiki dates Space Jam 9/30/3018; it aired 2018-09-30." }
{ "op": "pinPublicGuid", "target": "480", "guid": "tag:audioboom.com,2024-05-31:/posts/8516682", "reason": "The feed drops the subtitle: 'Furiosa with Kyle Buchanan'." }
{ "op": "ackUnmatchedFeed", "guid": "tag:audioboom.com,2024-05-10:/posts/8503464", "reason": "The show trailer has no wiki row." }
```

Then:

1. Validate without touching the network. This is what the `series-data` CI job runs on your PR:

   ```bash
   uv run series-data check
   ```

   `pending:` lines are fine: they mean an override targets a wiki number that isn't in the committed dataset yet. `error:` lines fail the check, for example an episode ID or series ID that isn't in `series.json` (usually a typo).

2. To see the effect before opening the PR, regenerate locally. This fetches the wiki and feed (7 requests today: 3 wiki pages, 3 batches of redirect lookups and the feed) and rewrites `data/series.json`:

   ```bash
   uv run series-data generate --report /tmp/series-report.md
   ```

   Commit only `data/overrides.json`, and discard the regenerated dataset (`git checkout -- ../../data/series.json`). Every change to `series.json` should come from the workflow.

3. Open a PR (`fix(data): ...`). After it merges, the next Monday run picks the override up, or trigger the workflow by hand (section 4, without the acceptance option).

If a wiki fix is simple, consider also fixing the wiki itself. Once the wiki is right, the report lists any `ackUnmatchedWiki` that's no longer needed, and a `fix` that no longer changes anything can be deleted.

## 4. Accepting guardrail changes

A run fails, and opens no PR, if compared with the dataset on `main`:

- the number of episodes fell by more than 5, or by more than 1%,
- any published episode ID disappeared,
- any series lost episodes,
- more than 5% of published episodes changed series, or
- a published episode's public GUID or Patreon post ID changed to a different value.

The last one means an ID might now point at a different episode. The tool keeps IDs on their episodes when the wiki renumbers rows (it checks the title, date and hints, not only the number), so this firing usually means a wiki link or the feed changed; check that the episode named still has the right GUID or post.

GitHub emails you about the failed run. Open the run's log: the failing step lists each guardrail with the series and episodes involved. Then look at the wiki's recent changes to decide whether it's a mistake, vandalism, or a real reorganization.

- **Mistake or vandalism:** fix or revert it on the wiki (or add overrides) and wait for the next run.
- **Real change:** go to *Actions → series-data update → Run workflow*, tick **Propose the dataset even if guardrails fail**, and run it. The PR's **Guardrails overridden** section lists each guardrail you accepted.

Locally, the same is:

```bash
uv run series-data generate --accept-guardrail-changes --report /tmp/series-report.md
```

To debug a parser failure, every run uploads the raw wiki and feed responses as the `series-data-raw-<run id>` artifact (kept 30 days). Download it, unzip it to a directory, and replay it without the network:

```bash
uv run series-data generate --offline <dir> --output /tmp/series.json --report /tmp/series-report.md
```

## 5. Checking Patreon matching locally

The Patreon feed URL contains a personal access token. It must never be committed, logged, pasted into a PR or issue, or given to CI. `check-patreon` reads it from the macOS Keychain, keeps the feed in memory, and prints only titles, dates and dataset IDs.

1. Store the URL once. With nothing after `-w`, `security` prompts for the value, so it never lands in your shell history:

   ```bash
   security add-generic-password -s blankie-patreon-feed -a "$USER" -w
   ```

   To replace it later, add `-U` to the same command.

2. Run the check against the committed dataset:

   ```bash
   uv run series-data check-patreon
   ```

   It lists the Special Features episodes that matched the same feed item as another episode, then: those acknowledged with `ackUnmatchedWiki` in `data/overrides.json`, acknowledged ones that now match (that override can go), unmatched, ambiguous, matched by title and date, and matched by the Patreon post ID from the wiki. The exit code is 1 if anything unacknowledged is unmatched or ambiguous, or if two episodes share a feed item.

3. For each unmatched, ambiguous or shared episode, decide whether it's a genuine miss. Fix the wiki row's Patreon link (preferred), or add a `fix` or `ackUnmatchedWiki` override (section 3). Patreon video posts (announcements, the fashion show, some live events) are on the wiki but never in the podcast feed; acknowledge those with `ackUnmatchedWiki` and a reason saying so.

If the command says there is no URL in the Keychain, it hasn't made any network request; store the URL (step 1). If it reports an HTTP status such as 403, the token has probably been rotated: copy the current feed URL from Patreon and store it again with `-U`.
