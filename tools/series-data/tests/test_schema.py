import copy

import pytest

from series_data.schema import SchemaError, schema_errors, validate

VALID = {
    "schemaVersion": 1,
    "generatedAt": "2026-10-05T09:00:00Z",
    "source": {
        "name": "Blank Check with Griffin and David Wiki",
        "url": "https://blank-check.fandom.com",
        "license": "CC BY-SA",
        "licenseUrl": "https://www.fandom.com/licensing",
    },
    "series": [
        {
            "id": "podcastfellas",
            "title": "Podcastfellas",
            "subject": "Martin Scorsese",
            "category": "director",
            "wikiUrl": "https://blank-check.fandom.com/wiki/Podcastfellas",
            "episodes": ["2026-09-27:after-hours"],
        }
    ],
    "episodes": {
        "2026-09-27:after-hours": {
            "title": "After Hours",
            "airDate": "2026-09-27",
            "feed": "main",
            "wikiNumber": "600",
            "series": ["podcastfellas"],
            "hints": {
                "publicGuid": "cb353980-fae9-11f0-9ff5-ebf9d6641dd0",
                "publicTitle": "After Hours with Alison Sivitz",
            },
        },
        "2026-05-21:mortal-kombat-ii": {
            "title": "Mortal Kombat II",
            "airDate": "2026-05-21",
            "feed": "special-features",
            "wikiNumber": "SF294",
            "series": [],
            "hints": {"patreonPostId": "158692113"},
        },
    },
}


def _mutated(fn):
    doc = copy.deepcopy(VALID)
    fn(doc)
    return doc


def test_schema_valid_document():
    assert schema_errors(VALID) == []
    validate(VALID)


@pytest.mark.parametrize(
    ("name", "mutate", "needle"),
    [
        (
            "missing air date",
            lambda d: d["episodes"]["2026-09-27:after-hours"].pop("airDate"),
            "'airDate' is a required property",
        ),
        (
            "bad category",
            lambda d: d["series"][0].update(category="franchise"),
            "'franchise' is not one of",
        ),
        (
            "unknown feed value",
            lambda d: d["episodes"]["2026-09-27:after-hours"].update(feed="patreon"),
            "'patreon' is not one of",
        ),
        (
            "audio URL present",
            lambda d: d["episodes"]["2026-09-27:after-hours"].update(
                audioUrl="https://traffic.megaphone.fm/EXAMPLE.mp3"
            ),
            "Additional properties are not allowed ('audioUrl'",
        ),
        (
            "enclosure URL in hints",
            lambda d: d["episodes"]["2026-09-27:after-hours"]["hints"].update(
                enclosureUrl="https://traffic.megaphone.fm/EXAMPLE.mp3"
            ),
            "Additional properties are not allowed ('enclosureUrl'",
        ),
        (
            "missing attribution",
            lambda d: d["source"].pop("license"),
            "'license' is a required property",
        ),
        (
            "malformed date",
            lambda d: d["episodes"]["2026-09-27:after-hours"].update(airDate="9/27/2026"),
            "airDate",
        ),
    ],
)
def test_schema_rejects_invalid(name, mutate, needle):
    errors = schema_errors(_mutated(mutate))
    assert any(needle in e for e in errors), errors
    with pytest.raises(SchemaError):
        validate(_mutated(mutate))
