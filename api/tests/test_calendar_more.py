"""More for the calendar: repeats, holidays, to-dos and goals on it, quick add, search, countdowns, weather, balance,
the year, what to bring, moving an event (api/app/calendar.py, calendar_more.py, holidays.py)."""
from datetime import date, time, timedelta

import pytest

from app import calendar, calendar_more, holidays, openmeteo

TODAY = date.today()
WED = date(2026, 10, 21)            # quick add's "today" in these tests (a Wednesday)


def D(days):
    return (TODAY + timedelta(days=days)).isoformat()


def event(client, **body):
    r = client.post("/api/calendar/events", json={"title": "Thing", "starts_on": D(0), **body})
    assert r.status_code == 201, r.text
    return r.json()


def on(e, start, end):
    return [d.isoformat() for d in calendar.days_of({**e, "skipped": [], "starts_on": date.fromisoformat(e["starts_on"]),
                                                     "repeat_until": None}, date.fromisoformat(start), date.fromisoformat(end))]


# ---------------------------------------------------------------- repeats
def test_monthly_falls_back_to_a_short_months_last_day():
    e = {"starts_on": "2026-01-31", "repeats": "monthly", "repeat_every": 1, "repeat_days": None}
    assert on(e, "2026-01-01", "2026-04-30") == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]
    assert on({**e, "repeat_every": 2}, "2026-01-01", "2026-06-30") == ["2026-01-31", "2026-03-31", "2026-05-31"]


def test_monthly_nth_is_the_same_weekday_of_the_same_week():
    e = {"starts_on": "2026-10-10", "repeats": "monthly_nth", "repeat_every": 1, "repeat_days": None}   # 2nd Saturday
    assert on(e, "2026-10-01", "2027-01-31") == ["2026-10-10", "2026-11-14", "2026-12-12", "2027-01-09"]
    last = {**e, "starts_on": "2026-10-31"}                                                            # 5th = the last
    assert on(last, "2026-10-01", "2026-12-31") == ["2026-10-31", "2026-11-28", "2026-12-26"]


def test_yearly_and_29_february():
    e = {"starts_on": "2024-02-29", "repeats": "yearly", "repeat_every": 1, "repeat_days": None}
    assert on(e, "2024-01-01", "2028-12-31") == ["2024-02-29", "2025-02-28", "2026-02-28", "2027-02-28", "2028-02-29"]


def test_chosen_weekdays_every_other_week():
    e = {"starts_on": "2026-10-19", "repeats": "weekdays", "repeat_every": 2, "repeat_days": [0, 3]}     # Mon + Thu, fortnightly
    assert on(e, "2026-10-19", "2026-11-05") == ["2026-10-19", "2026-10-22", "2026-11-02", "2026-11-05"]


def test_new_event_fields_are_checked(client):
    assert client.post("/api/calendar/events", json={"title": "x", "starts_on": D(0), "repeats": "weekdays"}).status_code == 422
    assert client.post("/api/calendar/events", json={"title": "x", "starts_on": D(0), "lat": 1}).status_code == 422
    e = event(client, repeats="weekdays", repeat_days=[3, 0, 3], countdown=True, lat=-27.5, lon=153.0,
              checklist=[{"text": "Knee pads"}])
    assert e["repeat_days"] == [0, 3] and e["countdown"] and e["checklist"] == [{"text": "Knee pads", "done": False}]
    assert client.patch(f"/api/calendar/events/{e['event_id']}", json={"repeat_days": [7]}).status_code == 422
    assert client.patch(f"/api/calendar/events/{e['event_id']}", json={"countdown": None}).status_code == 422


# ---------------------------------------------------------------- holidays, to-dos and goals on the calendar
def test_queensland_holidays_2026():
    days = dict((d.isoformat(), n) for d, n in holidays.queensland(2026))
    assert days["2026-04-03"] == "Good Friday" and days["2026-04-06"] == "Easter Monday"
    assert days["2026-05-04"] == "Labour Day" and days["2026-10-05"] == "King's Birthday"
    assert days["2026-08-12"].startswith("Ekka") and days["2026-01-26"] == "Australia Day"


def test_christmas_on_a_weekend_moves_both_holidays():
    days = dict((d.isoformat(), n) for d, n in holidays.queensland(2027))     # Christmas Saturday, Boxing Day Sunday
    assert days["2027-12-27"] == "Christmas Day (holiday)" and days["2027-12-28"] == "Boxing Day (holiday)"
    assert holidays.easter(2025) == date(2025, 4, 20) and holidays.easter(2027) == date(2027, 3, 28)


def test_calendar_carries_todos_goals_and_holidays(client):
    client.post("/api/todos", json={"title": "Order paint", "due_on": D(1)})
    planned = client.post("/api/todos", json={"title": "Prime the hull"}).json()
    assert client.patch(f"/api/todos/{planned['todo_id']}", json={"plan_on": D(2), "plan_time": "19:00", "plan_minutes": 60}).status_code == 200
    assert client.patch(f"/api/todos/{planned['todo_id']}", json={"plan_minutes": 1}).status_code == 422
    client.post("/api/goals", json={"title": "Read 10 books", "target_date": D(3)})
    out = client.get(f"/api/calendar?start={D(0)}&end={D(6)}").json()
    assert [t["title"] for t in out["todos"]] == ["Order paint", "Prime the hull"]
    assert out["todos"][1]["plan_time"] == "19:00:00" and out["todos"][1]["plan_minutes"] == 60
    assert [g["title"] for g in out["goals"]] == ["Read 10 books"]
    assert client.get("/api/calendar?start=2026-12-20&end=2026-12-31").json()["holidays"][0]["day"] == "2026-12-24"


# ---------------------------------------------------------------- quick add
@pytest.mark.parametrize("text, want", [
    ("Volleyball Tue 7-9pm at Sports hall weekly",
     {"title": "Volleyball", "hobby": "volleyball", "starts_on": date(2026, 10, 27), "start_time": time(19), "end_time": time(21),
      "location": "Sports hall", "repeats": "weekly"}),
    ("Chess club every thursday 6:30pm at the library",
     {"title": "Chess club", "hobby": "chess", "starts_on": date(2026, 10, 22), "start_time": time(18, 30), "location": "the library",
      "repeats": "weekly"}),
    ("Games night with Sam and Jo on 14 Nov at 7",
     {"title": "Games night with Sam and Jo", "hobby": "boardgames", "starts_on": date(2026, 11, 14), "start_time": time(19)}),
    ("Regional comp Sat 28 Nov 8am-4pm at Sports hall",
     {"title": "Regional comp", "starts_on": date(2026, 11, 28), "start_time": time(8), "end_time": time(16), "location": "Sports hall"}),
    ("Club shoot on the 2nd Saturday of the month 8am",
     {"title": "Club shoot", "hobby": "shooting", "starts_on": date(2026, 11, 14), "start_time": time(8), "repeats": "monthly_nth"}),
    ("Mum's birthday 3 March yearly", {"title": "Mum's birthday", "starts_on": date(2027, 3, 3), "start_time": None, "repeats": "yearly"}),
    ("Hike tomorrow 6am for 3 hours at Mt Coot-tha",
     {"title": "Hike", "hobby": "hiking", "starts_on": date(2026, 10, 22), "start_time": time(6), "end_time": time(9), "location": "Mt Coot-tha"}),
    ("Gym every mon and thu 6pm", {"title": "Gym", "starts_on": date(2026, 10, 22), "repeats": "weekdays", "repeat_days": [0, 3],
                                   "start_time": time(18)}),
    ("Paint night next friday 7:30pm until dec fortnightly",
     {"title": "Paint night", "hobby": "models", "starts_on": date(2026, 10, 23), "start_time": time(19, 30), "repeats": "fortnightly",
      "repeat_until": date(2026, 12, 31)}),
])
def test_quick_add_reads_plain_words(text, want):
    got = calendar_more.parse(text, WED)
    assert {k: got[k] for k in want} == want


def test_quick_add_route(client):
    out = client.post("/api/calendar/parse", json={"text": "Range day tomorrow 9am"}).json()
    assert out["title"] == "Range day" and out["hobby"] == "shooting" and out["start_time"] == "09:00:00"
    assert client.post("/api/calendar/parse", json={"text": ""}).status_code == 422


# ---------------------------------------------------------------- search, countdowns, weather
def test_search_finds_words_anywhere_with_the_next_day(client):
    event(client, title="Volleyball comp", location="Sports hall", starts_on=D(-14), repeats="weekly")
    event(client, title="Old show", starts_on=D(-30), notes="at the sports hall")
    out = client.get("/api/calendar/search?q=sports hall").json()
    assert [e["title"] for e in out] == ["Volleyball comp", "Old show"]
    assert out[0]["upcoming"] and out[0]["day"] == D(0) and not out[1]["upcoming"]


def test_countdowns_soonest_first(client):
    event(client, title="Regional comp", starts_on=D(12), countdown=True)
    event(client, title="Trip", starts_on=D(5), countdown=True)
    event(client, title="Not counted", starts_on=D(3))
    event(client, title="Past", starts_on=D(-3), countdown=True)
    assert [(c["title"], c["days_left"]) for c in client.get("/api/calendar/countdowns").json()] == [("Trip", 5), ("Regional comp", 12)]


def test_weather_on_upcoming_events(client, monkeypatch):
    monkeypatch.setattr(openmeteo, "_get", lambda url, params: {"daily": {
        "time": [D(i) for i in range(16)], "temperature_2m_max": [30] * 16, "temperature_2m_min": [20] * 16,
        "precipitation_probability_max": [40] * 16, "weather_code": [63] * 16}})
    event(client, title="Hike", starts_on=D(2), lat=-27.47, lon=153.03)
    event(client, title="At home", starts_on=D(3))
    event(client, title="Too far", starts_on=D(30), lat=-27.47, lon=153.03)
    out = client.get("/api/calendar/weather").json()
    assert [(w["day"], w["icon"], w["rain_chance"]) for w in out["weather"]] == [(D(2), "🌧️", 40)]   # no home set
    client.put("/api/garden/settings", json={"place_name": "Brisbane", "lat": -27.47, "lon": 153.03})
    assert len(client.get("/api/calendar/weather").json()["weather"]) == 2


def test_weather_when_open_meteo_is_down(client, monkeypatch):
    def down(url, params):
        raise openmeteo.WeatherError("Couldn't reach Open-Meteo (ConnectError).")
    monkeypatch.setattr(openmeteo, "_get", down)
    event(client, title="Hike", starts_on=D(2), lat=-27.47, lon=153.03)
    out = client.get("/api/calendar/weather").json()
    assert out["weather"] == [] and "Open-Meteo" in out["error"]


# ---------------------------------------------------------------- balance, year, bring
def test_balance_planned_against_done(client):
    event(client, title="Comp", hobby="volleyball", starts_on=D(0), start_time="19:00", end_time="21:00")
    event(client, title="Games", hobby="boardgames", starts_on=D(0), start_time="18:00", end_time="19:30")
    game = client.post("/api/board-games", json={"name": "Catan"}).json()
    client.post(f"/api/board-games/{game['game_id']}/plays", json={"played_on": D(0), "minutes": 45})
    out = {r["hobby"]: r for r in client.get(f"/api/calendar/balance?start={D(0)}&end={D(6)}").json()}
    assert out["volleyball"] == {"hobby": "volleyball", "planned_events": 1, "planned_minutes": 120, "done_days": 0, "done_minutes": None}
    assert out["boardgames"]["planned_minutes"] == 90 and out["boardgames"]["done_days"] == 1 and out["boardgames"]["done_minutes"] == 45


def test_the_year_day_by_day(client):
    game = client.post("/api/board-games", json={"name": "Catan"}).json()
    client.post(f"/api/board-games/{game['game_id']}/plays", json={"played_on": D(0)})
    client.post("/api/journal", json={"mood": "good"})
    out = client.get(f"/api/calendar/year?year={TODAY.year}").json()
    today = next(d for d in out["days"] if d["day"] == D(0))
    assert today["count"] == 1 and today["hobbies"] == ["boardgames"] and today["mood"] == "good"
    assert any(h["name"] == "Christmas Day" for h in out["holidays"])
    assert client.get("/api/calendar/year?year=1999").status_code == 422


def test_bring_offers_the_hobbys_gear_and_packing_lists(client):
    client.post("/api/gear", json={"name": "Knee pads", "hobby": "volleyball"})
    out = client.get("/api/calendar/bring?hobby=volleyball").json()
    assert out["gear"] == ["Knee pads"] and any(p["name"] == "Essentials" for p in out["packing_lists"])
    assert client.get("/api/calendar/bring?hobby=shooting").json()["gear"] == []


# ---------------------------------------------------------------- moving
def test_moving_a_one_off_event_changes_its_day_and_time(client):
    e = event(client, title="Show", starts_on=D(1), start_time="10:00")
    moved = client.post(f"/api/calendar/events/{e['event_id']}/move", json={"from_day": D(1), "to_day": D(3)}).json()
    assert moved["starts_on"] == D(3) and moved["start_time"] == "10:00:00"
    timed = client.post(f"/api/calendar/events/{e['event_id']}/move",
                        json={"from_day": D(3), "to_day": D(3), "keep_time": False, "start_time": "14:00", "end_time": "13:00"}).json()
    assert timed["start_time"] == "14:00:00" and timed["end_time"] is None
    assert client.post(f"/api/calendar/events/{e['event_id']}/move", json={"from_day": D(9), "to_day": D(3)}).status_code == 409


def test_moving_one_day_of_a_repeating_event_leaves_the_rest(client):
    e = event(client, title="Training", starts_on=D(0), repeats="weekly", checklist=[{"text": "Ball"}])
    copy = client.post(f"/api/calendar/events/{e['event_id']}/move", json={"from_day": D(7), "to_day": D(8)}).json()
    assert copy["event_id"] != e["event_id"] and copy["repeats"] == "never" and copy["checklist"] == [{"text": "Ball", "done": False}]
    days = [(x["title"], x["day"]) for x in client.get(f"/api/calendar?start={D(0)}&end={D(14)}").json()["events"]]
    assert days == [("Training", D(0)), ("Training", D(8)), ("Training", D(14))]


def test_video_game_time_is_each_days_change_not_the_running_total(client):
    from app.db import db
    with db() as conn:                                  # Steam only gives totals: 600, then 660, then 690 minutes
        for days, total in ((-2, 600), (-1, 660), (0, 690)):
            conn.execute("INSERT INTO vg_playtime (platform, app_id, day, minutes) VALUES ('steam', '730', %s, %s)", (D(days), total))
    out = {r["hobby"]: r for r in client.get(f"/api/calendar/balance?start={D(-1)}&end={D(0)}").json()}
    assert out["videogames"]["done_minutes"] == 90
