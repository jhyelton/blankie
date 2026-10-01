"""Reading RSS feeds into `FeedItem`s (GUID, title, publication date)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from series_data.matching import FeedItem


class FeedParseError(Exception):
    """The feed isn't RSS the tool can read. Messages never include feed content."""


def parse_feed(xml: bytes) -> list[FeedItem]:
    """Items in feed order. The date is the calendar date in the offset the feed states."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise FeedParseError(f"feed is not valid XML (line {exc.position[0]})") from None
    items = []
    for index, item in enumerate(root.iterfind("./channel/item")):
        guid = (item.findtext("guid") or "").strip()
        title = (item.findtext("title") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not guid or not title or not pub:
            raise FeedParseError(f"feed item {index} is missing its guid, title or pubDate")
        try:
            pub_date = parsedate_to_datetime(pub).date()
        except (TypeError, ValueError):
            raise FeedParseError(f"feed item {index} has an unreadable pubDate") from None
        items.append(FeedItem(guid=guid, title=title, pub_date=pub_date))
    if not items:
        raise FeedParseError("feed has no items")
    return items
