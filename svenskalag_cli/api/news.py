"""News listing and article details."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from svenskalag_cli.api.normalize import (
    clean_text,
    parse_recent_swedish_date,
)
from svenskalag_cli.errors import NotFoundError, ParseError
from svenskalag_cli.session import get


def _article_id(href):
    match = re.search(r"/nyheter/(\d+)", href or "", re.IGNORECASE)
    return match.group(1) if match else None


def parse_news(html, group_slug, base_url):
    """Parse the visible news list and deduplicate articles."""
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen = set()
    anchors = soup.select('a.news-item-inner[href*="/nyheter/"]')
    if not anchors:
        anchors = soup.select('a[href*="/nyheter/"]')
    for anchor in anchors:
        article_id = _article_id(anchor.get("href"))
        if not article_id or article_id in seen:
            continue
        container = anchor
        title_node = container.select_one(".headline, .title, p")
        title = clean_text(title_node.get_text(" ", strip=True)) if title_node else clean_text(anchor.get_text(" ", strip=True))
        if not title:
            continue
        date_node = container.select_one(".date, .time, .text-muted.small")
        date_value = parse_recent_swedish_date(date_node.get_text(" ", strip=True)) if date_node else None
        articles.append({
            "id": article_id, "group": None, "group_slug": group_slug,
            "title": title, "author": None, "date": date_value,
            "body": None, "comments": [],
            "url": urljoin(base_url, anchor.get("href")),
        })
        seen.add(article_id)
    return articles


def parse_news_article(html, group_slug, article_id, url):
    """Parse title, metadata, body text, and comments."""
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.find("h1") or soup.select_one(".headline")
    if title_node is None:
        raise ParseError("Could not parse the news title.")
    title = clean_text(title_node.get_text(" ", strip=True))
    author_node = soup.select_one(".author__name, .author-name, [itemprop='author']")
    time_node = soup.find("time") or soup.select_one(".article-date, .news-date, .meta__item")
    date_value = None
    if time_node:
        raw = time_node.get("datetime") or time_node.get("title") or time_node.get_text(" ", strip=True)
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", raw)
        date_value = iso_match.group(0) if iso_match else parse_recent_swedish_date(raw)
    if time_node is None:
        time_node = soup.select_one(".template-info .text-muted")
        if time_node:
            date_value = parse_recent_swedish_date(time_node.get_text(" ", strip=True))
    body_node = soup.select_one(".article-body, .news-content, .content-block, .template-text, [itemprop='articleBody']")
    if body_node is None:
        anchor = soup.select_one("#anchor-comments")
        if anchor:
            pieces = []
            for sibling in anchor.next_siblings:
                classes = " ".join(getattr(sibling, "get", lambda *_: [])("class", []))
                if "author" in classes or "socialShare" in classes:
                    break
                if hasattr(sibling, "get_text"):
                    pieces.append(sibling.get_text("\n", strip=True))
            body = clean_text("\n".join(pieces))
        else:
            body = None
    else:
        body = clean_text(body_node.get_text("\n", strip=True))

    comments = []
    for item in soup.select("#news-comment-list li, .commentList__itemInner"):
        name = item.select_one(".commentList__name, .comment-author")
        when = item.select_one(".commentList__time, .comment-date")
        text = item.select_one(".commentList__text, .comment-text")
        if name or text:
            comments.append({
                "author": clean_text(name.get_text(" ", strip=True)) if name else None,
                "date": clean_text(when.get_text(" ", strip=True)) if when else None,
                "text": clean_text(text.get_text("\n", strip=True)) if text else None,
            })
    return {
        "id": str(article_id), "group": None, "group_slug": group_slug,
        "title": title,
        "author": clean_text(author_node.get_text(" ", strip=True)) if author_node else None,
        "date": date_value, "body": body, "comments": comments, "url": url,
    }


def fetch_news(session, group_url, group_name, limit=None):
    response = get(session, f"{group_url}/nyheter")
    group_slug = group_url.rstrip("/").rsplit("/", 1)[-1]
    articles = parse_news(response.text, group_slug, group_url)
    for article in articles:
        article["group"] = group_name
    articles.sort(key=lambda item: (item["date"] or "", item["id"]), reverse=True)
    return articles[:limit] if limit is not None else articles


def fetch_news_article(session, group_url, group_name, article_id):
    url = f"{group_url}/nyheter/{article_id}"
    response = get(session, url)
    if "/blank/PageNotFound" in response.url:
        raise NotFoundError(f"News item '{article_id}' was not found.")
    group_slug = group_url.rstrip("/").rsplit("/", 1)[-1]
    article = parse_news_article(response.text, group_slug, article_id, response.url)
    article["group"] = group_name
    return article
