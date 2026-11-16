"""Vinyl, more: loans, the cleaning log, the stylus, value history and the listening year."""
from datetime import date, datetime, timedelta

from app.db import db
from app.vinyl_care import play_minutes, seconds_of
from app.vinyl_more import change, year_numbers


def add(client, **record):
    r = client.post("/api/vinyl/records", json={"title": "A Record", **record})
    assert r.status_code == 201, r.text
    return r.json()


TRACKS = [{"position": "A1", "title": "One", "duration": "10:00"}, {"position": "A2", "title": "Two", "duration": "10:00"},
          {"position": "B1", "title": "Three", "duration": "5:00"}]


def test_play_minutes():
    assert seconds_of("3:41") == 221 and seconds_of("") is None and seconds_of("x") is None
    assert play_minutes("A", TRACKS, '12"', 1) == 20          # the timed tracks on side A
    assert play_minutes("", TRACKS, '12"', 1) == 25           # the whole record
    assert play_minutes("A, B", [], '12"', 1) == 40           # no tracklist: a usual side each
    assert play_minutes("", [], '7"', 1) == 8
    assert play_minutes("", [{"position": "A1", "title": "x"}], '12"', 2) == 80    # no times: 4 sides of 20


def test_loans_and_cleaning(client):
    r = add(client)
    loaned = client.patch(f"/api/vinyl/records/{r['record_id']}", json={"loaned_to": "  Sam "}).json()
    assert loaned["loaned_to"] == "Sam" and loaned["loaned_on"] == str(date.today())
    out = client.get("/api/vinyl/loans").json()
    assert [(x["record_id"], x["loaned_to"], x["days"]) for x in out] == [(r["record_id"], "Sam", 0)]
    assert client.get("/api/vinyl/summary").json()["loaned"] == 1
    back = client.patch(f"/api/vinyl/records/{r['record_id']}", json={"loaned_to": ""}).json()
    assert back["loaned_to"] is None and back["loaned_on"] is None and client.get("/api/vinyl/loans").json() == []
    cleaned = client.post(f"/api/vinyl/records/{r['record_id']}/clean", json={"done_on": "2026-10-01", "note": "wet clean"}).json()
    assert [(c["done_on"], c["note"]) for c in cleaned["care"]] == [("2026-10-01", "wet clean")]
    assert client.post("/api/vinyl/records/99999/clean", json={}).status_code == 404
    assert client.delete(f"/api/vinyl/care/{cleaned['care'][0]['care_id']}").status_code == 204
    assert client.get(f"/api/vinyl/records/{r['record_id']}").json()["care"] == []
    assert client.delete("/api/vinyl/care/99999").status_code == 404


def test_stylus_hours_and_due(client):
    r = add(client, size='12"')
    client.patch(f"/api/vinyl/records/{r['record_id']}", json={"tracklist": TRACKS})
    cd = add(client, title="A CD", medium="CD")
    for _ in range(3):
        client.post(f"/api/vinyl/records/{r['record_id']}/plays", json={"sides": "A", "scrobble": False})
    client.post(f"/api/vinyl/records/{cd['record_id']}/plays", json={"scrobble": False})     # a CD: no stylus
    with db() as conn:
        conn.execute("UPDATE vinyl_settings SET stylus_since = NULL, stylus_limit_hours = 800 WHERE id = 1")
    s = client.get("/api/vinyl/stylus").json()
    assert (s["hours"], s["plays"], s["due"], s["soon"]) == (1.0, 3, False, False)
    assert client.put("/api/vinyl/stylus", json={"limit_hours": 1.1}).json()["soon"] is True
    assert client.put("/api/vinyl/stylus", json={"limit_hours": 1}).json()["due"] is True
    assert client.get("/api/vinyl/summary").json()["stylus"]["due"] is True
    assert client.put("/api/vinyl/stylus", json={"limit_hours": 0}).status_code == 422
    # A new stylus starts the count again.
    tomorrow = str(date.today() + timedelta(days=1))
    fresh = client.post("/api/vinyl/stylus/fitted", json={"fitted_on": tomorrow}).json()
    assert fresh["hours"] == 0 and fresh["since"] == tomorrow and not fresh["due"]
    client.put("/api/vinyl/stylus", json={"limit_hours": 800})
    with db() as conn:
        conn.execute("UPDATE vinyl_settings SET stylus_since = NULL WHERE id = 1")


def test_value_history_and_movers(client):
    r = add(client, status="Owned")
    rid = r["record_id"]
    old = date.today() - timedelta(days=100)
    with db() as conn:
        conn.execute("INSERT INTO vinyl_values (record_id, value, seen_on) VALUES (%s, 10, %s), (%s, 25, current_date)", (rid, old, rid))
        conn.execute("UPDATE vinyl_records SET value = 25 WHERE record_id = %s", (rid,))
    h = client.get("/api/vinyl/value-history").json()
    assert h["now"] == 25 and h["series"][0]["value"] == 10
    assert h["changes"][0]["days"] == 30 and h["changes"][0]["change"] == 15
    assert [(m["record_id"], m["was"], m["moved"]) for m in h["movers"]] == [(rid, 10, 15)]
    assert client.get("/api/vinyl/value-history?weeks=1").status_code == 422


def test_change_helper():
    series = [{"week": date(2026, 1, 5), "value": 100.0}, {"week": date(2026, 3, 2), "value": 150.0}]
    assert change(series, 30, date(2026, 3, 4)) == {"days": 30, "was": 100.0, "change": 50.0, "percent": 50.0}
    assert change(series, 365, date(2026, 3, 4)) is None and change([], 30, date(2026, 3, 4)) is None


def test_year_numbers_and_review(client):
    plays = [{"played_at": datetime(2026, 2, 7, 20, 0), "record_id": 1, "title": "Blue", "artist": "Joni", "sides": "A",
              "tracklist": TRACKS, "size": '12"', "discs": 1, "scrobbled": 2},
             {"played_at": datetime(2026, 2, 8, 20, 0), "record_id": 1, "title": "Blue", "artist": "Joni", "sides": "",
              "tracklist": TRACKS, "size": '12"', "discs": 1, "scrobbled": None},
             {"played_at": datetime(2026, 6, 1, 9, 0), "record_id": 2, "title": "Kind", "artist": None, "sides": "A",
              "tracklist": [], "size": '12"', "discs": 1, "scrobbled": 0}]
    y = year_numbers(plays, 2026)
    assert (y["plays"], y["records_played"], y["days"], y["hours"], y["scrobbled"]) == (3, 2, 3, 1.1, 2)
    assert y["by_month"][1]["plays"] == 2 and y["top_records"][0]["title"] == "Blue" and y["top_artists"] == [{"label": "Joni", "plays": 2}]
    assert y["busiest_day"]["plays"] == 1
    # the endpoint: plays in the year, and new arrivals
    r = add(client, title="Played")
    add(client, title="Fresh")
    client.post(f"/api/vinyl/records/{r['record_id']}/plays", json={"scrobble": False})
    rev = client.get("/api/vinyl/review").json()
    assert rev["plays"] == 1 and rev["records_played"] == 1 and len(rev["new_arrivals"]) == 2 and rev["new_unplayed"] == 1
    assert rev["year"] in rev["years"]
    assert client.get("/api/vinyl/review?year=2001").json()["plays"] == 0
