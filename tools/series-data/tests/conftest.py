from pathlib import Path

import pytest
from helpers import write_offline_dir


@pytest.fixture
def offline_dir(tmp_path: Path) -> Path:
    return write_offline_dir(tmp_path / "raw")
