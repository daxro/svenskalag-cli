"""Resource-specific fetchers and HTML parsers."""

from svenskalag_cli.api.activity import fetch_activity, parse_activity
from svenskalag_cli.api.calendar import fetch_calendar, parse_calendar_month
from svenskalag_cli.api.groups import (
    fetch_context,
    fetch_groups,
    parse_context,
    parse_groups,
)
from svenskalag_cli.api.invitations import fetch_invitations, parse_invitations
from svenskalag_cli.api.news import (
    fetch_news,
    fetch_news_article,
    parse_news,
    parse_news_article,
)
from svenskalag_cli.api.people import fetch_people, parse_people

__all__ = [
    "fetch_activity",
    "fetch_calendar",
    "fetch_context",
    "fetch_groups",
    "fetch_invitations",
    "fetch_news",
    "fetch_news_article",
    "fetch_people",
    "parse_activity",
    "parse_calendar_month",
    "parse_context",
    "parse_groups",
    "parse_invitations",
    "parse_news",
    "parse_news_article",
    "parse_people",
]
