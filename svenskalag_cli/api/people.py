"""People whose invitations the signed-in account can read."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from svenskalag_cli.api.normalize import clean_text
from svenskalag_cli.session import get


def parse_people(html, base_url):
    """Parse person IDs from My Pages and invitation tabs."""
    soup = BeautifulSoup(html, "html.parser")
    people = []
    seen = set()
    for anchor in soup.select('a[href*="/personuppgifter/"]'):
        href = urljoin(base_url, anchor.get("href"))
        match = re.search(r"/personuppgifter/(\d+)/", href)
        if not match or match.group(1) in seen:
            continue
        text = clean_text(anchor.get_text(" ", strip=True)) or ""
        is_self = "Mina uppgifter" in text
        name = "Me" if is_self else re.sub(r"\s+uppgifter$", "", text)
        people.append({"id": match.group(1), "name": name, "self": is_self})
        seen.add(match.group(1))

    for anchor in soup.select('a[href*="userid="]'):
        match = re.search(r"[?&]userid=(\d+)", anchor.get("href", ""))
        if not match or match.group(1) in seen:
            continue
        name = re.sub(r"\s*\(\d+\)\s*$", "", clean_text(anchor.get_text(" ", strip=True)) or "")
        people.append({"id": match.group(1), "name": "Me" if name == "Till mig" else name, "self": name == "Till mig"})
        seen.add(match.group(1))
    return sorted(people, key=lambda item: (not item["self"], item["name"].casefold(), item["id"]))


def fetch_people(session, configured_url):
    page = get(session, f"{configured_url}/minasidor")
    people = parse_people(page.text, configured_url)
    invitation_page = get(session, f"{configured_url}/minasidor/kallelser")
    extra = parse_people(invitation_page.text, configured_url)
    by_id = {item["id"]: item for item in people}
    by_id.update({item["id"]: item for item in extra if item["id"] not in by_id})
    return sorted(by_id.values(), key=lambda item: (not item["self"], item["name"].casefold(), item["id"]))
