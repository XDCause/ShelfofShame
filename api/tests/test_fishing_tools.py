"""Fishing tools: the forecast (Open-Meteo, faked with the walk-through's made-up answers), one day's solunar times, the
snapshot a trip keeps, and boat ramps / fishing spots from OpenStreetMap (faked the same way)."""
from datetime import datetime, timedelta, timezone

import pytest

from app import fishing_tools, openmeteo, overpass, solunar, stand_ins
from app.db import db


@pytest.fixture(autouse=True)
def clean_spots():
    yield
    with db() as conn:
        conn.execute("DELETE FROM fishing_spots")
        conn.execute("UPDATE fishing_settings SET home_lat = NULL, home_lon = NULL WHERE id = 1")


def weather(monkeypatch):
    def get(url, params):
        return (stand_ins.marine_stand_in() if "marine" in url else stand_ins.fishing_stand_in() if "pressure_msl" in params.get("hourly", "")
                else stand_ins.wind_stand_in())
    monkeypatch.setattr(openmeteo, "_get", get)
    openmeteo._cache.clear()


def add_spot(name="Wellington Point", water="salt", lat=-27.47, lon=153.24):
    with db() as conn:
        return conn.execute("INSERT INTO fishing_spots (name, water, lat, lon) VALUES (%s, %s, %s, %s) RETURNING spot_id",
                            (name, water, lat, lon)).fetchone()["spot_id"]


def raising(error):
    def go(*_a, **_k):
        raise error
    return go


# ---------------------------------------------------------------- Open-Meteo's fishing weather

def test_fishing_weather_reads_the_forecast_and_works_out_the_pressure_trend(monkeypatch):
    weather(monkeypatch)
    days = openmeteo.fishing_weather(-27.47, 153.24, fresh=True)
    assert len(days) == 7 and days[0]["day"] == datetime.now().date().isoformat()          # yesterday was only for the trend
    assert set(days[0]) == {"day", "wind_max", "wind_dir", "gusts", "pressure_mean", "pressure_trend", "rain_mm", "temp_max"}
    assert days[0]["wind_max"] == 12 and days[0]["wind_dir"] == 110 and days[0]["gusts"] == 20 and days[0]["pressure_mean"] == 1016.0
    assert [d["pressure_trend"] for d in days] == ["steady", "steady", "falling", "steady", "steady", "rising", "steady"]


def test_fishing_weather_without_pressure_has_no_trend(monkeypatch):
    openmeteo._cache.clear()
    monkeypatch.setattr(openmeteo, "_get", lambda url, params: {"daily": {"time": ["2026-01-10"], "wind_speed_10m_max": [10]}})
    d = openmeteo.fishing_weather(-27.5, 153.4, fresh=True)
    assert d[0]["pressure_mean"] is None and d[0]["pressure_trend"] is None and d[0]["wind_max"] == 10


# ---------------------------------------------------------------- the forecast

def test_forecast_for_a_salt_spot(client, monkeypatch):
    weather(monkeypatch)
    spot = add_spot()
    r = client.get(f"/api/fishing/forecast?spot_id={spot}")
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["place"] == "Wellington Point" and f["water"] == "salt" and len(f["days"]) == 7 and f["notices"] == [] and f["kept_since"] is None
    assert "Open-Meteo" in f["credit"] and "navigation" in f["credit"] and "theory" in f["note"]
    day = f["days"][0]
    assert set(day) >= {"date", "sunrise", "sunset", "moon", "majors", "minors", "rating", "tide", "wind_max", "wind_dir", "gusts",
                        "pressure_mean", "pressure_trend", "rain_mm", "sst", "swell_max", "best", "score", "why"}
    assert set(day["moon"]) >= {"phase", "pct", "rise", "set"} and day["moon"]["phase"] in solunar.PHASES
    assert day["date"] == datetime.now().date().isoformat() and day["wind_max"] == 12 and day["sst"] == 24.5
    assert len(day["tide"]) in (3, 4, 5) and {t["kind"] for t in day["tide"]} <= {"high", "low"}
    assert all(set(t) == {"time", "height", "kind"} for t in day["tide"])
    kinds = [t["kind"] for d in f["days"] for t in d["tide"]]
    assert all(a != b for a, b in zip(kinds, kinds[1:]))                      # highs and lows alternate
    assert 1 <= day["rating"] <= 4 and all(1 <= d["score"] <= 5 and d["why"] for d in f["days"])
    assert f["days"][4]["wind_max"] == 36 and "windy" in f["days"][4]["why"]
    assert f["days"][2]["pressure_trend"] == "falling" and "pressure falling" in f["days"][2]["why"]


def test_forecast_for_a_freshwater_spot_asks_no_sea(client, monkeypatch):
    asked = []

    def get(url, params):
        asked.append(url)
        if "pressure_msl" not in params.get("hourly", ""):
            raise AssertionError(url)
        return stand_ins.fishing_stand_in()
    monkeypatch.setattr(openmeteo, "_get", get)
    openmeteo._cache.clear()
    spot = add_spot("Lake Somerset", "fresh", -27.12, 152.55)
    f = client.get(f"/api/fishing/forecast?spot_id={spot}").json()
    assert asked and all("marine" not in u for u in asked)
    assert all(d["tide"] == [] and d["sst"] is None and d["swell_max"] is None for d in f["days"]) and f["water"] == "fresh"
    assert f["days"][0]["wind_max"] == 12


def test_forecast_best_windows_meet_a_tide_or_dawn_or_dusk(client, monkeypatch):
    weather(monkeypatch)
    f = client.get("/api/fishing/forecast?lat=-27.47&lon=153.24").json()
    assert f["place"] == "-27.47, 153.24" and f["water"] is None and f["days"][0]["tide"]            # unknown water: the sea is asked
    windows = [w for d in f["days"] for w in d["best"]]
    assert windows and all(set(w) == {"start", "end", "why"} and w["start"] < w["end"] for w in windows)
    assert all(("tide" in w["why"] or "dawn" in w["why"] or "dusk" in w["why"]) and w["why"][:5] in ("Major", "Minor") for w in windows)
    assert all(d["best"] == sorted(d["best"], key=lambda w: w["start"]) for d in f["days"])


def test_forecast_without_weather_still_has_the_solunar_part(client, monkeypatch):
    monkeypatch.setattr(openmeteo, "_get", raising(openmeteo.WeatherError("Couldn't reach Open-Meteo (ConnectError).")))
    openmeteo._cache.clear()
    spot = add_spot()
    r = client.get(f"/api/fishing/forecast?spot_id={spot}")
    assert r.status_code == 200
    f = r.json()
    assert len(f["days"]) == 7 and f["days"][0]["majors"] and f["days"][0]["wind_max"] is None and f["days"][0]["tide"] == []
    assert any("No weather" in n for n in f["notices"]) and any("No tide" in n for n in f["notices"])
    assert all(1 <= d["score"] <= 5 for d in f["days"])


def test_forecast_keeps_the_last_good_weather(client, monkeypatch):
    weather(monkeypatch)
    spot = add_spot()
    client.get(f"/api/fishing/forecast?spot_id={spot}")
    openmeteo._cache.clear()                                                  # an hour later, and Open-Meteo is unreachable
    monkeypatch.setattr(openmeteo, "_get", raising(openmeteo.WeatherError("down")))
    f = client.get(f"/api/fishing/forecast?spot_id={spot}").json()
    assert f["kept_since"] and f["days"][0]["wind_max"] == 12 and f["notices"] == []


def test_forecast_refusals(client, monkeypatch):
    weather(monkeypatch)
    assert client.get("/api/fishing/forecast?spot_id=99999").status_code == 404
    assert client.get("/api/fishing/forecast").status_code == 422                       # no spot, no point, no home position
    assert client.get("/api/fishing/forecast?lat=-27").status_code == 422
    assert client.get("/api/fishing/forecast?lat=99&lon=153").status_code == 422
    nowhere = add_spot("Somewhere", "salt", None, None)
    assert client.get(f"/api/fishing/forecast?spot_id={nowhere}").status_code == 422
    with db() as conn:
        conn.execute("UPDATE fishing_settings SET home_lat = -27.47, home_lon = 153.02 WHERE id = 1")
    home = client.get("/api/fishing/forecast")
    assert home.status_code == 200 and home.json()["place"] == "Home"


# ---------------------------------------------------------------- one day's solunar

def test_solunar_for_any_date(client):
    r = client.get("/api/fishing/solunar?lat=-27.47&lon=153.03&date=2026-12-24")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["date"] == "2026-12-24" and d["moon"]["phase"] == "Full moon" and d["rating"] >= 3 and len(d["majors"]) in (1, 2)
    assert d["lat"] == -27.47 and "theory" in d["note"] and d["tz"] == "Australia/Brisbane"
    old = client.get("/api/fishing/solunar?lat=-27.47&lon=153.03&date=1999-07-04")
    assert old.status_code == 200 and old.json()["date"] == "1999-07-04"
    today = client.get("/api/fishing/solunar?lat=-27.47&lon=153.03").json()
    assert today["date"] == datetime.now().date().isoformat()
    assert client.get("/api/fishing/solunar?lat=51.5&lon=-0.12&date=2026-06-21&tz=Europe/London").json()["sunrise"].startswith("2026-06-21T04:")


def test_solunar_refusals(client):
    assert client.get("/api/fishing/solunar").status_code == 422
    assert client.get("/api/fishing/solunar?lat=-27&lon=153&date=nope").status_code == 422
    assert client.get("/api/fishing/solunar?lat=-27&lon=153&date=2026-02-30").status_code == 422
    assert client.get("/api/fishing/solunar?lat=-27&lon=153&date=3000-01-01").status_code == 422
    assert client.get("/api/fishing/solunar?lat=-27&lon=153&tz=Mars/Base").status_code == 422
    assert client.get("/api/fishing/solunar?lat=-27&lon=999").status_code == 422


# ---------------------------------------------------------------- the snapshot

def spot_dict(water="salt"):
    return {"lat": -27.47, "lon": 153.24, "water": water}


def test_snapshot_today_has_the_solunar_weather_and_tide(monkeypatch):
    weather(monkeypatch)
    s = fishing_tools.snapshot(None, spot_dict(), datetime.now(timezone(timedelta(hours=10))))
    assert set(s) == {"moon_phase", "moon_pct", "rating", "sunrise", "sunset", "tide", "wind_kmh", "wind_dir", "pressure_hpa",
                      "pressure_trend", "sst"}
    assert s["wind_kmh"] == 12 and s["wind_dir"] == 110 and s["pressure_hpa"] == 1016.0 and s["sst"] == 24.5 and s["tide"]
    assert s["moon_phase"] in solunar.PHASES and 1 <= s["rating"] <= 4


def test_snapshot_of_a_past_trip_is_only_solunar_and_asks_no_website(monkeypatch):
    monkeypatch.setattr(openmeteo, "_get", raising(AssertionError("asked a website")))
    s = fishing_tools.snapshot(None, spot_dict(), datetime(2025, 3, 1, 5, 30))                 # naive = Brisbane time
    assert set(s) == {"moon_phase", "moon_pct", "rating", "sunrise", "sunset"} and s["sunrise"].startswith("2025-03-01T")
    far = fishing_tools.snapshot(None, spot_dict(), datetime.now() + timedelta(days=20))
    assert "wind_kmh" not in far and "rating" in far


def test_snapshot_never_raises_and_leaves_missing_parts_out(monkeypatch):
    weather(monkeypatch)
    assert fishing_tools.snapshot(None, {"lat": None, "lon": None}, datetime.now()) == {}
    assert fishing_tools.snapshot(None, None, datetime.now()) == {}
    assert fishing_tools.snapshot(None, spot_dict(), "not a time") == {}
    fresh = fishing_tools.snapshot(None, spot_dict("fresh"), datetime.now())
    assert "tide" not in fresh and "sst" not in fresh and fresh["wind_kmh"] == 12
    monkeypatch.setattr(openmeteo, "_get", raising(openmeteo.WeatherError("down")))
    openmeteo._cache.clear()
    down = fishing_tools.snapshot(None, {"lat": -20.0, "lon": 148.0, "water": "salt"}, datetime.now())      # (nothing kept for here)
    assert set(down) == {"moon_phase", "moon_pct", "rating", "sunrise", "sunset"}


# ---------------------------------------------------------------- boat ramps and fishing spots (OpenStreetMap)

def test_osm_near_ramps_and_spots_and_import(client, monkeypatch):
    monkeypatch.setattr(overpass, "_post", stand_ins.fishing_osm)
    ramps = client.get("/api/fishing/osm/near?lat=-27.47&lon=153.02&km=60")
    assert ramps.status_code == 200, ramps.text
    ramps = ramps.json()
    kms = [r["km"] for r in ramps]
    assert kms == sorted(kms)
    assert {r["name"] for r in ramps} == {"Stand-in Boat Ramp", "Stand-in Jetty Ramp"} and all(r["kind"] == "Boat ramp" for r in ramps)
    one = next(r for r in ramps if r["osm"] == "node/990201")
    assert one["lat"] == -27.40 and one["already"] is None and one["km"] > 5 and set(one) >= {"osm", "name", "kind", "lat", "lon", "already"}
    spots = client.get("/api/fishing/osm/near?lat=-27.47&lon=153.02&what=spots").json()
    assert [s["name"] for s in spots] == ["Stand-in Fishing Pier"] and spots[0]["kind"] == "Fishing spot"

    r = client.post("/api/fishing/osm/import", json={"osm": "node/990201"})
    assert r.status_code == 201, r.text
    spot = r.json()
    assert spot["name"] == "Stand-in Boat Ramp" and spot["kind"] == "Boat ramp" and spot["lat"] == -27.40 and spot["osm"] == "node/990201"
    assert spot["existing"] is False and "OpenStreetMap" in spot["notes"]
    again = client.post("/api/fishing/osm/import", json={"osm": "node/990201"})
    assert again.status_code == 200 and again.json()["spot_id"] == spot["spot_id"] and again.json()["existing"] is True
    near = client.get("/api/fishing/osm/near?lat=-27.47&lon=153.02&km=60").json()
    assert next(x for x in near if x["osm"] == "node/990201")["already"] == spot["spot_id"]
    pier = client.post("/api/fishing/osm/import", json={"osm": "node/990203"}).json()
    assert pier["kind"] == "Fishing spot"


def test_osm_unnamed_places_get_their_kind_as_a_name():
    got = fishing_tools.osm_place({"type": "node", "id": 5, "lat": -27.0, "lon": 153.0, "tags": {"leisure": "slipway"}})
    assert got["name"] == "Boat ramp" and got["named"] is False and got["osm"] == "node/5"
    way = fishing_tools.osm_place({"type": "way", "id": 6, "center": {"lat": -27.1, "lon": 153.1},
                                   "tags": {"leisure": "fishing", "name": " Pier ", "addr:suburb": "Manly"}})
    assert way["name"] == "Pier" and way["kind"] == "Fishing spot" and way["place"] == "Manly" and way["lon"] == 153.1
    assert fishing_tools.osm_place({"type": "node", "id": 1, "tags": {}}) is None


def test_osm_refusals(client, monkeypatch):
    assert client.get("/api/fishing/osm/near").status_code == 422
    assert client.get("/api/fishing/osm/near?lat=-27&lon=153&km=500").status_code == 422
    assert client.get("/api/fishing/osm/near?lat=-27&lon=153&what=sharks").status_code == 422
    assert client.post("/api/fishing/osm/import", json={"osm": "somewhere"}).status_code == 422
    monkeypatch.setattr(overpass, "_post", raising(overpass.OverpassError("Couldn't reach OpenStreetMap's Overpass (ConnectError).")))
    r = client.get("/api/fishing/osm/near?lat=-27&lon=153")
    assert r.status_code == 502 and "Overpass" in r.json()["detail"]
    assert client.post("/api/fishing/osm/import", json={"osm": "node/5"}).status_code == 502
    monkeypatch.setattr(overpass, "_post", stand_ins.fishing_osm)
    assert client.post("/api/fishing/osm/import", json={"osm": "node/5"}).status_code == 404


def test_the_walkthrough_stand_in_tells_fishing_from_scuba(monkeypatch):
    seen = []
    monkeypatch.setattr(overpass, "_post", lambda data: seen.append(data) or {"elements": []})
    overpass.fishing_near(-27.0, 153.0, 1000, "ramps")
    overpass.fishing_near(-27.0, 153.0, 1000, "spots")
    assert len(seen) == 2 and all(stand_ins.is_fishing_query(q) for q in seen)
    assert not stand_ins.is_fishing_query('[out:json];nwr["sport"="scuba_diving"](around:1,0,0);out;')
    assert stand_ins.is_fishing_query("[out:json];node(990201);out center tags;")
