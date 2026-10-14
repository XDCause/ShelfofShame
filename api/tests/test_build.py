"""Kit stash statuses, the shelf-of-shame summary, the timer and the build log."""
from datetime import date, timedelta

import pytest

from app.db import db


def new_model(client, **fields):
    r = client.post("/api/models", json={"name": "Sherman", **fields})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- stash
def test_new_kits_go_in_the_stash_with_what_you_paid(client):
    m = new_model(client, price_paid="54.95", purchase_date="2026-10-01", purchased_from="Hobbyrama")
    assert (m["status"], float(m["price_paid"]), m["purchased_from"]) == ("In stash", 54.95, "Hobbyrama")
    assert m["started_on"] is None and m["total_minutes"] == 0 and m["log"] == [] and m["sessions"] == []


@pytest.mark.parametrize("status", ["Not started", "Building", ""])
def test_unknown_statuses_are_refused(client, status):
    assert client.post("/api/models", json={"name": "X", "status": status}).status_code == 422


def test_starting_and_finishing_dates_themselves(client):
    m = new_model(client, status="Wanted")
    m = client.patch(f"/api/models/{m['model_id']}", json={"status": "In progress"}).json()
    assert m["started_on"] == str(date.today()) and m["finished_on"] is None
    m = client.patch(f"/api/models/{m['model_id']}", json={"status": "Finished"}).json()
    assert m["finished_on"] == str(date.today())
    # dates you set yourself are kept
    m = client.patch(f"/api/models/{m['model_id']}", json={"started_on": "2026-01-02", "status": "Finished"}).json()
    assert m["started_on"] == "2026-01-02"


def test_shelf_of_shame_summary(client):
    new_model(client, status="In stash", price_paid="50")
    new_model(client, status="In progress", price_paid="30.50")
    new_model(client, status="On hold")                       # no price
    new_model(client, status="Wanted", price_paid="99")       # not owned yet
    new_model(client, status="Finished", price_paid="20")
    s = client.get("/api/models/summary").json()
    assert s["counts"] == {"Wanted": 1, "In stash": 1, "In progress": 1, "On hold": 1, "Finished": 1, "Gone": 0}
    assert s["shelf_of_shame"] == {"kits": 3, "value": 80.5, "unpriced": 1}
    assert s["all_kits"] == {"kits": 4, "value": 100.5, "unpriced": 1, "finished": 1, "finished_value": 20}   # + the finished one
    spending = client.get("/api/spending").json()
    assert spending["kits_spent"] == 100.5 and spending["kits_priced"] == 3   # wanted kits aren't spent


# ---------------------------------------------------------------- timer
def backdate_running(model_id, minutes):
    with db() as conn:
        conn.execute("UPDATE model_sessions SET started_at = now() - %s * interval '1 minute' "
                     "WHERE model_id = %s AND ended_at IS NULL", (minutes, model_id))


def test_timer_start_and_stop(client):
    m = new_model(client)
    m = client.post(f"/api/models/{m['model_id']}/timer/start").json()
    assert m["running_since"] and m["status"] == "In progress" and m["started_on"] == str(date.today())
    assert client.get("/api/timer").json()["name"] == "Sherman"
    assert client.post(f"/api/models/{m['model_id']}/timer/start").status_code == 409

    backdate_running(m["model_id"], 45)
    m = client.post(f"/api/models/{m['model_id']}/timer/stop", json={"note": "Tracks"}).json()
    assert m["running_since"] is None and m["total_minutes"] == 45
    assert (m["sessions"][0]["minutes"], m["sessions"][0]["note"]) == (45, "Tracks")
    assert client.get("/api/timer").json() is None
    assert client.post(f"/api/models/{m['model_id']}/timer/stop").status_code == 404


def test_only_one_timer_runs_at_a_time(client):
    a, b = new_model(client, name="A"), new_model(client, name="B")
    client.post(f"/api/models/{a['model_id']}/timer/start")
    client.post(f"/api/models/{b['model_id']}/timer/start")
    assert client.get(f"/api/models/{a['model_id']}").json()["running_since"] is None
    assert client.get("/api/timer").json()["name"] == "B"


def test_finished_kits_keep_their_status_when_timed(client):
    m = new_model(client, status="Finished")
    assert client.post(f"/api/models/{m['model_id']}/timer/start").json()["status"] == "Finished"


def test_time_added_by_hand(client):
    m = new_model(client)
    yesterday = str(date.today() - timedelta(days=1))
    m = client.post(f"/api/models/{m['model_id']}/sessions",
                    json={"minutes": 90, "day": yesterday, "note": "Hull"}).json()
    assert m["total_minutes"] == 90 and m["sessions"][0]["started_at"].startswith(yesterday)
    assert client.get("/api/models/summary").json()["total_minutes"] == 90
    for bad in (0, -5, 24 * 60 + 1):
        assert client.post(f"/api/models/{m['model_id']}/sessions", json={"minutes": bad}).status_code == 422
    m = client.delete(f"/api/model-sessions/{m['sessions'][0]['session_id']}").json()
    assert m["total_minutes"] == 0
    assert client.delete("/api/model-sessions/9999").status_code == 404


def test_deleting_a_model_deletes_its_time_and_log(client):
    m = new_model(client)
    client.post(f"/api/models/{m['model_id']}/sessions", json={"minutes": 10})
    client.post(f"/api/models/{m['model_id']}/log", json={"text": "Started"})
    client.delete(f"/api/models/{m['model_id']}")
    with db() as conn:
        assert conn.execute("SELECT (SELECT count(*) FROM model_sessions) + (SELECT count(*) FROM model_log) AS n"
                            ).fetchone()["n"] == 0


# ---------------------------------------------------------------- build log
def test_build_log_with_photos(client):
    m = new_model(client)
    entry = client.post(f"/api/models/{m['model_id']}/log", json={"text": "  Primed the hull  "}).json()
    assert (entry["text"], entry["entry_date"], entry["photos"]) == ("Primed the hull", str(date.today()), [])
    older = client.post(f"/api/models/{m['model_id']}/log", json={"text": "Opened the box",
                                                                   "entry_date": "2026-10-01"}).json()
    url = f"/api/model-log/{entry['entry_id']}/photos"
    one = client.post(url, content=b"\xff\xd8one", headers={"content-type": "image/jpeg"})
    assert one.status_code == 201 and len(one.json()["photos"]) == 1
    two = client.post(url, content=b"\x89PNGtwo", headers={"content-type": "image/png"}).json()["photos"]
    assert len(two) == 2 and two[0] < two[1]                                   # in the order added
    got = client.get(f"/api/model-log-photos/{two[1]}")
    assert got.content == b"\x89PNGtwo" and got.headers["content-type"] == "image/png"
    assert "immutable" in got.headers["cache-control"]                         # a photo never changes

    log = client.get(f"/api/models/{m['model_id']}").json()["log"]
    assert [(e["text"], len(e["photos"])) for e in log] == [("Primed the hull", 2), ("Opened the box", 0)]   # newest first
    assert client.delete(f"/api/model-log-photos/{two[0]}").status_code == 204
    assert client.get(f"/api/model-log-photos/{two[0]}").status_code == 404
    assert client.get(f"/api/models/{m['model_id']}").json()["log"][0]["photos"] == [two[1]]

    assert client.patch(f"/api/model-log/{older['entry_id']}", json={"text": "Opened it"}).json()["text"] == "Opened it"
    changed = client.patch(f"/api/model-log/{older['entry_id']}", json={"text": "   ", "entry_date": "2026-10-02"}).json()
    assert (changed["text"], changed["entry_date"]) == (None, "2026-10-02")         # a blank note = none
    assert client.patch(f"/api/model-log/{older['entry_id']}", json={"entry_date": None}).json()["entry_date"] == "2026-10-02"
    assert client.delete(f"/api/model-log/{older['entry_id']}").status_code == 204
    assert client.delete(f"/api/model-log/{older['entry_id']}").status_code == 404
    assert client.delete(f"/api/model-log/{entry['entry_id']}").status_code == 204      # its photos go with it
    assert client.get(f"/api/model-log-photos/{two[1]}").status_code == 404


def test_log_photos_must_be_images(client):
    m = new_model(client)
    entry = client.post(f"/api/models/{m['model_id']}/log", json={"text": "x"}).json()
    url = f"/api/model-log/{entry['entry_id']}/photos"
    assert client.post(url, content=b"hello", headers={"content-type": "text/plain"}).status_code == 415
    assert client.post(url, content=b"", headers={"content-type": "image/png"}).status_code == 422
    assert client.post("/api/model-log/9999/photos", content=b"x", headers={"content-type": "image/png"}).status_code == 404


def test_an_entry_holds_up_to_30_photos(client, monkeypatch):
    from app import build
    monkeypatch.setattr(build, "PHOTOS_PER_ENTRY", 2)
    model = client.post("/api/models", json={"name": "Zero"}).json()
    entry = client.post(f"/api/models/{model['model_id']}/log", json={"text": "Cockpit"}).json()
    url = f"/api/model-log/{entry['entry_id']}/photos"
    for _ in range(2):
        assert client.post(url, content=b"\xff\xd8x", headers={"content-type": "image/jpeg"}).status_code == 201
    assert client.post(url, content=b"\xff\xd8x", headers={"content-type": "image/jpeg"}).status_code == 409
