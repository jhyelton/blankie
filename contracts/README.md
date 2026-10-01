# Contracts

Files in this directory are shared between implementations. The Python tool in `tools/series-data/` loads them in its tests today, and the app's matcher (Dart, in `blankie-v1`) must load the same files in its tests. If an implementation disagrees with a case, the implementation is wrong.

## `matching-vectors.json`

The test cases for the `episode-matching` spec: how titles are normalized, and how a wiki episode is matched to a feed item. `matching-vectors.schema.json` describes the file's shape.

### Normalization cases

```json
{ "name": "apostrophe removed", "input": "Alice Doesn't Live Here Anymore", "expected": "alice-doesnt-live-here-anymore" }
```

`normalize(input)` must return exactly `expected`. The steps, in order:

1. Remove HTML tags (`<...>`), then decode HTML entities (`&amp;` becomes `&`).
2. Fold accents: Unicode NFKD decomposition, then drop combining marks.
3. Lowercase.
4. Remove apostrophes and quotation marks: `'` `"` `` ` `` `´` `‘` `’` `“` `”`. They are deleted, not turned into separators, so "Doesn't" and "Doesnt" agree.
5. Trim whitespace, then remove the exact suffix `(ad-free)` from the end (case already folded) if present. No other parenthetical suffix is removed.
6. Replace every run of characters outside `a-z` and `0-9` with a single `-`.
7. Trim leading and trailing `-`.

### Match cases

```json
{
  "name": "guest suffix",
  "episode": { "title": "Taxi Driver", "airDate": "2026-08-30", "hints": { "patreonPostId": "..." } },
  "candidates": [ { "guid": "...", "title": "Taxi Driver with Tracy Letts", "pubDate": "2026-08-30" } ],
  "expected": "ca63c896-..."
}
```

`match(episode, candidates)` must return the `guid` in `expected`, or no match when `expected` is `null`. `hints` and `note` are optional. Dates are calendar dates (`YYYY-MM-DD`). A feed's `pubDate` becomes a calendar date in the time zone offset the feed states, not converted to the device's zone.

The rules:

1. **Hints first.** If the episode has a `publicGuid` or `patreonPostId` hint and a candidate's `guid` equals it, that candidate is the match. Title and date are ignored. A hint that matches no candidate is ignored.
2. **Candidates.** A feed item is a candidate when both hold:
   - its `pubDate` is at most 3 days from the episode's `airDate`
   - with `w = normalize(episode title)` and `f = normalize(item title)`: `f == w`, or `f` starts with `w + "-"`. If neither holds, drop a leading `the-` from both `w` and `f` (where present) and try again.
3. **Pick one.** One candidate is the match. With several, compare in this order:
   1. the smallest date distance;
   2. an exact title (`f == w`, directly or after dropping `the-`) before one that only starts with `w + "-"`, so "Warriors" beats "Warriors (Bite-Free Version)";
   3. the longest overlap, where the overlap is the length of `w` as it was compared (so a direct match beats one that needed `the-` removed).

   If the best two still tie, or there are no candidates, the result is no match. Never guess.

Patreon items in this file are synthetic (fake numeric GUIDs, no URLs). Real Patreon feed content must never be added here; see the repository README.

### Adding a case

Every real mismatch found and fixed in code gets a case here, in the same PR as the fix. Both implementations' tests must pass before merging.
