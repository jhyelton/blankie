"""The pure stages of `generate`: overrides, feed matching, IDs and the dataset.

    rows -> apply_overrides -> drop_shared_post_ids -> match_public_feed
         -> assign_ids -> build_dataset

Matching runs before ID assignment so that a matched public GUID can anchor an
existing ID (design D4). None of these functions touch the network or disk.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from series_data.matching import FeedItem, match, normalize, slug
from series_data.overrides import Override, OverrideError
from series_data.series import SeriesInfo
from series_data.wiki import WikiRow

SCHEMA_VERSION = 1
SOURCE = {
    "name": "Blank Check with Griffin and David Wiki",
    "url": "https://blank-check.fandom.com",
    "license": "CC BY-SA",
    "licenseUrl": "https://www.fandom.com/licensing",
}


class GenerationError(Exception):
    """The dataset can't be built: a duplicate ID, a stale override, or similar."""


@dataclass
class Episode:
    """One wiki row on its way into the dataset."""

    row: WikiRow
    title: str
    air_date: date
    series: list[str]
    id: str | None = None
    public_guid: str | None = None
    public_title: str | None = None
    pinned_guid: str | None = None
    patreon_post_id: str | None = None
    excluded: bool = False
    acknowledged_unmatched: bool = False
    applied: list[int] = field(default_factory=list)
    targeted_ids: list[tuple[str, str]] = field(default_factory=list)

    @property
    def feed(self) -> str:
        return self.row.feed

    @property
    def number(self) -> str | None:
        return self.row.number

    def __post_init__(self) -> None:
        self.patreon_post_id = self.row.patreon_post_id

    @property
    def minted_id(self) -> str:
        """The ID this row would have been given from the wiki's own title and date."""
        return f"{self.row.air_date.isoformat()}:{slug(self.row.title)}"

    def describe(self) -> str:
        return self.row.describe()


def episodes_from_rows(
    rows: Iterable[WikiRow], series_keys: Mapping[int, list[str]]
) -> list[Episode]:
    """`series_keys` maps `id(row)` to the row's resolved series keys."""
    return [
        Episode(row=row, title=row.title, air_date=row.air_date, series=list(series_keys[id(row)]))
        for row in rows
    ]


# --- Finding the row behind an existing ID (design D4) ---------------------------
#
# A published episode is anchored, in order, by its wiki number, its Patreon post
# ID, its public GUID, the ID itself (it was minted from the wiki's title and
# date), and its current title and date. The wiki number and post ID are only
# trusted when the row's other hints don't contradict them, so renumbered rows
# fall through to the GUID instead of handing their IDs to other episodes.

ANCHORS = ("number", "post", "guid", "minted", "title")


def _anchor_keys(
    episode_id: str, previous: Mapping[str, Any], use_guid: bool
) -> list[tuple[str, str]]:
    keys = []
    if previous.get("wikiNumber"):
        keys.append(("number", previous["wikiNumber"]))
    hints = previous.get("hints", {})
    if hints.get("patreonPostId"):
        keys.append(("post", hints["patreonPostId"]))
    if use_guid and hints.get("publicGuid"):
        keys.append(("guid", hints["publicGuid"]))
    keys.append(("minted", episode_id))
    keys.append(("title", f"{previous['airDate']}|{normalize(previous['title'])}"))
    return keys


def _episode_anchors(episode: Episode, kind: str) -> set[str]:
    if kind == "number":
        values = {episode.number}
    elif kind == "post":
        values = {episode.patreon_post_id}
    elif kind == "guid":
        values = {episode.public_guid}
    elif kind == "minted":
        values = {episode.minted_id}
    else:
        # The current title and date, and the wiki's own, so a `fix` can't hide the row.
        values = {
            f"{episode.air_date.isoformat()}|{normalize(episode.title)}",
            f"{episode.row.air_date.isoformat()}|{normalize(episode.row.title)}",
        }
    return {v for v in values if v}


def _index(episodes: Iterable[Episode], kind: str) -> dict[str, list[Episode]]:
    index: dict[str, list[Episode]] = defaultdict(list)
    for episode in episodes:
        for value in _episode_anchors(episode, kind):
            index[value].append(episode)
    return index


def _same_episode(previous: Mapping[str, Any], episode: Episode) -> bool:
    """The row still has the published title or air date (current or as on the wiki).

    A wiki correction changes one of them, not both. A row that differs in both
    is a different episode that has taken over the number or post ID.
    """
    title = normalize(previous["title"])
    titles = {normalize(episode.title), normalize(episode.row.title)}
    dates = {episode.air_date.isoformat(), episode.row.air_date.isoformat()}
    return title in titles or previous["airDate"] in dates


def _contradicts(previous: Mapping[str, Any], episode: Episode, kind: str) -> bool:
    """True when a number or post-ID anchor is contradicted by the row's content."""
    if kind not in ("number", "post"):
        return False
    if not _same_episode(previous, episode):
        return True
    hints = previous.get("hints", {})
    pairs = [(hints.get("publicGuid"), episode.public_guid)]
    if kind == "number":
        pairs.append((hints.get("patreonPostId"), episode.patreon_post_id))
    return any(old and new and old != new for old, new in pairs)


def find_previous(
    episode_id: str, previous: Mapping[str, Any], episodes: list[Episode], use_guid: bool
) -> Episode | None:
    """The current episode that a previously published episode anchors to, if any."""
    for kind, value in _anchor_keys(episode_id, previous, use_guid):
        found = [e for e in _index(episodes, kind).get(value, []) if not e.excluded]
        if len(found) == 1 and not _contradicts(previous, found[0], kind):
            return found[0]
    return None


# --- Overrides --------------------------------------------------------------------


def _resolve_target(
    override: Override, episodes: list[Episode], previous: Mapping[str, Any]
) -> Episode:
    target = override.target
    assert target is not None
    if override.targets_wiki_number:
        found = [e for e in episodes if e.number == target]
        if len(found) != 1:
            raise OverrideError(f"{override.describe()}: no wiki row has number {target}")
        # A number can move to another row. If it's published, the row must still be
        # that episode, or the override would land on a different one.
        for episode_id, published in previous.items():
            if published.get("wikiNumber") == target and not _same_episode(published, found[0]):
                raise OverrideError(
                    f"{override.describe()}: wiki number {target} now belongs to "
                    f"{found[0].describe()}, not the published {episode_id}; "
                    "target the episode ID instead"
                )
        return found[0]
    published = previous.get(target)
    if published is None:
        raise OverrideError(f"{override.describe()}: episode ID {target} isn't in series.json")
    episode = find_previous(target, published, episodes, use_guid=False)
    if episode is None:
        raise OverrideError(
            f"{override.describe()}: episode ID {target} no longer matches a wiki row"
        )
    return episode


def apply_overrides(
    episodes: list[Episode],
    overrides: Iterable[Override],
    previous_episodes: Mapping[str, Any],
    feed_guids: set[str],
    series_keys_by_id: Mapping[str, str],
) -> set[str]:
    """Apply every override in order. Returns the acknowledged unmatched feed GUIDs."""
    acknowledged_feed: set[str] = set()
    for override in overrides:
        if override.op == "ackUnmatchedFeed":
            if override.guid not in feed_guids:
                raise OverrideError(f"{override.describe()}: no public feed item has that GUID")
            acknowledged_feed.add(override.guid)
            continue
        episode = _resolve_target(override, episodes, previous_episodes)
        episode.applied.append(override.index)
        if override.target is not None and not override.targets_wiki_number:
            episode.targeted_ids.append((override.describe(), override.target))
        if override.op == "fix":
            episode.title = override.title or episode.title
            episode.air_date = override.air_date or episode.air_date
        elif override.op == "pinPublicGuid":
            if override.guid not in feed_guids:
                raise OverrideError(f"{override.describe()}: no public feed item has that GUID")
            episode.pinned_guid = override.guid
        elif override.op in ("addToSeries", "removeFromSeries"):
            key = series_keys_by_id.get(override.series or "")
            if key is None:
                raise OverrideError(f"{override.describe()}: unknown series {override.series!r}")
            if override.op == "addToSeries" and key not in episode.series:
                episode.series.append(key)
            elif override.op == "removeFromSeries":
                if key not in episode.series:
                    raise OverrideError(
                        f"{override.describe()}: the episode isn't in series {override.series!r}"
                    )
                episode.series.remove(key)
        elif override.op == "exclude":
            episode.excluded = True
        elif override.op == "ackUnmatchedWiki":
            episode.acknowledged_unmatched = True
    return acknowledged_feed


# --- Matching ---------------------------------------------------------------------


@dataclass
class MatchResult:
    unmatched_episodes: list[Episode]
    unmatched_items: list[FeedItem]
    contested: dict[str, list[Episode]]
    acks_no_longer_needed: list[Episode]


def drop_shared_post_ids(episodes: list[Episode]) -> dict[str, list[Episode]]:
    """Remove a Patreon post ID hint that more than one episode claims.

    Two episodes can't be the same Patreon post, so one of the wiki links is
    wrong. Neither keeps the hint, and the report lists them for a wiki fix.
    """
    claims: dict[str, list[Episode]] = defaultdict(list)
    for episode in episodes:
        if not episode.excluded and episode.patreon_post_id:
            claims[episode.patreon_post_id].append(episode)
    shared = {post: claimants for post, claimants in claims.items() if len(claimants) > 1}
    for claimants in shared.values():
        for episode in claimants:
            episode.patreon_post_id = None
    return shared


def match_public_feed(
    episodes: list[Episode], items: list[FeedItem], acknowledged_feed: set[str]
) -> MatchResult:
    """Attach public GUID and title hints to main-feed episodes.

    Pinned GUIDs are assigned first and taken out of the pool, so a pin always
    wins over another episode's title match. A feed item that several episodes
    claim otherwise is given to none of them, and is reported, because one of
    the claims must be wrong.
    """
    main = [e for e in episodes if not e.excluded and e.feed == "main"]
    claims: dict[str, list[Episode]] = defaultdict(list)
    for episode in main:
        if episode.pinned_guid:
            claims[episode.pinned_guid].append(episode)
    pinned = set(claims)
    pool = [item for item in items if item.guid not in pinned]
    for episode in main:
        if episode.pinned_guid:
            continue
        item = match(episode.title, episode.air_date, pool)
        if item is not None:
            claims[item.guid].append(episode)
    by_guid = {item.guid: item for item in items}
    contested = {}
    for guid, claimants in claims.items():
        if len(claimants) > 1:
            contested[guid] = claimants
            continue
        claimants[0].public_guid = guid
        claimants[0].public_title = by_guid[guid].title
    claimed = {e.public_guid for e in main if e.public_guid}
    return MatchResult(
        unmatched_episodes=[e for e in main if not e.public_guid and not e.acknowledged_unmatched],
        unmatched_items=[
            i for i in items if i.guid not in claimed and i.guid not in acknowledged_feed
        ],
        contested=contested,
        acks_no_longer_needed=[e for e in main if e.public_guid and e.acknowledged_unmatched],
    )


# --- IDs --------------------------------------------------------------------------


def new_episode_id(episode: Episode) -> str:
    return f"{episode.air_date.isoformat()}:{slug(episode.title)}"


def assign_ids(episodes: list[Episode], previous_episodes: Mapping[str, Any]) -> None:
    """Carry every published ID forward; give new rows `<date>:<slug>` IDs."""
    live = [e for e in episodes if not e.excluded]
    unassigned = list(live)
    pending = dict(previous_episodes)
    for kind in ANCHORS:
        index = _index(unassigned, kind)
        for episode_id, published in sorted(pending.items()):
            keys = dict(_anchor_keys(episode_id, published, use_guid=True))
            value = keys.get(kind)
            candidates = index.get(value, []) if value else []
            if (
                len(candidates) == 1
                and candidates[0].id is None
                and not _contradicts(published, candidates[0], kind)
            ):
                candidates[0].id = episode_id
                del pending[episode_id]
        unassigned = [e for e in unassigned if e.id is None]

    for episode in live:
        for override, target in episode.targeted_ids:
            if episode.id != target:
                # The override and the ID it names ended up on different rows. Checked
                # before minting, so the error names the override, not a duplicate ID.
                raise OverrideError(
                    f"{override}: applied to {episode.describe()}, but that row's ID is "
                    f"{episode.id or 'not carried forward'}, not {target}"
                )

    owners: dict[str, Episode] = {e.id: e for e in live if e.id}
    for episode in unassigned:
        episode_id = new_episode_id(episode)
        if episode_id in owners:
            raise GenerationError(
                f"duplicate episode ID {episode_id}: {owners[episode_id].describe()} "
                f"and {episode.describe()}"
            )
        episode.id = episode_id
        owners[episode_id] = episode


def assign_series_ids(
    infos: Iterable[SeriesInfo], previous_series: Iterable[Mapping[str, Any]]
) -> dict[str, str]:
    """Series key -> series ID, keeping a published ID for the same wiki page."""
    by_url = {s["wikiUrl"]: s["id"] for s in previous_series}
    ids: dict[str, str] = {}
    owners: dict[str, str] = {}
    for info in infos:
        series_id = by_url.get(info.wiki_url, info.key)
        if series_id in owners:
            raise GenerationError(
                f"duplicate series ID {series_id}: {owners[series_id]!r} and {info.title!r}"
            )
        owners[series_id] = info.title
        ids[info.key] = series_id
    return ids


# --- Dataset ----------------------------------------------------------------------


def _order_key(episode: Episode) -> tuple:
    number = episode.number or ""
    digits = number.removeprefix("SF")
    try:
        numeric = float(digits)
    except ValueError:
        numeric = float("inf")
    return (episode.air_date, episode.feed != "main", numeric, episode.id)


def build_dataset(
    episodes: list[Episode], series_info: Mapping[str, SeriesInfo], series_ids: Mapping[str, str]
) -> dict[str, Any]:
    """The series.json document, without `generatedAt` (the writer adds it)."""
    live = sorted((e for e in episodes if not e.excluded), key=_order_key)
    members: dict[str, list[str]] = defaultdict(list)
    episode_docs: dict[str, Any] = {}
    for episode in live:
        assert episode.id is not None
        hints: dict[str, str] = {}
        if episode.public_guid:
            hints["publicGuid"] = episode.public_guid
            hints["publicTitle"] = episode.public_title or ""
        if episode.patreon_post_id:
            hints["patreonPostId"] = episode.patreon_post_id
        doc: dict[str, Any] = {
            "title": episode.title,
            "airDate": episode.air_date.isoformat(),
            "feed": episode.feed,
            "series": [series_ids[key] for key in episode.series],
            "hints": hints,
        }
        if episode.number:
            doc["wikiNumber"] = episode.number
        episode_docs[episode.id] = doc
        for key in episode.series:
            members[key].append(episode.id)

    series_docs = []
    for key, episode_ids in members.items():
        info = series_info[key]
        series_docs.append(
            {
                "id": series_ids[key],
                "title": info.title,
                "subject": info.subject,
                "category": info.category,
                "wikiUrl": info.wiki_url,
                "episodes": episode_ids,
            }
        )
    series_docs.sort(key=lambda s: (episode_docs[s["episodes"][0]]["airDate"], s["id"]))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": dict(SOURCE),
        "series": series_docs,
        "episodes": episode_docs,
    }


def consistency_errors(dataset: Mapping[str, Any]) -> list[str]:
    """Cross-references the schema can't express."""
    errors = []
    episodes = dataset.get("episodes", {})
    seen_series = set()
    for series in dataset.get("series", []):
        if series["id"] in seen_series:
            errors.append(f"series {series['id']} is listed twice")
        seen_series.add(series["id"])
        for episode_id in series["episodes"]:
            if episode_id not in episodes:
                errors.append(f"series {series['id']} lists unknown episode {episode_id}")
            elif series["id"] not in episodes[episode_id]["series"]:
                errors.append(f"series {series['id']} lists {episode_id}, which doesn't list it")
        dates = [episodes[e]["airDate"] for e in series["episodes"] if e in episodes]
        if dates != sorted(dates):
            errors.append(f"series {series['id']} isn't in air-date order")
    members = {(s["id"], e) for s in dataset.get("series", []) for e in s["episodes"]}
    for episode_id, episode in episodes.items():
        for series_id in episode["series"]:
            if (series_id, episode_id) not in members:
                errors.append(
                    f"episode {episode_id} lists series {series_id}, which doesn't list it"
                )
    return errors
