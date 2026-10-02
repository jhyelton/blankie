"""Comparing a new dataset with the published one before proposing it.

Each guardrail catches a sign that the wiki broke or was vandalised. A run fails
on any of them unless the owner accepts the change explicitly
(`--accept-guardrail-changes`), in which case the report lists them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MAX_ROW_DROP = 5
MAX_ROW_DROP_FRACTION = 0.01
MAX_MEMBERSHIP_CHANGE_FRACTION = 0.05


@dataclass(frozen=True)
class Violation:
    name: str
    detail: str

    def __str__(self) -> str:
        return f"{self.name}: {self.detail}"


def _preview(items: list[str], limit: int = 10) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f", and {len(items) - limit} more" if len(items) > limit else "")


def check_guardrails(new: Mapping[str, Any], previous: Mapping[str, Any]) -> list[Violation]:
    violations = []
    old_episodes = previous["episodes"]
    new_episodes = new["episodes"]

    drop = len(old_episodes) - len(new_episodes)
    if drop > MAX_ROW_DROP or (old_episodes and drop / len(old_episodes) > MAX_ROW_DROP_FRACTION):
        violations.append(
            Violation(
                "row count dropped",
                f"{len(old_episodes)} episodes before, {len(new_episodes)} now ({drop} fewer)",
            )
        )

    gone = sorted(set(old_episodes) - set(new_episodes))
    if gone:
        violations.append(Violation("episode IDs disappeared", f"{len(gone)}: {_preview(gone)}"))

    new_series = {s["id"]: s for s in new["series"]}
    for series in previous["series"]:
        current = set(new_series.get(series["id"], {}).get("episodes", []))
        lost = [e for e in series["episodes"] if e not in current]
        if lost:
            violations.append(
                Violation(
                    "series lost episodes",
                    f"{series['title']} ({series['id']}) lost {len(lost)}: {_preview(lost)}",
                )
            )

    for key in ("publicGuid", "patreonPostId"):
        moved = sorted(
            episode_id
            for episode_id, old in old_episodes.items()
            if episode_id in new_episodes
            and old["hints"].get(key)
            and new_episodes[episode_id]["hints"].get(key)
            and old["hints"][key] != new_episodes[episode_id]["hints"][key]
        )
        if moved:
            violations.append(
                Violation(
                    f"{key} changed for existing episodes", f"{len(moved)}: {_preview(moved)}"
                )
            )

    changed = sorted(
        episode_id
        for episode_id, old in old_episodes.items()
        if episode_id in new_episodes
        and sorted(old["series"]) != sorted(new_episodes[episode_id]["series"])
    )
    if old_episodes and len(changed) / len(old_episodes) > MAX_MEMBERSHIP_CHANGE_FRACTION:
        violations.append(
            Violation(
                "membership changed for more than 5% of episodes",
                f"{len(changed)} of {len(old_episodes)}: {_preview(changed)}",
            )
        )
    return violations
