"""The Markdown report: printed by `generate` and used as the weekly PR body."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from series_data.guardrails import Violation
from series_data.matching import FeedItem
from series_data.series import SeriesInfo


@dataclass
class ReportInputs:
    new: Mapping[str, Any]
    previous: Mapping[str, Any] | None
    unmatched_episodes: list[tuple[str, str]] = field(default_factory=list)  # (id, description)
    unmatched_items: list[FeedItem] = field(default_factory=list)
    contested: dict[str, list[str]] = field(default_factory=dict)  # guid -> descriptions
    shared_post_ids: dict[str, list[str]] = field(default_factory=dict)  # post -> descriptions
    acks_no_longer_needed: list[str] = field(default_factory=list)
    unlisted_series: list[SeriesInfo] = field(default_factory=list)
    accepted: list[Violation] = field(default_factory=list)


def _episode_line(
    episode_id: str, episode: Mapping[str, Any], series_titles: dict[str, str]
) -> str:
    series = ", ".join(series_titles.get(s, s) for s in episode["series"]) or "no series"
    return f"- `{episode_id}` {episode['title']} ({episode['airDate']}): {series}"


def _section(title: str, lines: Iterable[str], empty: str | None = "None.") -> list[str]:
    lines = list(lines)
    if not lines and empty is None:
        return []
    return [f"### {title}", "", *(lines or [empty]), ""]


def _changes(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[str]:
    parts = []
    for key, label in (("title", "title"), ("airDate", "air date"), ("wikiNumber", "wiki number")):
        if old.get(key) != new.get(key):
            parts.append(f"{label} {old.get(key)!r} → {new.get(key)!r}")
    for key in ("publicGuid", "publicTitle", "patreonPostId"):
        before, after = old.get("hints", {}).get(key), new.get("hints", {}).get(key)
        if before != after:
            parts.append(f"{key} {before!r} → {after!r}")
    return parts


def render_report(inputs: ReportInputs) -> str:
    new = inputs.new
    episodes = new["episodes"]
    series_titles = {s["id"]: s["title"] for s in new["series"]}
    main = [e for e in episodes.values() if e["feed"] == "main"]
    matched = sum(1 for e in main if e["hints"].get("publicGuid"))

    out = [
        "## Series data update",
        "",
        "| | Count |",
        "|---|---|",
        f"| Episodes | {len(episodes)} ({len(main)} main feed, "
        f"{len(episodes) - len(main)} Special Features) |",
        f"| Series | {len(new['series'])} |",
        f"| Main-feed episodes matched to the public feed | {matched} of {len(main)} |",
        f"| Unmatched wiki episodes (unacknowledged) | {len(inputs.unmatched_episodes)} |",
        f"| Unmatched public feed items (unacknowledged) | {len(inputs.unmatched_items)} |",
        "",
    ]

    if inputs.accepted:
        out += _section(
            "Guardrails overridden",
            [f"- **{v.name}**: {v.detail}" for v in inputs.accepted],
        )

    previous = inputs.previous
    if previous is None:
        out += [
            "### First run",
            "",
            "There is no previous dataset, so the comparison guardrails were skipped "
            "and every episode is new.",
            "",
        ]
    else:
        old_episodes = previous["episodes"]
        old_titles = {s["id"]: s["title"] for s in previous["series"]}
        membership = []
        for episode_id in sorted(set(old_episodes) & set(episodes)):
            before, after = (
                set(old_episodes[episode_id]["series"]),
                set(episodes[episode_id]["series"]),
            )
            if before != after:
                added = ", ".join(f"+{series_titles.get(s, s)}" for s in sorted(after - before))
                removed = ", ".join(f"−{old_titles.get(s, s)}" for s in sorted(before - after))
                change = ", ".join(p for p in (added, removed) if p)
                membership.append(f"- `{episode_id}` {episodes[episode_id]['title']}: {change}")
        out += _section("Series membership changes", membership)

        added = [
            _episode_line(i, episodes[i], series_titles)
            for i in sorted(set(episodes) - set(old_episodes))
        ]
        out += _section("Added episodes", added)

        changed = []
        for episode_id in sorted(set(old_episodes) & set(episodes)):
            parts = _changes(old_episodes[episode_id], episodes[episode_id])
            if parts:
                changed.append(f"- `{episode_id}`: " + "; ".join(parts))
        out += _section("Changed episodes", changed)

        removed = [
            f"- `{i}` {old_episodes[i]['title']} ({old_episodes[i]['airDate']})"
            for i in sorted(set(old_episodes) - set(episodes))
        ]
        out += _section("Removed episodes", removed, empty=None)

    out += _section(
        "Unmatched wiki episodes (main feed)",
        [f"- `{i}` {d}" for i, d in sorted(inputs.unmatched_episodes)],
    )
    out += _section(
        "Unmatched public feed items",
        [
            f"- {item.title} ({item.pub_date.isoformat()}) `{item.guid}`"
            for item in sorted(inputs.unmatched_items, key=lambda i: (i.pub_date, i.guid))
        ],
    )
    out += _section(
        "Patreon post IDs linked from more than one wiki row (hint dropped; fix the wiki)",
        [
            f"- `{post}`: " + "; ".join(sorted(d))
            for post, d in sorted(inputs.shared_post_ids.items())
        ],
        empty=None,
    )
    out += _section(
        "Feed items claimed by more than one episode",
        [f"- `{guid}`: " + "; ".join(sorted(d)) for guid, d in sorted(inputs.contested.items())],
        empty=None,
    )
    out += _section(
        "Series not on the Miniseries page (category `other`)",
        [
            f"- {info.title} ({info.wiki_url})"
            for info in sorted(inputs.unlisted_series, key=lambda i: i.key)
        ],
        empty=None,
    )
    out += _section(
        "Acknowledged as unmatched, but now matched (the override can go)",
        [f"- {d}" for d in sorted(inputs.acks_no_longer_needed)],
        empty=None,
    )
    out += [
        "---",
        "",
        "Series data comes from the [Blank Check fan wiki](https://blank-check.fandom.com), "
        "licensed [CC BY-SA](https://www.fandom.com/licensing).",
        "",
    ]
    return "\n".join(out)
