"""Title normalization and wiki-to-feed matching (the `episode-matching` spec).

contracts/matching-vectors.json is the source of truth for these rules, and
contracts/README.md describes them step by step. The app implements the same
rules in Dart, so keep this module small and literal.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

DATE_WINDOW_DAYS = 3
# Hints that name a feed item's GUID exactly. Other hint fields are ignored.
HINT_KEYS = ("publicGuid", "patreonPostId")

_TAG = re.compile(r"<[^>]*>")
_QUOTES = re.compile("['\"`´‘’“”]")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_AD_FREE = "(ad-free)"
_THE = "the-"


def normalize(title: str) -> str:
    text = html.unescape(_TAG.sub("", title))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _QUOTES.sub("", text.lower()).strip()
    if text.endswith(_AD_FREE):
        text = text[: -len(_AD_FREE)]
    return _NON_ALNUM.sub("-", text).strip("-")


def slug(title: str) -> str:
    """The slug used in IDs. Identical to the normalized title."""
    return normalize(title)


@dataclass(frozen=True)
class FeedItem:
    guid: str
    title: str
    pub_date: date


def _strip_the(s: str) -> str:
    return s[len(_THE) :] if s.startswith(_THE) else s


def _title_match(wiki: str, feed: str) -> tuple[bool, int] | None:
    """(exact, overlap) when the titles match, else None.

    `exact` is true when the normalized titles are equal (directly or after
    dropping a leading "the"); `overlap` is the length of the wiki title as
    compared.
    """
    for w, f in ((wiki, feed), (_strip_the(wiki), _strip_the(feed))):
        if w and (f == w or f.startswith(w + "-")):
            return f == w, len(w)
    return None


@dataclass(frozen=True)
class MatchOutcome:
    """`item` is the match. `how` is "hint", "title", "none" or "ambiguous"."""

    item: FeedItem | None
    how: str


def match_outcome(
    title: str,
    air_date: date,
    items: Iterable[FeedItem],
    hints: Mapping[str, str] | None = None,
) -> MatchOutcome:
    items = list(items)
    hint_values = {(hints or {}).get(key) for key in HINT_KEYS} - {None, ""}
    for item in items:
        if item.guid in hint_values:
            return MatchOutcome(item, "hint")

    wiki = normalize(title)
    scored = []
    for item in items:
        distance = abs((item.pub_date - air_date).days)
        if distance > DATE_WINDOW_DAYS:
            continue
        found = _title_match(wiki, normalize(item.title))
        if found:
            exact, overlap = found
            scored.append(((distance, not exact, -overlap), item))
    if not scored:
        return MatchOutcome(None, "none")
    scored.sort(key=lambda pair: pair[0])
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return MatchOutcome(None, "ambiguous")
    return MatchOutcome(scored[0][1], "title")


def match(
    title: str,
    air_date: date,
    items: Iterable[FeedItem],
    hints: Mapping[str, str] | None = None,
) -> FeedItem | None:
    """Return the feed item that is this episode, or None when there isn't exactly one."""
    return match_outcome(title, air_date, items, hints).item
