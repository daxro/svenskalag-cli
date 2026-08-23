import pytest

from svenskalag_cli import session as session_module
from svenskalag_cli.errors import AuthError, ParseError


class FakeResponse:
    def __init__(self, text="", payload=None, url="https://www.svenskalag.se/demo-grupp"):
        self.text = text
        self._payload = payload
        self.url = url
        self.status_code = 200

    def json(self):
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


def test_authentication_preserves_hidden_fields(monkeypatch, fixture_text):
    calls = []
    responses = iter([
        FakeResponse(fixture_text("login.html")),
        FakeResponse(payload={"redirect": "/demo-grupp/kontrollpanelen"}),
        FakeResponse(fixture_text("navigation.html")),
    ])

    def fake_request(session, method, url, **kwargs):
        calls.append((method, url, kwargs))
        return next(responses)

    monkeypatch.setattr(session_module, "_request", fake_request)
    authenticated = session_module.authenticate("https://www.svenskalag.se/demo-grupp", "demo-user", "demo-password")
    assert authenticated is not None
    method, url, kwargs = calls[1]
    assert method == "POST"
    assert url.endswith("/demo-grupp/logga-in")
    assert kwargs["data"]["verification"] == "sanitized-token"
    assert kwargs["data"]["UserName"] == "demo-user"
    assert kwargs["data"]["UserPass"] == "demo-password"


def test_authentication_rejects_server_error(monkeypatch, fixture_text):
    responses = iter([
        FakeResponse(fixture_text("login.html")),
        FakeResponse(payload={"error": "error"}),
    ])
    monkeypatch.setattr(session_module, "_request", lambda *args, **kwargs: next(responses))
    with pytest.raises(AuthError):
        session_module.authenticate("https://www.svenskalag.se/demo-grupp", "demo", "wrong")


def test_authentication_requires_form(monkeypatch):
    monkeypatch.setattr(session_module, "_request", lambda *args, **kwargs: FakeResponse("<html></html>"))
    with pytest.raises(ParseError):
        session_module.authenticate("https://www.svenskalag.se/demo-grupp", "demo", "demo")


def test_authentication_rejects_external_form_action(monkeypatch, fixture_text):
    html = fixture_text("login.html").replace(
        'action="/demo-grupp/logga-in"', 'action="https://evil.example/login"'
    )
    monkeypatch.setattr(session_module, "_request", lambda *args, **kwargs: FakeResponse(html))
    with pytest.raises(AuthError):
        session_module.authenticate("https://www.svenskalag.se/demo-grupp", "demo", "demo")


def test_get_reauthenticates_when_later_request_expires(monkeypatch, fixture_text):
    current = session_module.new_session()
    current._svenskalag_config = {
        "url": "https://www.svenskalag.se/demo-grupp",
        "username": "demo",
        "password": "secret",
    }
    responses = iter([
        FakeResponse(fixture_text("login.html")),
        FakeResponse(fixture_text("navigation.html")),
    ])
    fresh = session_module.new_session()
    fresh.cookies.set("session", "new", domain="www.svenskalag.se", path="/")
    monkeypatch.setattr(session_module, "_request", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(session_module, "authenticate", lambda *args, **kwargs: fresh)
    monkeypatch.setattr(session_module, "save_session", lambda *args, **kwargs: None)
    response = session_module.get(current, "https://www.svenskalag.se/demo-grupp/kalender")
    assert "Logga ut" in response.text
    assert current.cookies.get("session") == "new"


def test_get_accepts_authenticated_page_with_global_login_modal(monkeypatch, fixture_text):
    current = session_module.new_session()
    html = fixture_text("navigation.html").replace(
        "</body>", fixture_text("login.html") + "</body>"
    )
    monkeypatch.setattr(session_module, "_request", lambda *args, **kwargs: FakeResponse(html))

    response = session_module.get(current, "https://www.svenskalag.se/demo-grupp/kalender")

    assert "Logga ut" in response.text
