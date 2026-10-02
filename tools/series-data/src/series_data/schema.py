"""Validation of a dataset against data/series.schema.json."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from series_data.paths import SCHEMA_JSON


class SchemaError(Exception):
    """The dataset doesn't match the published schema."""


@cache
def _validator(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def schema_errors(dataset: Any, schema_path: Path = SCHEMA_JSON) -> list[str]:
    """Return one readable line per schema violation, sorted, empty when valid."""
    errors = _validator(schema_path).iter_errors(dataset)
    return sorted(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors
    )


def validate(dataset: Any, schema_path: Path = SCHEMA_JSON) -> None:
    errors = schema_errors(dataset, schema_path)
    if errors:
        raise SchemaError("series.json failed schema validation:\n  " + "\n  ".join(errors))
