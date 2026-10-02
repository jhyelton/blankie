"""`series-data check-patreon`: check Special Features matching against your own feed.

Runs only on the owner's Mac. The Patreon feed URL carries a personal access
token, so this command:

- reads the URL from the macOS Keychain and never takes it as an argument,
- keeps the feed in memory and writes nothing to disk,
- prints only episode titles, dates and dataset IDs,
- replaces every network error with one that names the status, never the URL.

Store the URL once (macOS prompts for it, so it never enters shell history):

    security add-generic-password -s blankie-patreon-feed -a "$USER" -w
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from collections.abc import Callable, Collection
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from series_data.feed import FeedParseError, parse_feed
from series_data.matching import FeedItem, match_outcome
from series_data.overrides import Override, OverrideError, load_overrides

KEYCHAIN_SERVICE = "blankie-patreon-feed"
SETUP = (
    "No Patreon feed URL in the Keychain. Store it once with:\n"
    f'  security add-generic-password -s {KEYCHAIN_SERVICE} -a "$USER" -w\n'
    "macOS then prompts for the value, so it never lands in your shell history."
)


class PatreonCheckError(Exception):
    """A failure whose message is safe to print: no URL, token or feed content."""


def keychain_url(run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> str | None:
    try:
        result = run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    url = result.stdout.strip() if result.returncode == 0 else ""
    return url or None


def fetch_feed(url: str, client: httpx.Client | None = None) -> bytes:
    # httpx and httpcore log request URLs at INFO and DEBUG. Keep them quiet.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        raise PatreonCheckError(
            f"fetching the Patreon feed failed ({type(exc).__name__})"
        ) from None
    except Exception:
        raise PatreonCheckError("fetching the Patreon feed failed") from None
    if response.is_error:
        raise PatreonCheckError(f"fetching the Patreon feed failed (HTTP {response.status_code})")
    return response.content


def acknowledged_ids(dataset: dict[str, Any], overrides: list[Override]) -> set[str]:
    """Episode IDs that `ackUnmatchedWiki` overrides target, by ID or by wiki number."""
    by_number = {e.get("wikiNumber"): i for i, e in dataset["episodes"].items()}
    targets = {o.target for o in overrides if o.op == "ackUnmatchedWiki" and o.target}
    return {by_number.get(t, t) for t in targets}


def build_report(
    dataset: dict[str, Any], items: list[FeedItem], acknowledged: Collection[str] = frozenset()
) -> tuple[str, int]:
    """The report text, and how many episodes are unmatched, ambiguous or share an item.

    Unmatched or ambiguous episodes acknowledged with `ackUnmatchedWiki` (for
    example video-only posts) are listed separately and don't count as problems.
    """
    groups: dict[str, list[str]] = {
        "hint": [],
        "title": [],
        "none": [],
        "ambiguous": [],
        "acknowledged": [],
        "stale": [],
    }
    claims: dict[str, list[str]] = {}
    for episode_id, episode in sorted(
        dataset["episodes"].items(), key=lambda pair: (pair[1]["airDate"], pair[0])
    ):
        if episode["feed"] != "special-features":
            continue
        outcome = match_outcome(
            episode["title"],
            date.fromisoformat(episode["airDate"]),
            items,
            episode["hints"],
        )
        line = f"  {episode['airDate']}  {episode['title']}  [{episode_id}]"
        if episode_id in acknowledged and outcome.item is None:
            groups["acknowledged"].append(line)
        else:
            groups[outcome.how].append(line)
            if episode_id in acknowledged:
                groups["stale"].append(line)
        if outcome.item is not None:
            claims.setdefault(outcome.item.guid, []).append(line)
    shared = [line for lines in claims.values() if len(lines) > 1 for line in lines]

    lines = [f"Patreon feed: {len(items)} items. Special Features episodes in series.json:"]
    lines.append(f"\nMatched to the same feed item as another episode: {len(shared)}")
    lines += shared
    for how, heading in (
        ("acknowledged", "Acknowledged as not in the feed (ackUnmatchedWiki)"),
        ("stale", "Acknowledged, but now matched (the override can go)"),
        ("none", "Unmatched"),
        ("ambiguous", "Ambiguous (several equally good items)"),
        ("title", "Matched by title and date (no post ID hint)"),
        ("hint", "Matched by Patreon post ID"),
    ):
        lines.append(f"\n{heading}: {len(groups[how])}")
        lines += groups[how]
    problems = len(groups["none"]) + len(groups["ambiguous"]) + len(shared)
    return "\n".join(lines) + "\n", problems


def run(
    dataset_path: Path,
    url_reader: Callable[[], str | None] = keychain_url,
    client: httpx.Client | None = None,
    overrides_path: Path | None = None,
) -> int:
    url = url_reader()
    if not url:
        print(SETUP, file=sys.stderr)
        return 2
    try:
        dataset = json.loads(dataset_path.read_text())
        overrides = load_overrides(overrides_path) if overrides_path else []
        items = parse_feed(fetch_feed(url, client))
        report, problems = build_report(dataset, items, acknowledged_ids(dataset, overrides))
    except (PatreonCheckError, FeedParseError, OverrideError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("error: series.json not found; run generate first", file=sys.stderr)
        return 1
    print(report, end="")
    return 1 if problems else 0
