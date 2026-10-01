"""Parsing the wiki's Episodes, Special Features and Miniseries pages.

Episode tables have seven columns: # | Title | Audio | Guest(s) | Length | Date |
Series. Two real-world irregularities are handled on purpose:

- `rowspan` can cover any column, not only Series (a two-part episode can share
  its guest, date and series cells).
- Some rows leave out the Guest(s) cell entirely instead of leaving it empty.

Anything else that doesn't fit that layout raises `WikiParseError`, so a change
to the page's format fails the run instead of being misread.
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from datetime import date

import mwparserfromhell
from mwparserfromhell.nodes import Tag
from mwparserfromhell.wikicode import Wikicode

EPISODES_PAGE = "Episodes"
SPECIAL_FEATURES_PAGE = "Blank Check: Special Features"

COLUMNS = 7
NUMBER, TITLE, AUDIO, GUESTS, LENGTH, DATE, SERIES = range(COLUMNS)

_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_LENGTH = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_NUMBER = re.compile(r"^(SF)?0*(\d+)(\.\d+)?")
_POST_URL = re.compile(r"patreon\.com/(?:[A-Za-z0-9_-]+/)?posts/([^\s\]|?#]+)")
_POST_ID = re.compile(r"(?:^|-)(\d+)$")
# Bold and italic quotes. MediaWiki closes an unclosed ''' at the end of the line,
# but mwparserfromhell lets it run on and swallow the rest of the table, so the
# quotes are removed before parsing. They carry no meaning for this data.
_STYLE = re.compile(r"'{2,}")

CATEGORY_BY_HEADING = {
    "star wars": "star-wars",
    "director filmographies": "director",
    "special features": "special-features",
    "other series": "other",
}


class WikiParseError(Exception):
    """A wiki page doesn't have the layout the parser expects."""


def _parse(wikitext: str) -> Wikicode:
    return mwparserfromhell.parse(_STYLE.sub("", wikitext))


@dataclass(frozen=True)
class SeriesLink:
    """A link in a Series cell, as written: `[[target#fragment|label]]`."""

    target: str
    fragment: str = ""
    label: str = ""


@dataclass
class WikiRow:
    page: str
    number: str | None
    title: str
    air_date: date
    feed: str
    series: list[SeriesLink] = field(default_factory=list)
    patreon_post_id: str | None = None

    def describe(self) -> str:
        number = f"#{self.number} " if self.number else ""
        return f"{self.page} row {number}{self.title!r} ({self.air_date.isoformat()})"


@dataclass(frozen=True)
class MiniseriesEntry:
    link: SeriesLink
    subject: str
    category: str


def _text(code: Wikicode | None) -> str:
    """Plain text of a cell: no markup, no footnotes, single spaces."""
    if code is None:
        return ""
    code = mwparserfromhell.parse(str(code))
    for tag in code.filter_tags(recursive=True):
        name = str(tag.tag).strip().lower()
        if name in ("ref", "sup"):
            with contextlib.suppress(ValueError):  # already removed with its parent
                code.remove(tag)
        elif name == "br":
            code.replace(tag, " ")
    return " ".join(code.strip_code(normalize=True, collapse=True).split())


def _rowspan(cell: Tag) -> int:
    if not cell.has("rowspan"):
        return 1
    value = str(cell.get("rowspan").value).strip().strip("\"'")
    return int(value) if value.isdigit() and int(value) > 0 else 1


def _cells(row: Tag) -> list[Tag]:
    return row.contents.filter_tags(matches=lambda n: n.tag in ("td", "th"), recursive=False)


def _rows(table: Tag) -> list[Tag]:
    return table.contents.filter_tags(matches=lambda n: n.tag == "tr", recursive=False)


def _tables(code: Wikicode) -> list[Tag]:
    return code.filter_tags(matches=lambda n: n.tag == "table", recursive=True)


def series_links(cell: Wikicode | None) -> list[SeriesLink]:
    """Every series linked from a Series cell. Plain text without a link is an error."""
    if cell is None:
        return []
    code = mwparserfromhell.parse(str(cell))
    links = []
    for link in code.filter_wikilinks():
        target, _, fragment = str(link.title).partition("#")
        label = _text(link.text) if link.text else ""
        links.append(SeriesLink(target.strip(), fragment.strip().replace("_", " "), label))
        code.remove(link)
    leftover = _text(code)
    if leftover:
        raise WikiParseError(f"series cell has text that isn't a link: {leftover!r}")
    return links


def patreon_post_id(audio_cell: str) -> str | None:
    """The post ID from a `patreon.com/[creator/]posts/<slug>-<id>` link, if any."""
    found = _POST_URL.search(audio_cell)
    if not found:
        return None
    post_id = _POST_ID.search(found.group(1))
    return post_id.group(1) if post_id else None


def canonical_number(text: str) -> str | None:
    """`"033"` -> `"33"`, `"SF001"` -> `"SF1"`, `"SF182.5"` stays; None if not a number."""
    found = _NUMBER.match(text)
    if not found:
        return None
    return f"{found.group(1) or ''}{found.group(2)}{found.group(3) or ''}"


def _fill(own: list[Tag], spanned: dict[int, Tag], skip: frozenset[int]) -> list[Tag | None] | None:
    """Lay one row's own cells and the cells spanned from above onto the seven columns."""
    grid: list[Tag | None] = []
    queue = list(own)
    for column in range(COLUMNS):
        if column in spanned:
            grid.append(spanned[column])
        elif column in skip or not queue:
            grid.append(None)
        else:
            grid.append(queue.pop(0))
    if queue:
        return None
    date_text = _text(grid[DATE].contents) if grid[DATE] is not None else ""
    length_text = _text(grid[LENGTH].contents) if grid[LENGTH] is not None else ""
    # Every column needs a cell (an empty Series cell means no series), and the
    # Length cell must not hold a date.
    if any(grid[c] is None and c not in skip for c in range(COLUMNS)):
        return None
    if not _DATE.match(date_text) or _DATE.match(length_text):
        return None
    if length_text and not _LENGTH.match(length_text):
        return None
    return grid


def parse_episode_table_rows(wikitext: str, page: str, feed: str) -> list[WikiRow]:
    """Every episode row from the seven-column tables on an Episodes-style page."""
    rows: list[WikiRow] = []
    for table in _tables(_parse(wikitext)):
        pending: dict[int, list] = {}  # column -> [rows left, cell]
        for row in _rows(table):
            own = _cells(row)
            if not own or str(own[0].tag) == "th":
                continue
            spanned = {c: span[1] for c, span in pending.items()}
            pending = {c: [n - 1, cell] for c, (n, cell) in pending.items() if n > 1}

            if not _text(own[TITLE].contents if len(own) > TITLE else None):
                continue  # placeholder row ("..."), nothing aired yet

            grid = _fill(own, spanned, frozenset()) or _fill(own, spanned, frozenset({GUESTS}))
            if grid is None:
                preview = " | ".join(_text(c.contents)[:30] for c in own)
                raise WikiParseError(
                    f"{page}: row with {len(own)} cells doesn't fit the table layout: {preview}"
                )
            for column, cell in enumerate(grid):
                if cell is not None and any(cell is o for o in own) and _rowspan(cell) > 1:
                    pending[column] = [_rowspan(cell) - 1, cell]

            month, day, year = map(int, _DATE.match(_text(grid[DATE].contents)).groups())
            try:
                air_date = date(year, month, day)
            except ValueError:
                raise WikiParseError(
                    f"{page}: invalid date {_text(grid[DATE].contents)!r}"
                ) from None
            title = _text(grid[TITLE].contents)
            try:
                links = series_links(grid[SERIES].contents if grid[SERIES] is not None else None)
            except WikiParseError as exc:
                raise WikiParseError(f"{page} row {title!r}: {exc}") from None
            rows.append(
                WikiRow(
                    page=page,
                    number=canonical_number(_text(grid[NUMBER].contents)),
                    title=title,
                    air_date=air_date,
                    feed=feed,
                    series=links,
                    patreon_post_id=patreon_post_id(str(grid[AUDIO].contents)),
                )
            )
    if not rows:
        raise WikiParseError(f"{page}: no episode rows found")
    return rows


def parse_episodes(wikitext: str) -> list[WikiRow]:
    return parse_episode_table_rows(wikitext, EPISODES_PAGE, "main")


def parse_special_features(wikitext: str) -> list[WikiRow]:
    return parse_episode_table_rows(wikitext, SPECIAL_FEATURES_PAGE, "special-features")


def parse_miniseries(wikitext: str) -> list[MiniseriesEntry]:
    """Series rows from the Miniseries page, with the category taken from the section heading."""
    entries: list[MiniseriesEntry] = []
    for section in _parse(wikitext).get_sections(levels=[3]):
        heading = _text(section.filter_headings()[0].title).lower()
        category = CATEGORY_BY_HEADING.get(heading)
        if category is None:
            # A renamed heading would otherwise turn a whole group into `other`.
            raise WikiParseError(f"Miniseries: unknown section heading {heading!r}")
        for table in _tables(section):
            for row in _rows(table):
                cells = _cells(row)
                if len(cells) < 2:
                    continue
                links = mwparserfromhell.parse(str(cells[0].contents)).filter_wikilinks()
                if not links:
                    continue  # the column header row
                link = links[0]
                target, _, fragment = str(link.title).partition("#")
                entries.append(
                    MiniseriesEntry(
                        link=SeriesLink(
                            target.strip(),
                            fragment.strip().replace("_", " "),
                            _text(link.text) if link.text else "",
                        ),
                        subject=_text(cells[1].contents),
                        category=category,
                    )
                )
    if not entries:
        raise WikiParseError("Miniseries: no series rows found")
    return entries
