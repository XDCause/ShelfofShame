"""Fishing: trips and catches (client_key makes resending safe), the rules you typed and the warnings, photos, spots, species,
lures, the summary and its alerts, the stats (moon, tide stage, seasons), and the parts other pages show (activity, goals,
calendar, CSV exports)."""
from datetime import date, datetime, timedelta

import pytest

from app import fishing_trips, goal_sources
from app.db import db
from app.fishing_catches import in_closed_season
from app.fishing_stats import tide_stage

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


@pytest.fixture(autouse=True)
def no_weather(monkeypatch):
    """A trip at a spot with a position asks fishing_tools.snapshot for the conditions: leave it out unless a test wants it."""
    monkeypatch.setattr(fishing_trips, "snapshot_for", lambda conn, spot_id, started_at: None)


def today():
    with db() as conn:
        return conn.execute("SELECT current_date AS d").fetchone()["d"]


def species(client, name):
    return next(s for s in client.get("/api/fishing/species").json() if s["name"] == name)


def trip(client, started="2026-05-02T06:00:00+10:00", ended="2026-05-02T10:00:00+10:00", **extra):
    r = client.post("/api/fishing/trips", json={"started_at": started, "ended_at": ended, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def catch(client, trip_id, **extra):
    r = client.post(f"/api/fishing/trips/{trip_id}/catches", json=extra)
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---------------------------------------------------------------- the species list and the rules check

def test_species_are_seeded_with_names_only(client):
    sp = client.get("/api/fishing/species").json()
    assert len(sp) == 23 and species(client, "Snapper")["sci_name"] == "Chrysophrys auratus"
    assert all(s["min_cm"] is None and s["max_cm"] is None and s["bag"] is None and not s["no_take"] for s in sp)
    assert all(s["caught"] == 0 and s["best_cm"] is None and s["last_on"] is None for s in sp)


def test_closed_season_wraps_over_new_year():
    assert in_closed_season(date(2026, 8, 20), "08-01", "09-14") and not in_closed_season(date(2026, 9, 15), "08-01", "09-14")
    assert in_closed_season(date(2026, 12, 25), "11-01", "02-15") and in_closed_season(date(2027, 2, 15), "11-01", "02-15")
    assert in_closed_season(date(2027, 1, 1), "11-01", "02-15") and not in_closed_season(date(2026, 6, 1), "11-01", "02-15")
    assert not in_closed_season(date(2026, 6, 1), None, None)


def test_a_kept_fish_is_checked_against_the_rules_you_typed(client):
    snapper = species(client, "Snapper")
    r = client.patch(f"/api/fishing/species/{snapper['species_id']}",
                     json={"min_cm": 35, "max_cm": 70, "bag": 2, "rules_checked_on": "2026-11-01"})
    assert r.status_code == 200 and r.json()["min_cm"] == 35 and r.json()["rules_checked_on"] == "2026-11-01"
    t = trip(client)["trip_id"]
    sid = snapper["species_id"]
    ok = catch(client, t, species_id=sid, length_cm=50, fate="kept")
    assert ok["warnings"] == [] and ok["species_name"] == "Snapper"
    small = catch(client, t, species_id=sid, length_cm=30, fate="kept")
    assert len(small["warnings"]) == 1 and "30 cm is under the 35 cm minimum" in small["warnings"][0]
    assert "as you typed it on 2026-11-01" in small["warnings"][0] and "check the official rules" in small["warnings"][0]
    big = catch(client, t, species_id=sid, length_cm=75.5, fate="kept")                 # the third kept: over the bag too
    assert any("over the 70 cm maximum" in w for w in big["warnings"]) and any("possession limit is 2" in w for w in big["warnings"])
    # released fish are never checked; a fish with no length isn't checked for size
    assert catch(client, t, species_id=sid, length_cm=10, fate="released")["warnings"] == []
    assert catch(client, t, species_id=sid, fate="died")["warnings"] != []                # died counts: bag
    # the trip shows each catch's warnings, and changing a catch's fate checks it again
    full = client.get(f"/api/fishing/trips/{t}").json()
    assert [bool(c["warnings"]) for c in full["catches"]] == [False, True, True, False, True]
    fixed = client.patch(f"/api/fishing/catches/{small['catch_id']}", json={"fate": "released"}).json()
    assert fixed["warnings"] == []
    # a species with no rules says nothing
    assert catch(client, t, species="Pike", length_cm=5, fate="kept")["warnings"] == []
    assert catch(client, t, species_id=species(client, "Tailor")["species_id"], length_cm=5, fate="kept")["warnings"] == []


def test_no_take_and_closed_season_and_no_check_date(client):
    tailor = species(client, "Tailor")["species_id"]
    client.patch(f"/api/fishing/species/{tailor}", json={"no_take": True})
    mulloway = species(client, "Mulloway")["species_id"]
    client.patch(f"/api/fishing/species/{mulloway}", json={"closed_from": "05-01", "closed_to": "08-31"})
    t = trip(client)["trip_id"]                                                      # 2 May: inside
    w = catch(client, t, species_id=tailor, length_cm=40, fate="kept")["warnings"]
    assert len(w) == 1 and "marked no-take" in w[0] and "(no check date)" in w[0]
    w = catch(client, t, species_id=mulloway, length_cm=90, fate="kept")["warnings"]
    assert len(w) == 1 and "closed season (05-01 to 08-31" in w[0]
    t2 = trip(client, "2026-10-02T06:00:00+10:00", "2026-10-02T09:00:00+10:00")["trip_id"]
    assert catch(client, t2, species_id=mulloway, length_cm=90, fate="kept")["warnings"] == []


def test_the_bag_counts_the_day_only(client):
    bream = species(client, "Yellowfin bream")["species_id"]
    client.patch(f"/api/fishing/species/{bream}", json={"bag": 1})
    a, b = trip(client)["trip_id"], trip(client, "2026-05-03T06:00:00+10:00", "2026-05-03T09:00:00+10:00")["trip_id"]
    assert catch(client, a, species_id=bream, fate="kept")["warnings"] == []
    assert catch(client, b, species_id=bream, fate="kept")["warnings"] == []             # another day
    assert len(catch(client, a, species_id=bream, fate="kept")["warnings"]) == 1        # the second that day


def test_species_rules_are_validated(client):
    s = species(client, "Snapper")["species_id"]
    assert client.patch(f"/api/fishing/species/{s}", json={"min_cm": 50, "max_cm": 40}).status_code == 422
    assert client.patch(f"/api/fishing/species/{s}", json={"closed_from": "13-01", "closed_to": "02-01"}).status_code == 422
    assert client.patch(f"/api/fishing/species/{s}", json={"closed_from": "11-01"}).status_code == 422   # needs both
    assert client.patch(f"/api/fishing/species/{s}", json={"name": None}).status_code == 422
    assert client.patch(f"/api/fishing/species/{s}", json={"closed_from": "11-01", "closed_to": "02-15"}).status_code == 200


def test_species_add_rename_delete(client):
    r = client.post("/api/fishing/species", json={"name": " Pike ", "water": "fresh"})
    assert r.status_code == 201 and r.json()["name"] == "Pike" and r.json()["caught"] == 0
    assert client.post("/api/fishing/species", json={"name": "Pike"}).status_code == 409
    sid = r.json()["species_id"]
    t = trip(client)["trip_id"]
    catch(client, t, species_id=sid, length_cm=40)
    gone = client.delete(f"/api/fishing/species/{sid}")
    assert gone.status_code == 409 and "1 of your catches" in gone.json()["detail"]
    other = client.post("/api/fishing/species", json={"name": "Carp"}).json()["species_id"]
    assert client.delete(f"/api/fishing/species/{other}").status_code == 204
    assert client.delete(f"/api/fishing/species/{other}").status_code == 404
    row = species(client, "Pike")
    assert row["caught"] == 1 and row["best_cm"] == 40 and row["last_on"] == "2026-05-02"


# ---------------------------------------------------------------- trips and catches

def test_a_trip_in_full(client):
    spot = client.post("/api/fishing/spots", json={"name": "Wynnum jetty", "water": "salt", "lat": -27.46, "lon": 153.17}).json()["spot_id"]
    lure = client.post("/api/fishing/lures", json={"name": "Zerek Prawn 3.5", "kind": "soft plastic"}).json()["lure_id"]
    t = trip(client, spot_id=spot, platform="jetty", target="Flathead", companions="Sam", rating=4, notes="Windy")
    assert t["spot_name"] == "Wynnum jetty" and t["hours"] == 4.0 and t["catches"] == [] and t["fish_per_hour"] == 0
    assert t["conditions"] is None and t["prev_id"] is None and t["next_id"] is None
    fl = species(client, "Dusky flathead")["species_id"]
    c = catch(client, t["trip_id"], species_id=fl, length_cm=62.5, weight_kg=2.1, fate="released", lure_id=lure, method="Casting",
              depth_m=3, lat=-27.46, lon=153.17, caught_at="2026-05-02T07:30:00+10:00")
    assert c["species_name"] == "Dusky flathead" and c["lure_name"] == "Zerek Prawn 3.5" and c["length_cm"] == 62.5
    assert c["warnings"] == [] and c["catch"]["catch_id"] == c["catch_id"] and "warnings" not in c["catch"]
    catch(client, t["trip_id"], species="Mystery fish", bait="Live yabby")
    full = client.get(f"/api/fishing/trips/{t['trip_id']}").json()
    assert full["fish_per_hour"] == 0.5 and [x["species_name"] for x in full["catches"]] == ["Mystery fish", "Dusky flathead"]
    assert next(x for x in full["catches"] if x["species"] == "Mystery fish")["lure_name"] == "Live yabby"
    # the list brief
    brief = client.get("/api/fishing/trips").json()[0]
    assert brief["catches"] == 2 and brief["kept"] == 0 and brief["hours"] == 4.0 and brief["spot_name"] == "Wynnum jetty"
    assert brief["species"] == ["Dusky flathead", "Mystery fish"] and brief["best"] == {"species": "Dusky flathead", "length_cm": 62.5}
    # edit, previous / next
    assert client.patch(f"/api/fishing/trips/{t['trip_id']}", json={"rating": 5, "target": None}).json()["rating"] == 5
    later = trip(client, "2026-06-01T06:00:00+10:00", "2026-06-01T08:00:00+10:00")
    assert client.get(f"/api/fishing/trips/{later['trip_id']}").json()["prev_id"] == t["trip_id"]
    assert client.get(f"/api/fishing/trips/{t['trip_id']}").json()["next_id"] == later["trip_id"]
    # deleting the trip takes its catches; deleting a spot keeps the trip
    assert client.delete(f"/api/fishing/spots/{spot}").status_code == 204
    kept = client.get(f"/api/fishing/trips/{t['trip_id']}").json()
    assert kept["spot_id"] is None and kept["spot_name"] is None
    assert client.delete(f"/api/fishing/trips/{t['trip_id']}").status_code == 204
    assert client.get(f"/api/fishing/trips/{t['trip_id']}").status_code == 404
    assert client.delete(f"/api/fishing/catches/{c['catch_id']}").status_code == 404


def test_a_trip_and_a_catch_are_checked(client):
    assert client.post("/api/fishing/trips", json={"started_at": "2026-05-02T10:00:00+10:00", "ended_at": "2026-05-02T08:00:00+10:00"}).status_code == 422
    assert client.post("/api/fishing/trips", json={"platform": "submarine"}).status_code == 422
    assert client.post("/api/fishing/trips", json={"spot_id": 999}).status_code == 404
    assert client.post("/api/fishing/trips", json={"rating": 9}).status_code == 422
    assert client.patch("/api/fishing/trips/1", json={"started_at": None}).status_code in (404, 422)
    t = trip(client)["trip_id"]
    assert client.patch(f"/api/fishing/trips/{t}", json={"started_at": None}).status_code == 422
    url = f"/api/fishing/trips/{t}/catches"
    assert client.post(url, json={}).status_code == 422                                  # what did you catch?
    assert client.post(url, json={"species": "  "}).status_code == 422
    assert client.post(url, json={"species_id": 9999}).status_code == 404
    assert client.post(url, json={"species": "Bream", "lure_id": 9999}).status_code == 404
    assert client.post(url, json={"species": "Bream", "length_cm": -1}).status_code == 422
    assert client.post(url, json={"species": "Bream", "fate": "eaten"}).status_code == 422
    assert client.post("/api/fishing/trips/9999/catches", json={"species": "Bream"}).status_code == 404
    c = catch(client, t, species="Bream")
    assert c["fate"] == "released"
    assert client.patch(f"/api/fishing/catches/{c['catch_id']}", json={"species": None}).status_code == 422
    assert client.patch(f"/api/fishing/catches/{c['catch_id']}", json={"fate": None}).status_code == 422


def test_starting_and_ending_a_trip_on_the_water(client):
    t = client.post("/api/fishing/trips", json={"platform": "kayak"}).json()
    assert t["ended_at"] is None and t["started_at"] and t["hours"] is None
    summary = client.get("/api/fishing/summary").json()
    assert summary["open_trip"]["trip_id"] == t["trip_id"]
    ended = client.post(f"/api/fishing/trips/{t['trip_id']}/end").json()
    assert ended["ended_at"] is not None
    assert client.get("/api/fishing/summary").json()["open_trip"] is None
    again = client.post(f"/api/fishing/trips/{t['trip_id']}/end", json={"ended_at": "2099-01-01T00:00:00+10:00"}).json()
    assert again["ended_at"].startswith("2098-12-31") or again["ended_at"].startswith("2099-01-01")
    assert client.post(f"/api/fishing/trips/{t['trip_id']}/end", json={"ended_at": "2000-01-01T00:00:00+10:00"}).status_code == 422
    assert client.post("/api/fishing/trips/999/end").status_code == 404


def test_a_catch_sent_twice_is_one_catch(client):
    t = trip(client)["trip_id"]
    url = f"/api/fishing/trips/{t}/catches"
    first = client.post(url, json={"species": "Bream", "length_cm": 30, "client_key": "phone-1"})
    again = client.post(url, json={"species": "Bream", "length_cm": 30, "client_key": "phone-1"})
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["catch_id"] == again.json()["catch_id"]
    assert len(client.get(f"/api/fishing/trips/{t}").json()["catches"]) == 1


def test_a_trip_sent_twice_is_one_trip(client):
    body = {"platform": "kayak", "client_key": "trip-1"}
    first, again = client.post("/api/fishing/trips", json=body), client.post("/api/fishing/trips", json=body)
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["trip_id"] == again.json()["trip_id"] and again.json()["client_key"] == "trip-1"
    assert len(client.get("/api/fishing/trips").json()) == 1
    assert client.post("/api/fishing/trips", json={"client_key": ""}).status_code == 422


def test_the_conditions_snapshot(client, monkeypatch):
    calls = []
    def fake(conn, spot_id, started_at):
        if spot_id is None:
            return None
        calls.append((spot_id, started_at))
        return {"moon_phase": "Full moon", "moon_pct": 99}
    monkeypatch.setattr(fishing_trips, "snapshot_for", fake)
    spot = client.post("/api/fishing/spots", json={"name": "Wynnum", "lat": -27.4, "lon": 153.1}).json()["spot_id"]
    t = trip(client, spot_id=spot)
    assert t["conditions"] == {"moon_phase": "Full moon", "moon_pct": 99} and len(calls) == 1
    client.patch(f"/api/fishing/trips/{t['trip_id']}", json={"notes": "x"})              # already has them: not asked again
    assert len(calls) == 1
    typed = trip(client, spot_id=spot, conditions={"moon_phase": "New moon"})
    assert typed["conditions"] == {"moon_phase": "New moon"}
    # a trip with a spot added later gets them
    plain = trip(client)
    assert plain["conditions"] is None
    got = client.patch(f"/api/fishing/trips/{plain['trip_id']}", json={"spot_id": spot}).json()
    assert got["conditions"]["moon_phase"] == "Full moon"


def test_a_failing_snapshot_never_stops_a_trip(client, monkeypatch):
    monkeypatch.undo()                                            # the real snapshot_for, with the tools raising
    from app import fishing_tools

    def boom(*_a):
        raise RuntimeError("the weather is down")
    monkeypatch.setattr(fishing_tools, "snapshot", boom)
    spot = client.post("/api/fishing/spots", json={"name": "Wynnum", "lat": -27.4, "lon": 153.1}).json()["spot_id"]
    t = trip(client, spot_id=spot)
    assert t["conditions"] is None
    # and the real one answers for a past day (the solunar part only: no outside site)
    monkeypatch.undo()
    t = trip(client, "2026-05-02T06:00:00+10:00", "2026-05-02T08:00:00+10:00", spot_id=spot)
    assert t["conditions"] is None or "moon_phase" in t["conditions"]


def test_trip_list_filters(client):
    s1 = client.post("/api/fishing/spots", json={"name": "Wynnum jetty"}).json()["spot_id"]
    s2 = client.post("/api/fishing/spots", json={"name": "Lake Somerset"}).json()["spot_id"]
    a = trip(client, spot_id=s1, target="bream")["trip_id"]
    b = trip(client, "2025-03-01T06:00:00+10:00", "2025-03-01T08:00:00+10:00", spot_id=s2, notes="100% great_day")["trip_id"]
    catch(client, b, species_id=species(client, "Golden perch")["species_id"])
    ids = lambda **p: [x["trip_id"] for x in client.get("/api/fishing/trips", params=p).json()]    # noqa: E731
    assert ids() == [a, b] and ids(spot_id=s2) == [b] and ids(year=2025) == [b] and ids(year=2026) == [a]
    assert ids(q="jetty") == [a] and ids(q="golden") == [b] and ids(q="bream") == [a] and ids(q="100%") == [b]
    assert ids(q="50%") == []
    assert client.get("/api/fishing/trips", params={"q": "x" * 101}).status_code == 422
    assert client.get("/api/fishing/trips", params={"year": "abc"}).status_code == 422


# ---------------------------------------------------------------- photos

def test_catch_photos(client):
    t = trip(client)["trip_id"]
    c = catch(client, t, species="Bream")["catch_id"]
    h = {"Content-Type": "image/jpeg"}
    p = client.post(f"/api/fishing/catches/{c}/photos", content=JPEG, headers=h)
    assert p.status_code == 201 and p.json()["url"] == f"/api/fishing/photos/{p.json()['photo_id']}"
    img = client.get(p.json()["url"])
    assert img.status_code == 200 and img.content == JPEG and "max-age=31536000" in img.headers["cache-control"]
    assert client.post(f"/api/fishing/catches/{c}/photos", content=b"x", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.post(f"/api/fishing/catches/{c}/photos", content=b"", headers=h).status_code == 422
    assert client.post("/api/fishing/catches/999/photos", content=JPEG, headers=h).status_code == 404
    shown = client.get(f"/api/fishing/trips/{t}").json()["catches"][0]["photos"]
    assert shown == [{"photo_id": p.json()["photo_id"], "url": p.json()["url"]}]
    assert client.delete(f"/api/fishing/photos/{p.json()['photo_id']}").status_code == 204
    assert client.get(p.json()["url"]).status_code == 404 and client.delete(p.json()["url"]).status_code == 404
    q = client.post(f"/api/fishing/catches/{c}/photos", content=JPEG, headers=h).json()
    client.delete(f"/api/fishing/catches/{c}")                                               # the photo goes with its catch
    assert client.get(q["url"]).status_code == 404


# ---------------------------------------------------------------- spots, lures, settings

def test_spots(client):
    s = client.post("/api/fishing/spots", json={"name": " Wynnum jetty ", "water": "salt", "kind": "Jetty", "lat": -27.46, "lon": 153.17}).json()
    assert s["name"] == "Wynnum jetty" and s["trips"] == 0 and s["fish_per_hour"] is None and s["trip_list"] == []
    t = trip(client, spot_id=s["spot_id"])["trip_id"]                                            # 4 hours
    for sp in ("Snapper", "Snapper", "Tailor"):
        catch(client, t, species_id=species(client, sp)["species_id"])
    catch(client, t, species="Pike")
    got = client.get(f"/api/fishing/spots/{s['spot_id']}").json()
    assert got["trips"] == 1 and got["catches"] == 4 and got["fish_per_hour"] == 1.0 and got["last_on"] == "2026-05-02"
    assert [(x["species"], x["catches"]) for x in got["species_caught"]] == [("Snapper", 2), ("Pike", 1), ("Tailor", 1)]
    assert got["trip_list"][0]["trip_id"] == t
    assert client.get("/api/fishing/spots").json()[0]["catches"] == 4
    assert client.patch(f"/api/fishing/spots/{s['spot_id']}", json={"name": None}).status_code == 422
    assert client.patch(f"/api/fishing/spots/{s['spot_id']}", json={"water": "lava"}).status_code == 422
    assert client.patch(f"/api/fishing/spots/{s['spot_id']}", json={"lat": 91}).status_code == 422
    assert client.patch(f"/api/fishing/spots/{s['spot_id']}", json={"sip_needed": True, "place": "Moreton Bay"}).json()["sip_needed"] is True
    assert client.post("/api/fishing/spots", json={"name": ""}).status_code == 422
    assert client.get("/api/fishing/spots/999").status_code == 404 and client.delete("/api/fishing/spots/999").status_code == 404


def test_lures(client):
    a = client.post("/api/fishing/lures", json={"name": "Zerek Prawn", "kind": "soft plastic", "qty": 3}).json()
    b = client.post("/api/fishing/lures", json={"name": "Pilchard", "kind": "bait"}).json()
    t = trip(client)["trip_id"]
    catch(client, t, species_id=species(client, "Snapper")["species_id"], lure_id=a["lure_id"])
    catch(client, t, species="Pike", lure_id=a["lure_id"])
    row = [x for x in client.get("/api/fishing/lures").json() if x["lure_id"] == a["lure_id"]][0]
    assert row["catches"] == 2 and row["species"] == ["Pike", "Snapper"]
    client.patch(f"/api/fishing/lures/{b['lure_id']}", json={"retired": True})
    assert [x["name"] for x in client.get("/api/fishing/lures", params={"retired": "true"}).json()] == ["Pilchard"]
    assert [x["name"] for x in client.get("/api/fishing/lures", params={"retired": "false"}).json()] == ["Zerek Prawn"]
    assert len(client.get("/api/fishing/lures").json()) == 2
    assert client.patch(f"/api/fishing/lures/{a['lure_id']}", json={"kind": "spaceship"}).status_code == 422
    assert client.patch(f"/api/fishing/lures/{a['lure_id']}", json={"name": None}).status_code == 422
    assert client.delete(f"/api/fishing/lures/{a['lure_id']}").status_code == 204        # its catches keep their record
    assert client.get(f"/api/fishing/trips/{t}").json()["catches"][0]["lure_id"] is None
    assert client.delete(f"/api/fishing/lures/{a['lure_id']}").status_code == 404


def test_settings(client):
    s = client.get("/api/fishing/settings").json()
    assert s["id"] == 1 and s["rules_url"].startswith("https://www.qld.gov.au/") and s["sip_until"] is None
    r = client.put("/api/fishing/settings", json={"sip_until": "2027-01-31", "home_lat": -27.47, "home_lon": 153.02}).json()
    assert r["sip_until"] == "2027-01-31" and r["home_lat"] == -27.47
    assert client.put("/api/fishing/settings", json={"rules_url": "ftp://x"}).status_code == 422
    assert client.put("/api/fishing/settings", json={"home_lat": 100}).status_code == 422
    assert client.put("/api/fishing/settings", json={"rules_url": "https://example.org/rules"}).json()["rules_url"] == "https://example.org/rules"
    assert client.put("/api/fishing/settings", json={"rules_url": " "}).json()["rules_url"].startswith("https://www.qld.gov.au/")
    assert client.put("/api/fishing/settings", json={"sip_until": None}).json()["sip_until"] is None


# ---------------------------------------------------------------- the summary

def test_the_summary_when_empty(client):
    s = client.get("/api/fishing/summary").json()
    assert (s["trips"], s["catches"], s["species"], s["hours"]) == (0, 0, 0, 0) and s["last_trip"] is None and s["open_trip"] is None
    assert s["personal_bests"] == [] and s["alerts"] == [] and s["recent"] == [] and s["this_year"] == {"trips": 0, "catches": 0}


def test_the_summary(client):
    t = trip(client, "2025-05-02T06:00:00+10:00", "2025-05-02T10:00:00+10:00")["trip_id"]       # 4 h, last year
    snapper, tailor = species(client, "Snapper")["species_id"], species(client, "Tailor")["species_id"]
    catch(client, t, species_id=snapper, length_cm=40, weight_kg=1.2, fate="released")
    best = catch(client, t, species_id=snapper, length_cm=55)
    catch(client, t, species_id=tailor, length_cm=30)
    catch(client, t, species="Pike")
    now = datetime.now().astimezone().isoformat()
    t2 = trip(client, now, now)["trip_id"]
    catch(client, t2, species_id=tailor, length_cm=35)
    s = client.get("/api/fishing/summary").json()
    assert (s["trips"], s["catches"], s["species"], s["hours"]) == (2, 5, 3, 4.0)
    assert s["this_year"] == {"trips": 1, "catches": 1} and s["last_trip"]["trip_id"] == t2 and len(s["recent"]) == 2
    pbs = s["personal_bests"]
    assert [(p["species"], p["length_cm"]) for p in pbs] == [("Snapper", 55), ("Tailor", 35)]      # best of each species
    assert pbs[0]["catch_id"] == best["catch_id"] and pbs[0]["caught_at"] and pbs[0]["trip_id"] == t


def test_alerts(client):
    day = today()
    client.put("/api/fishing/settings", json={"sip_until": str(day + timedelta(days=30)), "boat_rego_until": str(day - timedelta(days=3))})
    kinds = {a["kind"]: a for a in client.get("/api/fishing/summary").json()["alerts"]}
    assert kinds["boat_rego"]["text"] == "Boat registration is overdue by 3 days"
    assert kinds["sip"]["text"] == "Stocked Impoundment Permit is due in 30 days" and "rules" not in kinds
    assert [a["kind"] for a in client.get("/api/fishing/summary").json()["alerts"]] == ["boat_rego", "sip"]    # soonest first
    client.put("/api/fishing/settings", json={"sip_until": str(day + timedelta(days=61)), "boat_rego_until": None})
    assert client.get("/api/fishing/summary").json()["alerts"] == []
    # rules: only for species you've KEPT, with no check date or an old one
    t = trip(client)["trip_id"]
    snapper = species(client, "Snapper")["species_id"]
    catch(client, t, species_id=snapper, fate="released")
    assert client.get("/api/fishing/summary").json()["alerts"] == []
    catch(client, t, species_id=snapper, fate="kept")
    a = client.get("/api/fishing/summary").json()["alerts"]
    assert [x["kind"] for x in a] == ["rules"] and "Snapper" in a[0]["text"] and a[0]["due"] == str(day)
    client.patch(f"/api/fishing/species/{snapper}", json={"rules_checked_on": str(day - timedelta(days=100))})
    assert client.get("/api/fishing/summary").json()["alerts"] == []
    client.patch(f"/api/fishing/species/{snapper}", json={"rules_checked_on": str(day - timedelta(days=400))})
    assert [x["kind"] for x in client.get("/api/fishing/summary").json()["alerts"]] == ["rules"]


# ---------------------------------------------------------------- the stats

def test_tide_stage():
    tides = [{"time": "2026-05-02T05:00", "height": 0.3, "kind": "low"}, {"time": "2026-05-02T11:10", "height": 1.8, "kind": "high"},
             {"time": "2026-05-02T17:20", "height": 0.4, "kind": "low"}]
    at = lambda h, m=0: datetime(2026, 5, 2, h, m)       # noqa: E731
    assert tide_stage(tides, at(5, 20)) == "low" and tide_stage(tides, at(11, 40)) == "high"
    assert tide_stage(tides, at(8)) == "rising" and tide_stage(tides, at(14)) == "falling"
    assert tide_stage(tides, at(3)) == "falling"             # before the first low: heading down to it
    assert tide_stage(tides, at(22)) == "rising"             # after the last low: coming back up
    assert tide_stage(tides, datetime(2026, 5, 4, 12)) is None and tide_stage([], at(8)) is None and tide_stage(None, at(8)) is None
    aware = [{"time": "2026-05-02T05:00:00+10:00", "kind": "low"}, {"time": "2026-05-01T21:10:00+00:00", "kind": "high"}]
    assert tide_stage(aware, at(8)) == "falling"             # 21:10 UTC is 07:10 in Brisbane: the high is behind us
    assert tide_stage([{"time": "junk", "kind": "high"}, "x", {"kind": "low"}], at(8)) is None


def test_stats_when_empty(client):
    s = client.get("/api/fishing/stats").json()
    assert s["totals"] == {"trips": 0, "catches": 0, "kept": 0, "released": 0, "hours": 0, "blanks": 0}
    assert len(s["by_month"]) == 24 and s["by_hour"] == [0] * 24 and len(s["by_moon"]) == 8
    assert s["by_species"] == [] and s["seasons"] == [] and s["length_trend"] == [] and s["top_spots"] == []
    assert [x["stage"] for x in s["by_tide"]] == ["rising", "high", "falling", "low"]


def test_stats(client):
    spot = client.post("/api/fishing/spots", json={"name": "Wynnum jetty"}).json()["spot_id"]
    lure = client.post("/api/fishing/lures", json={"name": "Zerek"}).json()["lure_id"]
    snapper, tailor = species(client, "Snapper")["species_id"], species(client, "Tailor")["species_id"]
    tides = [{"time": "2026-05-02T05:00", "kind": "low"}, {"time": "2026-05-02T11:10", "kind": "high"}]
    a = trip(client, spot_id=spot, conditions={"moon_phase": "Full moon", "tide": tides})["trip_id"]       # 06:00-10:00 (4 h)
    catch(client, a, species_id=snapper, length_cm=40, fate="kept", lure_id=lure, caught_at="2026-05-02T07:15:00+10:00")   # rising
    catch(client, a, species_id=snapper, length_cm=50, fate="released", lure_id=lure, caught_at="2026-05-02T11:00:00+10:00")   # high
    catch(client, a, species_id=tailor, length_cm=30)                                                # 06:00 (the trip's start)
    b = trip(client, "2025-12-10T05:00:00+10:00", "2025-12-10T07:00:00+10:00", conditions={"moon_phase": "New moon"})["trip_id"]
    catch(client, b, species_id=snapper, length_cm=45, fate="tagged")
    trip(client, "2026-01-05T05:00:00+10:00", "2026-01-05T06:00:00+10:00")                            # a blank
    s = client.get("/api/fishing/stats").json()
    assert s["totals"] == {"trips": 3, "catches": 4, "kept": 1, "released": 3, "hours": 7.0, "blanks": 1}
    assert [(x["species"], x["catches"], x["kept"], x["best_cm"], x["avg_cm"]) for x in s["by_species"]] == \
        [("Snapper", 3, 1, 50, 45), ("Tailor", 1, 0, 30, 30)]
    assert s["seasons"][0] == {"species": "Snapper", "months": [0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 1]}
    assert s["by_hour"][7] == 1 and s["by_hour"][11] == 1 and s["by_hour"][6] == 1 and s["by_hour"][5] == 1 and sum(s["by_hour"]) == 4
    moon = {x["phase"]: x for x in s["by_moon"]}
    assert moon["Full moon"] == {"phase": "Full moon", "catches": 3, "trips": 1} and moon["New moon"]["catches"] == 1
    assert [x["phase"] for x in s["by_moon"]][0] == "New moon" and len(s["by_moon"]) == 8
    assert {x["stage"]: x["catches"] for x in s["by_tide"]} == {"rising": 2, "high": 1, "falling": 0, "low": 0}   # 07:15 and 06:00 rising, 11:00 high
    assert [(x["name"], x["catches"]) for x in s["top_lures"]] == [("Zerek", 2)]
    assert s["top_spots"] == [{"spot_id": spot, "name": "Wynnum jetty", "catches": 3, "fish_per_hour": 0.75}]
    assert sum(m["catches"] for m in s["by_month"]) == 4 and s["length_trend"] == []
    # one year, and a species' length trend
    y = client.get("/api/fishing/stats", params={"year": 2026, "species_id": snapper}).json()
    assert y["totals"]["trips"] == 2 and y["totals"]["catches"] == 3 and y["totals"]["blanks"] == 1
    assert [x["length_cm"] for x in y["length_trend"]] == [40, 50] and y["length_trend"][0]["species"] == "Snapper"
    assert len(y["by_month"]) == 24
    assert client.get("/api/fishing/stats", params={"year": "x"}).status_code == 422
    assert client.get("/api/fishing/stats", params={"species_id": 99999}).json()["length_trend"] == []


# ---------------------------------------------------------------- what other pages show

def test_activity_goals_calendar_and_exports(client):
    spot = client.post("/api/fishing/spots", json={"name": "Wynnum jetty", "place": "Moreton Bay"}).json()["spot_id"]
    now = datetime.now().astimezone()
    t = trip(client, now.isoformat(), (now + timedelta(hours=3)).isoformat(), spot_id=spot, platform="jetty", companions='Sam, "Jo"',
             conditions={"moon_phase": "Full moon", "wind_kmh": 12, "pressure_hpa": 1015, "sst": 23})["trip_id"]
    flat = species(client, "Dusky flathead")["species_id"]
    catch(client, t, species_id=flat, length_cm=55.5, fate="kept", bait="=cmd", caught_at=now.isoformat())
    catch(client, t, species_id=species(client, "Snapper")["species_id"], length_cm=44)
    trip(client, now.isoformat(), None)
    feed = [a for a in client.get("/api/activity").json() if a["kind"] == "fishtrip"]
    assert len(feed) == 2
    mine = [a for a in feed if a["ref"] == t][0]
    assert mine["title"] == "Wynnum jetty" and mine["verb"] == "Fished" and "2 caught" in mine["detail"] and "3 h" in mine["detail"]
    assert any(a["title"] == "Fishing trip" for a in feed)
    # goals
    assert {"fishing_trips", "fishing_catches", "fishing_species"} <= set(goal_sources.SOURCES)
    for key, want in (("fishing_trips", 2), ("fishing_catches", 2), ("fishing_species", 2)):
        g = client.post("/api/goals", json={"title": key, "timeframe": "year", "source": key, "target_value": 50}).json()
        assert g["hobby"] == "fishing" and g["current_value"] == want, key
    # calendar: the hobby is known, a trip counts as done, and "fishing" in a quick add finds it
    e = client.post("/api/calendar/events", json={"title": "Fishing at Wynnum", "hobby": "fishing", "starts_on": str(today())})
    assert e.status_code == 201 and e.json()["hobby"] == "fishing"
    from app import journal_more
    assert journal_more.HOBBY["fishtrip"] == "Fishing"
    # exports
    csv = client.get("/api/export/fishing-trips.csv").text
    assert csv.lstrip("﻿").startswith("Date,Start,End,Hours,Spot,Place,Platform") and "Wynnum jetty,Moreton Bay,jetty" in csv
    assert '"Sam, ""Jo"""' in csv and ",Full moon,12,1015,23," in csv
    fish = client.get("/api/export/fishing-catches.csv").text
    assert fish.lstrip("﻿").startswith("Date,Time,Species,Length (cm)") and "Dusky flathead,55.5" in fish and "'=cmd" in fish


def test_the_routes_never_crash(client):
    for path in ("/api/fishing/trips/0", "/api/fishing/spots/0", "/api/fishing/photos/0"):
        assert client.get(path).status_code == 404
    assert client.patch("/api/fishing/catches/0", json={"fate": "kept"}).status_code == 404
    assert client.patch("/api/fishing/species/0", json={}).status_code == 404
    assert client.patch("/api/fishing/lures/0", json={}).status_code == 404
    assert client.get("/api/fishing/trips/99999999999").status_code in (404, 422)
    assert client.get("/api/fishing/trips", params={"spot_id": 99999999999}).status_code in (200, 422)
    assert client.post("/api/fishing/trips/1/catches", json={"species": "x", "caught_at": "not a time"}).status_code == 422
