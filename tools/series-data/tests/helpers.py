"""Shared test helpers (importable as `helpers`)."""

import json
import shutil
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def wikitext(name: str) -> str:
    return (FIXTURES / "wiki" / f"{name}.wikitext").read_text()


def write_offline_dir(directory: Path) -> Path:
    """Lay the fixtures out the way `generate --save-raw` saves real responses."""
    directory.mkdir(parents=True, exist_ok=True)
    for key in ("episodes", "special-features", "miniseries"):
        payload = {"parse": {"wikitext": wikitext(key)}}
        (directory / f"{key}.json").write_text(json.dumps(payload))
    shutil.copy(FIXTURES / "wiki" / "redirects.json", directory / "redirects.json")
    shutil.copy(FIXTURES / "public-feed.xml", directory / "public-feed.xml")
    return directory
