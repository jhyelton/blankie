from datetime import date

import pytest
from helpers import wikitext

from series_data.wiki import (
    SeriesLink,
    WikiParseError,
    parse_episodes,
    parse_miniseries,
    parse_special_features,
    patreon_post_id,
)

HEADER = """{| class="wikitable"
|-
! # !! Title !! Audio !! Guest(s) !! Length !! Date !! Series
"""


@pytest.fixture(scope="module")
def episodes():
    return {row.number or row.title: row for row in parse_episodes(wikitext("episodes"))}


@pytest.fixture(scope="module")
def special_features():
    return {row.number: row for row in parse_special_features(wikitext("special-features"))}


def test_rowspan_series_carried_down(episodes):
    for number in [str(n) for n in range(1, 12)]:
        assert episodes[number].series == [SeriesLink("The Phantom Podcast")]
    assert episodes["11"].title == "Watch With Us"


def test_rowspan_ends(episodes):
    assert episodes["23"].series == [
        SeriesLink("Standalones", "Other Standalone Episodes", "Standalone")
    ]
    assert episodes["24"].series == [SeriesLink("Revenge of The Podcast")]


def test_rowspan_over_guests_with_missing_guest_cell(episodes):
    # #032 spans its guest cell over #033, and #033 leaves the cell out.
    row = episodes["33"]
    assert row.title == "Watch With Us Live @ Union Hall"
    assert row.air_date == date(2015, 11, 30)
    assert row.series == [SeriesLink("Revenge of The Podcast")]


def test_two_series_in_one_cell(episodes):
    assert episodes["80"].series == [
        SeriesLink("Standalones", "Other Standalone Episodes", "Standalone"),
        SeriesLink("Stealth McQuarrie Miniseries"),
    ]


def test_span_markup_stripped_from_titles(episodes):
    assert episodes["85"].title == "Avatar"
    assert episodes["86"].title == "Toruk: The First Flight"


def test_typo_year_parsed_as_is(episodes):
    assert episodes["185"].title == "Space Jam"
    assert episodes["185"].air_date == date(3018, 9, 30)


def test_unclosed_bold_does_not_swallow_the_table(episodes):
    row = episodes["Blank Check LIVE! at Town Hall (2025)"]
    assert row.number is None
    assert row.air_date == date(2025, 3, 6)
    assert row.series == [SeriesLink("Announcements")]
    assert "584" in episodes


def test_commented_and_placeholder_rows_skipped(episodes):
    assert "601" not in episodes
    assert all(row.title != "The Color of Money" for row in episodes.values())
    assert "..." not in episodes
    assert episodes["600"].title == "After Hours"
    assert episodes["600"].air_date == date(2026, 9, 27)


def test_main_feed_rows_have_no_post_id(episodes):
    assert all(row.patreon_post_id is None for row in episodes.values())
    assert all(row.feed == "main" for row in episodes.values())


def test_row_with_empty_series_cell_has_no_series():
    table = (
        HEADER
        + """|-
| 001
| '''[[Some Episode]]'''
| [https://example.invalid/a 🔊]
| [[A Guest]]
| 1:00
| 1/2/2020
|
|}"""
    )
    (row,) = parse_episodes(table)
    assert row.series == []
    assert row.air_date == date(2020, 1, 2)


@pytest.mark.parametrize(
    "cells",
    [
        # Series cell missing with no rowspan covering it.
        "| 001\n| '''[[A]]'''\n| audio\n| guest\n| 1:00\n| 1/2/2020",
        # An extra column.
        "| 001\n| '''[[A]]'''\n| audio\n| guest\n| 1:00\n| 1/2/2020\n| [[S]]\n| extra",
        # Date in the wrong format.
        "| 001\n| '''[[A]]'''\n| audio\n| guest\n| 1:00\n| 2020-01-02\n| [[S]]",
    ],
)
def test_unexpected_layout_raises(cells):
    with pytest.raises(WikiParseError):
        parse_episodes(HEADER + "|-\n" + cells + "\n|}")


def test_series_cell_with_plain_text_raises():
    table = HEADER + "|-\n| 001\n| '''[[A]]'''\n| a\n| g\n| 1:00\n| 1/2/2020\n| Not a link\n|}"
    with pytest.raises(WikiParseError, match="isn't a link"):
        parse_episodes(table)


def test_special_features_numbers_and_post_ids(special_features):
    assert special_features["SF294"].title == "Mortal Kombat II"
    assert special_features["SF294"].patreon_post_id == "158692113"
    assert special_features["SF294"].feed == "special-features"
    assert special_features["SF269"].title == "Spreadmaster's Delight 3: Decade-of-Dreams Warriors"


def test_special_features_two_series(special_features):
    assert special_features["SF296"].series == [
        SeriesLink("Podinator: Judgment Cast"),
        SeriesLink("Patreon Standalones"),
    ]
    assert special_features["SF296"].patreon_post_id == "159935660"


def test_special_features_rowspans_over_several_columns(special_features):
    half = special_features["SF182.5"]
    assert half.air_date == date(2023, 7, 11)
    assert half.series == [SeriesLink("Patreon Standalones")]
    assert half.patreon_post_id == "85911862"


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("[https://www.patreon.com/posts/mortal-kombat-ii-158692113 🔊]", "158692113"),
        ("[https://www.patreon.com/blankcheck/posts/billie-eilish-me-159935660 🔊]", "159935660"),
        ("[https://www.patreon.com/posts/158692113 🔊]", "158692113"),
        ("[https://soundcloud.com/x/y 🔊]", None),
        ("[ 🔊]", None),
    ],
)
def test_patreon_post_id_link_forms(cell, expected):
    assert patreon_post_id(cell) == expected


@pytest.fixture(scope="module")
def miniseries():
    return {entry.link.target: entry for entry in parse_miniseries(wikitext("miniseries"))}


def test_miniseries_director(miniseries):
    entry = miniseries["PodcastFellas"]
    assert entry.subject == "Martin Scorsese"
    assert entry.category == "director"


def test_miniseries_star_wars(miniseries):
    assert miniseries["The Phantom Podcast"].category == "star-wars"


def test_miniseries_other_and_special_features(miniseries):
    assert miniseries["Mortal Kombat"].category == "special-features"
    assert miniseries["Stealth McQuarrie Miniseries"].category == "other"
    ben = miniseries["Standalones"]  # the bare Standalones row comes first...
    assert ben.category == "other"


def test_miniseries_subject_drops_footnotes(miniseries):
    assert (
        miniseries["Revenge of The Podcast"].subject == "Star Wars Episode III: Revenge Of The Sith"
    )


def test_miniseries_unknown_heading_raises():
    renamed = wikitext("miniseries").replace("===Director Filmographies===", "===Directors===")
    with pytest.raises(WikiParseError, match="unknown section heading 'directors'"):
        parse_miniseries(renamed)
