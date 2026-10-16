"""The calendar: events (one-off and repeating), skipping a day, and what happened each day."""
from datetime import date, timedelta


def add(client, **overrides):
    body = {"title": "Volleyball comp", "hobby": "volleyball", "starts_on": "2026-10-06",
            "start_time": "19:00", "end_time": "20:30", "location": "Sports hall"}
    body.update(overrides)
    r = client.post("/api/calendar/events", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def days(client, start, end):
    return [(e["day"], e["title"]) for e in client.get(f"/api/calendar?start={start}&end={end}").json()["events"]]


def test_a_one_off_event_shows_on_its_day_only(client):
    add(client, title="Model show", hobby="models", starts_on="2026-10-18", start_time=None, end_time=None)
    assert days(client, "2026-10-01", "2026-10-31") == [("2026-10-18", "Model show")]
    assert days(client, "2026-11-01", "2026-11-30") == []


def test_weekly_and_fortnightly_repeats_until_a_day(client):
    add(client, repeats="weekly", repeat_until="2026-10-27")            # Tuesdays
    add(client, title="Games night", hobby="boardgames", starts_on="2026-10-02", repeats="fortnightly",
        start_time="18:00", end_time=None)
    assert days(client, "2026-10-01", "2026-11-05") == [
        ("2026-10-02", "Games night"), ("2026-10-06", "Volleyball comp"), ("2026-10-13", "Volleyball comp"),
        ("2026-10-16", "Games night"), ("2026-10-20", "Volleyball comp"), ("2026-10-27", "Volleyball comp"),
        ("2026-10-30", "Games night")]
    # A window that starts part-way through still lands on the right days.
    assert days(client, "2026-10-14", "2026-10-21") == [("2026-10-16", "Games night"),
                                                        ("2026-10-20", "Volleyball comp")]


def test_skipping_one_day_of_a_repeating_event(client):
    event = add(client, repeats="weekly")
    r = client.post(f"/api/calendar/events/{event['event_id']}/skip", json={"day": "2026-10-13"})
    assert r.status_code == 200, r.text
    assert days(client, "2026-10-06", "2026-10-20") == [("2026-10-06", "Volleyball comp"),
                                                        ("2026-10-20", "Volleyball comp")]
    wrong_day = client.post(f"/api/calendar/events/{event['event_id']}/skip", json={"day": "2026-10-14"})
    assert wrong_day.status_code == 409


def test_editing_checks_and_deleting(client):
    event = add(client)
    url = f"/api/calendar/events/{event['event_id']}"
    assert client.patch(url, json={"end_time": "18:00"}).status_code == 422          # before the start
    assert client.patch(url, json={"repeats": "weekly", "repeat_until": "2026-09-01"}).status_code == 422
    assert client.post("/api/calendar/events", json={"title": " ", "starts_on": "2026-10-06"}).status_code == 422
    moved = client.patch(url, json={"starts_on": "2026-10-07", "notes": "Court 2"}).json()
    assert (moved["starts_on"], moved["notes"]) == ("2026-10-07", "Court 2")
    assert client.delete(url).status_code == 204
    assert days(client, "2026-10-01", "2026-10-31") == []


def test_upcoming_is_soonest_first_from_today(client):
    today = date.today()
    add(client, title="Last week", starts_on=(today - timedelta(days=7)).isoformat())
    add(client, title="Weekly", starts_on=(today - timedelta(days=3)).isoformat(), repeats="weekly")
    add(client, title="Tomorrow", starts_on=(today + timedelta(days=1)).isoformat(), start_time=None, end_time=None)
    titles = [e["title"] for e in client.get("/api/calendar/upcoming?limit=3").json()]
    assert titles == ["Tomorrow", "Weekly", "Weekly"]


def test_what_happened_comes_from_the_activity_feed(client):
    page = client.post("/api/journal", json={"title": "Comp night", "entry_date": "2026-10-06"}).json()
    data = client.get("/api/calendar?start=2026-10-01&end=2026-10-31").json()
    [wrote] = data["happened"]
    assert (wrote["day"], wrote["kind"], wrote["ref"], wrote["verb"]) == ("2026-10-06", "page", page["page_id"], "Wrote")
    assert client.get("/api/calendar?start=2026-10-31&end=2026-10-01").status_code == 422


def test_a_volleyball_event_knows_when_its_game_is_logged(client):
    event = add(client, repeats="weekly")
    client.post("/api/volleyball/games", json={"played_on": "2026-10-13", "event_id": event["event_id"],
                                               "opponent": "Spikers", "sets_won": 3, "sets_lost": 1})
    events = client.get("/api/calendar?start=2026-10-06&end=2026-10-13").json()["events"]
    assert [e["logged_id"] is not None for e in events] == [False, True]


def test_all_day_events_and_every_hobby(client):
    e = client.post("/api/calendar/events", json={"title": "Track day", "hobby": "car", "starts_on": "2026-11-07"}).json()
    assert (e["start_time"], e["end_time"], e["hobby"]) == (None, None, "car")                  # no time = all day
    timed = client.post("/api/calendar/events", json={"title": "Chess club", "hobby": "chess", "starts_on": "2026-11-07",
                                                     "start_time": "18:00"}).json()
    # Turned into an all-day event: the times go.
    assert client.patch(f"/api/calendar/events/{timed['event_id']}", json={"start_time": None, "end_time": None}).json()["start_time"] is None
    for hobby in ("videogames", "reading"):
        assert client.post("/api/calendar/events", json={"title": "X", "hobby": hobby, "starts_on": "2026-11-08"}).status_code == 201
