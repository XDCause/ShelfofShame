"""More for the journal: on this day, today, calendar + streaks, insights, review, notebooks, templates, weather,
places, private pages and export (api/app/journal_more.py)."""
from datetime import date, timedelta

from app import journal_more, openmeteo

TODAY = date.today()


def D(days):
    return (TODAY + timedelta(days=days)).isoformat()


def page(client, **body):
    r = client.post("/api/journal", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def game_played(client, *days, name="Catan"):
    game = client.post("/api/board-games", json={"name": name}).json()
    for day in days:
        assert client.post(f"/api/board-games/{game['game_id']}/plays", json={"played_on": day}).status_code == 201
    return game


# ---------------------------------------------------------------- on this day, today
def test_on_this_day_finds_earlier_years_pages_and_what_you_did(client):
    year_ago = TODAY.replace(year=TODAY.year - 1) if not (TODAY.month == 2 and TODAY.day == 29) else TODAY - timedelta(days=366)
    page(client, title="A year back", entry_date=year_ago.isoformat())
    page(client, title="Secret", entry_date=year_ago.isoformat(), private=True)
    page(client, title="Not this day", entry_date=(year_ago - timedelta(days=1)).isoformat())
    game_played(client, year_ago.isoformat())
    out = client.get(f"/api/journal/on-this-day?day={TODAY.isoformat()}").json()
    assert len(out) == 1 and out[0]["years_ago"] == 1
    assert [p["title"] for p in out[0]["pages"]] == ["A year back"]          # not the private one
    assert [d["title"] for d in out[0]["did"]] == ["Catan"]
    assert client.get(f"/api/journal/on-this-day?day={D(-400)}").json() == []


def test_on_this_day_skips_29_february_in_ordinary_years(client):
    page(client, title="Leap", entry_date="2024-02-29")
    assert client.get("/api/journal/on-this-day?day=2028-02-29").json()[0]["pages"][0]["title"] == "Leap"
    assert client.get("/api/journal/on-this-day?day=2025-02-28").json() == []


def test_today_lists_what_you_did_and_pages_already_written(client):
    game_played(client, D(0))
    page(client, title="Game night")
    out = client.get("/api/journal/today").json()
    assert out["day"] == D(0)
    assert [d["title"] for d in out["did"]] == ["Catan"]          # a page written isn't something to write about
    assert [p["title"] for p in out["pages"]] == ["Game night"]


# ---------------------------------------------------------------- calendar and streaks
def test_streaks_count_back_from_today_or_yesterday():
    now = date(2026, 10, 21)
    days = {now - timedelta(days=i) for i in (1, 2, 3, 7, 8, 9, 10, 11)}
    assert journal_more.streaks(days, now) == {"current": 3, "longest": 5, "today": False}
    assert journal_more.streaks(days | {now}, now)["current"] == 4
    assert journal_more.streaks(set(), now) == {"current": 0, "longest": 0, "today": False}


def test_calendar_gives_each_days_pages_mood_and_streak(client):
    first = page(client, title="One", mood="good")
    page(client, title="Two")
    page(client, title="Yesterday", entry_date=D(-1))
    out = client.get(f"/api/journal/calendar?month={TODAY.isoformat()[:7]}").json()
    today = next(d for d in out["days"] if d["day"] == D(0))
    assert today == {"day": D(0), "pages": 2, "page_id": first["page_id"], "mood": "good"}
    assert out["streak"]["current"] == 2 and out["streak"]["today"] is True
    assert client.get("/api/journal/calendar?month=2026-13").status_code == 422


# ---------------------------------------------------------------- insights, review
def test_insights_compare_mood_on_hobby_days_with_usual(client):
    for i, mood in enumerate(["great", "great", "great", "meh", "meh", "meh"]):
        page(client, mood=mood, entry_date=D(-i))
    game_played(client, D(0), D(-1), D(-2))            # the great days were game days
    out = client.get("/api/journal/insights?days=30").json()
    assert out["usual"] == 3.5 and out["mood_days"] == 6 and out["pages"] == 6
    assert out["by_hobby"] == [{"hobby": "Board games", "days": 3, "average": 5.0, "vs_usual": 1.5}]
    assert out["spread"] == {"great": 3, "meh": 3}
    assert sum(w["days"] for w in out["weekly"]) == 6


def test_insights_need_three_mood_days_for_a_hobby(client):
    page(client, mood="good")
    game_played(client, D(0))
    assert client.get("/api/journal/insights").json()["by_hobby"] == []


def test_review_groups_the_week_by_hobby(client, make_supply):
    game_played(client, D(-1), D(-2))
    make_supply()                                      # (stock isn't something to review)
    page(client, title="Tuesday", mood="okay", entry_date=D(-1))
    out = client.get(f"/api/journal/review?start={D(-6)}&end={D(0)}").json()
    assert out["hobbies"][0]["hobby"] == "Board games" and out["hobbies"][0]["count"] == 2
    assert [p["title"] for p in out["pages"]] == ["Tuesday"] and out["moods"][0]["mood"] == "okay"
    assert client.get(f"/api/journal/review?start={D(0)}&end={D(-1)}").status_code == 422
    assert [h["hobby"] for h in out["hobbies"]] == ["Board games"]


def test_a_review_page_offers_no_suggestions(client):
    game = game_played(client, D(-3))
    said = [{"type": "paragraph", "content": [{"type": "text", "text": "Played ", "styles": {}},
             {"type": "mention", "props": {"kind": "game", "ref": str(game["game_id"]), "label": "Catan"}}]}]
    assert page(client, content=said)["suggestions"]                              # an ordinary page: "Log a play?"
    assert page(client, content=said, tags=["review"])["suggestions"] == []      # a review: it was already logged


# ---------------------------------------------------------------- notebooks, templates
def test_notebooks_hold_pages_and_deleting_one_keeps_them(client):
    nb = client.post("/api/journal/notebooks", json={"name": " Build logs ", "colour": "purple"}).json()
    assert nb["name"] == "Build logs" and nb["pages"] == 0
    assert client.post("/api/journal/notebooks", json={"name": "Build logs"}).status_code == 409
    inside = page(client, title="Hull", notebook_id=nb["notebook_id"])
    page(client, title="Loose")
    assert [p["title"] for p in client.get(f"/api/journal?notebook={nb['notebook_id']}").json()] == ["Hull"]
    assert client.get("/api/journal/notebooks").json()[0]["pages"] == 1
    renamed = client.patch(f"/api/journal/notebooks/{nb['notebook_id']}", json={"name": "Builds"}).json()
    assert renamed["name"] == "Builds" and renamed["colour"] == "purple"
    assert client.get("/api/journal").json()[1]["notebook"] == "Builds"
    assert client.post("/api/journal", json={"notebook_id": 999}).status_code == 404
    assert client.delete(f"/api/journal/notebooks/{nb['notebook_id']}").status_code == 204
    assert client.get(f"/api/journal/{inside['page_id']}").json()["notebook_id"] is None


def test_templates_save_and_go(client):
    blocks = [{"type": "heading", "props": {"level": 2}, "content": [{"type": "text", "text": "Wins", "styles": {}}], "children": []}]
    t = client.post("/api/journal/templates", json={"name": "Debrief", "title": "Session", "content": blocks, "tags": ["range", " "]}).json()
    assert t["content"] == blocks and t["tags"] == ["range"]
    assert [x["name"] for x in client.get("/api/journal/templates").json()] == ["Debrief"]
    assert client.delete(f"/api/journal/templates/{t['template_id']}").status_code == 204
    assert client.delete(f"/api/journal/templates/{t['template_id']}").status_code == 404


# ---------------------------------------------------------------- place, weather, map, paper, private
def test_a_page_place_needs_both_numbers_and_clearing_it_clears_them(client):
    p = page(client, place_name="Noosa", lat=-26.39, lon=153.09, paper="dot")
    assert (p["lat"], p["lon"], p["paper"]) == (-26.39, 153.09, "dot")
    assert client.post("/api/journal", json={"lat": 1}).status_code == 422
    assert client.patch(f"/api/journal/{p['page_id']}", json={"lat": 2}).status_code == 422
    assert client.patch(f"/api/journal/{p['page_id']}", json={"paper": "wavy"}).status_code == 422
    cleared = client.patch(f"/api/journal/{p['page_id']}", json={"place_name": ""}).json()
    assert (cleared["place_name"], cleared["lat"], cleared["lon"]) == (None, None, None)
    assert [x["title"] for x in client.get("/api/journal/places").json()] == []


def test_weather_comes_from_the_page_place_or_home(client, monkeypatch):
    asked = []

    def fake(url, params):
        asked.append(params)
        return {"daily": {"time": [params["start_date"]], "temperature_2m_max": [26.1], "temperature_2m_min": [17.4],
                          "precipitation_sum": [0.2], "weather_code": [2]}}
    monkeypatch.setattr(openmeteo, "_get", fake)
    p = page(client, title="Somewhere")
    assert client.post(f"/api/journal/{p['page_id']}/weather").status_code == 409     # no place, no home
    client.put("/api/garden/settings", json={"place_name": "Brisbane", "lat": -27.47, "lon": 153.03})
    assert client.get("/api/journal/home-place").json()["place_name"] == "Brisbane"
    stamped = client.post(f"/api/journal/{p['page_id']}/weather").json()
    assert stamped["weather"] == {"sky": "Partly cloudy", "icon": "⛅", "max": 26.1, "min": 17.4, "rain_mm": 0.2}
    assert stamped["place_name"] == "Brisbane" and asked[-1]["start_date"] == D(0)
    assert [x["title"] for x in client.get("/api/journal/places").json()] == ["Somewhere"]
    moved = client.patch(f"/api/journal/{p['page_id']}", json={"place_name": "Noosa", "lat": -26.39, "lon": 153.09}).json()
    assert moved["weather"] is None                     # the weather was for the old place
    old = page(client, entry_date=D(-120))
    assert client.post(f"/api/journal/{old['page_id']}/weather").status_code == 422


def test_weather_when_open_meteo_is_down(client, monkeypatch):
    def down(url, params):
        raise openmeteo.WeatherError("Couldn't reach Open-Meteo (ConnectError).")
    monkeypatch.setattr(openmeteo, "_get", down)
    p = page(client, place_name="Noosa", lat=-26.39, lon=153.09)
    assert client.post(f"/api/journal/{p['page_id']}/weather").status_code == 502


def test_private_pages_stay_out_of_lists_activity_and_mentions(client):
    page(client, title="Open page")
    secret = page(client, title="Secret page", private=True)
    assert [p["title"] for p in client.get("/api/journal").json()] == ["Open page"]
    assert [p["title"] for p in client.get("/api/journal?private=true").json()] == ["Secret page"]
    assert [a["title"] for a in client.get("/api/activity").json()] == ["Open page"]
    assert [m["label"] for m in client.get("/api/journal/mentionable?q=page").json()] == ["Open page"]
    assert client.get(f"/api/journal/{secret['page_id']}").json()["private"] is True


def test_export_gives_whole_pages_oldest_first(client):
    page(client, title="Later", entry_date=D(-1))
    page(client, title="Earlier", entry_date=D(-3), content=[{"type": "paragraph", "content": [{"type": "text", "text": "hi", "styles": {}}]}])
    page(client, title="Secret", entry_date=D(-2), private=True)
    out = client.get(f"/api/journal/export?start={D(-7)}&end={D(0)}").json()
    assert [p["title"] for p in out] == ["Earlier", "Later"] and out[0]["content"][0]["type"] == "paragraph"
    assert len(client.get(f"/api/journal/export?start={D(-7)}&end={D(0)}&private=true").json()) == 3
    assert client.get(f"/api/journal/export?start={D(0)}&end={D(-7)}").status_code == 422
