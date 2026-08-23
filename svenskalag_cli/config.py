"""Load and serialize the local profile."""

import json
import re
from urllib.parse import urlparse

from dotenv import dotenv_values

from svenskalag_cli.errors import InputError, NotConfiguredError
from svenskalag_cli.paths import CONFIG_FILE, atomic_write_text

BASE_URL = "https://www.svenskalag.se"


def normalize_url(value):
    """Normalize a Svenskalag group URL and reject other hosts."""
    value = (value or "").strip()
    if not value:
        raise InputError("URL is required.")
    if "://" not in value:
        value = f"{BASE_URL}/{value.lstrip('/')}"
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {
        "svenskalag.se", "www.svenskalag.se"
    }:
        raise InputError("URL must be an HTTPS address on www.svenskalag.se.")
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise InputError("URL must contain a team or group slug.")
    slug = parts[0]
    if not re.fullmatch(r"[A-Za-z0-9ÅÄÖåäö_-]+", slug):
        raise InputError("The URL contains an invalid slug.")
    return f"{BASE_URL}/{slug}", slug


def load_config(required=True):
    """Load the profile without interpolating credential values."""
    values = dotenv_values(CONFIG_FILE, interpolate=False) if CONFIG_FILE.exists() else {}
    config = {
        "url": values.get("SVENSKALAG_URL"),
        "username": values.get("SVENSKALAG_USERNAME"),
        "password": values.get("SVENSKALAG_PASSWORD"),
    }
    if required and not all(config.values()):
        raise NotConfiguredError("The CLI is not configured. Run: svenskalag setup")
    if config["url"]:
        config["url"], config["slug"] = normalize_url(config["url"])
    return config


def _quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def save_config(url, username, password):
    """Save verified credentials in a private dotenv format."""
    content = (
        f"SVENSKALAG_URL={_quote(url)}\n"
        f"SVENSKALAG_USERNAME={_quote(username)}\n"
        f"SVENSKALAG_PASSWORD={_quote(password)}\n"
    )
    atomic_write_text(CONFIG_FILE, content)
