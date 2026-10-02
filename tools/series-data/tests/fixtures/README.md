# Test fixtures

Nothing here comes from the Patreon feed. Patreon-style items used in tests are synthetic: fake numeric GUIDs and no URLs.

## `wiki/`: excerpts of the Blank Check fan wiki

Text from the [Blank Check with Griffin and David Wiki](https://blank-check.fandom.com), licensed [CC BY-SA](https://www.fandom.com/licensing). Fetched on 2026-09-30 with the MediaWiki API (`action=parse&prop=wikitext`).

- `episodes.wikitext`: excerpts of [Episodes](https://blank-check.fandom.com/wiki/Episodes). Whole rowspan blocks were kept and other rows removed; nothing else was changed. The blocks cover a rowspan series, a rowspan over the Guest(s) column with a row that leaves out its Guest(s) cell, `<span>` markup in titles, the 3018 date typo (#185), an unnumbered row whose bold markup is never closed, the "..." placeholder row, and the commented-out upcoming episode at the end.
- `special-features.wikitext`: excerpts of [Blank Check: Special Features](https://blank-check.fandom.com/wiki/Blank_Check:_Special_Features), including SF182/SF182.5 (rowspans over several columns), SF269 (`<sup>` in the number), SF294 and SF296.
- `miniseries.wikitext`: the whole [Miniseries](https://blank-check.fandom.com/wiki/Miniseries) page.
- `redirects.json`: the wiki's redirects for every series link in the files above, as saved by `series-data generate --save-raw`.

## `public-feed.xml`

An excerpt of the public feed (`feeds.megaphone.fm/blank-check`) reduced to each item's title, GUID and publication date.

## `golden/`

Expected output of `generate` for these fixtures. Regenerate with `UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py` and review the diff.
