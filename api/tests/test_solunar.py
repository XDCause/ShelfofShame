"""solunar.py: the sun and moon maths for fishing, checked against published values for Brisbane (no database, no outside site)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app import solunar

BNE = (-27.47, 153.03)
AEST = timezone(timedelta(hours=10))


def minutes(stamp: str) -> int:
    return int(stamp[11:13]) * 60 + int(stamp[14:16])


def test_sunrise_and_sunset_in_brisbane_at_the_solstices():
    june = solunar.day(date(2026, 6, 21), *BNE)
    assert abs(minutes(june["sunrise"]) - (6 * 60 + 38)) <= 5
    assert abs(minutes(june["sunset"]) - (17 * 60 + 0)) <= 6
    dec = solunar.day(date(2026, 12, 21), *BNE)
    assert abs(minutes(dec["sunrise"]) - (4 * 60 + 46)) <= 5
    assert abs(minutes(dec["sunset"]) - (18 * 60 + 41)) <= 6
    assert june["tz"] == "Australia/Brisbane" and june["sunrise"].startswith("2026-06-21T")


def test_full_and_new_moon_dates_in_2026():
    def lit(d):
        return solunar.moon_phase(datetime(d.year, d.month, d.day, 12, tzinfo=AEST))
    # published (Brisbane dates): full 3 Jan, 2 Feb, 4 Mar, 2 Apr, 1 May, 31 May, 30 Jun, 24 Dec; new 19 Jan, 18 Feb, 19 Mar, 15 Jun, 9 Dec
    for d in [date(2026, 1, 3), date(2026, 2, 2), date(2026, 3, 3), date(2026, 4, 2), date(2026, 5, 1), date(2026, 5, 31), date(2026, 6, 30), date(2026, 12, 24)]:
        assert lit(d)[1] > 98, d
    for d in [date(2026, 1, 19), date(2026, 2, 18), date(2026, 3, 19), date(2026, 6, 15), date(2026, 12, 9)]:
        assert lit(d)[1] < 2, d
    name, pct, age = lit(date(2026, 12, 24))
    assert name == "Full moon" and 14 <= age <= 15.5
    assert lit(date(2026, 12, 9))[0] == "New moon"


def test_phase_names_cover_the_month_in_order():
    names = []
    for i in range(30):
        d = date(2026, 6, 15) + timedelta(days=i)
        n = solunar.moon_phase(datetime(d.year, d.month, d.day, 12, tzinfo=AEST))[0]
        if not names or names[-1] != n:
            names.append(n)
    assert set(names) == set(solunar.PHASES)
    assert solunar.PHASES[0] == "New moon" and len(solunar.PHASES) == 8


def test_moonrise_is_where_the_phase_says():
    full = solunar.day(date(2026, 12, 24), *BNE)["moon"]           # a full moon rises near sunset
    assert abs(minutes(full["rise"]) - minutes(solunar.day(date(2026, 12, 24), *BNE)["sunset"])) <= 90
    new = solunar.day(date(2026, 12, 9), *BNE)
    assert abs(minutes(new["moon"]["rise"]) - minutes(new["sunrise"])) <= 90      # a new moon rises with the sun
    quarter = solunar.day(date(2026, 6, 21), *BNE)["moon"]                        # a first quarter: up at noon, set near midnight
    assert 10 * 60 <= minutes(quarter["rise"]) <= 13 * 60 and minutes(quarter["set"]) >= 22 * 60 + 30
    assert abs(minutes(quarter["overhead"]) - (17 * 60 + 20)) <= 30


def test_majors_and_minors_are_centred_on_the_moon_events():
    d = solunar.day(date(2026, 6, 21), *BNE)
    assert len(d["majors"]) == 2 and len(d["minors"]) == 2
    for p in d["majors"]:
        assert datetime.fromisoformat(p["end"]) - datetime.fromisoformat(p["start"]) == timedelta(hours=2)
    for p in d["minors"]:
        assert datetime.fromisoformat(p["end"]) - datetime.fromisoformat(p["start"]) == timedelta(hours=1)
    m = d["moon"]
    centres = {datetime.fromisoformat(p["start"]) + timedelta(hours=1) for p in d["majors"]}
    assert {datetime.fromisoformat(m["overhead"]), datetime.fromisoformat(m["underfoot"])} == centres
    assert [p["start"] for p in d["majors"]] == sorted(p["start"] for p in d["majors"])


def test_rating_is_higher_near_new_and_full_moon():
    ratings = {d: solunar.day(d, *BNE)["rating"] for d in (date(2026, 12, 24), date(2026, 12, 9), date(2026, 12, 16), date(2026, 12, 2))}
    assert all(1 <= r <= 4 for r in ratings.values())
    assert min(ratings[date(2026, 12, 24)], ratings[date(2026, 12, 9)]) >= 3
    assert max(ratings[date(2026, 12, 16)], ratings[date(2026, 12, 2)]) <= 3          # the quarters: no better than 3
    assert min(ratings[date(2026, 12, 24)], ratings[date(2026, 12, 9)]) >= max(ratings[date(2026, 12, 16)], ratings[date(2026, 12, 2)]) - 1


def test_a_dawn_major_adds_a_point():
    # find a day where a major / minor overlaps sunrise or sunset and one where none does: the bonus is the difference
    seen = {}
    for i in range(30):
        d = date(2026, 6, 15) + timedelta(days=i)
        day = solunar.day(d, *BNE)
        sun = [datetime.fromisoformat(day["sunrise"]), datetime.fromisoformat(day["sunset"])]
        hit = any(datetime.fromisoformat(p["start"]) <= s + timedelta(minutes=30) and datetime.fromisoformat(p["end"]) >= s - timedelta(minutes=30)
                  for p in day["majors"] + day["minors"] for s in sun)
        seen.setdefault(hit, []).append(day["rating"])
    assert True in seen and False in seen
    assert max(seen[True]) == 4 and max(seen[False]) <= 3


def test_other_zones_and_places():
    london = solunar.day(date(2026, 6, 21), 51.5, -0.12, "Europe/London")
    assert 4 * 60 <= minutes(london["sunrise"]) <= 5 * 60 + 10 and 21 * 60 <= minutes(london["sunset"]) <= 21 * 60 + 40   # 04:43 / 21:21 BST
    with pytest.raises(ValueError):
        solunar.zone("Mars/Olympus")


def test_polar_night_has_no_sunrise():
    night = solunar.day(date(2026, 12, 21), 78.2, 15.6, "Arctic/Longyearbyen")
    assert night["sunrise"] is None and night["sunset"] is None and 1 <= night["rating"] <= 4
