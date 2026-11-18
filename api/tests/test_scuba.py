"""Scuba diving: the logbook (numbering from the dives logged before the app, SAC, surface interval, previous / next),
sightings and the life list, sites, trips, cards, gear service and what's due, the no-fly rule, the summary, the stats,
and the parts other pages show (activity, goals, calendar, CSV exports)."""
from datetime import date, datetime, time, timedelta

import pytest

from app import goal_sources, scuba
from app.db import db
from app.scuba_dives import sac, surface_interval


@pytest.fixture(autouse=True)
def plain_settings():
    """scuba_settings is one row the clean-up leaves alone: put it back after each test."""
    yield
    with db() as conn:
        conn.execute("""UPDATE scuba_settings SET gas_o2 = 21, tank_l = 12, start_bar = 200, sac_l_min = 20, gf_low = 40, gf_high = 85,
                        ppo2_max = 1.40, dives_before = 0, minutes_before = 0, medical_due = NULL, insurance_until = NULL,
                        home_lat = NULL, home_lon = NULL WHERE id = 1""")


def dive(client, on="2026-05-02", **extra):
    r = client.post("/api/scuba/dives", json={"dived_on": on, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def today():
    with db() as conn:
        return conn.execute("SELECT current_date AS d").fetchone()["d"]


# ---------------------------------------------------------------- the sums

def test_sac_maths():
    # 100 bar of a 12 L tank in 40 min at 18 m average: 1200 L / 40 min = 30 L/min at depth, / 2.8 bar = 10.7
    assert sac(200, 100, 12, 40, 18, 25) == 10.7
    assert sac(200, 100, 12, 40, None, 20) == round(1200 / 40 / (12 / 10 + 1), 1) == 13.6     # 0.6 x max depth when no average
    assert sac(200, 100, 12, 40, None, None) is None
    assert sac(None, 100, 12, 40, 18, 25) is None and sac(200, 100, None, 40, 18, 25) is None
    assert sac(200, 100, 12, None, 18, 25) is None and sac(200, 100, 12, 0, 18, 25) is None


def test_sac_on_the_dive_and_in_the_list(client):
    d = dive(client, max_depth=25, avg_depth=18, minutes=40, tank_l=12, start_bar=200, end_bar=100)
    assert d["sac"] == 10.7
    assert client.get(f"/api/scuba/dives/{d['dive_id']}").json()["sac"] == 10.7
    assert client.get("/api/scuba/dives").json()[0]["sac"] == 10.7
    no_avg = dive(client, "2026-05-03", max_depth=20, minutes=40, tank_l=12, start_bar=200, end_bar=100)
    assert no_avg["sac"] == 13.6
    assert dive(client, "2026-05-04", max_depth=20, minutes=40, start_bar=200, end_bar=100)["sac"] is None      # no tank size
    assert dive(client, "2026-05-05")["sac"] is None


def test_surface_interval_maths():
    prev = {"dived_on": date(2026, 5, 2), "time_in": time(9, 0), "minutes": 45}
    assert surface_interval(prev, {"dived_on": date(2026, 5, 2), "time_in": time(11, 0)}) == 75
    assert surface_interval(prev, {"dived_on": date(2026, 5, 4), "time_in": time(9, 46)}) is None    # past 48 hours
    assert surface_interval(prev, {"dived_on": date(2026, 5, 4), "time_in": time(9, 30)}) == 48 * 60 - 15
    assert surface_interval(prev, {"dived_on": date(2026, 5, 2), "time_in": None}) is None
    assert surface_interval({**prev, "minutes": None}, {"dived_on": date(2026, 5, 2), "time_in": time(11, 0)}) is None
    assert surface_interval(prev, {"dived_on": date(2026, 5, 2), "time_in": time(9, 30)}) is None    # overlapping: bad data


# ---------------------------------------------------------------- numbering

def test_numbers_carry_on_from_dives_before(client):
    assert client.get("/api/scuba/summary").json()["next_no"] == 1
    assert client.put("/api/scuba/settings", json={"dives_before": 50, "minutes_before": 3000}).status_code == 200
    assert client.get("/api/scuba/summary").json()["next_no"] == 51
    a, b = dive(client), dive(client, "2026-05-03")
    assert (a["dive_no"], b["dive_no"]) == (51, 52)
    assert dive(client, "2026-05-04", dive_no=80)["dive_no"] == 80                     # typed: kept, and numbering carries on
    assert dive(client, "2026-05-05")["dive_no"] == 81
    assert dive(client, "2026-05-06", dive_no=10)["dive_no"] == 10                     # (a gap you chose to fill)
    assert dive(client, "2026-05-07")["dive_no"] == 82
    dup = client.post("/api/scuba/dives", json={"dived_on": "2026-05-08", "dive_no": 80})
    assert dup.status_code == 409 and "80" in dup.json()["detail"]
    assert client.patch(f"/api/scuba/dives/{a['dive_id']}", json={"dive_no": 52}).status_code == 409
    assert client.patch(f"/api/scuba/dives/{a['dive_id']}", json={"dive_no": 51}).status_code == 200   # (itself is fine)
    assert client.patch(f"/api/scuba/dives/{a['dive_id']}", json={"dive_no": 0}).status_code == 422


# ---------------------------------------------------------------- the dive

def test_a_dive_in_full(client):
    site = client.post("/api/scuba/sites", json={"name": "Flinders Reef", "place": "Moreton Bay", "lat": -26.97, "lon": 153.48}).json()
    trip = client.post("/api/scuba/trips", json={"name": "Moreton weekend", "start_on": "2026-05-02", "end_on": "2026-05-03"}).json()
    d = dive(client, site_id=site["site_id"], trip_id=trip["trip_id"], time_in="09:30", max_depth=24.5, avg_depth=15, minutes=48,
             water_temp=22.5, visibility_m=15, current="light", entry="boat", tags=["Wreck", " wreck ", "photo", ""], gas_o2=32,
             tank_l=12, start_bar=210, end_bar=70, weight_kg=6, suit="5 mm wetsuit", buddy="Sam", rating=5, notes="Grey nurse sharks")
    assert d["site_name"] == "Flinders Reef" and d["trip_name"] == "Moreton weekend"
    assert d["tags"] == ["wreck", "photo"] and d["gas_o2"] == 32 and d["has_profile"] is False
    assert "samples" not in d and d["sightings"] == [] and d["prev_id"] is None and d["next_id"] is None
    assert d["surface_interval_min"] is None
    one = client.patch(f"/api/scuba/dives/{d['dive_id']}", json={"minutes": 50, "tags": [], "site_id": None}).json()
    assert one["minutes"] == 50 and one["tags"] == [] and one["site_id"] is None and one["site_name"] is None
    assert client.patch(f"/api/scuba/dives/{d['dive_id']}", json={"dived_on": None}).status_code == 422
    assert client.patch(f"/api/scuba/dives/{d['dive_id']}", json={"gas_o2": None}).status_code == 422
    assert client.patch(f"/api/scuba/dives/{d['dive_id']}", json={"site_id": 999}).status_code == 404
    assert client.patch("/api/scuba/dives/999", json={"minutes": 5}).status_code == 404
    assert client.get("/api/scuba/dives/999").status_code == 404
    assert client.delete("/api/scuba/dives/999").status_code == 404


def test_a_dive_is_checked(client):
    bad = [{"dived_on": "2026-05-02", "max_depth": 400}, {"dived_on": "2026-05-02", "gas_o2": 10}, {"dived_on": "2026-05-02", "rating": 6},
           {"dived_on": "2026-05-02", "current": "gale"}, {"dived_on": "2026-05-02", "entry": "swim"}, {"dived_on": "nope"},
           {"dived_on": "2026-05-02", "avg_depth": 30, "max_depth": 20}, {"dived_on": "2026-05-02", "start_bar": 100, "end_bar": 150},
           {"dived_on": "2026-05-02", "minutes": 0}, {}]
    for body in bad:
        assert client.post("/api/scuba/dives", json=body).status_code == 422, body
    msg = client.post("/api/scuba/dives", json={"dived_on": "2026-05-02", "avg_depth": 30, "max_depth": 20}).json()["detail"]
    assert "average depth" in msg
    assert client.post("/api/scuba/dives", json={"dived_on": "2026-05-02", "site_id": 99}).status_code == 404
    assert client.post("/api/scuba/dives", json={"dived_on": "2026-05-02", "trip_id": 99}).status_code == 404


def test_previous_next_and_surface_interval(client):
    a = dive(client, "2026-05-02", time_in="09:00", minutes=45)
    b = dive(client, "2026-05-02", time_in="11:30", minutes=40)
    c = dive(client, "2026-05-03", time_in="09:00", minutes=40)
    far = dive(client, "2026-05-20", time_in="09:00", minutes=40)
    full = {x["dive_id"]: client.get(f"/api/scuba/dives/{x['dive_id']}").json() for x in (a, b, c, far)}
    assert (full[a["dive_id"]]["prev_id"], full[a["dive_id"]]["next_id"]) == (None, b["dive_id"])
    assert (full[b["dive_id"]]["prev_id"], full[b["dive_id"]]["next_id"]) == (a["dive_id"], c["dive_id"])
    assert full[far["dive_id"]]["next_id"] is None and full[far["dive_id"]]["prev_id"] == c["dive_id"]
    assert full[a["dive_id"]]["surface_interval_min"] is None                 # the first
    assert full[b["dive_id"]]["surface_interval_min"] == 105                  # 09:45 to 11:30
    assert full[c["dive_id"]]["surface_interval_min"] == 20 * 60 + 50         # 12:10 to 09:00 next day
    assert full[far["dive_id"]]["surface_interval_min"] is None               # more than 48 h
    # no start time: no interval
    d = dive(client, "2026-05-03", minutes=30)
    assert client.get(f"/api/scuba/dives/{d['dive_id']}").json()["surface_interval_min"] is None


def test_the_logbook_list_and_filters(client):
    site = client.post("/api/scuba/sites", json={"name": "Julian Rocks", "place": "Byron Bay"}).json()["site_id"]
    other = client.post("/api/scuba/sites", json={"name": "Wolf Rock"}).json()["site_id"]
    trip = client.post("/api/scuba/trips", json={"name": "Byron", "start_on": "2025-12-01"}).json()["trip_id"]
    a = dive(client, "2025-12-01", time_in="08:00", site_id=site, trip_id=trip, max_depth=18, minutes=50, buddy="Jo", tags=["night"])
    b = dive(client, "2026-05-02", time_in="09:00", site_id=other, max_depth=12, minutes=40, notes="Saw a Wobbegong")
    c = dive(client, "2026-05-02", time_in="13:00", site_id=other, max_depth=14, minutes=35)
    log = client.get("/api/scuba/dives").json()
    assert [x["dive_id"] for x in log] == [c["dive_id"], b["dive_id"], a["dive_id"]]            # newest first, the later dive first
    assert set(log[0]) == {"dive_id", "dive_no", "dived_on", "time_in", "site_id", "site_name", "trip_id", "max_depth", "minutes",
                           "water_temp", "gas_o2", "rating", "tags", "has_profile", "sac"}
    ids = lambda **p: {x["dive_id"] for x in client.get("/api/scuba/dives", params=p).json()}      # noqa: E731
    assert ids(site_id=other) == {b["dive_id"], c["dive_id"]}
    assert ids(trip_id=trip) == {a["dive_id"]}
    assert ids(year=2026) == {b["dive_id"], c["dive_id"]} and ids(year=2025) == {a["dive_id"]}
    assert ids(q="byron") == {a["dive_id"]} and ids(q="wobbegong") == {b["dive_id"]} and ids(q="jo") == {a["dive_id"]}
    assert ids(q="night") == {a["dive_id"]} and ids(q="WOLF") == {b["dive_id"], c["dive_id"]}
    assert ids(q=str(b["dive_no"])) == {b["dive_id"]}
    assert ids(q="100%") == set() and ids(q="_") == set()                         # LIKE's own characters are plain text
    client.put(f"/api/scuba/dives/{a['dive_id']}/sightings", json=[{"species": "Grey nurse shark"}])
    assert ids(q="nurse") == {a["dive_id"]}
    assert ids(site_id=other, year=2025) == set()


# ---------------------------------------------------------------- sightings and the life list

def test_sightings_replace_and_the_life_list(client):
    a = dive(client, "2026-05-02", time_in="09:00")["dive_id"]
    b = dive(client, "2026-05-09")["dive_id"]
    r = client.put(f"/api/scuba/dives/{a}/sightings", json=[{"species": "Green turtle", "how_many": 2}, {"species": " Manta ray ", "notes": "cleaning station"},
                                                            {"species": "green TURTLE", "how_many": 9}])
    assert r.status_code == 200
    assert r.json() == [{"species": "Green turtle", "how_many": 2, "notes": None}, {"species": "Manta ray", "how_many": None, "notes": "cleaning station"}]
    client.put(f"/api/scuba/dives/{b}/sightings", json=[{"species": "green turtle", "how_many": 1}, {"species": "Leopard shark", "how_many": 1}])
    life = client.get("/api/scuba/species").json()
    assert [s["species"] for s in life] == ["Green turtle", "Leopard shark", "Manta ray"]
    turtle = life[0]
    assert (turtle["dives"], turtle["total"], turtle["first_on"], turtle["last_on"], turtle["first_dive_id"]) == (2, 3, "2026-05-02", "2026-05-09", a)
    assert life[2]["total"] == 0 and life[2]["dives"] == 1
    assert client.get("/api/scuba/summary").json()["species"] == 3
    # replace: the old list goes
    r = client.put(f"/api/scuba/dives/{a}/sightings", json=[{"species": "Eagle ray"}])
    assert [s["species"] for s in r.json()] == ["Eagle ray"]
    assert [s["species"] for s in client.get(f"/api/scuba/dives/{a}").json()["sightings"]] == ["Eagle ray"]
    assert client.put(f"/api/scuba/dives/{a}/sightings", json=[]).json() == []
    assert client.put(f"/api/scuba/dives/{a}/sightings", json=[{"species": "  "}]).status_code == 422
    assert client.put(f"/api/scuba/dives/{a}/sightings", json=[{"species": "X", "how_many": 0}]).status_code == 422
    assert client.put("/api/scuba/dives/999/sightings", json=[]).status_code == 404
    # a deleted dive takes its sightings with it
    assert client.delete(f"/api/scuba/dives/{b}").status_code == 204
    assert client.get("/api/scuba/species").json() == []


# ---------------------------------------------------------------- sites

def test_sites(client):
    s = client.post("/api/scuba/sites", json={"name": " Cook Island ", "place": "Tweed", "lat": -28.19, "lon": 153.57, "kind": "Reef", "entry": "boat",
                                              "depth_min": 5, "depth_max": 25}).json()
    sid = s["site_id"]
    assert s["name"] == "Cook Island" and s["dives"] == 0 and s["last_on"] is None and s["recent_dives"] == []
    assert client.post("/api/scuba/sites", json={"name": "  "}).status_code == 422
    assert client.post("/api/scuba/sites", json={"name": "X", "lat": 95}).status_code == 422
    assert client.post("/api/scuba/sites", json={"name": "X", "entry": "swim"}).status_code == 422
    a = dive(client, "2026-05-02", site_id=sid, max_depth=18, water_temp=22, visibility_m=10)
    dive(client, "2026-05-09", site_id=sid, max_depth=24, water_temp=23, visibility_m=20)
    client.put(f"/api/scuba/dives/{a['dive_id']}/sightings", json=[{"species": "Turtle"}, {"species": "Wobbegong"}])
    d2 = client.get("/api/scuba/dives", params={"site_id": sid}).json()[0]["dive_id"]
    client.put(f"/api/scuba/dives/{d2}/sightings", json=[{"species": "turtle"}])
    got = client.get(f"/api/scuba/sites/{sid}").json()
    assert (got["dives"], got["last_on"], got["deepest"], got["avg_temp"], got["avg_vis"]) == (2, "2026-05-09", 24, 22.5, 15)
    assert [x["dived_on"] for x in got["recent_dives"]] == ["2026-05-09", "2026-05-02"]
    assert got["species_seen"] == [{"species": "Turtle", "dives": 2}, {"species": "Wobbegong", "dives": 1}]
    listing = client.get("/api/scuba/sites").json()
    assert listing[0]["dives"] == 2 and listing[0]["deepest"] == 24
    upd = client.patch(f"/api/scuba/sites/{sid}", json={"name": "Cook Island Reef", "notes": "turtles", "kind": None}).json()
    assert upd["name"] == "Cook Island Reef" and upd["kind"] is None
    assert client.patch(f"/api/scuba/sites/{sid}", json={"name": None}).status_code == 422
    assert client.patch("/api/scuba/sites/999", json={"notes": "x"}).status_code == 404
    # a deleted site leaves its dives in the logbook
    assert client.delete(f"/api/scuba/sites/{sid}").status_code == 204
    after = client.get(f"/api/scuba/dives/{a['dive_id']}").json()
    assert after["site_id"] is None and after["site_name"] is None
    assert client.get(f"/api/scuba/sites/{sid}").status_code == 404 and client.delete(f"/api/scuba/sites/{sid}").status_code == 404
    assert len(client.get("/api/scuba/dives").json()) == 2


# ---------------------------------------------------------------- trips

def test_trips(client):
    assert client.post("/api/scuba/trips", json={"name": "Back to front", "start_on": "2026-05-05", "end_on": "2026-05-01"}).status_code == 422
    assert client.post("/api/scuba/trips", json={"name": "No dates"}).status_code == 422
    t = client.post("/api/scuba/trips", json={"name": "Yongala", "start_on": "2026-06-01", "end_on": "2026-06-05", "place": "Townsville",
                                              "operator": "Yongala Dive"}).json()
    older = client.post("/api/scuba/trips", json={"name": "Old trip", "start_on": "2025-01-01"}).json()
    assert [x["name"] for x in client.get("/api/scuba/trips").json()] == ["Yongala", "Old trip"]
    s1 = client.post("/api/scuba/sites", json={"name": "SS Yongala"}).json()["site_id"]
    s2 = client.post("/api/scuba/sites", json={"name": "Wreck two"}).json()["site_id"]
    dive(client, "2026-06-02", trip_id=t["trip_id"], site_id=s1, minutes=45, max_depth=28)
    dive(client, "2026-06-03", trip_id=t["trip_id"], site_id=s1, minutes=50, max_depth=30)
    dive(client, "2026-06-04", trip_id=t["trip_id"], site_id=s2, minutes=40, max_depth=20)
    got = client.get(f"/api/scuba/trips/{t['trip_id']}").json()
    assert got["totals"] == {"dives": 3, "minutes": 135, "deepest": 30, "sites": 2}
    assert [d["dived_on"] for d in got["dive_list"]] == ["2026-06-04", "2026-06-03", "2026-06-02"]
    assert client.get("/api/scuba/trips").json()[0]["dives"] == 3
    assert client.patch(f"/api/scuba/trips/{t['trip_id']}", json={"end_on": "2026-05-01"}).status_code == 422
    assert client.patch(f"/api/scuba/trips/{t['trip_id']}", json={"operator": "Other", "end_on": None}).json()["end_on"] is None
    assert client.patch(f"/api/scuba/trips/{t['trip_id']}", json={"start_on": None}).status_code == 422
    assert client.patch("/api/scuba/trips/999", json={"notes": "x"}).status_code == 404
    assert client.delete(f"/api/scuba/trips/{t['trip_id']}").status_code == 204        # the dives stay
    assert len(client.get("/api/scuba/dives").json()) == 3
    assert all(d["trip_id"] is None for d in client.get("/api/scuba/dives").json())
    assert client.get(f"/api/scuba/trips/{older['trip_id']}").json()["totals"]["dives"] == 0
    assert client.delete("/api/scuba/trips/999").status_code == 404


# ---------------------------------------------------------------- cards

def test_certs(client):
    c = client.post("/api/scuba/certs", json={"agency": "PADI", "name": "Open Water Diver", "cert_no": "1234", "certified_on": "2020-03-01",
                                              "instructor": "Alex"})
    assert c.status_code == 201, c.text
    cid = c.json()["cert_id"]
    client.post("/api/scuba/certs", json={"agency": "PADI", "name": "Advanced", "certified_on": "2022-01-01"})
    client.post("/api/scuba/certs", json={"agency": "DAN", "name": "Oxygen provider"})
    assert [x["name"] for x in client.get("/api/scuba/certs").json()] == ["Advanced", "Open Water Diver", "Oxygen provider"]
    assert client.post("/api/scuba/certs", json={"agency": " ", "name": "X"}).status_code == 422
    assert client.patch(f"/api/scuba/certs/{cid}", json={"name": None}).status_code == 422
    assert client.patch(f"/api/scuba/certs/{cid}", json={"cert_no": "99", "expires_on": "2030-01-01"}).json()["cert_no"] == "99"
    assert client.patch("/api/scuba/certs/999", json={"cert_no": "1"}).status_code == 404
    assert client.delete(f"/api/scuba/certs/{cid}").status_code == 204
    assert client.delete(f"/api/scuba/certs/{cid}").status_code == 404
    assert len(client.get("/api/scuba/certs").json()) == 2


# ---------------------------------------------------------------- gear service

def add_gear(client, name="Regulator", hobby="scuba", **extra):
    r = client.post("/api/gear", json={"name": name, "hobby": hobby, "kind": "Regulator", **extra})
    assert r.status_code == 201, r.text
    return r.json()["gear_id"]


def test_gear_and_service(client):
    reg = add_gear(client)
    tank = add_gear(client, "Tank 12 L", kind="Tank")
    shoes = add_gear(client, "Court shoes", hobby="volleyball")
    gear = client.get("/api/scuba/gear").json()
    assert [g["name"] for g in gear] == ["Regulator", "Tank 12 L"]
    assert gear[0]["last_service"] is None and gear[0]["next_due"] is None and gear[0]["dives_since_service"] == 0
    dive(client, "2026-03-01")
    dive(client, "2026-05-01")
    dive(client, "2026-06-01")
    assert client.get("/api/scuba/gear").json()[0]["dives_since_service"] == 3                      # never serviced: all of them
    s = client.post(f"/api/scuba/gear/{reg}/service", json={"done_on": "2026-04-01", "what": "Annual service", "done_by": "Dive shop",
                                                             "cost": 180, "next_due": "2027-04-01"})
    assert s.status_code == 201, s.text
    sid = s.json()["service_id"]
    g = client.get("/api/scuba/gear").json()[0]
    assert g["last_service"]["what"] == "Annual service" and g["next_due"] == "2027-04-01" and g["dives_since_service"] == 2 and g["services"] == 1
    # a tank has two kinds of service: the soonest due date counts
    client.post(f"/api/scuba/gear/{tank}/service", json={"done_on": "2026-01-10", "what": "Visual inspection", "next_due": "2027-01-10"})
    client.post(f"/api/scuba/gear/{tank}/service", json={"done_on": "2024-01-10", "what": "Hydro test", "next_due": "2029-01-10"})
    client.post(f"/api/scuba/gear/{tank}/service", json={"done_on": "2025-01-10", "what": "visual inspection", "next_due": "2026-01-10"})   # older: superseded
    t = [g for g in client.get("/api/scuba/gear").json() if g["gear_id"] == tank][0]
    assert t["next_due"] == "2027-01-10" and t["last_service"]["what"] == "Visual inspection"
    listing = client.get(f"/api/scuba/gear/{tank}/service").json()
    assert [x["done_on"] for x in listing] == ["2026-01-10", "2025-01-10", "2024-01-10"]
    # checks
    assert client.post(f"/api/scuba/gear/{reg}/service", json={"done_on": "2026-04-01", "what": "X", "next_due": "2026-01-01"}).status_code == 422
    assert client.post(f"/api/scuba/gear/{reg}/service", json={"done_on": "2026-04-01", "what": " "}).status_code == 422
    assert client.post(f"/api/scuba/gear/{reg}/service", json={"done_on": "2026-04-01", "what": "X", "cost": -1}).status_code == 422
    assert client.post(f"/api/scuba/gear/{shoes}/service", json={"done_on": "2026-04-01", "what": "X"}).status_code == 404     # not scuba gear
    assert client.get(f"/api/scuba/gear/{shoes}/service").status_code == 404
    assert client.post("/api/scuba/gear/999/service", json={"done_on": "2026-04-01", "what": "X"}).status_code == 404
    assert client.delete(f"/api/scuba/service/{sid}").status_code == 204
    assert client.delete(f"/api/scuba/service/{sid}").status_code == 404
    assert client.get("/api/scuba/gear").json()[0]["last_service"] is None
    # the gear's own delete takes its service log with it
    assert client.delete(f"/api/gear/{tank}").status_code == 204
    assert client.get(f"/api/scuba/gear/{tank}/service").status_code == 404


# ---------------------------------------------------------------- what's due

def test_alerts(client):
    t = today()
    assert client.get("/api/scuba/summary").json()["alerts"] == []
    client.put("/api/scuba/settings", json={"medical_due": str(t + timedelta(days=30)), "insurance_until": str(t - timedelta(days=3))})
    client.post("/api/scuba/certs", json={"agency": "DAN", "name": "Oxygen provider", "expires_on": str(t + timedelta(days=59))})
    client.post("/api/scuba/certs", json={"agency": "PADI", "name": "Open Water", "expires_on": str(t + timedelta(days=200))})       # too far off
    reg = add_gear(client)
    client.post(f"/api/scuba/gear/{reg}/service", json={"done_on": str(t - timedelta(days=364)), "what": "Annual service", "next_due": str(t)})
    old = add_gear(client, "Old BCD")
    client.post(f"/api/scuba/gear/{old}/service", json={"done_on": str(t - timedelta(days=400)), "what": "Service", "next_due": str(t - timedelta(days=5))})
    client.patch(f"/api/gear/{old}", json={"condition": "Retired"})                                       # retired gear isn't nagged about
    quiet = add_gear(client, "Fins")
    client.post(f"/api/scuba/gear/{quiet}/service", json={"done_on": str(t - timedelta(days=1)), "what": "Check", "next_due": str(t + timedelta(days=61))})
    a = client.get("/api/scuba/summary").json()["alerts"]
    assert [(x["kind"], x["due"]) for x in a] == [("insurance", str(t - timedelta(days=3))), ("service", str(t)),
                                                  ("medical", str(t + timedelta(days=30))), ("cert", str(t + timedelta(days=59)))]
    assert a[0]["text"] == "Dive insurance is overdue by 3 days" and a[1]["text"] == "Regulator: annual service is due today"
    assert a[2]["text"] == "Dive medical is due in 30 days" and a[3]["text"] == "DAN Oxygen provider card is due in 59 days"
    # a newer service pushes the alert away
    client.post(f"/api/scuba/gear/{reg}/service", json={"done_on": str(t), "what": "Annual service", "next_due": str(t + timedelta(days=365))})
    assert "service" not in {x["kind"] for x in client.get("/api/scuba/summary").json()["alerts"]}


# ---------------------------------------------------------------- no-fly

def test_the_no_fly_rule():
    def rows(*dives):
        return [{"dived_on": d, "time_in": t, "minutes": m} for d, t, m in dives]
    d1 = date(2026, 5, 2)
    now = datetime(2026, 5, 2, 15, 0)
    assert scuba.no_fly_until([], now) is None
    # one dive, 09:00 + 45 min: 12 h after 09:45
    assert scuba.no_fly_until(rows((d1, time(9), 45)), now) == datetime(2026, 5, 2, 21, 45)
    # a repeat dive the same day: 18 h after the end of the last
    assert scuba.no_fly_until(rows((d1, time(9), 45), (d1, time(12), 40)), now) == datetime(2026, 5, 3, 6, 40)
    # dives on two days running: 18 h
    assert scuba.no_fly_until(rows((d1 - timedelta(days=1), time(9), 45), (d1, time(10), 30)), now) == datetime(2026, 5, 3, 4, 30)
    # a gap day in between: only the last day counts (12 h)
    assert scuba.no_fly_until(rows((d1 - timedelta(days=2), time(9), 45), (d1, time(10), 30)), now) == datetime(2026, 5, 2, 22, 30)
    # passed: nothing
    assert scuba.no_fly_until(rows((d1, time(9), 45)), datetime(2026, 5, 2, 21, 45)) is None
    assert scuba.no_fly_until(rows((d1, time(9), 45)), datetime(2026, 5, 3, 8, 0)) is None
    # no start time: the end of the day; no length: the start
    assert scuba.no_fly_until(rows((d1, None, 45)), now) == datetime(2026, 5, 3, 12, 44)
    assert scuba.no_fly_until(rows((d1, time(9), None)), now) == datetime(2026, 5, 2, 21, 0)
    # the order of the rows doesn't matter
    assert scuba.no_fly_until(rows((d1, time(12), 40), (d1, time(9), 45)), now) == datetime(2026, 5, 3, 6, 40)


def test_no_fly_in_the_summary(client):
    assert client.get("/api/scuba/summary").json()["no_fly_until"] is None
    dive(client, "2020-01-01", time_in="09:00", minutes=45)
    assert client.get("/api/scuba/summary").json()["no_fly_until"] is None                    # long ago
    with db() as conn:
        now = conn.execute("SELECT localtimestamp AS t").fetchone()["t"]
    start = now - timedelta(minutes=100)                                                    # a 40 minute dive that ended an hour ago
    dive(client, str(start.date()), time_in=start.strftime("%H:%M"), minutes=40)
    got = client.get("/api/scuba/summary").json()["no_fly_until"]
    assert got is not None
    until = datetime.fromisoformat(got)
    # 12 h after it ended (18 h when a dive the day before or earlier today made it a repeat): never less than 11 h from now
    assert timedelta(hours=10) < until - now < timedelta(hours=19)


# ---------------------------------------------------------------- the summary

def test_the_summary(client):
    s = client.get("/api/scuba/summary").json()
    assert (s["dives"], s["minutes"], s["dives_logged"], s["deepest"], s["last_dive"], s["recent"], s["sites"], s["species"]) == (0, 0, 0, None, None, [], 0, 0)
    client.put("/api/scuba/settings", json={"dives_before": 40, "minutes_before": 1800})
    site = client.post("/api/scuba/sites", json={"name": "Wolf Rock"}).json()["site_id"]
    y = today().year
    for i in range(6):
        dive(client, f"{y - 1}-06-0{i + 1}", time_in="09:00", max_depth=10 + i, minutes=30 + i, site_id=site)
    dive(client, f"{y}-01-05", time_in="10:00", max_depth=32, minutes=51)
    s = client.get("/api/scuba/summary").json()
    assert s["dives"] == 47 and s["dives_logged"] == 7 and s["minutes"] == 1800 + sum(30 + i for i in range(6)) + 51
    assert s["deepest"] == 32 and s["longest"] == 51 and s["next_no"] == 48 and s["sites"] == 1 and s["this_year"] == 1
    assert len(s["recent"]) == 5 and s["recent"][0]["dived_on"] == f"{y}-01-05" and s["last_dive"] == s["recent"][0]
    assert s["last_dive"]["dive_no"] == 47


# ---------------------------------------------------------------- settings

def test_settings(client):
    s = client.get("/api/scuba/settings").json()
    assert (s["gas_o2"], float(s["tank_l"]), s["start_bar"], float(s["sac_l_min"]), s["gf_low"], s["gf_high"], float(s["ppo2_max"]), s["dives_before"]) \
        == (21, 12, 200, 20, 40, 85, 1.4, 0)
    s = client.put("/api/scuba/settings", json={"gas_o2": 32, "tank_l": 11.1, "gf_low": 30, "gf_high": 70, "dives_before": 25, "medical_due": "2027-01-01",
                                                "home_lat": -27.47, "home_lon": 153.03}).json()
    assert s["gas_o2"] == 32 and float(s["tank_l"]) == 11.1 and s["medical_due"] == "2027-01-01" and s["gf_high"] == 70
    assert client.put("/api/scuba/settings", json={"medical_due": None}).json()["medical_due"] is None
    assert client.put("/api/scuba/settings", json={"gf_low": 90}).status_code == 422                   # above the high one (70)
    assert "gradient" in client.put("/api/scuba/settings", json={"gf_low": 90}).json()["detail"]
    for bad in ({"gas_o2": 10}, {"tank_l": 0}, {"ppo2_max": 2}, {"dives_before": -1}, {"gas_o2": None}, {"dives_before": None}, {"home_lat": 100}):
        assert client.put("/api/scuba/settings", json=bad).status_code == 422, bad
    assert client.put("/api/scuba/settings", json={}).status_code == 200
    assert client.get("/api/scuba/settings").json()["gas_o2"] == 32


# ---------------------------------------------------------------- stats

def test_stats(client):
    y = today().year
    client.put("/api/scuba/settings", json={"dives_before": 10, "minutes_before": 600})
    a = client.post("/api/scuba/sites", json={"name": "Alpha"}).json()["site_id"]
    b = client.post("/api/scuba/sites", json={"name": "Beta"}).json()["site_id"]
    one = dive(client, f"{y - 1}-03-01", time_in="09:00", site_id=a, max_depth=9, minutes=40, water_temp=26, visibility_m=25, tags=["training"],
               tank_l=12, start_bar=200, end_bar=120, avg_depth=6)                           # 960 / 40 / 1.6 = 15.0
    two = dive(client, f"{y}-01-10", time_in="09:00", site_id=a, max_depth=17.9, minutes=55, water_temp=21, visibility_m=8, tags=["wreck", "training"])
    three = dive(client, f"{y}-01-20", time_in="09:00", site_id=b, max_depth=18, minutes=30, water_temp=20, visibility_m=12, tags=["wreck"])
    four = dive(client, f"{y}-02-02", time_in="09:00", site_id=a, max_depth=29.9, minutes=45, water_temp=27, tank_l=12, start_bar=200, end_bar=100)   # avg 17.94
    five = dive(client, f"{y}-02-03", time_in="09:00", max_depth=45, minutes=20, water_temp=24)
    dive(client, f"{y}-02-04")                                                              # nothing known
    client.put(f"/api/scuba/dives/{one['dive_id']}/sightings", json=[{"species": "Turtle"}])
    st = client.get("/api/scuba/stats").json()
    t = st["totals"]
    assert t["dives"] == 16 and t["dives_logged"] == 6 and t["minutes"] == 600 + 40 + 55 + 30 + 45 + 20 and t["sites"] == 2 and t["species"] == 1
    assert t["avg_depth"] == round((9 + 17.9 + 18 + 29.9 + 45) / 5, 1) and t["hours"] == round(t["minutes"] / 60, 1) and t["dive_days"] == 6
    r = st["records"]
    assert r["deepest"]["dive_id"] == five["dive_id"] and r["longest"]["dive_id"] == two["dive_id"] and r["coldest"]["dive_id"] == three["dive_id"]
    assert r["warmest"]["dive_id"] == four["dive_id"] and r["best_vis"]["dive_id"] == one["dive_id"] and r["deepest"]["site_name"] is None
    assert [x["year"] for x in st["by_year"]] == [y - 1, y] and st["by_year"][1] == {"year": y, "dives": 5, "minutes": 150}
    assert len(st["by_month"]) == 24 and st["by_month"][-1]["month"] == today().strftime("%Y-%m")
    months = {m["month"]: m for m in st["by_month"]}
    assert months[f"{y}-01"] == {"month": f"{y}-01", "dives": 2, "minutes": 85} and months[f"{y}-02"]["dives"] == 3
    assert st["depth_bands"] == [{"band": "0-10", "dives": 1}, {"band": "10-18", "dives": 1}, {"band": "18-30", "dives": 2}, {"band": "30-40", "dives": 0},
                                 {"band": "40+", "dives": 1}]
    assert [s["dive_id"] for s in st["sac_trend"]] == [one["dive_id"], four["dive_id"]] and st["sac_trend"][0]["sac"] == 15.0
    assert st["sac_trend"][1]["sac"] == round(1200 / 45 / (29.9 * 0.6 / 10 + 1), 1)
    assert st["top_sites"][0] == {"site_id": a, "name": "Alpha", "dives": 3} and st["top_sites"][1]["name"] == "Beta"
    assert st["tags"] == [{"tag": "training", "dives": 2}, {"tag": "wreck", "dives": 2}]
    assert [x["water_temp"] for x in st["temps"]] == [26, 21, 20, 27, 24]
    # one year: the dives before the app aren't in it
    cur = client.get("/api/scuba/stats", params={"year": y}).json()
    assert cur["totals"]["dives"] == 5 and cur["totals"]["minutes"] == 150 and cur["records"]["best_vis"]["dive_id"] == three["dive_id"]
    assert [x["dive_id"] for x in cur["sac_trend"]] == [four["dive_id"]] and len(cur["by_year"]) == 2
    assert client.get("/api/scuba/stats", params={"year": 1999}).json()["records"]["deepest"] is None
    assert client.get("/api/scuba/stats", params={"year": "x"}).status_code == 422


def test_stats_when_empty(client):
    st = client.get("/api/scuba/stats").json()
    assert st["totals"]["dives"] == 0 and st["records"]["deepest"] is None and st["by_year"] == [] and st["top_sites"] == []
    assert len(st["by_month"]) == 24 and len(st["depth_bands"]) == 5 and st["sac_trend"] == [] and st["tags"] == [] and st["temps"] == []


# ---------------------------------------------------------------- the rest of the app

def test_activity_goals_calendar_and_exports(client):
    site = client.post("/api/scuba/sites", json={"name": "Julian Rocks", "place": "Byron Bay"}).json()["site_id"]
    d = dive(client, str(today()), time_in="09:00", site_id=site, max_depth=18.2, minutes=44, gas_o2=32, tank_l=12, start_bar=200, end_bar=90, buddy="Sam, \"Jo\"")
    dive(client, str(today()), time_in="13:00", minutes=40)
    client.put(f"/api/scuba/dives/{d['dive_id']}/sightings", json=[{"species": "Grey nurse shark", "how_many": 3, "notes": "=cmd"}])
    feed = client.get("/api/activity").json()
    mine = [a for a in feed if a["kind"] == "scubadive"]
    assert len(mine) == 2
    first = [a for a in mine if a["ref"] == d["dive_id"]][0]
    assert first["title"] == "Julian Rocks" and first["verb"] == "Dived" and "#1" in first["detail"] and "18.2 m" in first["detail"] and "Nitrox 32" in first["detail"]
    assert any(a["title"] == "Dive 2" for a in mine)
    # goals
    assert {"scuba_dives", "scuba_minutes"} <= set(goal_sources.SOURCES)
    g = client.post("/api/goals", json={"title": "20 dives", "timeframe": "year", "source": "scuba_dives", "target_value": 20}).json()
    assert (g["unit"], g["hobby"]) == ("dives", "scuba") and g["current_value"] == 2
    m = client.post("/api/goals", json={"title": "Hours down", "timeframe": "year", "source": "scuba_minutes", "target_value": 600}).json()
    assert m["current_value"] == 84
    # calendar: the hobby is known, and a dive counts as done on its day
    e = client.post("/api/calendar/events", json={"title": "Dive trip", "hobby": "scuba", "starts_on": str(today())})
    assert e.status_code == 201 and e.json()["hobby"] == "scuba"
    # journal groups the activity under its hobby
    from app import journal_more
    assert journal_more.HOBBY["scubadive"] == "Scuba diving"
    # exports
    csv = client.get("/api/export/scuba-dives.csv").text
    lines = csv.splitlines()
    assert lines[0].lstrip("﻿").startswith("Dive no,Date,Time in,Site,Place") and "Julian Rocks,Byron Bay" in csv
    assert "09:00" in csv and ',32,12.0,200,90,' in csv and ",14.3," in csv                   # SAC: 1320 L / 44 min / (10.92 m / 10 + 1)
    assert '"Sam, ""Jo"""' in csv
    sight = client.get("/api/export/scuba-sightings.csv").text
    assert "Grey nurse shark,3,1," in sight and "'=cmd" in sight


def test_the_routes_never_crash(client):
    for path in ("/api/scuba/dives/0", "/api/scuba/sites/0", "/api/scuba/trips/0", "/api/scuba/gear/0/service"):
        assert client.get(path).status_code == 404
    assert client.get("/api/scuba/dives", params={"year": "abc"}).status_code == 422
    assert client.get("/api/scuba/dives", params={"q": "x" * 200}).status_code == 422
    assert client.get("/api/scuba/dives", params={"site_id": 99999999999}).status_code in (200, 422)
