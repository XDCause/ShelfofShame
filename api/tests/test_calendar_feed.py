"""The phone calendar's feed (calendar_feed.py): a private .ics address with its own key - events (repeats spread out)
and trips; no key, a wrong key or the feed off all look like nothing is there."""
from datetime import date, datetime, timedelta, timezone

from app import calendar_feed

FEED = "/api/calendar/feed.ics"


def test_off_until_turned_on_and_a_new_key_retires_the_old(client, anon):
    assert client.get("/api/calendar/feed").json() == {"on": False, "path": None}
    assert anon.get(FEED).status_code == 404
    first = client.post("/api/calendar/feed").json()
    assert first["on"] and first["path"].startswith(FEED + "?key=")
    assert anon.get(first["path"]).status_code == 200                       # no sign-in: the key is enough
    assert anon.get(FEED + "?key=nope").status_code == 404
    assert anon.get("/api/calendar/feed").status_code == 401                # (turning it on / off needs a sign-in)
    second = client.post("/api/calendar/feed").json()
    assert second["path"] != first["path"]
    assert anon.get(first["path"]).status_code == 404 and anon.get(second["path"]).status_code == 200
    assert "calendar_feed_key" not in client.get("/api/settings").json()    # (never shown with the other settings)
    assert client.delete("/api/calendar/feed").status_code == 204
    assert anon.get(second["path"]).status_code == 404


def test_events_repeats_and_trips_in_the_feed(client, anon):
    today = datetime.now(calendar_feed.BRISBANE).date()
    client.post("/api/calendar/events", json={"title": "Volleyball, finals; bring water", "starts_on": str(today),
                                             "start_time": "19:00", "end_time": "21:00", "repeats": "weekly",
                                             "location": "Sports hall", "hobby": "volleyball"})
    client.post("/api/calendar/events", json={"title": "Club day", "starts_on": str(today + timedelta(days=3))})
    client.post("/api/travel/trips", json={"name": "Patagonia", "kind": "Overseas", "status": "Planned",
                                           "start_date": str(today + timedelta(days=20)), "end_date": str(today + timedelta(days=30))})
    path = client.post("/api/calendar/feed").json()["path"]
    r = anon.get(path)
    assert r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.rstrip().endswith("END:VCALENDAR")
    assert "SUMMARY:Volleyball\\, finals\\; bring water" in body                 # (commas and semicolons escaped)
    start = datetime.combine(today, datetime.strptime("19:00", "%H:%M").time(), calendar_feed.BRISBANE).astimezone(timezone.utc)
    assert f"DTSTART:{start:%Y%m%dT%H%M%SZ}" in body                                  # 7 pm Brisbane, in UTC
    assert body.count("SUMMARY:Volleyball") >= 50                                     # weekly, a year ahead
    assert f"DTSTART;VALUE=DATE:{today + timedelta(days=3):%Y%m%d}" in body          # an all-day event
    assert "SUMMARY:Trip: Patagonia" in body and f"DTEND;VALUE=DATE:{today + timedelta(days=31):%Y%m%d}" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))             # folded at 75 octets


def test_folding_and_escaping():
    long = "A" * 200 + "é" * 10
    folded = calendar_feed.fold("SUMMARY:" + long)
    parts = folded.split("\r\n ")
    assert all(len(p.encode()) <= 75 for p in parts) and "".join(parts) == "SUMMARY:" + long
    assert calendar_feed.escape("a\\b;c,d\ne") == "a\\\\b\\;c\\,d\\ne"
    out = calendar_feed.ics([], [], datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert "DTSTAMP" not in out and "X-WR-CALNAME:Off the Clock" in out
    assert date(2026, 1, 1)                                                        # (nothing else to check here)
