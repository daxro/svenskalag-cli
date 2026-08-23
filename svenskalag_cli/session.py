"""HTTP sessions, adaptive login, and secure cookie persistence."""

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from svenskalag_cli.errors import AuthError, NetworkError, NotFoundError, ParseError
from svenskalag_cli.paths import SESSION_FILE, atomic_write_text

HTTP_TIMEOUT = 20
USER_AGENT = "svenskalag-cli/0.1 (+https://github.com/daxro/svenskalag-cli)"
TRUSTED_HOSTS = {"svenskalag.se", "www.svenskalag.se"}


def new_session():
    """Create a session with an identifiable but secret-free user agent."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _request(session, method, url, **kwargs):
    kwargs.setdefault("timeout", HTTP_TIMEOUT)
    try:
        response = session.request(method, url, **kwargs)
        if response.status_code == 404:
            raise NotFoundError("Resource not found.")
        response.raise_for_status()
        return response
    except requests.Timeout as exc:
        raise NetworkError("The request to Svenskalag timed out.") from exc
    except requests.RequestException as exc:
        raise NetworkError("Could not communicate with Svenskalag.") from exc


def is_authenticated_html(html):
    """Identify stable markers for an authenticated web view."""
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.find("a", href=lambda value: value and "/logga-ut" in value))


def _trusted_url(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in TRUSTED_HOSTS


def verify_session(session, url):
    """Verify the session against My Pages without changing remote data."""
    response = _request(session, "GET", f"{url}/minasidor")
    if not _trusted_url(response.url):
        raise AuthError("Svenskalag redirected to an untrusted host.")
    return is_authenticated_html(response.text)


def authenticate(url, username, password):
    """Authenticate through the current login form and verify the result."""
    session = new_session()
    response = _request(session, "GET", url)
    if not _trusted_url(response.url):
        raise AuthError("Svenskalag redirected to an untrusted host.")
    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.select_one("#login-form")
    if form is None:
        raise ParseError("Could not find the Svenskalag login form.")
    action = form.get("action")
    if not action:
        raise ParseError("The login form has no action URL.")

    data = {}
    for field in form.select("input[name]"):
        if field.get("type", "").lower() == "hidden":
            data[field["name"]] = field.get("value", "")
    username_field = form.select_one('input[autocomplete="username"][name], input[type="text"][name]')
    password_field = form.select_one('input[type="password"][name]')
    if username_field is None or password_field is None:
        raise ParseError("The login form has no credential fields.")
    data[username_field["name"]] = username
    data[password_field["name"]] = password
    remember = form.select_one('input[type="checkbox"][name]')
    if remember is not None:
        data[remember["name"]] = remember.get("value", "on")
    action_url = urljoin(url, action)
    if not _trusted_url(action_url):
        raise AuthError("The login form points to an untrusted host.")
    login_response = _request(
        session,
        "POST",
        action_url,
        data=data,
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    if not _trusted_url(login_response.url):
        raise AuthError("Login redirected to an untrusted host.")
    try:
        payload = login_response.json()
    except requests.JSONDecodeError:
        payload = {}
    if payload.get("error"):
        raise AuthError("Incorrect username or password.")
    if not verify_session(session, url):
        raise AuthError("Login could not be verified.")
    return session


def save_session(session, path=SESSION_FILE):
    """Save only required cookie properties as JSON."""
    cookies = []
    for cookie in session.cookies:
        cookies.append({
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "secure": bool(cookie.secure),
            "expires": cookie.expires,
        })
    atomic_write_text(path, json.dumps({"cookies": cookies}, ensure_ascii=False))


def load_session(path=SESSION_FILE):
    """Load a previous cookie session; safely ignore malformed files."""
    session = new_session()
    path = Path(path)
    if not path.exists():
        return session
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for cookie in payload.get("cookies", []):
            if not isinstance(cookie, dict) or not cookie.get("name"):
                continue
            session.cookies.set(
                cookie["name"], cookie.get("value", ""),
                domain=cookie.get("domain"), path=cookie.get("path", "/"),
                secure=bool(cookie.get("secure")), expires=cookie.get("expires"),
            )
    except (OSError, ValueError, TypeError):
        return new_session()
    return session


def get_authenticated_session(config):
    """Reuse cookies or reauthenticate exactly once."""
    session = load_session()
    if verify_session(session, config["url"]):
        session._svenskalag_config = dict(config)
        return session
    session = authenticate(config["url"], config["username"], config["password"])
    session._svenskalag_config = dict(config)
    save_session(session)
    return session


def get(session, url):
    """Public GET helper with shared error handling."""
    response = _request(session, "GET", url)
    if is_authenticated_html(response.text):
        return response
    config = getattr(session, "_svenskalag_config", None)
    if not config:
        return response
    fresh = authenticate(config["url"], config["username"], config["password"])
    session.cookies.clear()
    session.cookies.update(fresh.cookies)
    save_session(session)
    retry = _request(session, "GET", url)
    if not is_authenticated_html(retry.text):
        raise AuthError("The session expired and reauthentication failed.")
    return retry
