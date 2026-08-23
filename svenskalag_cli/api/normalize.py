"""Normalize Swedish dates, times, and HTML text."""

import re
from datetime import date, timedelta

from svenskalag_cli.errors import InputError

MONTHS = {
    "jan": 1, "januari": 1, "feb": 2, "februari": 2, "mar": 3, "mars": 3,
    "apr": 4, "april": 4, "maj": 5, "jun": 6, "juni": 6, "jul": 7,
    "juli": 7, "aug": 8, "augusti": 8, "sep": 9, "september": 9,
    "okt": 10, "oktober": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
MONTH_SLUGS = {
    1: "januari", 2: "februari", 3: "mars", 4: "april", 5: "maj", 6: "juni",
    7: "juli", 8: "augusti", 9: "september", 10: "oktober", 11: "november", 12: "december",
}


def clean_text(value):
    """Collapse whitespace while preserving intentional paragraph breaks."""
    if value is None:
        return None
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(value).splitlines()]
    return "\n".join(line for line in lines if line) or None


def parse_iso_date(value):
    """Validate a real ISO date."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def parse_swedish_date(value, year=None):
    """Parse values such as '16 aug' or '16 augusti 2026'."""
    if not value:
        return None
    match = re.search(r"(\d{1,2})\s+([a-zåäö]+)(?:\s+(\d{4}))?", value, re.IGNORECASE)
    if not match:
        return None
    month = MONTHS.get(match.group(2).lower().rstrip("."))
    actual_year = int(match.group(3)) if match.group(3) else year
    if not month or not actual_year:
        return None
    try:
        return date(actual_year, month, int(match.group(1))).isoformat()
    except ValueError:
        return None


def parse_recent_swedish_date(value, today=None):
    """Parse a yearless news date as the latest reasonable date."""
    today = today or date.today()
    parsed = parse_swedish_date(value, today.year)
    if parsed is None:
        return None
    candidate = date.fromisoformat(parsed)
    if candidate > today + timedelta(days=31):
        return candidate.replace(year=candidate.year - 1).isoformat()
    return candidate.isoformat()


def extract_times(value):
    """Return up to two times in HH:MM format."""
    times = re.findall(r"(?<!\d)(\d{1,2}:\d{2})(?!\d)", value or "")
    normalized = [f"{int(item.split(':')[0]):02d}:{item.split(':')[1]}" for item in times]
    return (normalized + [None, None])[:2]


def infer_type(title):
    """Conservatively infer an activity type from the title."""
    lowered = (title or "").casefold()
    for needle, value in (
        ("träning", "training"), ("traning", "training"), ("match", "match"),
        ("möte", "meeting"), ("mote", "meeting"), ("tävling", "competition"),
        ("tavling", "competition"), ("läger", "camp"), ("lager", "camp"),
    ):
        if needle in lowered:
            return value
    return None


def parse_title_year(title):
    """Extract a year from the page title or meta title."""
    match = re.search(r"\b(20\d{2})\b", title or "")
    return int(match.group(1)) if match else None
