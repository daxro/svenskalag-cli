"""Command-line interface for svenskalag-cli."""

import argparse
import getpass
import json
import os
import re
import sys
from datetime import date, timedelta

from svenskalag_cli import __version__
from svenskalag_cli.api import (
    fetch_activity,
    fetch_calendar,
    fetch_context,
    fetch_groups,
    fetch_invitations,
    fetch_news,
    fetch_news_article,
    fetch_people,
)
from svenskalag_cli.api.normalize import parse_iso_date
from svenskalag_cli.config import load_config, normalize_url, save_config
from svenskalag_cli.errors import (
    EXIT_USAGE,
    InputError,
    NotFoundError,
    SvenskalagError,
    emit_error,
)
from svenskalag_cli.paths import CONFIG_FILE, SESSION_FILE, STATE_FILE
from svenskalag_cli.session import authenticate, get_authenticated_session, save_session

STATUS_FIELDS = {"configured", "username", "organization", "default_group", "session", "config_path", "session_path"}
GROUP_FIELDS = {"name", "slug", "url"}
PEOPLE_FIELDS = {"id", "name", "self"}
ACTIVITY_FIELDS = {
    "id", "group", "group_slug", "type", "title", "cancelled", "date",
    "start_time", "end_time", "assembly_time", "location", "description",
    "url", "registration",
}
NEWS_FIELDS = {"id", "group", "group_slug", "title", "author", "date", "body", "comments", "url"}
INVITATION_FIELDS = {
    "id", "group", "group_slug", "title", "date", "start_time", "person",
    "person_id", "response", "url",
}


class Parser(argparse.ArgumentParser):
    """Argument parser that writes usage errors as JSON."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action="help", help="show this help message and exit")

    def error(self, message):
        print(json.dumps({"error": "usage_error", "message": message}, ensure_ascii=False), file=sys.stderr)
        self.exit(EXIT_USAGE)


def _common_parent(fields=False, group=False):
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("-q", "--quiet", action="store_true", help="suppress progress")
    if fields:
        parent.add_argument("--fields", help="comma-separated JSON fields")
    if group:
        parent.add_argument("--group", help="exact group slug")
    return parent


def build_parser():
    """Build the public argparse structure."""
    parser = Parser(prog="svenskalag", description="An unofficial, read-only CLI for Svenskalag.se.")
    parser.add_argument("--version", action="version", version=f"svenskalag {__version__}", help="show version and exit")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", parents=[_common_parent()], help="configure and authenticate")
    setup.add_argument("--no-input", action="store_true", help="read credentials from environment variables")

    status = sub.add_parser("status", parents=[_common_parent(fields=True)], help="show profile status")
    status.add_argument("--json", action="store_true", dest="json_output", help="write status as JSON")

    sub.add_parser("groups", parents=[_common_parent(fields=True)], help="list visible groups")
    sub.add_parser("people", parents=[_common_parent(fields=True)], help="list available people")

    calendar = sub.add_parser("calendar", parents=[_common_parent(fields=True, group=True)], help="list calendar activities")
    calendar.add_argument("--since", help="first date, YYYY-MM-DD")
    calendar.add_argument("--until", help="last date, YYYY-MM-DD")
    calendar.add_argument("--limit", type=int, help="maximum number of activities")

    activity = sub.add_parser("activity", parents=[_common_parent(fields=True, group=True)], help="show an activity")
    activity.add_argument("id", help="numeric activity ID")

    news = sub.add_parser("news", parents=[_common_parent(fields=True, group=True)], help="list or show news")
    news.add_argument("id", nargs="?", help="numeric news ID")
    news.add_argument("--limit", type=int, help="maximum number of news items")

    invitations = sub.add_parser("invitations", parents=[_common_parent(fields=True, group=True)], help="list invitations")
    invitations.add_argument("--person", help="exact person ID")
    invitations.add_argument("--since", help="first date, YYYY-MM-DD")
    invitations.add_argument("--until", help="last date, YYYY-MM-DD")
    invitations.add_argument("--limit", type=int, help="maximum number of invitations")

    sub.add_parser("reset", parents=[_common_parent()], help="remove local profile and session")
    return parser


def _progress(message, quiet=False):
    if not quiet:
        print(message, file=sys.stderr)


def _mask(value):
    if not value:
        return None
    if len(value) <= 3:
        return value[0] + "****"
    return value[:3] + "****"


def _validated_fields(raw, allowed):
    if raw is None:
        return None
    fields = [field.strip() for field in raw.split(",")]
    if not fields or any(not field for field in fields):
        raise InputError("--fields contains an empty field name.")
    unknown = sorted(set(fields) - allowed)
    if unknown:
        raise InputError(f"Unknown fields: {', '.join(unknown)}.")
    return fields


def _filter(value, fields):
    if fields is None:
        return value
    if isinstance(value, list):
        return [{key: item.get(key) for key in fields} for item in value]
    return {key: value.get(key) for key in fields}


def _output(value, args, allowed):
    fields = _validated_fields(getattr(args, "fields", None), allowed)
    print(json.dumps(_filter(value, fields), ensure_ascii=False, separators=(",", ":")))


def _positive_limit(value):
    if value is not None and value < 1:
        raise InputError("--limit must be at least 1.")
    return value


def _numeric_id(value, label):
    if not re.fullmatch(r"\d+", value or ""):
        raise InputError(f"{label} must be a numeric ID.")
    return value


def _setup(args):
    non_interactive = args.no_input or not sys.stdin.isatty()
    if non_interactive:
        raw_url = os.environ.get("SVENSKALAG_URL")
        username = os.environ.get("SVENSKALAG_USERNAME")
        password = os.environ.get("SVENSKALAG_PASSWORD")
        if not all((raw_url, username, password)):
            raise InputError("SVENSKALAG_URL, SVENSKALAG_USERNAME, and SVENSKALAG_PASSWORD are required in non-interactive mode.")
    else:
        raw_url = input("Team or group URL: ").strip()
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
    if not username or not password:
        raise InputError("Username and password are required.")
    url, _ = normalize_url(raw_url)
    _progress("Verifying login...", args.quiet)
    session = authenticate(url, username, password)
    context = fetch_context(session, url)
    if not context["organization"]["slug"] or context["organization"]["slug"] == context["group"]["slug"]:
        raise InputError("The URL must point to a team or group page, not an association root page.")
    save_config(url, username, password)
    save_session(session)
    _progress(f"Profile saved to {CONFIG_FILE}.", args.quiet)
    print(json.dumps({"configured": True, "username": _mask(username), "url": url}, ensure_ascii=False, separators=(",", ":")))


def _status(args):
    _validated_fields(args.fields, STATUS_FIELDS)
    if args.fields and not args.json_output:
        raise InputError("--fields requires status --json.")
    config = load_config(required=False)
    configured = bool(config.get("url") and config.get("username") and config.get("password"))
    value = {
        "configured": configured, "username": _mask(config.get("username")),
        "organization": None, "default_group": None, "session": None,
        "config_path": str(CONFIG_FILE), "session_path": str(SESSION_FILE),
    }
    if configured:
        session = get_authenticated_session(config)
        context = fetch_context(session, config["url"])
        value.update({"organization": context["organization"], "default_group": context["group"], "session": "valid"})
    if args.json_output:
        _output(value, args, STATUS_FIELDS)
    else:
        if not configured:
            print("Not configured. Run: svenskalag setup")
        else:
            print(f"User: {value['username']}")
            print(f"Association: {(value['organization'] or {}).get('name') or '-'}")
            print(f"Default group: {(value['default_group'] or {}).get('name') or '-'}")
            print(f"Session: {value['session']}")
            print(f"Config: {value['config_path']}")


def _runtime():
    config = load_config()
    session = get_authenticated_session(config)
    return config, session


def _resolve_group(session, config, requested):
    groups = fetch_groups(session, config["url"])
    slug = requested or config["slug"]
    matches = [group for group in groups if group["slug"] == slug]
    if not matches:
        raise NotFoundError(f"Group '{slug}' was not found. Run: svenskalag groups")
    return matches[0]


def _groups(args):
    _validated_fields(args.fields, GROUP_FIELDS)
    config, session = _runtime()
    _output(fetch_groups(session, config["url"]), args, GROUP_FIELDS)


def _people(args):
    _validated_fields(args.fields, PEOPLE_FIELDS)
    config, session = _runtime()
    _output(fetch_people(session, config["url"]), args, PEOPLE_FIELDS)


def _calendar(args):
    _validated_fields(args.fields, ACTIVITY_FIELDS)
    limit = _positive_limit(args.limit)
    since = parse_iso_date(args.since) if args.since else date.today()
    until = parse_iso_date(args.until) if args.until else since + timedelta(days=30)
    config, session = _runtime()
    group = _resolve_group(session, config, args.group)
    value = fetch_calendar(session, group["url"], group["name"], since, until, limit)
    _output(value, args, ACTIVITY_FIELDS)


def _activity(args):
    _numeric_id(args.id, "Activity ID")
    _validated_fields(args.fields, ACTIVITY_FIELDS)
    config, session = _runtime()
    group = _resolve_group(session, config, args.group)
    _output(fetch_activity(session, group["url"], group["name"], args.id), args, ACTIVITY_FIELDS)


def _news(args):
    if args.id:
        _numeric_id(args.id, "News ID")
    _validated_fields(args.fields, NEWS_FIELDS)
    limit = _positive_limit(args.limit)
    config, session = _runtime()
    group = _resolve_group(session, config, args.group)
    value = fetch_news_article(session, group["url"], group["name"], args.id) if args.id else fetch_news(
        session, group["url"], group["name"], limit
    )
    _output(value, args, NEWS_FIELDS)


def _invitations(args):
    if args.person:
        _numeric_id(args.person, "Person ID")
    _validated_fields(args.fields, INVITATION_FIELDS)
    since = parse_iso_date(args.since).isoformat() if args.since else None
    until = parse_iso_date(args.until).isoformat() if args.until else None
    if since and until and until < since:
        raise InputError("--until cannot be earlier than --since.")
    limit = _positive_limit(args.limit)
    config, session = _runtime()
    group = _resolve_group(session, config, args.group)
    people = fetch_people(session, config["url"])
    if args.person:
        if args.person not in {person["id"] for person in people}:
            raise NotFoundError(f"Person '{args.person}' was not found. Run: svenskalag people")
        values = fetch_invitations(session, group["url"], group["name"], args.person)
    else:
        values = []
        for person in people:
            values.extend(fetch_invitations(session, group["url"], group["name"], person["id"]))
        values.sort(key=lambda item: (item["date"] or "", item["start_time"] or "", item["id"], item["person_id"] or ""))
    values = [item for item in values if (not since or (item["date"] and item["date"] >= since)) and (not until or (item["date"] and item["date"] <= until))]
    if limit is not None:
        values = values[:limit]
    _output(values, args, INVITATION_FIELDS)


def _reset(args):
    deleted = []
    failed = []
    for path in (CONFIG_FILE, SESSION_FILE, STATE_FILE):
        try:
            path.unlink()
            deleted.append(str(path))
        except FileNotFoundError:
            continue
        except OSError:
            failed.append(str(path))
    value = {"reset": not failed, "deleted": deleted, "failed": failed}
    if failed:
        raise SvenskalagError("One or more local files could not be removed.")
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    _progress("The local profile has been reset.", args.quiet)


HANDLERS = {
    "setup": _setup, "status": _status, "groups": _groups, "people": _people,
    "calendar": _calendar, "activity": _activity, "news": _news,
    "invitations": _invitations, "reset": _reset,
}


def main(argv=None):
    """Run the CLI and translate expected failures into its error contract."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        HANDLERS[args.command](args)
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"error": "interrupted", "message": "Interrupted."}, ensure_ascii=False), file=sys.stderr)
        return 130
    except SvenskalagError as error:
        return emit_error(error)
    except OSError:
        return emit_error(SvenskalagError("A local file error occurred."))
    except Exception:
        return emit_error(SvenskalagError("An unexpected error occurred."))


if __name__ == "__main__":
    sys.exit(main())
