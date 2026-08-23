"""Read Svenskalag's month-based group calendar."""

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from svenskalag_cli.api.normalize import (
    MONTH_SLUGS,
    clean_text,
    extract_times,
    infer_type,
)
from svenskalag_cli.errors import InputError
from svenskalag_cli.session import get


def _month_iter(start, end):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month == 13:
            year += 1
            month = 1


def parse_calendar_month(html, group_slug, year, month, base_url="https://www.svenskalag.se"):
    """Parse activity rows from a calendar month."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()
    current_day = None
    for row in soup.select("table tr"):
        date_node = row.select_one(".date b")
        if date_node is not None:
            try:
                current_day = int(date_node.get_text(strip=True))
            except ValueError:
                current_day = None
        if "clickable-row" not in (row.get("class") or []):
            continue
        anchor = row.find("a", href=re.compile(r"/aktivitet/\d+"))
        if anchor is None:
            continue
        href = urljoin(base_url, anchor.get("href"))
        match = re.search(r"/aktivitet/(\d+)", href)
        if not match or match.group(1) in seen:
            continue
        name_node = row.select_one(".activity-name")
        if current_day is None or name_node is None:
            continue
        try:
            event_date = date(year, month, current_day).isoformat()
        except ValueError:
            continue
        cells = row.find_all("td")
        start_time, end_time = extract_times(cells[1].get_text(" ", strip=True) if len(cells) > 1 else "")
        title = clean_text(name_node.get_text(" ", strip=True))
        location = None
        if len(cells) > 2:
            candidates = cells[2].select("span.text-muted.small")
            if candidates:
                location = clean_text(candidates[0].get_text(" ", strip=True))
        events.append({
            "id": match.group(1),
            "group": None,
            "group_slug": group_slug,
            "type": infer_type(title),
            "title": title,
            "cancelled": "danger" in (row.get("class") or []),
            "date": event_date,
            "start_time": start_time,
            "end_time": end_time,
            "assembly_time": None,
            "location": location,
            "description": None,
            "url": href,
            "registration": None,
        })
        seen.add(match.group(1))
    return events


def fetch_calendar(session, group_url, group_name, since, until, limit=None):
    """Fetch only the months and rows that are needed."""
    if until < since:
        raise InputError("--until cannot be earlier than --since.")
    if (until.year - since.year) * 12 + until.month - since.month >= 24:
        raise InputError("The calendar range may span at most 24 months.")
    group_slug = group_url.rstrip("/").rsplit("/", 1)[-1]
    events = []
    seen = set()
    for year, month in _month_iter(since, until):
        response = get(session, f"{group_url}/kalender/{year}/{MONTH_SLUGS[month]}")
        for event in parse_calendar_month(response.text, group_slug, year, month, group_url):
            if event["id"] in seen or not (since.isoformat() <= event["date"] <= until.isoformat()):
                continue
            event["group"] = group_name
            events.append(event)
            seen.add(event["id"])
            if limit is not None and len(events) >= limit:
                return sorted(events, key=_sort_key)
    return sorted(events, key=_sort_key)


def _sort_key(item):
    return (item["date"], item["start_time"] or "", item["id"])
