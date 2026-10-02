"""Runs every case in contracts/matching-vectors.json."""

import json
from datetime import date

import pytest
from jsonschema import Draft202012Validator

from series_data.matching import FeedItem, match, normalize
from series_data.paths import MATCHING_VECTORS_JSON, MATCHING_VECTORS_SCHEMA_JSON

VECTORS = json.loads(MATCHING_VECTORS_JSON.read_text())


def test_vectors_file_matches_its_schema():
    schema = json.loads(MATCHING_VECTORS_SCHEMA_JSON.read_text())
    Draft202012Validator.check_schema(schema)
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(VECTORS)]
    assert errors == []


def test_vector_names_are_unique():
    for kind in ("normalization", "matching"):
        names = [case["name"] for case in VECTORS[kind]]
        assert len(names) == len(set(names)), kind


@pytest.mark.parametrize("case", VECTORS["normalization"], ids=lambda c: c["name"])
def test_normalization(case):
    assert normalize(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", VECTORS["matching"], ids=lambda c: c["name"])
def test_matching(case):
    episode = case["episode"]
    items = [
        FeedItem(c["guid"], c["title"], date.fromisoformat(c["pubDate"]))
        for c in case["candidates"]
    ]
    result = match(
        episode["title"], date.fromisoformat(episode["airDate"]), items, episode.get("hints")
    )
    assert (result.guid if result else None) == case["expected"]
