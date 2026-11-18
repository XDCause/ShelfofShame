"""Scuba diving tools: the no-stop table, the planner (fresh and repetitive), a logged dive's profile analysis, importing
UDDF / Subsurface files, the sea conditions (Open-Meteo Marine, faked with the walk-through's made-up answers) and dive
sites from OpenStreetMap (faked the same way)."""
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from psycopg.types.json import Jsonb

from app import openmeteo, overpass, scuba_tools, stand_ins
from app.db import db

FIX = Path(__file__).parent / "fixtures"
UDDF = (FIX / "sample.uddf").read_bytes()
SSRF = (FIX / "sample.ssrf").read_bytes()


@pytest.fixture(autouse=True)
def plain_settings():
    """scuba_settings is one row the clean-up may leave alone: put it back after each test."""
    yield
    with db() as conn:
        conn.execute("UPDATE scuba_settings SET gas_o2 = 21, gf_low = 40, gf_high = 85, ppo2_max = 1.4, dives_before = 0 WHERE id = 1")


def upload(client, raw, dry=False, **kw):
    return client.post("/api/scuba/import" + ("?dry=1" if dry else ""), content=raw, headers={"Content-Type": "application/xml"}, **kw)


def seas(monkeypatch):
    monkeypatch.setattr(openmeteo, "_get", lambda url, params: stand_ins.marine_stand_in() if "marine" in url else stand_ins.wind_stand_in())
    openmeteo._cache.clear()


def add_site(**extra):
    with db() as conn:
        return conn.execute("INSERT INTO scuba_sites (name, lat, lon) VALUES (%s, %s, %s) RETURNING site_id",
                            (extra.get("name", "Flinders Reef"), extra.get("lat", -26.97), extra.get("lon", 153.49))).fetchone()["site_id"]


# ---------------------------------------------------------------- the no-stop table and the planner

def test_ndl_table(client):
    r = client.get("/api/scuba/ndl")
    assert r.status_code == 200
    rows = r.json()
    assert [x["depth"] for x in rows] == [9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39]
    assert all(x["ndl"] is not None for x in rows)                         # air's good past 39 m at ppO2 1.4
    assert rows[3]["ndl"] in range(40, 50) and rows[7]["ndl"] in range(9, 16)          # GF 85 from the settings
    assert [x["ndl"] for x in rows] == sorted((x["ndl"] for x in rows), reverse=True)
    rich = client.get("/api/scuba/ndl?gas_o2=32&gf_high=100").json()
    assert rich[7]["ndl"] > rows[7]["ndl"] and rich[8]["ndl"] is not None and rich[9]["ndl"] is None     # EAN32's MOD is 33.75 m
    assert all(x["ndl"] is None for x in client.get("/api/scuba/ndl?gas_o2=100").json())
    assert client.get("/api/scuba/ndl?gas_o2=5").status_code == 422
    assert client.get("/api/scuba/ndl?gf_high=500").status_code == 422


def test_ndl_uses_the_settings_ppo2_limit(client):
    with db() as conn:
        conn.execute("UPDATE scuba_settings SET ppo2_max = 1.2, gas_o2 = 32 WHERE id = 1")
    rows = client.get("/api/scuba/ndl").json()
    assert rows[6]["ndl"] is not None and rows[7]["ndl"] is None          # MOD of EAN32 at 1.2 is 27.5 m: 27 m yes, 30 m no


def test_plan_defaults_come_from_the_settings(client):
    r = client.post("/api/scuba/plan", json={"depth": 18, "minutes": 40})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["gas_o2"] == 21 and p["gf_low"] == 40 and p["gf_high"] == 85 and p["repetitive"] is False
    assert p["stops"] == [] and p["ndl"] in range(40, 50) and p["mod"] == 56.7 and p["ppo2"] == 0.59
    assert p["tts"] == pytest.approx(2.0, abs=0.1) and p["runtime"] == pytest.approx(42.0, abs=0.1)
    assert set(p) >= {"cns", "otu", "gas_l", "gas_bar", "end_bar", "turn_bar", "rock_bottom_bar", "warnings", "note"}
    assert "learning and checking" in p["note"]
    with db() as conn:
        conn.execute("UPDATE scuba_settings SET gas_o2 = 32, gf_high = 100 WHERE id = 1")
    q = client.post("/api/scuba/plan", json={"depth": 18, "minutes": 40}).json()
    assert q["gas_o2"] == 32 and q["gf_high"] == 100 and q["ndl"] > p["ndl"]


def test_plan_with_stops_and_your_own_numbers(client):
    r = client.post("/api/scuba/plan", json={"depth": 30, "minutes": 30, "gas_o2": 32, "gf_low": 30, "gf_high": 70, "sac": 18,
                                              "tank_l": 15, "start_bar": 230})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["stops"] and p["stops"][-1]["depth"] == 3 and p["gas_o2"] == 32 and p["gf_low"] == 30
    assert any("decompression" in w for w in p["warnings"])
    assert p["end_bar"] == 230 - p["gas_bar"]


def test_plan_refuses_nonsense(client):
    assert client.post("/api/scuba/plan", json={"depth": 18}).status_code == 422
    assert client.post("/api/scuba/plan", json={"depth": 0, "minutes": 10}).status_code == 422
    assert client.post("/api/scuba/plan", json={"depth": 18, "minutes": 10, "gas_o2": 10}).status_code == 422
    r = client.post("/api/scuba/plan", json={"depth": 18, "minutes": 10, "gf_low": 90, "gf_high": 50})
    assert r.status_code == 422 and "GF low" in r.json()["detail"]


def log_dive(minutes_ago_start, minutes, depth, o2=21, samples=None):
    """A dive in the logbook that started so long ago (the date and time cross midnight properly)."""
    start = datetime.now() - timedelta(minutes=minutes_ago_start)
    with db() as conn:
        return conn.execute("INSERT INTO scuba_dives (dived_on, time_in, minutes, max_depth, gas_o2, samples) VALUES (%s, %s, %s, %s, %s, %s) RETURNING dive_id",
                            (start.date(), start.time().replace(microsecond=0), minutes, depth, o2,
                             None if samples is None else Jsonb(samples))).fetchone()["dive_id"]


def test_repetitive_plan_starts_from_the_tissues_the_logbook_left(client):
    fresh = client.post("/api/scuba/plan", json={"depth": 24, "minutes": 20, "repetitive": True}).json()
    assert fresh["prior_dives"] == 0 and fresh["start_surface_gf"] == 0 and fresh["ndl"] > 20
    log_dive(100, 40, 24)                                                   # 40 min at 24 m, 1 h 40 min ago (ended an hour ago)
    again = client.post("/api/scuba/plan", json={"depth": 24, "minutes": 20, "repetitive": True}).json()
    assert again["prior_dives"] == 1 and again["start_surface_gf"] > 0
    assert again["ndl"] < fresh["ndl"]
    plain = client.post("/api/scuba/plan", json={"depth": 24, "minutes": 20}).json()
    assert plain["ndl"] == fresh["ndl"] and "prior_dives" not in plain
    # a dive more than a day old counts for nothing
    with db() as conn:
        conn.execute("TRUNCATE scuba_dives CASCADE")
    log_dive(60 * 30, 40, 24)
    old = client.post("/api/scuba/plan", json={"depth": 24, "minutes": 20, "repetitive": True}).json()
    assert old["prior_dives"] == 0 and old["ndl"] == fresh["ndl"]


def test_tissues_now_walks_a_recorded_profile(client):
    samples = [[0, 0.0, None], [70, 20.0, None], [1500, 20.0, None], [1700, 0.0, None]]
    log_dive(60, 28, 20, samples=samples)
    with db() as conn:
        t, n = scuba_tools.tissues_now(conn)
    assert n == 1 and t.n2[5] > scuba_tools.dm.new_tissues().n2[5]


# ---------------------------------------------------------------- import

def test_import_uddf_end_to_end(client):
    r = upload(client, UDDF, dry=True)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["format"] == "uddf" and body["found"] == 1 and body["added"] == 1 and body["skipped"] == 0 and body["dry"] is True
    assert body["dives"][0]["site"] == "Test Reef" and "dive_id" not in body["dives"][0]
    assert client.get("/api/scuba/dives").json() == []                      # a preview saves nothing
    assert client.get("/api/scuba/sites").json() == []

    r = upload(client, UDDF)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["added"] == 1 and got["dives"][0]["dive_id"] and got["dives"][0]["dive_no"] == 1
    dive = client.get(f"/api/scuba/dives/{got['dives'][0]['dive_id']}").json()
    assert dive["dived_on"] == "2026-03-14" and dive["max_depth"] == 21.4 and dive["gas_o2"] == 32 and dive["computer"] == "Test Computer"
    assert dive["site_name"] == "Test Reef" and dive["dive_no"] == 1
    site = client.get("/api/scuba/sites").json()[0]
    assert site["name"] == "Test Reef" and site["lat"] == -27.3 and site["lon"] == 153.45

    again = upload(client, UDDF).json()                                     # the same file again: nothing new
    assert again["added"] == 0 and again["skipped"] == 1 and again["dives"][0]["skipped"] is True
    assert len(client.get("/api/scuba/dives").json()) == 1 and len(client.get("/api/scuba/sites").json()) == 1


def test_import_subsurface_numbers_carry_on_and_sites_are_reused(client):
    with db() as conn:
        conn.execute("UPDATE scuba_settings SET dives_before = 120 WHERE id = 1")
        conn.execute("INSERT INTO scuba_sites (name) VALUES ('made-up WRECK')")          # the same place by name, any case
    got = upload(client, SSRF).json()
    assert got["format"] == "subsurface" and got["added"] == 2
    assert [d["dive_no"] for d in got["dives"]] == [121, 122]               # in date order, after the dives logged before the app
    assert len(client.get("/api/scuba/sites").json()) == 1                  # no second "Made-up Wreck"
    first = client.get(f"/api/scuba/dives/{got['dives'][0]['dive_id']}").json()
    assert first["buddy"] == "Sam" and first["tags"] == ["wreck", "boat"] and first["rating"] == 4 and first["site_name"] == "made-up WRECK"
    uddf = upload(client, UDDF).json()                                      # and another file carries on after those
    assert uddf["dives"][0]["dive_no"] == 123


def test_import_multipart_and_other_inputs(client):
    r = client.post("/api/scuba/import", files={"file": ("dives.ssrf", SSRF, "application/xml")})
    assert r.status_code == 200, r.text
    assert r.json()["added"] == 2
    assert client.post("/api/scuba/import", content=b"", headers={"Content-Type": "application/xml"}).status_code == 422
    r = upload(client, b"<html/>")
    assert r.status_code == 422 and "neither" in r.json()["detail"]
    r = upload(client, b"<!DOCTYPE x [<!ENTITY e 'e'>]><uddf>&e;</uddf>")
    assert r.status_code == 422 and "DOCTYPE" in r.json()["detail"]
    r = upload(client, b"<divelog><dives></dives></divelog>")
    assert r.status_code == 422 and "No dives" in r.json()["detail"]
    assert upload(client, b"\x00\x01 not xml").status_code == 422


# ---------------------------------------------------------------- analysis

def test_analysis_of_a_dive_with_a_safety_stop(client):
    dive_id = upload(client, UDDF).json()["dives"][0]["dive_id"]
    r = client.get(f"/api/scuba/dives/{dive_id}/analysis")
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["profile"][0][:2] == [0, 0.0] and len(a["profile"]) <= 400 and max(p[1] for p in a["profile"]) <= 22
    assert a["safety_stop"]["found"] is True and a["safety_stop"]["seconds"] >= 180
    assert a["ascent_warnings"] == []
    assert a["tissues"][0][0] == 0 and len(a["tissues"]) <= 200 and max(p for _s, p in a["tissues"]) > 30
    assert 0 <= a["surface_gf"] < 100 and a["cns"] > 0 and a["otu"] > 0
    assert 0.9 < a["max_ppo2"] < 1.1                                         # EAN32 at 22 m


def test_analysis_of_a_fast_ascent_and_a_dive_without_a_profile(client):
    ids = [d["dive_id"] for d in upload(client, SSRF).json()["dives"]]
    a = client.get(f"/api/scuba/dives/{ids[0]}/analysis").json()
    assert a["ascent_warnings"] and a["ascent_warnings"][0]["rate"] > 10
    assert a["safety_stop"]["found"] is False and 0.9 < a["max_ppo2"] < 1.1
    r = client.get(f"/api/scuba/dives/{ids[1]}/analysis")
    assert r.status_code == 409 and "no recorded profile" in r.json()["detail"]
    assert client.get("/api/scuba/dives/999999/analysis").status_code == 404
    assert client.get("/api/scuba/dives/abc/analysis").status_code == 422


# ---------------------------------------------------------------- conditions

def test_verdicts():
    assert scuba_tools.verdict(0.5, 0.4, 10)[0] == "good"
    assert scuba_tools.verdict(1.3, 0.5, 10) == ("fair", "Marginal: waves to 1.3 m")
    assert scuba_tools.verdict(0.5, 0.4, 27)[0] == "fair"
    v, why = scuba_tools.verdict(2.2, 1.6, 30)
    assert v == "poor" and "waves to 2.2 m" in why and "swell 1.6 m" in why and "wind to 30 km/h" in why
    assert scuba_tools.verdict(0.5, 0.4, 40)[0] == "poor"
    assert scuba_tools.verdict(0.5, 1.2, 5, period=4)[0] == "fair"
    assert scuba_tools.verdict(None, None, None)[0] == "fair" and scuba_tools.verdict(None, None, 10)[1].startswith("No sea data")


def test_conditions_for_a_site_and_for_a_point(client, monkeypatch):
    seas(monkeypatch)
    site_id = add_site()
    r = client.get(f"/api/scuba/conditions?site_id={site_id}")
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["place"] == "Flinders Reef" and c["lat"] == -26.97 and len(c["days"]) == 7 and c["kept_since"] is None
    assert "Open-Meteo" in c["credit"] and "navigation" in c["credit"]
    day = c["days"][0]
    assert set(day) >= {"date", "wave_max", "swell_max", "swell_period", "swell_dir", "sst", "wind_max_kmh", "tide", "verdict", "why"}
    assert day["sst"] == 24.5 and day["swell_period"] == 9.0 and day["swell_dir"] == 110 and day["wind_max_kmh"] == 12
    assert day["verdict"] == "good" and len(day["tide"]) in (3, 4, 5)               # two highs and two lows a day (a day can show 3-5)
    assert all(set(t) == {"time", "height"} for t in day["tide"])
    assert [d["verdict"] for d in c["days"]][4] == "poor"                           # 36 km/h wind on day 5
    assert day["date"] == date.today().isoformat()
    p = client.get("/api/scuba/conditions?lat=-27.5&lon=153.4").json()
    assert p["place"] == "-27.50, 153.40" and len(p["days"]) == 7


def test_conditions_without_wind_and_with_trouble(client, monkeypatch):
    monkeypatch.setattr(openmeteo, "_get", lambda url, params: stand_ins.marine_stand_in() if "marine" in url else (_ for _ in ()).throw(openmeteo.WeatherError("no wind")))
    openmeteo._cache.clear()
    c = client.get("/api/scuba/conditions?lat=-27.5&lon=153.4").json()
    assert c["days"][0]["wind_max_kmh"] is None and c["days"][0]["verdict"] in ("good", "fair")
    assert client.get("/api/scuba/conditions").status_code == 422
    assert client.get("/api/scuba/conditions?lat=-27.5").status_code == 422
    assert client.get("/api/scuba/conditions?site_id=999999").status_code == 404
    with db() as conn:
        site_id = conn.execute("INSERT INTO scuba_sites (name) VALUES ('Nowhere') RETURNING site_id").fetchone()["site_id"]
    r = client.get(f"/api/scuba/conditions?site_id={site_id}")
    assert r.status_code == 422 and "no position" in r.json()["detail"]


def test_conditions_keep_the_last_good_answer(client, monkeypatch):
    seas(monkeypatch)
    assert client.get("/api/scuba/conditions?lat=-27.5&lon=153.4").status_code == 200
    openmeteo._cache.clear()                                                # an hour later, and Open-Meteo is unreachable

    def down(url, params):
        raise openmeteo.WeatherError("Couldn't reach Open-Meteo (ConnectError).")
    monkeypatch.setattr(openmeteo, "_get", down)
    r = client.get("/api/scuba/conditions?lat=-27.5&lon=153.4")
    assert r.status_code == 200 and r.json()["kept_since"] and len(r.json()["days"]) == 7
    r = client.get("/api/scuba/conditions?lat=10.0&lon=10.0")               # a place never asked: nothing kept
    assert r.status_code == 502 and "Open-Meteo" in r.json()["detail"]


def test_marine_reads_open_meteos_hourly_answer(monkeypatch):
    seas(monkeypatch)
    days = openmeteo.marine(-27.5, 153.4, fresh=True)
    assert len(days) == 7 and days[0]["wave_max"] > 0 and days[6]["swell_max"] > days[0]["swell_max"]
    openmeteo._cache.clear()
    monkeypatch.setattr(openmeteo, "_get", lambda url, params: {"hourly": {"time": ["2026-01-01T00:00", "2026-01-01T01:00"], "wave_height": [None, None]}})
    empty = openmeteo.marine(-27.5, 153.4, fresh=True)
    assert empty == [{"day": "2026-01-01", "wave_max": None, "swell_max": None, "swell_period": None, "swell_dir": None, "sst": None, "tide": []}]


# ---------------------------------------------------------------- OpenStreetMap dive sites

def test_osm_near_and_import(client, monkeypatch):
    monkeypatch.setattr(overpass, "_post", stand_ins.scuba_osm)
    r = client.get("/api/scuba/osm/near?lat=-27.47&lon=153.02&km=60")
    assert r.status_code == 200, r.text
    sites = r.json()
    assert [s["name"] for s in sites] == sorted((s["name"] for s in sites), key=lambda n: next(x["km"] for x in sites if x["name"] == n))
    assert {s["name"] for s in sites} == {"Stand-in Reef", "Stand-in Wreck", "Stand-in Pinnacle"}
    reef = next(s for s in sites if s["name"] == "Stand-in Reef")
    wreck = next(s for s in sites if s["name"] == "Stand-in Wreck")
    assert reef["osm"] == "node/990101" and reef["kind"] == "Reef" and reef["depth_max"] == 18.0 and reef["km"] > 20 and reef["site_id"] is None
    assert wreck["osm"] == "way/990102" and wreck["kind"] == "Wreck"

    r = client.post("/api/scuba/osm/import", json={"osm": "node/990101"})
    assert r.status_code == 201, r.text
    site = r.json()
    assert site["name"] == "Stand-in Reef" and site["lat"] == -27.30 and site["kind"] == "Reef" and site["depth_max"] == 18.0
    assert site["osm"] == "node/990101" and site["existing"] is False and "OpenStreetMap" in site["notes"]
    again = client.post("/api/scuba/osm/import", json={"osm": "node/990101"})
    assert again.status_code == 200 and again.json()["site_id"] == site["site_id"] and again.json()["existing"] is True
    assert len(client.get("/api/scuba/sites").json()) == 1
    assert next(s for s in client.get("/api/scuba/osm/near?lat=-27.47&lon=153.02").json() if s["name"] == "Stand-in Reef")["site_id"] == site["site_id"]
    assert client.post("/api/scuba/osm/import", json={"osm": "way/990102"}).status_code == 201


def test_osm_refusals(client, monkeypatch):
    assert client.get("/api/scuba/osm/near").status_code == 422
    assert client.get("/api/scuba/osm/near?lat=-27&lon=153&km=500").status_code == 422
    assert client.post("/api/scuba/osm/import", json={"osm": "somewhere"}).status_code == 422
    def down(data):
        raise overpass.OverpassError("Couldn't reach OpenStreetMap's Overpass (ConnectError).")
    monkeypatch.setattr(overpass, "_post", down)
    r = client.get("/api/scuba/osm/near?lat=-27&lon=153")                   # Overpass is down
    assert r.status_code == 502 and "Overpass" in r.json()["detail"]
    assert client.post("/api/scuba/osm/import", json={"osm": "node/5"}).status_code == 502
    monkeypatch.setattr(overpass, "_post", stand_ins.scuba_osm)
    assert client.post("/api/scuba/osm/import", json={"osm": "node/5"}).status_code == 404


def test_osm_site_reading():
    el = {"type": "way", "id": 7, "center": {"lat": -27.0, "lon": 153.0}, "tags": {"name": "Cave 1", "natural": "cave_entrance", "depth": "12,5 m", "addr:suburb": "Tangalooma"}}
    got = scuba_tools.osm_site(el)
    assert got == {"osm": "way/7", "name": "Cave 1", "lat": -27.0, "lon": 153.0, "kind": "Cave", "depth_max": 12.5, "place": "Tangalooma"}
    assert scuba_tools.osm_site({"type": "node", "id": 1, "tags": {}}) is None
    assert scuba_tools.osm_site({"type": "node", "id": 1, "lat": 1, "lon": 2, "tags": {"name": "SS Something Wreck"}})["kind"] == "Wreck"
