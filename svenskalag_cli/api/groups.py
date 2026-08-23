"""Association context and visible group navigation."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from svenskalag_cli.api.normalize import clean_text
from svenskalag_cli.session import get


def _slug(href):
    parts = [part for part in urlparse(href).path.split("/") if part]
    return parts[0] if parts else None


def parse_context(html, configured_url):
    """Parse the association and selected group from the page header."""
    soup = BeautifulSoup(html, "html.parser")
    configured_slug = _slug(configured_url)
    headings4 = soup.find_all("h4")
    headings5 = soup.find_all("h5")
    organization_name = clean_text(headings4[0].get_text(" ", strip=True)) if headings4 else None
    group_name = clean_text(headings5[0].get_text(" ", strip=True)) if headings5 else None

    organization_slug = None
    root_anchor = soup.select_one("ul.nav.navbar-nav > li > a[href]")
    if root_anchor is not None:
        organization_slug = _slug(urljoin(configured_url, root_anchor.get("href")))
    return {
        "organization": {
            "name": organization_name,
            "slug": organization_slug,
            "url": f"https://www.svenskalag.se/{organization_slug}" if organization_slug else None,
        },
        "group": {"name": group_name, "slug": configured_slug, "url": configured_url},
    }


def parse_groups(html, configured_url):
    """List the selected group and internal groups in the main navigation."""
    soup = BeautifulSoup(html, "html.parser")
    context = parse_context(html, configured_url)
    groups = [context["group"]]
    seen = {context["group"]["slug"]}
    organization_slug = context["organization"]["slug"]
    anchors = soup.select("ul.nav.navbar-nav a[href]")
    for anchor in anchors:
        url = urljoin(configured_url, anchor.get("href"))
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.hostname not in {"svenskalag.se", "www.svenskalag.se"} or len(parts) != 1:
            continue
        slug = parts[0]
        name = clean_text(anchor.get_text(" ", strip=True))
        if slug and slug != organization_slug and name and slug not in seen:
            seen.add(slug)
            groups.append({"name": name, "slug": slug, "url": f"https://www.svenskalag.se/{slug}"})
    return groups


def fetch_context(session, configured_url):
    response = get(session, configured_url)
    return parse_context(response.text, configured_url)


def fetch_groups(session, configured_url):
    response = get(session, configured_url)
    return parse_groups(response.text, configured_url)
