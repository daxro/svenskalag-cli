from pathlib import Path

import pytest


@pytest.fixture
def fixture_text():
    root = Path(__file__).parent / "fixtures"

    def load(name):
        return (root / name).read_text(encoding="utf-8")

    return load
