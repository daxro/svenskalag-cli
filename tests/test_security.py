import json
import os

import requests

from svenskalag_cli.paths import atomic_write_text
from svenskalag_cli.session import is_authenticated_html, load_session, save_session


def test_atomic_write_is_private(tmp_path):
    path = tmp_path / "private.env"
    atomic_write_text(path, "secret")
    assert path.read_text() == "secret"
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_cookie_session_uses_json(tmp_path):
    path = tmp_path / "session.json"
    session = requests.Session()
    session.cookies.set("session", "sanitized", domain="www.svenskalag.se", path="/", secure=True)
    save_session(session, path)
    assert json.loads(path.read_text())["cookies"][0]["name"] == "session"
    restored = load_session(path)
    assert restored.cookies.get("session") == "sanitized"


def test_authentication_markers(fixture_text):
    assert not is_authenticated_html(fixture_text("login.html"))
    assert is_authenticated_html(fixture_text("navigation.html"))


def test_logout_marker_wins_over_global_login_modal(fixture_text):
    html = fixture_text("navigation.html").replace(
        "</body>", fixture_text("login.html") + "</body>"
    )
    assert is_authenticated_html(html)
