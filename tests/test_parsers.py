from svenskalag_cli.api.activity import parse_activity
from svenskalag_cli.api.calendar import parse_calendar_month
from svenskalag_cli.api.groups import parse_context, parse_groups
from svenskalag_cli.api.invitations import parse_invitations
from svenskalag_cli.api.news import parse_news, parse_news_article
from svenskalag_cli.api.people import parse_people

BASE = "https://www.svenskalag.se/demo-grupp"


def test_context_and_groups(fixture_text):
    html = fixture_text("navigation.html")
    context = parse_context(html, BASE)
    assert context["organization"] == {
        "name": "Demo IF", "slug": "demo-forening",
        "url": "https://www.svenskalag.se/demo-forening",
    }
    assert parse_groups(html, BASE) == [
        {"name": "Demo grupp", "slug": "demo-grupp", "url": BASE},
        {"name": "Reserver", "slug": "demo-reserver", "url": "https://www.svenskalag.se/demo-reserver"},
    ]


def test_people_are_deduplicated_and_self_first(fixture_text):
    people = parse_people(fixture_text("people.html"), BASE)
    assert people == [
        {"id": "1001", "name": "Me", "self": True},
        {"id": "1002", "name": "Demo Barn", "self": False},
    ]


def test_calendar_month(fixture_text):
    events = parse_calendar_month(fixture_text("calendar.html"), "demo-grupp", 2026, 8)
    assert [event["id"] for event in events] == ["2001", "2002", "2003"]
    assert events[0]["date"] == "2026-08-24"
    assert events[0]["start_time"] == "07:05"
    assert events[0]["end_time"] == "07:50"
    assert events[0]["location"] == "Idrottshallen"
    assert events[0]["cancelled"] is True
    assert events[1]["date"] == "2026-08-24"
    assert events[1]["type"] == "meeting"
    assert events[2]["date"] == "2026-08-25"


def test_activity_detail_and_account_response(fixture_text):
    activity = parse_activity(fixture_text("activity.html"), "demo-grupp", "2001", f"{BASE}/aktivitet/2001")
    assert activity["date"] == "2026-08-24"
    assert activity["assembly_time"] == "07:00"
    assert activity["description"] == "Ta med vattenflaska.\nVälkommen!"
    assert activity["registration"]["deadline"] == {"date": "2026-08-24", "time": "07:00"}
    assert activity["registration"]["responses"][0]["response"] == "yes"


def test_news_list_and_detail(fixture_text):
    news = parse_news(fixture_text("news.html"), "demo-grupp", BASE)
    assert [item["id"] for item in news] == ["3002", "3001"]
    assert news[0]["date"] == "2026-08-25"
    article = parse_news_article(fixture_text("article.html"), "demo-grupp", "3002", f"{BASE}/nyheter/3002")
    assert article["author"] == "Demo Författare"
    assert article["body"] == "Första stycket.\nAndra stycket."
    assert article["comments"][0]["text"] == "Bra information."


def test_invitations_and_empty_page(fixture_text):
    invitations = parse_invitations(fixture_text("invitations.html"), "demo-grupp", BASE, "1002")
    assert invitations[0]["person"] == "Demo Barn"
    assert invitations[0]["response"] == "yes"
    assert invitations[0]["date"] == "2026-08-24"
    assert parse_invitations("<table><tr><td>Inga kallelser</td></tr></table>", "demo", BASE) == []
