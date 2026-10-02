"""Overrides (task 5.1) and stable IDs (task 5.2) on small hand-built rows."""

import copy
from datetime import date

import pytest

from series_data.matching import FeedItem
from series_data.overrides import OverrideError, parse_overrides
from series_data.pipeline import (
    GenerationError,
    apply_overrides,
    assign_ids,
    drop_shared_post_ids,
    episodes_from_rows,
    match_public_feed,
)
from series_data.wiki import WikiRow

FEED = [
    FeedItem("guid-space-jam", "Space Jam with James Newman", date(2018, 9, 30)),
    FeedItem("guid-podcastic", "The Podcastic Two", date(2015, 9, 14)),
    FeedItem(
        "guid-titanic-1", "Titanic with Emily Yoshida and Katey Rich - Part One", date(2016, 11, 4)
    ),
    FeedItem("guid-trailer", "Blank Check with Griffin & David Trailer", date(2016, 1, 18)),
]
SERIES_IDS = {"standalones-x": "x-key", "podinator-judgment-cast": "podinator-judgment-cast"}


def _rows():
    return [
        WikiRow("Episodes", "185", "Space Jam", date(3018, 9, 30), "main"),
        WikiRow("Episodes", "23", "The Podtastic Two", date(2015, 9, 14), "main"),
        WikiRow("Episodes", "82", "Titanic - Part One", date(2016, 11, 3), "main"),
        WikiRow("Episodes", "33", "Watch With Us Live @ Union Hall", date(2015, 11, 30), "main"),
        WikiRow(
            "Blank Check: Special Features",
            "SF294",
            "Mortal Kombat II",
            date(2026, 5, 21),
            "special-features",
            patreon_post_id="158692113",
        ),
    ]


def _episodes(series=None):
    rows = _rows()
    series = series or {}
    return episodes_from_rows(rows, {id(r): list(series.get(r.number, [])) for r in rows})


def _by_number(episodes):
    return {e.number: e for e in episodes}


def _apply(entries, episodes=None, previous=None):
    episodes = episodes if episodes is not None else _episodes()
    acked = apply_overrides(
        episodes,
        parse_overrides(entries),
        previous or {},
        {i.guid for i in FEED},
        {
            "podinator-judgment-cast": "podinator-judgment-cast",
            "patreon-standalones": "patreon-standalones",
        },
    )
    return episodes, acked


# --- 5.1 overrides ---------------------------------------------------------------


def test_fix_date_then_matches():
    episodes, _ = _apply(
        [{"op": "fix", "target": "185", "airDate": "2018-09-30", "reason": "typo"}]
    )
    match_public_feed(episodes, FEED, set())
    space_jam = _by_number(episodes)["185"]
    assert space_jam.air_date == date(2018, 9, 30)
    assert space_jam.public_guid == "guid-space-jam"


def test_fix_title():
    episodes, _ = _apply(
        [{"op": "fix", "target": "23", "title": "The Podcastic Two", "reason": "r"}]
    )
    match_public_feed(episodes, FEED, set())
    assert _by_number(episodes)["23"].public_guid == "guid-podcastic"


def test_pin_public_guid():
    episodes, _ = _apply(
        [{"op": "pinPublicGuid", "target": "82", "guid": "guid-titanic-1", "reason": "r"}]
    )
    match_public_feed(episodes, FEED, set())
    assert _by_number(episodes)["82"].public_guid == "guid-titanic-1"


def test_add_and_remove_series():
    episodes, _ = _apply(
        [
            {
                "op": "addToSeries",
                "target": "SF294",
                "series": "patreon-standalones",
                "reason": "r",
            },
            {
                "op": "addToSeries",
                "target": "82",
                "series": "podinator-judgment-cast",
                "reason": "r",
            },
            {
                "op": "removeFromSeries",
                "target": "82",
                "series": "podinator-judgment-cast",
                "reason": "r",
            },
        ]
    )
    assert _by_number(episodes)["SF294"].series == ["patreon-standalones"]
    assert _by_number(episodes)["82"].series == []


def test_remove_from_series_it_is_not_in():
    with pytest.raises(OverrideError, match="isn't in series"):
        _apply(
            [
                {
                    "op": "removeFromSeries",
                    "target": "82",
                    "series": "podinator-judgment-cast",
                    "reason": "r",
                }
            ]
        )


def test_unknown_series():
    with pytest.raises(OverrideError, match="unknown series 'nope'"):
        _apply([{"op": "addToSeries", "target": "82", "series": "nope", "reason": "r"}])


def test_exclude():
    episodes, _ = _apply([{"op": "exclude", "target": "33", "reason": "r"}])
    assert _by_number(episodes)["33"].excluded
    result = match_public_feed(episodes, FEED, set())
    assert all(e.number != "33" for e in result.unmatched_episodes)


def test_ack_unmatched_wiki_and_feed():
    episodes, acked = _apply(
        [
            {"op": "ackUnmatchedWiki", "target": "33", "reason": "live show"},
            {"op": "ackUnmatchedFeed", "guid": "guid-trailer", "reason": "trailer"},
        ]
    )
    result = match_public_feed(episodes, FEED, acked)
    assert all(e.number != "33" for e in result.unmatched_episodes)
    assert "guid-trailer" not in {i.guid for i in result.unmatched_items}
    assert "guid-titanic-1" in {i.guid for i in result.unmatched_items}


def test_ack_that_is_no_longer_needed_is_reported():
    episodes, _ = _apply(
        [
            {"op": "fix", "target": "185", "airDate": "2018-09-30", "reason": "r"},
            {"op": "ackUnmatchedWiki", "target": "185", "reason": "r"},
        ]
    )
    result = match_public_feed(episodes, FEED, set())
    assert [e.number for e in result.acks_no_longer_needed] == ["185"]


def test_target_by_episode_id():
    previous = {
        "3018-09-30:space-jam": {
            "title": "Space Jam",
            "airDate": "3018-09-30",
            "wikiNumber": "185",
            "feed": "main",
            "series": [],
            "hints": {},
        }
    }
    episodes, _ = _apply(
        [{"op": "fix", "target": "3018-09-30:space-jam", "airDate": "2018-09-30", "reason": "r"}],
        previous=previous,
    )
    assert _by_number(episodes)["185"].air_date == date(2018, 9, 30)


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            {"op": "ackUnmatchedWiki", "target": "2001-01-01:not-here", "reason": "r"},
            "isn't in series.json",
        ),
        ({"op": "exclude", "target": "999", "reason": "r"}, "no wiki row has number 999"),
        (
            {"op": "pinPublicGuid", "target": "82", "guid": "nope", "reason": "r"},
            "no public feed item",
        ),
        ({"op": "ackUnmatchedFeed", "guid": "nope", "reason": "r"}, "no public feed item"),
    ],
)
def test_stale_override_names_itself(entry, message):
    with pytest.raises(OverrideError, match=message) as info:
        _apply([entry])
    assert "override #0" in str(info.value)


def test_stale_id_whose_row_vanished():
    previous = {
        "2001-01-01:gone": {
            "title": "Gone",
            "airDate": "2001-01-01",
            "wikiNumber": "999",
            "feed": "main",
            "series": [],
            "hints": {},
        }
    }
    with pytest.raises(OverrideError, match="no longer matches a wiki row"):
        _apply(
            [{"op": "ackUnmatchedWiki", "target": "2001-01-01:gone", "reason": "r"}],
            previous=previous,
        )


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"op": "exclude", "target": "33"}, "'reason' is required"),
        ({"op": "exclude", "target": "33", "reason": "  "}, "'reason' is required"),
        ({"op": "rename", "target": "33", "reason": "r"}, "unknown op"),
        ({"op": "fix", "target": "33", "reason": "r"}, "needs 'title' and/or 'airDate'"),
        ({"op": "fix", "target": "33", "airDate": "9/30/2018", "reason": "r"}, "YYYY-MM-DD"),
        ({"op": "exclude", "target": "Space Jam", "reason": "r"}, "neither an episode ID"),
        ({"op": "exclude", "target": "33", "reason": "r", "extra": 1}, "unexpected field"),
    ],
)
def test_malformed_overrides(entry, message):
    with pytest.raises(OverrideError, match=message):
        parse_overrides([entry])


# --- 5.2 stable IDs --------------------------------------------------------------


def _published(episodes):
    return {
        e.id: {
            "title": e.title,
            "airDate": e.air_date.isoformat(),
            "feed": e.feed,
            "series": [],
            "hints": {
                k: v
                for k, v in (("publicGuid", e.public_guid), ("patreonPostId", e.patreon_post_id))
                if v
            },
            **({"wikiNumber": e.number} if e.number else {}),
        }
        for e in episodes
    }


def test_new_rows_get_date_slug_ids():
    episodes = _episodes()
    assign_ids(episodes, {})
    assert _by_number(episodes)["23"].id == "2015-09-14:the-podtastic-two"
    assert _by_number(episodes)["SF294"].id == "2026-05-21:mortal-kombat-ii"


def test_id_survives_title_fix():
    first = _episodes()
    assign_ids(first, {})
    previous = _published(first)
    episodes, _ = _apply(
        [{"op": "fix", "target": "23", "title": "The Podcastic Two", "reason": "r"}]
    )
    assign_ids(episodes, previous)
    podcastic = _by_number(episodes)["23"]
    assert podcastic.title == "The Podcastic Two"
    assert podcastic.id == "2015-09-14:the-podtastic-two"


def test_id_survives_date_fix():
    first = _episodes()
    assign_ids(first, {})
    previous = _published(first)
    episodes, _ = _apply([{"op": "fix", "target": "185", "airDate": "2018-09-30", "reason": "r"}])
    assign_ids(episodes, previous)
    assert _by_number(episodes)["185"].id == "3018-09-30:space-jam"


def test_id_anchors_without_wiki_number():
    previous = {
        "2024-01-25:blank-check-on-broadway": {
            "title": "Blank Check on Broadway",
            "airDate": "2024-01-25",
            "feed": "main",
            "series": [],
            "hints": {"publicGuid": "guid-broadway"},
        }
    }
    # The wiki renames it and moves the date; the matched public GUID still anchors it.
    renamed = [WikiRow("Episodes", None, "Blank Check: Broadway", date(2024, 1, 26), "main")]
    episodes = episodes_from_rows(renamed, {id(r): [] for r in renamed})
    episodes[0].public_guid = "guid-broadway"
    assign_ids(episodes, previous)
    assert episodes[0].id == "2024-01-25:blank-check-on-broadway"


def test_id_anchors_by_patreon_post_id():
    previous = {
        "2026-05-21:mk2": {
            "title": "MK2",
            "airDate": "2026-05-21",
            "feed": "special-features",
            "series": [],
            "hints": {"patreonPostId": "158692113"},
        }
    }
    episodes = _episodes()
    assign_ids(episodes, previous)
    assert _by_number(episodes)["SF294"].id == "2026-05-21:mk2"


def test_duplicate_id_names_both_rows():
    rows = [
        WikiRow("Episodes", "1", "Same Title", date(2020, 1, 1), "main"),
        WikiRow(
            "Blank Check: Special Features",
            "SF1",
            "Same Title!",
            date(2020, 1, 1),
            "special-features",
        ),
    ]
    episodes = episodes_from_rows(rows, {id(r): [] for r in rows})
    with pytest.raises(GenerationError) as info:
        assign_ids(episodes, {})
    message = str(info.value)
    assert "duplicate episode ID 2020-01-01:same-title" in message
    assert "#1 'Same Title'" in message and "#SF1 'Same Title!'" in message


def test_previous_dataset_not_mutated():
    previous = {
        "2026-05-21:mk2": {
            "title": "MK2",
            "airDate": "2026-05-21",
            "feed": "special-features",
            "series": [],
            "hints": {"patreonPostId": "158692113"},
        }
    }
    snapshot = copy.deepcopy(previous)
    assign_ids(_episodes(), previous)
    assert previous == snapshot


# --- regression tests from the pre-PR review --------------------------------------


def test_exclude_by_episode_id_is_rejected():
    with pytest.raises(OverrideError, match="must be a wiki number, not an episode ID"):
        parse_overrides([{"op": "exclude", "target": "2019-01-27:kiss-from-a-rose", "reason": "r"}])


def _main_rows(*specs):
    rows = [WikiRow("Episodes", n, t, d, "main") for n, t, d in specs]
    return episodes_from_rows(rows, {id(r): [] for r in rows})


def test_renumbered_rows_keep_their_ids():
    """The wiki swaps two numbers; the matched GUIDs keep each ID on its episode."""
    previous = {
        "2026-09-20:the-king-of-comedy": {
            "title": "The King of Comedy",
            "airDate": "2026-09-20",
            "wikiNumber": "599",
            "feed": "main",
            "series": [],
            "hints": {"publicGuid": "guid-king"},
        },
        "2026-09-27:after-hours": {
            "title": "After Hours",
            "airDate": "2026-09-27",
            "wikiNumber": "600",
            "feed": "main",
            "series": [],
            "hints": {"publicGuid": "guid-after"},
        },
    }
    episodes = _main_rows(
        ("600", "The King of Comedy", date(2026, 9, 20)),
        ("599", "After Hours", date(2026, 9, 27)),
    )
    items = [
        FeedItem("guid-king", "The King of Comedy with Stavros Halkias", date(2026, 9, 20)),
        FeedItem("guid-after", "After Hours with Alison Sivitz", date(2026, 9, 27)),
    ]
    match_public_feed(episodes, items, set())
    assign_ids(episodes, previous)
    by_title = {e.title: e.id for e in episodes}
    assert by_title == {
        "The King of Comedy": "2026-09-20:the-king-of-comedy",
        "After Hours": "2026-09-27:after-hours",
    }


def test_renumbered_special_features_fall_back_to_post_id():
    previous = {
        "2026-05-21:mortal-kombat-ii": {
            "title": "Mortal Kombat II",
            "airDate": "2026-05-21",
            "wikiNumber": "SF294",
            "feed": "special-features",
            "series": [],
            "hints": {"patreonPostId": "111"},
        },
    }
    rows = [
        WikiRow(
            "Blank Check: Special Features",
            "SF294",
            "Something Else",
            date(2026, 5, 20),
            "special-features",
            patreon_post_id="222",
        ),
        WikiRow(
            "Blank Check: Special Features",
            "SF295",
            "Mortal Kombat II",
            date(2026, 5, 21),
            "special-features",
            patreon_post_id="111",
        ),
    ]
    episodes = episodes_from_rows(rows, {id(r): [] for r in rows})
    assign_ids(episodes, previous)
    assert {e.title: e.id for e in episodes} == {
        "Mortal Kombat II": "2026-05-21:mortal-kombat-ii",
        "Something Else": "2026-05-20:something-else",
    }


def test_fix_by_id_on_unnumbered_row_resolves_on_later_runs():
    """The published title is the fixed one; the ID still finds the raw wiki row."""
    episode_id = "2022-02-26:special-blank-check-march-madness-announcement"
    previous = {
        episode_id: {
            "title": "March Madness Announcement",
            "airDate": "2022-02-27",
            "feed": "main",
            "series": [],
            "hints": {},
        }
    }
    overrides = [
        {
            "op": "fix",
            "target": episode_id,
            "title": "March Madness Announcement",
            "airDate": "2022-02-27",
            "reason": "r",
        },
        {"op": "ackUnmatchedWiki", "target": episode_id, "reason": "r"},
    ]
    episodes = _main_rows(
        (None, "SPECIAL BLANK CHECK MARCH MADNESS ANNOUNCEMENT!", date(2022, 2, 26))
    )
    episodes, _ = _apply(overrides, episodes=episodes, previous=previous)
    assign_ids(episodes, previous)
    (episode,) = episodes
    assert episode.title == "March Madness Announcement"
    assert episode.acknowledged_unmatched
    assert episode.id == episode_id


def test_shared_post_id_dropped_from_every_claimant():
    rows = [
        WikiRow(
            "Blank Check: Special Features",
            "SF269",
            "Warriors",
            date(2025, 10, 11),
            "special-features",
            patreon_post_id="140857396",
        ),
        WikiRow(
            "Blank Check: Special Features",
            "SF269.5",
            "Warriors (Bite-Free Version)",
            date(2025, 10, 11),
            "special-features",
            patreon_post_id="140857396",
        ),
        WikiRow(
            "Blank Check: Special Features",
            "SF270",
            "Other",
            date(2025, 10, 21),
            "special-features",
            patreon_post_id="333",
        ),
    ]
    episodes = episodes_from_rows(rows, {id(r): [] for r in rows})
    shared = drop_shared_post_ids(episodes)
    assert list(shared) == ["140857396"]
    assert [e.patreon_post_id for e in episodes] == [None, None, "333"]


def test_pin_beats_another_episodes_title_match():
    episodes = _main_rows(
        ("1", "Taxi Driver", date(2026, 8, 30)),
        ("2", "Something Unrelated", date(2026, 8, 30)),
    )
    episodes[1].pinned_guid = "guid-taxi"
    items = [FeedItem("guid-taxi", "Taxi Driver with Tracy Letts", date(2026, 8, 30))]
    result = match_public_feed(episodes, items, set())
    assert episodes[1].public_guid == "guid-taxi"
    assert episodes[0].public_guid is None
    assert result.contested == {}


# --- regression tests from the second pre-PR review --------------------------------


def _published_titanic():
    return {
        "2016-11-03:titanic-part-one": {
            "title": "Titanic - Part One",
            "airDate": "2016-11-03",
            "wikiNumber": "82",
            "feed": "main",
            "series": [],
            "hints": {"publicGuid": "guid-titanic-1"},
        },
        "2016-11-11:titanic-part-two": {
            "title": "Titanic - Part Two",
            "airDate": "2016-11-11",
            "wikiNumber": "83",
            "feed": "main",
            "series": [],
            "hints": {"publicGuid": "guid-titanic-2"},
        },
    }


def test_number_target_that_moved_to_another_row_fails_loudly():
    episodes = _main_rows(
        ("83", "Titanic - Part One", date(2016, 11, 3)),
        ("82", "Titanic - Part Two", date(2016, 11, 11)),
    )
    pin = [{"op": "pinPublicGuid", "target": "82", "guid": "guid-titanic-1", "reason": "r"}]
    with pytest.raises(OverrideError, match="wiki number 82 now belongs to .*Part Two"):
        _apply(pin, episodes=episodes, previous=_published_titanic())


def test_number_target_still_on_its_episode_is_fine():
    episodes = _main_rows(("82", "Titanic - Part One", date(2016, 11, 3)))
    pin = [{"op": "pinPublicGuid", "target": "82", "guid": "guid-titanic-1", "reason": "r"}]
    episodes, _ = _apply(pin, episodes=episodes, previous=_published_titanic())
    assert episodes[0].pinned_guid == "guid-titanic-1"


def test_zero_padded_number_target_is_canonical():
    (override,) = parse_overrides([{"op": "exclude", "target": "033", "reason": "r"}])
    assert override.target == "33"
    (override,) = parse_overrides([{"op": "exclude", "target": "SF001", "reason": "r"}])
    assert override.target == "SF1"


def test_id_target_after_renumbering_lands_on_its_episode():
    previous = {
        "2016-10-28:true-lies": {
            "title": "True Lies",
            "airDate": "2016-10-28",
            "wikiNumber": "81",
            "feed": "main",
            "series": [],
            "hints": {"publicGuid": "guid-true-lies"},
        },
    }
    episodes = _main_rows(
        ("81", "Aliens of the Deep/Ghosts of the Abyss", date(2016, 11, 18)),
        ("84", "True Lies", date(2016, 10, 28)),
    )
    add = [
        {
            "op": "addToSeries",
            "target": "2016-10-28:true-lies",
            "series": "podinator-judgment-cast",
            "reason": "r",
        }
    ]
    episodes, _ = _apply(add, episodes=episodes, previous=previous)
    by_title = {e.title: e for e in episodes}
    assert by_title["True Lies"].series == ["podinator-judgment-cast"]
    assert by_title["Aliens of the Deep/Ghosts of the Abyss"].series == []


def test_override_and_id_on_different_rows_is_an_error():
    """The override resolves by the minted ID, but the GUID gives the ID to another row."""
    previous = {
        "2020-01-01:x": {
            "title": "Renamed",
            "airDate": "2020-02-02",
            "wikiNumber": "5",
            "feed": "main",
            "series": [],
            "hints": {"publicGuid": "guid-x"},
        },
    }
    episodes = _main_rows(
        ("6", "X", date(2020, 1, 1)),
        ("5", "Other", date(2021, 1, 1)),
    )
    ack = [{"op": "ackUnmatchedWiki", "target": "2020-01-01:x", "reason": "r"}]
    episodes, _ = _apply(ack, episodes=episodes, previous=previous)
    episodes[1].public_guid = "guid-x"
    with pytest.raises(OverrideError, match="but that row's ID is"):
        assign_ids(episodes, previous)
