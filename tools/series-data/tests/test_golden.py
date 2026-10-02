"""Golden-file tests: `generate` on the committed fixtures, compared byte for byte."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from helpers import FIXTURES

from series_data.fetch import OfflineSource
from series_data.generate import generate, serialize
from series_data.overrides import load_overrides

GOLDEN = FIXTURES / "golden"
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"
NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)


def _check(path: Path, actual: str) -> None:
    if UPDATE:
        path.write_text(actual)
    assert actual == path.read_text(), f"{path.name} changed; rerun with UPDATE_GOLDEN=1 to review"


def _first_run(offline_dir):
    overrides = load_overrides(GOLDEN / "overrides.json")
    return generate(OfflineSource(offline_dir), overrides, None, now=NOW)


def test_first_run_dataset_and_report(offline_dir):
    result = _first_run(offline_dir)
    _check(GOLDEN / "series.json", serialize(result.dataset))
    _check(GOLDEN / "first-run-report.md", result.report)


def test_output_is_deterministic(offline_dir):
    one = _first_run(offline_dir).dataset
    two = generate(
        OfflineSource(offline_dir),
        load_overrides(GOLDEN / "overrides.json"),
        None,
        now=datetime(2027, 1, 1, tzinfo=UTC),
    ).dataset
    one.pop("generatedAt")
    two.pop("generatedAt")
    assert serialize(one) == serialize(two)


def test_unchanged_rerun_keeps_generated_at(offline_dir):
    first = _first_run(offline_dir).dataset
    again = generate(
        OfflineSource(offline_dir),
        load_overrides(GOLDEN / "overrides.json"),
        first,
        now=datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert serialize(again.dataset) == serialize(first)


def test_disclosure_day_sorts_last_in_its_series(offline_dir):
    dataset = _first_run(offline_dir).dataset
    (spielberg,) = [s for s in dataset["series"] if s["title"] == "Pod Me If You Cast"]
    last = dataset["episodes"][spielberg["episodes"][-1]]
    assert last["title"] == "Disclosure Day"
    assert spielberg["episodes"][-1] == "2026-06-14:disclosure-day"
    dates = [dataset["episodes"][e]["airDate"] for e in spielberg["episodes"]]
    assert dates == sorted(dates)


def test_odyssey_in_nolan_not_stanton(offline_dir):
    dataset = _first_run(offline_dir).dataset
    by_title = {s["title"]: s for s in dataset["series"]}
    assert "2026-07-19:the-odyssey" in by_title["The Pod Knight Casts"]["episodes"]
    assert "2026-07-19:the-odyssey" not in by_title["PODD-C"]["episodes"]


@pytest.mark.parametrize(
    ("episode_id", "series_title"),
    [
        ("2026-09-27:after-hours", "Podcastfellas"),
        (
            "2026-06-11:billie-eilish-hit-me-hard-and-soft-the-tour-live-in-3d-babe-pig-in-the-city-at-the-28th-wisconsin-film-festival",
            "Patreon Standalones",
        ),
    ],
)
def test_membership_both_ways(offline_dir, episode_id, series_title):
    dataset = _first_run(offline_dir).dataset
    (series,) = [s for s in dataset["series"] if s["title"] == series_title]
    assert episode_id in series["episodes"]
    assert series["id"] in dataset["episodes"][episode_id]["series"]


def test_after_hours_entry(offline_dir):
    dataset = _first_run(offline_dir).dataset
    assert dataset["episodes"]["2026-09-27:after-hours"] == {
        "title": "After Hours",
        "airDate": "2026-09-27",
        "feed": "main",
        "wikiNumber": "600",
        "series": ["podcastfellas"],
        "hints": {
            "publicGuid": "cb353980-fae9-11f0-9ff5-ebf9d6641dd0",
            "publicTitle": "After Hours with Alison Sivitz",
        },
    }


def test_attribution(offline_dir):
    dataset = _first_run(offline_dir).dataset
    assert dataset["source"]["license"] == "CC BY-SA"
    assert dataset["source"]["licenseUrl"] == "https://www.fandom.com/licensing"
    assert all(
        s["wikiUrl"].startswith("https://blank-check.fandom.com/wiki/") for s in dataset["series"]
    )


def test_no_urls_in_episodes(offline_dir):
    dataset = _first_run(offline_dir).dataset
    assert "http" not in json.dumps(dataset["episodes"])
