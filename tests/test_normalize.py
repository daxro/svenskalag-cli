import pytest

from svenskalag_cli.api.normalize import (
    extract_times,
    infer_type,
    parse_iso_date,
    parse_swedish_date,
)
from svenskalag_cli.errors import InputError


def test_swedish_dates_and_times():
    assert parse_swedish_date("Måndag 24 aug", 2026) == "2026-08-24"
    assert parse_swedish_date("24 augusti 2026") == "2026-08-24"
    assert extract_times("07:05-7:50") == ["07:05", "07:50"]


def test_iso_date_validation():
    assert parse_iso_date("2026-08-24").isoformat() == "2026-08-24"
    with pytest.raises(InputError):
        parse_iso_date("2026-02-30")


def test_activity_type_is_conservative():
    assert infer_type("Kvällsträning") == "training"
    assert infer_type("Information") is None
