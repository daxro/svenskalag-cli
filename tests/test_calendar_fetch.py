from datetime import date

from svenskalag_cli.api import calendar as calendar_module


def test_calendar_stops_fetching_when_limit_is_reached(monkeypatch, fixture_text):
    calls = []

    def fake_get(session, url):
        calls.append(url)
        return type("Response", (), {"text": fixture_text("calendar.html")})()

    monkeypatch.setattr(calendar_module, "get", fake_get)
    events = calendar_module.fetch_calendar(
        object(), "https://www.svenskalag.se/demo-grupp", "Demo grupp",
        date(2026, 8, 1), date(2026, 10, 1), limit=1,
    )
    assert len(events) == 1
    assert len(calls) == 1
