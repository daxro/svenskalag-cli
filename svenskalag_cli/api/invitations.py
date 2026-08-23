"""Read-only parser for My Pages > Invitations."""

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from svenskalag_cli.api.normalize import clean_text, extract_times, parse_swedish_date
from svenskalag_cli.session import get


def _person_tabs(soup):
    people = {}
    for anchor in soup.select('a[href*="userid="]'):
        values = parse_qs(urlparse(anchor.get("href", "")).query).get("userid")
        if not values:
            continue
        name = re.sub(r"\s*\(\d+\)\s*$", "", clean_text(anchor.get_text(" ", strip=True)) or "")
        people[values[0]] = "Me" if name == "Till mig" else name
    return people


def parse_invitations(html, group_slug, base_url, person_id=None):
    """Parse invitations; an empty table produces an empty list."""
    soup = BeautifulSoup(html, "html.parser")
    names = _person_tabs(soup)
    invitations = []
    seen = set()
    for row in soup.select("table tr"):
        anchor = row.find("a", href=re.compile(r"/aktivitet/\d+"))
        if anchor is None:
            continue
        href = urljoin(base_url, anchor.get("href"))
        match = re.search(r"/aktivitet/(\d+)", href)
        if not match:
            continue
        current_person = str(person_id) if person_id is not None else row.get("data-userid")
        key = (match.group(1), current_person)
        if key in seen:
            continue
        text = clean_text(row.get_text(" ", strip=True)) or ""
        date_value = parse_swedish_date(text)
        start_time = extract_times(text)[0]
        response = "unanswered"
        classes = " ".join(row.get("class", [])).casefold()
        if "accept" in classes or re.search(r"\bKommer\b", text):
            response = "yes"
        elif "decline" in classes or "Kan ej" in text:
            response = "no"
        title_node = row.select_one(".activity-name, .title") or anchor
        invitations.append({
            "id": match.group(1), "group": None, "group_slug": group_slug,
            "title": clean_text(title_node.get_text(" ", strip=True)),
            "date": date_value, "start_time": start_time,
            "person": names.get(current_person), "person_id": current_person,
            "response": response, "url": href,
        })
        seen.add(key)
    return invitations


def fetch_invitations(session, group_url, group_name, person_id=None):
    url = f"{group_url}/minasidor/kallelser"
    if person_id is not None:
        url += f"?userid={person_id}"
    response = get(session, url)
    group_slug = group_url.rstrip("/").rsplit("/", 1)[-1]
    invitations = parse_invitations(response.text, group_slug, group_url, person_id)
    for invitation in invitations:
        invitation["group"] = group_name
    return sorted(invitations, key=lambda item: (item["date"] or "", item["start_time"] or "", item["id"]))
