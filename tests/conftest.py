from pathlib import Path

import pytest

from company_lookup.core import Run, initialize_run


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return initialize_run(tmp_path, 10)

