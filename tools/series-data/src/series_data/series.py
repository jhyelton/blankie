"""Turning Series-cell links into series identities.

The wiki names one series in several ways: different capitalisation, older page
names that now redirect, and links to sections of the Standalones page. A link is
resolved through the wiki's redirects to a canonical page (and section), and:

- a link to the Standalones page itself, or to its "other standalones" sections,
  means the episode has no series;
- a link to any other Standalones section (Ben's Choice, Blank Check Mailbag,
  Patreon Standalones, ...) is a series named after that section;
- any other link is a series named after the canonical page.

The series key is the slug of that name, so two spellings that resolve to the
same page or section become one series.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import quote

from series_data.fetch import Redirect
from series_data.matching import slug
from series_data.wiki import MiniseriesEntry, SeriesLink, WikiRow

WIKI_BASE = "https://blank-check.fandom.com/wiki/"
STANDALONES_PAGE = "Standalones"
NO_SERIES_SECTIONS = {"", "other-standalone-episodes", "other-standalones", "standalone-episodes"}


@dataclass(frozen=True)
class SeriesInfo:
    key: str
    title: str
    subject: str
    category: str
    wiki_url: str
    on_miniseries_page: bool


@dataclass(frozen=True)
class _Resolved:
    key: str
    title: str
    wiki_url: str


def link_titles(rows: Iterable[WikiRow], miniseries: Iterable[MiniseriesEntry]) -> set[str]:
    """Every page title that needs a redirect lookup."""
    titles = {link.target for row in rows for link in row.series}
    titles |= {entry.link.target for entry in miniseries}
    return {t for t in titles if t}


def _wiki_url(page: str, fragment: str = "") -> str:
    url = WIKI_BASE + quote(page.replace(" ", "_"), safe="/:()',!&")
    if fragment:
        url += "#" + quote(fragment.replace(" ", "_"), safe="/:()',!&")
    return url


def _resolve(link: SeriesLink, redirects: dict[str, Redirect]) -> _Resolved | None:
    target = redirects.get(link.target, Redirect(link.target))
    fragment = link.fragment or target.fragment
    if target.page == STANDALONES_PAGE:
        if slug(fragment) in NO_SERIES_SECTIONS:
            return None
        return _Resolved(slug(fragment), fragment, _wiki_url(target.page, fragment))
    return _Resolved(slug(target.page), target.page, _wiki_url(target.page))


class SeriesResolver:
    def __init__(self, miniseries: Iterable[MiniseriesEntry], redirects: dict[str, Redirect]):
        self._redirects = redirects
        self.known: dict[str, SeriesInfo] = {}
        for entry in miniseries:
            resolved = _resolve(entry.link, redirects)
            if resolved is None or resolved.key in self.known:
                continue  # first listing wins, e.g. Star Wars before Special Features
            self.known[resolved.key] = SeriesInfo(
                resolved.key, resolved.title, entry.subject, entry.category, resolved.wiki_url, True
            )
        self.unlisted: dict[str, SeriesInfo] = {}

    def keys_for(self, row: WikiRow) -> list[str]:
        """Series keys for a row, in the order the wiki lists them, without duplicates."""
        keys: list[str] = []
        for link in row.series:
            resolved = _resolve(link, self._redirects)
            if resolved is None or resolved.key in keys:
                continue
            if resolved.key not in self.known and resolved.key not in self.unlisted:
                self.unlisted[resolved.key] = SeriesInfo(
                    resolved.key, resolved.title, "", "other", resolved.wiki_url, False
                )
            keys.append(resolved.key)
        return keys

    def info(self, key: str) -> SeriesInfo:
        return self.known.get(key) or self.unlisted[key]

    def info_by_key(self) -> dict[str, SeriesInfo]:
        return {**self.unlisted, **self.known}
