"""The network side of `generate`: wiki pages, redirect lookups and the public feed.

Live runs make three sequential `action=parse` requests, then batched
`action=query&redirects` lookups for the series link targets (50 titles per
request), then one request for the public feed. Requests never run in parallel.
Every raw response can be saved to a directory, and `--offline <dir>` replays a
saved directory without touching the network.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from series_data import __version__

WIKI_API = "https://blank-check.fandom.com/api.php"
PUBLIC_FEED_URL = "https://feeds.megaphone.fm/blank-check"
USER_AGENT = f"blankie-series-data/{__version__} (+https://github.com/jhyelton/blankie)"

# Page key -> wiki page title. The key is also the saved file name.
PAGES = {
    "episodes": "Episodes",
    "special-features": "Blank Check: Special Features",
    "miniseries": "Miniseries",
}
REDIRECTS_FILE = "redirects.json"
FEED_FILE = "public-feed.xml"

MAX_ATTEMPTS = 4
REDIRECT_BATCH = 50
RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchError(Exception):
    """A request failed after every retry, or a saved response is missing."""


@dataclass(frozen=True)
class Redirect:
    """Where a wiki title points. `fragment` is the section, or "" for the whole page."""

    page: str
    fragment: str = ""


class Source(Protocol):
    def wikitext(self, key: str) -> str: ...
    def redirects(self, titles: Iterable[str]) -> dict[str, Redirect]: ...
    def public_feed(self) -> bytes: ...


def _get(
    client: httpx.Client,
    url: str,
    params: dict[str, str] | None,
    what: str,
    sleep: Callable[[float], None],
) -> httpx.Response:
    last = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.get(url, params=params)
        except httpx.TransportError as exc:
            last = type(exc).__name__
        else:
            if response.status_code not in RETRY_STATUSES:
                if response.is_error:
                    raise FetchError(f"{what}: HTTP {response.status_code}")
                return response
            last = f"HTTP {response.status_code}"
            retry_after = response.headers.get("Retry-After", "")
            if attempt < MAX_ATTEMPTS and retry_after.isdigit():
                sleep(min(int(retry_after), 60))
                continue
        if attempt < MAX_ATTEMPTS:
            sleep(2**attempt)
    raise FetchError(f"{what}: gave up after {MAX_ATTEMPTS} attempts ({last})")


def _wikitext_from_response(payload: dict, key: str) -> str:
    try:
        return payload["parse"]["wikitext"]
    except (KeyError, TypeError):
        error = payload.get("error", {}).get("info", "no wikitext in response")
        raise FetchError(f"wiki page {PAGES[key]!r}: {error}") from None


def _redirects_from_response(payload: dict, titles: list[str]) -> dict[str, Redirect]:
    """Final targets for `titles`. The API lists every hop of a redirect chain
    (A -> B, B -> C), so hops are followed until a page that isn't a redirect."""
    query = payload.get("query", {})
    normalized = {n["from"]: n["to"] for n in query.get("normalized", [])}
    hops = {r["from"]: (r["to"], r.get("tofragment", "")) for r in query.get("redirects", [])}
    result = {}
    for title in titles:
        page, fragment, seen = normalized.get(title, title), "", set()
        while page in hops and page not in seen:
            seen.add(page)
            page, hop_fragment = hops[page]
            fragment = hop_fragment or fragment
        result[title] = Redirect(page, fragment)
    return result


class LiveSource:
    """Fetches from the network and keeps every raw response for `save`."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
        )
        self._sleep = sleep
        self._pages: dict[str, dict] = {}
        self._redirects: dict[str, Redirect] = {}
        self._feed: bytes | None = None

    def wikitext(self, key: str) -> str:
        if key not in self._pages:
            params = {
                "action": "parse",
                "page": PAGES[key],
                "prop": "wikitext",
                "format": "json",
                "formatversion": "2",
            }
            response = _get(
                self._client, WIKI_API, params, f"wiki page {PAGES[key]!r}", self._sleep
            )
            self._pages[key] = response.json()
        return _wikitext_from_response(self._pages[key], key)

    def redirects(self, titles: Iterable[str]) -> dict[str, Redirect]:
        wanted = sorted({t for t in titles if t not in self._redirects})
        for start in range(0, len(wanted), REDIRECT_BATCH):
            batch = wanted[start : start + REDIRECT_BATCH]
            params = {
                "action": "query",
                "redirects": "1",
                "titles": "|".join(batch),
                "format": "json",
                "formatversion": "2",
            }
            response = _get(self._client, WIKI_API, params, "wiki redirect lookup", self._sleep)
            self._redirects.update(_redirects_from_response(response.json(), batch))
        return {t: self._redirects[t] for t in titles}

    def public_feed(self) -> bytes:
        if self._feed is None:
            response = _get(self._client, PUBLIC_FEED_URL, None, "public feed", self._sleep)
            self._feed = response.content
        return self._feed

    def save(self, directory: Path) -> None:
        """Write every response fetched so far, in the layout `OfflineSource` reads."""
        directory.mkdir(parents=True, exist_ok=True)
        for key, payload in self._pages.items():
            (directory / f"{key}.json").write_text(json.dumps(payload, ensure_ascii=False))
        redirects = {
            t: {"page": r.page, "fragment": r.fragment} for t, r in self._redirects.items()
        }
        (directory / REDIRECTS_FILE).write_text(
            json.dumps(redirects, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )
        if self._feed is not None:
            (directory / FEED_FILE).write_bytes(self._feed)


class OfflineSource:
    """Replays responses saved by `LiveSource.save`."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def _read(self, name: str) -> bytes:
        path = self._dir / name
        if not path.is_file():
            raise FetchError(f"offline: {name} is missing from {self._dir}")
        return path.read_bytes()

    def wikitext(self, key: str) -> str:
        return _wikitext_from_response(json.loads(self._read(f"{key}.json")), key)

    def redirects(self, titles: Iterable[str]) -> dict[str, Redirect]:
        saved = json.loads(self._read(REDIRECTS_FILE))
        result = {}
        for title in titles:
            if title not in saved:
                raise FetchError(f"offline: no saved redirect lookup for {title!r}")
            result[title] = Redirect(saved[title]["page"], saved[title]["fragment"])
        return result

    def public_feed(self) -> bytes:
        return self._read(FEED_FILE)
