"""Dive maths (divemath.py): Buhlmann ZHL-16C with gradient factors, no-stop limits, stops, nitrox sums, oxygen exposure,
gas planning and the profile checks. The numbers are checked against well-known ones (published tables, textbook nitrox
examples) so a slip in the typed-in tables shows."""
import math

import pytest

from app import divemath as dm


def profile(points, step=10):
    """[(seconds, depth)] straight lines between (seconds, depth) corners, a sample every `step` seconds."""
    out = []
    for (t0, d0), (t1, d1) in zip(points, points[1:]):
        for t in range(t0, t1, step):
            out.append([t, d0 + (d1 - d0) * (t - t0) / (t1 - t0), None])
    out.append([points[-1][0], points[-1][1], None])
    return out


def test_tables_are_complete_and_sane():
    assert len(dm.N2_HALF) == len(dm.N2_A) == len(dm.N2_B) == len(dm.HE_HALF) == len(dm.HE_A) == len(dm.HE_B) == 16
    assert dm.N2_HALF == sorted(dm.N2_HALF) and dm.HE_HALF == sorted(dm.HE_HALF)
    assert all(0 < b < 1 for b in dm.N2_B + dm.HE_B)
    assert dm.N2_HALF[0] == 5.0 and dm.N2_HALF[-1] == 635.0 and dm.HE_HALF[0] == 1.88


def test_nitrox_sums():
    assert dm.mod(32, 1.4) == pytest.approx(33.75)
    assert dm.mod(32, 1.6) == pytest.approx(40.0)
    assert dm.mod(21, 1.4) == pytest.approx(56.67, abs=0.01)
    assert dm.ead(30, 32) == pytest.approx(24.43, abs=0.01)
    assert dm.ead(30, 21) == pytest.approx(30.0, abs=0.01)
    assert dm.ppo2(30, 32) == pytest.approx(1.28)
    assert dm.best_mix(30, 1.4) == 35
    assert dm.best_mix(33.75, 1.4) == 32
    assert dm.best_mix(60, 1.4) is None                 # even air is too rich at 60 m
    assert dm.best_mix(3, 1.4) == 100


def test_air_no_stop_limits_are_near_the_published_ones():
    """ZHL-16C on air, GF 100: roughly 18 m 55-60 min, 30 m 16-20 min, 39 m about 8-12 (counted from leaving the surface)."""
    got = {d: dm.ndl(d, 21, 100) for d in (12, 18, 21, 24, 30, 36, 39)}
    assert 50 <= got[18] <= 62
    assert 15 <= got[30] <= 20
    assert 8 <= got[39] <= 12
    assert list(got.values()) == sorted(got.values(), reverse=True)        # deeper, shorter
    assert 100 <= got[12] <= 200


def test_gradient_factor_high_shortens_the_limits_and_nitrox_lengthens_them():
    for depth in (18, 24, 30):
        assert dm.ndl(depth, 21, 85) < dm.ndl(depth, 21, 100)
        assert dm.ndl(depth, 32, 85) > dm.ndl(depth, 21, 85)
    assert dm.ndl(9, 21, 100) == dm.NDL_CAP                                # shallow enough to be unlimited here
    assert dm.ndl(100, 21, 85) == 0                                         # the descent alone is too much


def test_repetitive_dive_has_less_time():
    t = dm.new_tissues()
    dm.schreiner(t, 0, 30, 30 / dm.DESCENT)
    dm.schreiner(t, 30, 30, 17 - 30 / dm.DESCENT)
    dm.schreiner(t, 30, 0, 30 / dm.ASCENT)
    assert dm.ndl(18, 21, 85, tissues=t) < dm.ndl(18, 21, 85)
    before = list(t.n2)
    dm.ndl(18, 21, 85, tissues=t)
    assert t.n2 == before                                                   # (the caller's tissues are not changed)
    rested = dm.offgas(t.copy(), 180)
    assert dm.ndl(18, 21, 85, tissues=rested) > dm.ndl(18, 21, 85, tissues=t)


def test_schreiner_matches_the_plain_exponential_at_a_constant_depth():
    t = dm.new_tissues()
    p0 = t.n2[3]
    dm.schreiner(t, 20, 20, 10.0)
    inspired = (dm.amb(20) - dm.WATER_VAPOUR) * dm.AIR_N2
    assert t.n2[3] == pytest.approx(inspired + (p0 - inspired) * math.exp(-math.log(2) / 18.5 * 10))
    assert t.n2[3] > p0
    one = dm.new_tissues()
    dm.schreiner(one, 0, 20, 4.0)                                           # going down loads, but less than waiting at 20 m
    two = dm.new_tissues()
    dm.schreiner(two, 20, 20, 4.0)
    assert one.n2[0] < two.n2[0]


def test_helium_is_loaded_and_changes_the_ceiling():
    t = dm.new_tissues()
    dm.schreiner(t, 0, 40, 2.0, 21, 35)
    dm.schreiner(t, 40, 40, 20.0, 21, 35)
    assert t.he[0] > 1.0 and t.he[0] > t.he[-1]
    assert dm.ceiling(t, 0.85) > 0


def test_plan_without_stops():
    p = dm.plan(18, 30, 21, 40, 85, sac=15, tank_l=12, start_bar=200)
    assert p["stops"] == [] and p["ndl"] > 30
    assert p["tts"] == pytest.approx(2.0, abs=0.1) and p["runtime"] == pytest.approx(32.0, abs=0.1)
    assert p["ppo2"] == 0.59 and p["mod"] == 56.7
    # gas: down 1 min + 29 min at 18 m + up 2 min, at 15 L/min
    litres = 15 * (1 + 18 / 20) * 1.0 + 15 * 2.8 * 29 + 15 * (1 + 18 / 20) * 2
    assert p["gas_l"] == pytest.approx(litres, abs=3)
    assert p["gas_bar"] == math.ceil(litres / 12)
    assert p["end_bar"] == 200 - p["gas_bar"]
    assert p["rock_bottom_bar"] < p["turn_bar"] < 200
    assert p["warnings"] == []


def test_plan_with_stops_and_warnings():
    p = dm.plan(30, 25, 21, 40, 85)
    assert p["stops"] and p["stops"][-1]["depth"] == 3
    assert [s["depth"] for s in p["stops"]] == sorted((s["depth"] for s in p["stops"]), reverse=True)
    assert all(s["depth"] % 3 == 0 and s["minutes"] >= 1 for s in p["stops"])
    assert p["runtime"] == pytest.approx(25 + p["tts"], abs=0.1)
    assert any("decompression" in w for w in p["warnings"])
    deeper = dm.plan(30, 35, 21, 40, 85)
    assert sum(s["minutes"] for s in deeper["stops"]) > sum(s["minutes"] for s in p["stops"])
    assert dm.plan(30, 25, 21, 40, 100)["tts"] < p["tts"]                   # GF 100 asks for less than GF 85
    assert dm.plan(30, 25, 21, 30, 70)["tts"] > p["tts"]
    assert dm.plan(30, 25, 32, 40, 85)["tts"] < p["tts"]                    # nitrox: shorter stops


def test_plan_warns_about_oxygen_depth_and_gas():
    p = dm.plan(40, 10, 32, 40, 85, sac=25, tank_l=10, start_bar=150)
    assert any("ppO2" in w and "33.8" in w for w in p["warnings"])
    assert any("40 m" in w for w in dm.plan(45, 5, 21, 40, 85)["warnings"])
    short = dm.plan(25, 40, 21, 40, 85, sac=25, tank_l=8, start_bar=100)
    assert short["end_bar"] < short["rock_bottom_bar"]
    assert any("rock bottom" in w for w in short["warnings"]) and any("enough gas" in w for w in short["warnings"])


def test_a_dive_shorter_than_its_descent_is_stretched_to_it():
    p = dm.plan(30, 1, 21)
    assert p["runtime"] >= 30 / dm.DESCENT


def test_rock_bottom_is_two_stressed_divers():
    # 20 m, SAC 20 -> 80 L/min for the pair, doubled again by stress: 1 min at 3 bar, then 2.22 min at an average 2 bar
    stressed = 20 * 2 * 2
    expected = stressed * 3.0 * 1 + stressed * 2.0 * (20 / 9)
    assert dm.rock_bottom_l(20, 20) == pytest.approx(expected)
    assert dm.rock_bottom_l(30, 20) > dm.rock_bottom_l(20, 20)
    g = dm.gas_plan(1500, 20, 20, 12, 200)
    assert g["gas_bar"] == 125 and g["end_bar"] == 75
    assert g["rock_bottom_bar"] == math.ceil(expected / 12)
    assert g["turn_bar"] == math.ceil(200 - (200 - g["rock_bottom_bar"]) / 3)


def test_cns_and_otu():
    assert dm.cns_rate(1.4) == pytest.approx(100 / 180)
    assert dm.cns_rate(1.6) == pytest.approx(100 / 45)
    assert dm.cns_rate(1.0) == pytest.approx(100 / 300)
    assert dm.cns_rate(0.45) == 0
    assert dm.cns_rate(1.45) == pytest.approx(100 / 150)                    # between two rows of the table
    cns, otu = dm.exposure([(60.0, 33.75, 33.75)], 32)                     # an hour at ppO2 1.4
    assert cns == pytest.approx(100 / 3, abs=0.1)
    assert otu == pytest.approx(60 * ((1.4 - 0.5) / 0.5) ** (5 / 6), abs=0.1)
    assert dm.exposure([(30.0, 0, 0)], 21) == (0.0, 0.0)                   # air at the surface: below the 0.5 bar floor


def test_tissues_after_a_recorded_dive_and_gf():
    samples = profile([(0, 0), (70, 20), (1500, 20), (1580, 5), (1760, 5), (1780, 0)])
    t, series = dm.tissues_after(samples, 21)
    fresh = dm.new_tissues()
    assert t.n2[0] > fresh.n2[0] and t.n2[10] > fresh.n2[10]
    assert 0 < dm.surface_gf(t) < 100
    assert len(series) <= 200 and series[0][0] == 0 and series[-1][0] == 1780
    assert max(p for _s, p in series) > 40 and all(p >= 0 for _s, p in series)
    long = dm.tissues_after(profile([(0, 0), (60, 30), (3600, 30), (3700, 0)], 1), 21)[1]
    assert len(long) <= 200
    deep = dm.tissues_after(profile([(0, 0), (80, 30), (1500, 30), (1700, 0)]), 21)[0]
    assert dm.surface_gf(deep) > 100                                        # past the M-value: a missed stop
    assert dm.surface_gf(dm.offgas(deep.copy(), 600)) < dm.surface_gf(deep)


def test_ascent_warnings():
    slow = profile([(0, 0), (60, 18), (1200, 18), (1300, 0)])                # 10.8 m/min is too fast; 9 is not
    assert len(dm.ascent_warnings(slow)) == 1
    calm = profile([(0, 0), (60, 18), (1200, 18), (1320, 0)])                # 9 m/min
    assert dm.ascent_warnings(calm) == []
    fast = profile([(0, 0), (60, 18), (1200, 18), (1240, 0)])                # 27 m/min
    found = dm.ascent_warnings(fast)
    assert len(found) == 1 and found[0]["rate"] == pytest.approx(27.0, abs=1.5)
    assert 1190 <= found[0]["from_s"] <= 1230 and found[0]["to_s"] >= 1230
    spike = profile([(0, 0), (60, 18), (600, 18), (605, 15), (610, 18), (1300, 18), (1420, 0)], 5)   # one jumpy sample
    assert dm.ascent_warnings(spike) == []
    two = profile([(0, 0), (60, 20), (300, 20), (330, 8), (500, 8), (530, 0)])
    assert len(dm.ascent_warnings(two)) == 2
    assert dm.ascent_warnings([]) == [] and dm.ascent_warnings([[0, 0, None]]) == []


def test_safety_stop():
    stop = profile([(0, 0), (60, 18), (1200, 18), (1260, 5), (1500, 5), (1520, 0)])
    found = dm.safety_stop(stop)
    assert found["found"] is True and found["seconds"] == pytest.approx(255, abs=30)
    brief = profile([(0, 0), (60, 18), (1200, 18), (1260, 5), (1320, 5), (1340, 0)])
    assert dm.safety_stop(brief)["found"] is False and dm.safety_stop(brief)["seconds"] > 0
    none = profile([(0, 0), (60, 18), (1200, 18), (1280, 0)])
    assert dm.safety_stop(none)["found"] is False
    shallow = profile([(0, 0), (60, 5), (1200, 5), (1260, 0)])
    assert dm.safety_stop(shallow) == {"found": False, "seconds": 0}        # never below 6 m: nothing to stop from


def test_downsample_keeps_the_ends_and_the_deepest():
    samples = [[i, 10.0 if i != 777 else 31.0, None] for i in range(5000)]
    small = dm.downsample(samples, 400)
    assert len(small) <= 400 and small[0] == samples[0] and small[-1] == samples[-1]
    assert any(s[1] == 31.0 for s in small)
    assert dm.downsample(samples[:10], 400) == [list(s) for s in samples[:10]]
