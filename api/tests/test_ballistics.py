"""Precision shooting's ballistic solver (drag tables, atmosphere, zero, wind), the speed-against-temperature fit, and the routes."""
import pytest

from app import ballistics as b

STANDARD = b.atmosphere()


def test_standard_atmosphere_values():
    # ICAO standard day: 1.225 kg/m3, density altitude 0, speed of sound 340.3 m/s
    assert STANDARD["density"] == 1.225 and STANDARD["density_altitude_m"] == 0 and STANDARD["sound_ms"] == 340.3
    # thinner air when it's hot, high or humid: density altitude goes up
    hot = b.atmosphere(35, 1005, 60)
    assert hot["density"] < 1.15 and hot["density_altitude_m"] > 800
    assert b.atmosphere(15, 900)["density_altitude_m"] > 900 > b.atmosphere(15, 1013.25)["density_altitude_m"]
    assert b.air_density(20, 1013.25, 90) < b.air_density(20, 1013.25, 0)          # damp air is lighter than dry
    # a pressure of 1 atm at 0 C, dry, is the textbook 1.2922 kg/m3 (rounded: 1.292)
    assert round(b.air_density(0, 1013.25, 0), 3) == 1.292


def test_drag_tables():
    assert b.drag_cd("G1", 1.0) == 0.4805 and b.drag_cd("G7", 1.0) == 0.3803           # table rows
    assert round(b.drag_cd("G1", 0.9875), 4) == round((0.4448 + 0.4805) / 2, 4)          # straight line between rows
    assert b.drag_cd("G1", 9) == 0.4988 and b.drag_cd("G7", -1) == 0.1198               # flat beyond the ends
    assert all(b.drag_cd("G7", m / 10) < b.drag_cd("G1", m / 10) for m in range(0, 50))  # the G7 shape drags less


def test_trajectory_against_published_figures():
    # .308 Win 168 gr (BC 0.462 G1), 2650 fps = 807.7 m/s, 100 yd zero, 38 mm sight height, standard air. Published
    # load tables (Sierra / Hornady) put the drop at 300 yd near 15 in (38 cm) and 10 mph drift at 300 yd near 7.5 in (19 cm).
    rows = b.trajectory(807.7, 0.462, "G1", 91.44, 38, [91.44, 274.32, 457.2], STANDARD, wind_ms=10 * 0.44704)
    zero, mid, far = rows
    assert abs(zero["drop_cm"]) < 0.2
    assert 35 < -mid["drop_cm"] < 42 and 17 < mid["drift_cm"] < 21
    assert 150 < -far["drop_cm"] < 185 and far["velocity_ms"] < mid["velocity_ms"] < 807.7
    assert far["time_s"] > mid["time_s"] > 0.3


def test_trajectory_behaves():
    d = [75, 100, 200, 300]
    base = b.trajectory(800, 0.45, "G1", 100, 45, d, STANDARD)
    drops = [r["drop_cm"] for r in base]
    assert drops == sorted(drops, reverse=True) and abs(base[1]["drop_cm"]) < 0.2         # zeroed at 100 m, falling after
    assert base[0]["drop_cm"] > 0                                                         # on the way up, above the line of sight
    assert base[3]["elev_moa"] > base[2]["elev_moa"] > 0 and base[3]["elev_mrad"] > 0
    # a higher BC or more speed means less drop
    assert b.trajectory(800, 0.60, "G1", 100, 45, d, STANDARD)[3]["drop_cm"] > drops[3]
    assert b.trajectory(900, 0.45, "G1", 100, 45, d, STANDARD)[3]["drop_cm"] > drops[3]
    windy = b.trajectory(800, 0.45, "G1", 100, 45, d, STANDARD, wind_ms=5)
    assert windy[3]["drift_cm"] > windy[2]["drift_cm"] > 0 and base[3]["drift_cm"] == 0
    # thin air: the bullet drops less (zeroed in standard air, shot in the heat)
    thin = b.trajectory(800, 0.45, "G1", 100, 45, d, b.atmosphere(35, 1005, 60), STANDARD)
    assert thin[3]["drop_cm"] > drops[3]
    # the same air for the zero and the shot: the zero still holds
    assert abs(b.trajectory(800, 0.45, "G1", 100, 45, [100], b.atmosphere(35, 1005, 60))[0]["drop_cm"]) < 0.2
    # the energy column needs the bullet's weight
    assert b.trajectory(320, 0.14, "G1", 50, 40, [50], STANDARD, bullet_kg=40 * b.GRAIN_KG)[0]["energy_j"] > 100


def test_temperature_fit():
    pts = [(10, 320.0), (20, 324.0), (30, 328.0)]
    fit = b.temp_fit(pts)
    assert round(fit["slope"], 3) == 0.4 and round(fit["intercept"], 2) == 316.0 and fit["r2"] == 1.0 and fit["n"] == 3
    assert b.fps_per_degree(0.4) == {"fps_per_c": 1.31, "fps_per_f": 0.73}
    assert b.temp_fit(pts[:2]) is None                                          # too few sessions
    assert b.temp_fit([(20, 320), (21, 321), (22, 322)]) is None                # too close in temperature
    assert b.temp_fit([(10, 320), (20, 322), (30, 321)])["r2"] < 0.5


def _kit(client):
    rifle = client.post("/api/shooting/rifles", json={"name": "Ballistic test", "scope_unit": "MOA", "zero_m": 100,
                                                     "sight_height_mm": 45}).json()
    a = client.post("/api/shooting/ammo", json={"name": "Test load", "bullet_gr": 168, "bc": 0.462, "bc_model": "G1",
                                               "velocity_ms": 800}).json()
    return rifle["rifle_id"], a["ammo_id"]


def test_ballistics_route(client):
    rifle, ammo = _kit(client)
    r = client.get("/api/shooting/ballistics", params={"rifle_id": rifle, "ammo_id": ammo, "max_m": 300, "step": 100, "at": "150"}).json()
    assert [row["m"] for row in r["rows"]] == [100, 150, 200, 300] and r["unit"] == "MOA" and r["air"]["standard"]
    assert abs(r["rows"][0]["elevation"]) < 0.1 and r["rows"][3]["elevation"] > r["rows"][2]["elevation"] > 0
    assert r["rows"][3]["wind10"] > 0 and r["rows"][3]["energy_j"] > 0
    hot = client.get("/api/shooting/ballistics", params={"rifle_id": rifle, "ammo_id": ammo, "max_m": 300, "step": 150, "temp_c": 38,
                                                         "pressure_hpa": 1000, "humidity_pct": 70}).json()
    assert hot["air"]["density_altitude_m"] > 1000 and hot["rows"][0]["elevation"] < r["rows"][3]["elevation"]
    assert any("standard day" in n for n in hot["notes"])
    # a session's weather is used when nothing is typed
    s = client.post("/api/shooting/sessions", json={"rifle_id": rifle, "ammo_id": ammo, "temp_c": 5, "pressure_hpa": 1020,
                                                   "humidity_pct": 40}).json()
    assert (s["pressure_hpa"], s["humidity_pct"]) == (1020, 40)
    cold = client.get("/api/shooting/ballistics", params={"rifle_id": rifle, "ammo_id": ammo, "session_id": s["session_id"],
                                                          "max_m": 100, "step": 100}).json()
    assert cold["air"]["temp_c"] == 5 and cold["air"]["pressure_hpa"] == 1020


def test_ballistics_route_needs_the_details(client):
    rifle, ammo = _kit(client)
    bare = client.post("/api/shooting/ammo", json={"name": "Bare"}).json()["ammo_id"]
    assert client.get("/api/shooting/ballistics", params={"rifle_id": rifle, "ammo_id": bare}).status_code == 422
    assert client.get("/api/shooting/ballistics", params={"rifle_id": 999999, "ammo_id": ammo}).status_code == 404
    assert client.get("/api/shooting/ballistics", params={"rifle_id": rifle, "ammo_id": 999999}).status_code == 404
    no_zero = client.post("/api/shooting/rifles", json={"name": "No zero"}).json()["rifle_id"]
    assert client.get("/api/shooting/ballistics", params={"rifle_id": no_zero, "ammo_id": ammo}).status_code == 422
    assert client.get("/api/shooting/ammo/999999/temp-sensitivity").status_code == 404


def test_temp_sensitivity_route(client):
    rifle, ammo = _kit(client)
    empty = client.get(f"/api/shooting/ammo/{ammo}/temp-sensitivity").json()
    assert empty["enough"] is False and empty["fit"] is None
    for temp, speeds in ((8, [796, 798, 797]), (22, [802, 803, 801]), (34, [807, 806, 808])):
        client.post("/api/shooting/sessions", json={"rifle_id": rifle, "ammo_id": ammo, "temp_c": temp,
                                                   "groups": [{"distance": 100, "velocities": speeds}]})
    fit = client.get(f"/api/shooting/ammo/{ammo}/temp-sensitivity", params={"rifle_id": rifle}).json()
    assert fit["enough"] and len(fit["points"]) == 3 and 0.3 < fit["fit"]["slope"] < 0.5 and fit["fit"]["fps_per_f"] > 0
    # the solver then uses the fitted speed for the day's temperature
    r = client.get("/api/shooting/ballistics", params={"rifle_id": rifle, "ammo_id": ammo, "temp_c": 34, "max_m": 100, "step": 100}).json()
    assert 805 < r["ammo"]["mv_ms"] < 809 and any("chronograph" in n for n in r["notes"])
    typed = client.get("/api/shooting/ballistics", params={"rifle_id": rifle, "ammo_id": ammo, "temp_c": 34, "mv_ms": 800,
                                                           "max_m": 100, "step": 100}).json()
    assert typed["ammo"]["mv_ms"] == 800


@pytest.mark.parametrize("bad", [{"pressure_hpa": 5000}, {"humidity_pct": 120}])
def test_session_air_limits(client, bad):
    assert client.post("/api/shooting/sessions", json=bad).status_code == 422
