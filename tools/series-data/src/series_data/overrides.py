"""data/overrides.json: hand-written corrections applied after parsing the wiki.

The file is a JSON list. Every entry has an `op`, a `reason`, and the fields
that op needs:

    {"op": "fix", "target": "185", "airDate": "2018-09-30", "reason": "..."}
    {"op": "fix", "target": "...", "title": "The Podcastic Two", "reason": "..."}
    {"op": "pinPublicGuid", "target": "...", "guid": "<public feed guid>", "reason": "..."}
    {"op": "addToSeries", "target": "...", "series": "<series id>", "reason": "..."}
    {"op": "removeFromSeries", "target": "...", "series": "<series id>", "reason": "..."}
    {"op": "exclude", "target": "...", "reason": "..."}
    {"op": "ackUnmatchedWiki", "target": "...", "reason": "..."}
    {"op": "ackUnmatchedFeed", "guid": "<public feed guid>", "reason": "..."}

`target` is an episode ID from data/series.json, or a wiki number ("185",
"SF294") for a row that doesn't have an ID yet. `exclude` only takes a wiki
number: an excluded episode leaves series.json, so an ID target would stop
resolving on the next run.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from series_data.wiki import canonical_number

FIELDS = {
    "fix": {"target"},
    "pinPublicGuid": {"target", "guid"},
    "addToSeries": {"target", "series"},
    "removeFromSeries": {"target", "series"},
    "exclude": {"target"},
    "ackUnmatchedWiki": {"target"},
    "ackUnmatchedFeed": {"guid"},
}
OPTIONAL = {"fix": {"title", "airDate"}}
WIKI_NUMBER = re.compile(r"^(SF)?\d+(\.\d+)?$")
EPISODE_ID = re.compile(r"^\d{4}-\d{2}-\d{2}:[a-z0-9]+(-[a-z0-9]+)*$")


class OverrideError(Exception):
    """An override is malformed or doesn't resolve."""


@dataclass(frozen=True)
class Override:
    index: int
    op: str
    reason: str
    target: str | None = None
    guid: str | None = None
    series: str | None = None
    title: str | None = None
    air_date: date | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    def describe(self) -> str:
        what = self.target if self.target is not None else self.guid
        return f"override #{self.index} ({self.op} {what!r})"

    @property
    def targets_wiki_number(self) -> bool:
        return self.target is not None and bool(WIKI_NUMBER.match(self.target))


def _parse_entry(index: int, entry: Any) -> Override:
    where = f"override #{index}"
    if not isinstance(entry, dict):
        raise OverrideError(f"{where}: must be an object")
    op = entry.get("op")
    if op not in FIELDS:
        raise OverrideError(f"{where}: unknown op {op!r} (expected one of {', '.join(FIELDS)})")
    where = f"override #{index} ({op})"
    allowed = FIELDS[op] | OPTIONAL.get(op, set()) | {"op", "reason"}
    unknown = sorted(set(entry) - allowed)
    if unknown:
        raise OverrideError(f"{where}: unexpected field(s) {', '.join(unknown)}")
    for name in sorted(FIELDS[op] | {"reason"}):
        value = entry.get(name)
        if not isinstance(value, str) or not value.strip():
            raise OverrideError(f"{where}: {name!r} is required and must be a non-empty string")
    target = entry.get("target")
    if target is not None and not (WIKI_NUMBER.match(target) or EPISODE_ID.match(target)):
        raise OverrideError(
            f"{where}: target {target!r} is neither an episode ID nor a wiki number"
        )
    if op == "exclude" and not WIKI_NUMBER.match(target):
        raise OverrideError(f"{where}: target must be a wiki number, not an episode ID")
    if target is not None and WIKI_NUMBER.match(target):
        target = canonical_number(target)  # the wiki shows "033"; rows are parsed as "33"
    air_date = None
    if op == "fix":
        if "title" not in entry and "airDate" not in entry:
            raise OverrideError(f"{where}: needs 'title' and/or 'airDate'")
        if "title" in entry and (not isinstance(entry["title"], str) or not entry["title"].strip()):
            raise OverrideError(f"{where}: 'title' must be a non-empty string")
        if "airDate" in entry:
            try:
                air_date = date.fromisoformat(entry["airDate"])
            except (TypeError, ValueError):
                raise OverrideError(f"{where}: 'airDate' must be YYYY-MM-DD") from None
    return Override(
        index=index,
        op=op,
        reason=entry["reason"],
        target=target,
        guid=entry.get("guid"),
        series=entry.get("series"),
        title=entry.get("title"),
        air_date=air_date,
        raw=entry,
    )


def parse_overrides(data: Any) -> list[Override]:
    if not isinstance(data, list):
        raise OverrideError("overrides file must contain a JSON list")
    return [_parse_entry(i, entry) for i, entry in enumerate(data)]


def load_overrides(path: Path) -> list[Override]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise OverrideError(f"{path.name}: invalid JSON ({exc})") from None
    return parse_overrides(data)
