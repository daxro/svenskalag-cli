"""Detail parser for an activity and read-only response status."""

import re

from bs4 import BeautifulSoup

from svenskalag_cli.api.normalize import (
    clean_text,
    extract_times,
    infer_type,
    parse_swedish_date,
    parse_title_year,
)
from svenskalag_cli.errors import NotFoundError, ParseError
from svenskalag_cli.session import get


def _response_from_classes(classes):
    joined = " ".join(classes or []).casefold()
    if any(value in joined for value in ("accept", "yes", "attend")):
        return "yes"
    if any(value in joined for value in ("decline", "no", "deny")):
        return "no"
    return "unanswered"


def parse_activity(html, group_slug, event_id, url):
    """Parse activity details from the authenticated web page."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".schedule-info-container")
    title_node = container.find_previous("h1") if container else soup.find("h1")
    if title_node is None:
        raise ParseError("Could not parse the activity title.")
    title = clean_text(title_node.get_text(" ", strip=True))
    headings = container.find_all("h2") if container else soup.find_all("h2")
    date_text = clean_text(headings[0].get_text(" ", strip=True)) if headings else None
    year = parse_title_year(soup.title.get_text(" ", strip=True) if soup.title else "")
    event_date = parse_swedish_date(date_text, year)
    start_time, end_time = extract_times(date_text)
    location = clean_text(headings[1].get_text(" ", strip=True)) if len(headings) > 1 else None

    assembly_time = None
    description = None
    if container:
        assembly = container.find(string=re.compile(r"Samling:"))
        if assembly:
            assembly_time = extract_times(str(assembly))[0]
        description_node = container.select_one("div.break-long-words")
        description = clean_text(description_node.get_text("\n", strip=True)) if description_node else None

    registration = None
    registration_heading = soup.find(lambda tag: tag.name in {"h3", "h4"} and "Anmälan" in tag.get_text(" ", strip=True))
    person_rows = []
    for tbody in soup.select("tbody[data-memberid], tbody[data-member-id]"):
        person_id = tbody.get("data-memberid") or tbody.get("data-member-id")
        name_node = tbody.find("b")
        comment_node = tbody.select_one("input.comment")
        active = tbody.select_one(".reply-button.active")
        person_rows.append({
            "person_id": str(person_id),
            "person_name": clean_text(name_node.get_text(" ", strip=True)) if name_node else None,
            "response": _response_from_classes(active.get("class") if active else []),
            "comment": comment_node.get("value") or None if comment_node else None,
        })
    if registration_heading or person_rows:
        deadline = None
        deadline_node = soup.find(string=re.compile(r"Svara senast:"))
        if deadline_node:
            deadline_text = str(deadline_node).split(":", 1)[-1].strip()
            deadline = {
                "date": parse_swedish_date(deadline_text, year),
                "time": extract_times(deadline_text)[0],
            }
        registration = {"deadline": deadline, "responses": person_rows}

    return {
        "id": str(event_id), "group": None, "group_slug": group_slug,
        "type": infer_type(title), "title": title, "cancelled": False,
        "date": event_date, "start_time": start_time, "end_time": end_time,
        "assembly_time": assembly_time, "location": location,
        "description": description, "url": url, "registration": registration,
    }


def fetch_activity(session, group_url, group_name, event_id):
    """Fetch the activity through the stable ID-based path."""
    url = f"{group_url}/aktivitet/{event_id}"
    response = get(session, url)
    if "/blank/PageNotFound" in response.url or response.status_code == 404:
        raise NotFoundError(f"Activity '{event_id}' was not found.")
    group_slug = group_url.rstrip("/").rsplit("/", 1)[-1]
    activity = parse_activity(response.text, group_slug, event_id, response.url)
    activity["group"] = group_name
    return activity
