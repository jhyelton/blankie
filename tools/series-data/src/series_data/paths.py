"""Where the tool's inputs and outputs live in the repository."""

from __future__ import annotations

from pathlib import Path

# src/series_data/paths.py -> src -> tools/series-data -> tools -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data"
SERIES_JSON = DATA_DIR / "series.json"
SCHEMA_JSON = DATA_DIR / "series.schema.json"
OVERRIDES_JSON = DATA_DIR / "overrides.json"
CONTRACTS_DIR = REPO_ROOT / "contracts"
MATCHING_VECTORS_JSON = CONTRACTS_DIR / "matching-vectors.json"
MATCHING_VECTORS_SCHEMA_JSON = CONTRACTS_DIR / "matching-vectors.schema.json"
