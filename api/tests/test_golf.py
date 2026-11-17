"""Golf: the sums (daily handicap, strokes received, Stableford, net double bogey, the WHS index, strokes gained,
plays-like), courses (by hand and from OpenStreetMap's shapes), tees, rounds scored hole by hole, shots, the bag,
practice, the summary / stats / handicap pages, and the parts other pages show (activity, goals, calendar)."""
import pytest

from app import golf_map, golfmath as gm, overpass, stand_ins

PARS = [4, 4, 3, 5, 4, 4, 3, 4, 5, 4, 3, 4, 5, 4, 4, 3, 5, 4]                 # par 72
SI = [7, 11, 15, 1, 5, 13, 17, 3, 9, 8, 16, 2, 10, 6, 12, 18, 4, 14]


@pytest.fixture(autouse=True)
def plain_settings():
    """golf_settings is one row the clean-up leaves alone: put it back after each test."""
    yield
    from app.db import db
    with db() as conn:
        conn.execute("UPDATE golf_settings SET official_handicap = NULL, official_as_of = NULL, allowance = 0.93, "
                     "target_handicap = NULL, home_course_id = NULL WHERE id = 1")


def course(client, **extra):
    r = client.post("/api/golf/courses", json={"name": "Victoria Park", "place": "Herston, QLD", "lat": -27.45, "lon": 153.02,
                                               "pars": PARS, **extra})
    assert r.status_code == 201, r.text
    c = r.json()
    r = client.put(f"/api/golf/courses/{c['course_id']}/holes",
                   json=[{"hole_no": i + 1, "par": p, "stroke_index": SI[i]} for i, p in enumerate(PARS)])
    assert r.status_code == 200, r.text
    r = client.post(f"/api/golf/courses/{c['course_id']}/tees", json={"name": "Blue", "colour": "#2255cc", "rating": 71.0, "slope": 125,
                                                                      "lengths": {str(i + 1): 300 + i for i in range(18)}})
    assert r.status_code == 201, r.text
    return r.json()


def play(client, c, strokes, **extra):
    """A finished round with these strokes (None: picked up), two putts a hole."""
    tee = c["tees"][0]["tee_id"]
    r = client.post("/api/golf/rounds", json={"course_id": c["course_id"], "tee_id": tee, **extra})
    assert r.status_code == 201, r.text
    rid = r.json()["round_id"]
    holes = [{"hole_no": i + 1, "strokes": s, "putts": 2 if s and s >= 3 else None, "picked_up": s is None,
              "fairway": "hit" if PARS[i] > 3 else None} for i, s in enumerate(strokes)]
    r = client.put(f"/api/golf/rounds/{rid}/holes", json=holes)
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/golf/rounds/{rid}", json={"status": "done"})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- the sums

def test_daily_handicap_and_strokes():
    # Golf Australia's own example: GA Handicap 15.2, slope 124, rating 72, par 70 -> 17
    assert gm.daily_handicap(15.2, 124, 72, 70) == 17
    assert gm.daily_handicap(15.2, 124, 72, 70, allowance=1) == 19
    assert gm.daily_handicap(None, 124, 72, 70) is None
    assert gm.daily_handicap(20, 113, 36, 36, nine=True) == 9          # half the index for a nine
    assert gm.received(17, 1) == 1 and gm.received(17, 17) == 1 and gm.received(17, 18) == 0
    assert gm.received(20, 2) == 2 and gm.received(20, 3) == 1        # past 18: a second stroke on the hardest
    assert gm.received(-2, 17) == -1 and gm.received(-2, 16) == 0     # plus handicap: strokes back on the easiest
    assert gm.received(5, 9, nine_si=[1, 3, 5, 7, 9, 11, 13, 15, 17]) == 1     # rank 5 of the nine
    assert gm.received(5, 11, nine_si=[1, 3, 5, 7, 9, 11, 13, 15, 17]) == 0


def test_stableford_and_net_double_bogey():
    assert gm.stableford(4, 4, 0) == 2 and gm.stableford(3, 4, 0) == 3 and gm.stableford(5, 4, 1) == 2
    assert gm.stableford(7, 4, 0) == 0 and gm.stableford(None, 4, 1) == 0
    assert gm.adjusted(9, 4, 1) == 7 and gm.adjusted(5, 4, 1) == 5 and gm.adjusted(None, 3, 0) == 5


def test_whs_index():
    assert gm.handicap_index([(1, 10.0), (2, 12.0)]) is None                       # fewer than 3
    assert gm.handicap_index([(1, 10.0), (2, 12.0), (3, 14.0)])["index"] == 8.0      # lowest one, less 2
    six = gm.handicap_index([(i, d) for i, d in enumerate([10.0, 12.0, 14.0, 9.0, 20.0, 11.0])])
    assert six["index"] == 8.5 and sorted(six["used"]) == [0, 3]                   # lowest two averaged, less 1
    twenty = [(i, float(i)) for i in range(25)]                                    # only the newest 20 count
    assert gm.handicap_index(twenty)["index"] == 3.5 and gm.handicap_index(twenty)["of"] == 20
    assert gm.nine_to_18(5.0, 10.0) == 11.4


def test_strokes_gained_and_plays_like():
    assert gm.expected("green", 3 * 0.3048) == pytest.approx(1.04)
    assert gm.expected("tee", 400 * 0.9144) == pytest.approx(3.99)
    # tee shot 330 m on a par 4, then a wedge from 100 m that finishes 1 m away: one putt
    pin = (0.0, 0.0)
    shots = [{"lie": "tee", "lat": 330 / 111195, "lon": 0}, {"lie": "fairway", "lat": 100 / 111195, "lon": 0}]
    sg = gm.hole_strokes_gained(4, shots, pin, 1, 1.0, 0, 3)
    assert sg["off_tee"] > 0 and sg["approach"] > 0 and sg["around_green"] == 0 and sg["putting"] < 0.1
    assert gm.hole_strokes_gained(4, shots, pin, 1, 1.0, 0, 5) is not None           # strokes don't add up: putting only
    assert gm.hole_strokes_gained(4, shots, pin, 1, 1.0, 0, 5)["off_tee"] is None
    assert gm.hole_strokes_gained(4, [], None, 2, None, 0, 5) is None                 # nothing to go on
    assert gm.plays_like("gir", 35) == 10 and gm.plays_like("putts", 31) == 5
    assert gm.plays_like("gir", 70) == -5                                              # past the table: capped


def test_osm_shapes_become_holes():
    got = golf_map.holes(stand_ins.golf_osm("map_to_area golf")["elements"])
    assert got["name"] == "Stand-in Golf Club" and got["place"] == "Testville, QLD"
    one, two = got["holes"]
    assert (one["hole_no"], one["par"], one["stroke_index"]) == (1, 4, 3) and (two["par"], two["stroke_index"]) == (3, 15)
    assert one["map"]["green"] and len(one["map"]["tees"]) == 1 and one["map"]["fairways"] and one["map"]["bunkers"]
    assert one["map"]["water"] and two["map"]["green"] and not two["map"]["bunkers"]
    found = golf_map.courses(stand_ins.golf_osm('nwr["leisure"="golf_course"](around:1,2,3)')["elements"])
    assert found == [{"osm": "way/990001", "name": "Stand-in Golf Club", "lat": -27.47, "lon": 153.02, "place": "Testville, QLD"}]


# ---------------------------------------------------------------- courses

def test_course_by_hand(client):
    c = course(client)
    assert c["par"] == 72 and c["holes"] == 18 and len(c["holes_list"]) == 18 and c["rated"] == 1
    tee = c["tees"][0]
    assert tee["metres"] == sum(300 + i for i in range(18)) and tee["daily_handicap"] is None     # no handicap yet
    assert client.put(f"/api/golf/courses/{c['course_id']}/holes", json=[{"hole_no": 1, "par": 4, "stroke_index": 2},
                                                                         {"hole_no": 2, "par": 4, "stroke_index": 2}]).status_code == 422
    r = client.patch(f"/api/golf/tees/{tee['tee_id']}", json={"lengths": {"1": None}, "slope": 130})
    assert r.json()["tees"][0]["slope"] == 130 and "1" not in r.json()["tees"][0]["lengths"]
    nine = client.post("/api/golf/courses", json={"name": "Nine", "holes": 9}).json()
    assert nine["par"] == 36
    assert client.post("/api/golf/courses", json={"name": "Bad", "holes": 12}).status_code == 422
    assert client.post("/api/golf/courses", json={"name": "Bad", "holes": 9, "pars": [4] * 18}).status_code == 422
    assert client.patch(f"/api/golf/courses/{nine['course_id']}", json={"holes": 18}).json()["par"] == 72
    assert [x["name"] for x in client.get("/api/golf/courses").json()] == ["Nine", "Victoria Park"]


def test_course_from_openstreetmap(client, monkeypatch):
    monkeypatch.setattr(overpass, "_post", stand_ins.golf_osm)
    monkeypatch.setattr("app.openmeteo.find_place", lambda q: [{"name": "Testville", "region": "QLD", "lat": -27.4, "lon": 153.0}])
    found = client.get("/api/golf/osm/search", params={"q": "Testville"}).json()
    assert found["place"] == "Testville, QLD" and found["courses"][0]["name"] == "Stand-in Golf Club"
    assert found["courses"][0]["course_id"] is None and found["courses"][0]["metres"] > 0
    c = client.post("/api/golf/osm/import", json={"osm": "way/990001"}).json()
    assert c["name"] == "Stand-in Golf Club" and c["holes"] == 9 and c["mapped"] == 2
    assert c["holes_list"][0]["par"] == 4 and c["holes_list"][1]["par"] == 3 and c["holes_list"][2]["par"] == 4
    assert c["holes_list"][0]["map"]["green"]
    client.put(f"/api/golf/courses/{c['course_id']}/holes", json=[{"hole_no": 3, "par": 5}])
    again = client.post("/api/golf/osm/import", json={"osm": "way/990001"}).json()          # a refresh: your edits stay
    assert again["course_id"] == c["course_id"] and again["holes_list"][2]["par"] == 5
    assert client.get("/api/golf/osm/search", params={"lat": -27.4, "lon": 153.0}).json()["courses"][0]["course_id"] == c["course_id"]
    assert client.get("/api/golf/osm/search").status_code == 422
    assert client.post("/api/golf/osm/import", json={"osm": "node/1"}).status_code == 422


def test_openstreetmap_down(client):
    from tests.conftest import SITES_DOWN
    SITES_DOWN["on"] = True
    try:
        r = client.get("/api/golf/osm/search", params={"lat": -27.4, "lon": 153.0})
    finally:
        SITES_DOWN["on"] = False
    assert r.status_code == 502


# ---------------------------------------------------------------- rounds

def test_a_round_hole_by_hole(client):
    c = course(client)
    client.put("/api/golf/settings", json={"official_handicap": 15.2})
    r = client.post("/api/golf/rounds", json={"course_id": c["course_id"], "tee_id": c["tees"][0]["tee_id"]}).json()
    # (15.2 x 125 / 113 + (71 - 72)) x 0.93 = 14.7 -> 15
    assert r["handicap"] == 15.2 and r["daily_handicap"] == 15 and r["status"] == "playing" and r["format"] == "Stableford"
    assert len(r["holes"]) == 18 and r["holes"][0]["map"] == {"green": None} or r["holes"][0]["map"] is None and r["holes"][0]["metres"] == 300
    rid = r["round_id"]
    h1 = client.put(f"/api/golf/rounds/{rid}/holes/1", json={"strokes": 5, "putts": 2, "fairway": "left"}).json()
    one = h1["holes"][0]
    assert one["received"] == 1 and one["points"] == 2 and one["gir"] is False and h1["totals"]["entered"] == 1
    again = client.put(f"/api/golf/rounds/{rid}/holes/1", json={"strokes": 5, "putts": 2, "fairway": "left"}).json()   # sent twice: same
    assert again["totals"]["points"] == 2
    h4 = client.put(f"/api/golf/rounds/{rid}/holes/4", json={"picked_up": True}).json()
    assert h4["holes"][3]["points"] == 0 and h4["holes"][3]["adjusted"] == 5 + 2 + 1
    assert client.put(f"/api/golf/rounds/{rid}/holes/4", json={"picked_up": True, "strokes": 6}).status_code == 422
    assert client.put(f"/api/golf/rounds/{rid}/holes/2", json={"strokes": 3, "putts": 4}).status_code == 422
    cleared = client.put(f"/api/golf/rounds/{rid}/holes/4", json={}).json()
    assert cleared["totals"]["entered"] == 1
    assert client.put(f"/api/golf/rounds/{rid}/holes/19", json={"strokes": 4}).status_code == 422


def test_a_finished_round_and_the_handicap(client):
    c = course(client)
    rounds = [play(client, c, [p + (1 if i % 2 else 0) for i, p in enumerate(PARS)]) for _ in range(3)]
    t = rounds[-1]["totals"]
    assert t["gross"] == 81 and t["to_par"] == 9 and t["complete"] and t["adjusted_gross"] == 81
    # no handicap yet: no strokes received; (113 / 125) x (81 - 71) = 9.04 -> 9.0
    assert t["differential"] == 9.0 and t["points"] == 27
    assert rounds[-1]["stats"]["fairways"] == 14 and rounds[-1]["stats"]["gir"] == 9
    h = client.get("/api/golf/handicap").json()
    assert h["estimate"] == 7.0 and h["source"] == "estimate" and len(h["rounds"]) == 3 and h["counting"] == 3
    assert len(h["history"]) == 1 and h["need"] is None
    nxt = client.post("/api/golf/rounds", json={"course_id": c["course_id"], "tee_id": c["tees"][0]["tee_id"]}).json()
    assert nxt["handicap"] == 7.0 and nxt["daily_handicap"] == 6
    client.put("/api/golf/settings", json={"official_handicap": 12.0})
    assert client.get("/api/golf/handicap").json()["current"] == 12.0
    ambrose = client.post("/api/golf/rounds", json={"course_id": c["course_id"], "format": "Ambrose"}).json()
    assert ambrose["counts"] is False


def test_nine_holes_and_pickups(client):
    c = course(client)
    client.put("/api/golf/settings", json={"official_handicap": 20.0})
    r = client.post("/api/golf/rounds", json={"course_id": c["course_id"], "tee_id": c["tees"][0]["tee_id"], "holes": "back"}).json()
    assert [h["hole_no"] for h in r["holes"]] == list(range(10, 19))
    # (10 x 125 / 113 + (35.5 - 36)) x 0.93 = 9.8 -> 10: a stroke a hole (and one more on the hardest)
    assert r["daily_handicap"] == 10
    assert client.put(f"/api/golf/rounds/{r['round_id']}/holes/1", json={"strokes": 4}).status_code == 422
    holes = [{"hole_no": n, "strokes": PARS[n - 1] + 1} for n in range(10, 18)] + [{"hole_no": 18, "picked_up": True}]
    done = client.put(f"/api/golf/rounds/{r['round_id']}/holes", json=holes).json()
    assert done["totals"]["complete"] and done["totals"]["gross"] is None and done["totals"]["points"] == 17   # 2 a hole, 3 on the 12th (index 2: a second stroke), 0 on the 18th
    assert done["totals"]["differential"] is not None        # 9 holes: + the expected other nine


def test_shots_and_clubs(client):
    c = course(client)
    bag = client.post("/api/golf/clubs/standard-bag").json()
    assert len(bag) == 13 and bag[0]["name"] == "Driver"
    assert client.post("/api/golf/clubs/standard-bag").status_code == 409
    driver = bag[0]["club_id"]
    rid = client.post("/api/golf/rounds", json={"course_id": c["course_id"]}).json()["round_id"]
    client.put(f"/api/golf/rounds/{rid}/shots/1/1", json={"lie": "tee", "lat": -27.45, "lon": 153.02, "club_id": driver})
    r = client.put(f"/api/golf/rounds/{rid}/shots/1/2", json={"lie": "fairway", "lat": -27.45 + 210 / 111195, "lon": 153.02}).json()
    assert [s["seq"] for s in r["shots"]] == [1, 2] and r["shots"][0]["metres"] == 210 and r["shots"][0]["club"] == "Driver"
    r = client.put(f"/api/golf/rounds/{rid}/shots/1/1", json={"lie": "tee", "lat": -27.45, "lon": 153.02, "club_id": driver}).json()
    assert len(r["shots"]) == 2                                          # sent again: the same shot
    clubs = client.get("/api/golf/clubs").json()
    assert clubs[0]["measured"]["average"] == 210 and clubs[0]["measured"]["shots"] == 1
    r = client.request("DELETE", f"/api/golf/rounds/{rid}/shots/1/1").json()
    assert [s["seq"] for s in r["shots"]] == [1] and r["shots"][0]["lie"] == "fairway"
    assert client.put(f"/api/golf/rounds/{rid}/shots/1/1", json={"lie": "tee", "lat": 0, "lon": 0, "club_id": 999}).status_code == 404
    assert client.patch(f"/api/golf/clubs/{driver}", json={"carry_m": 230}).json()[0]["carry_m"] == 230
    assert client.delete(f"/api/golf/clubs/{driver}").status_code == 204


def test_a_course_with_rounds_stays(client):
    c = course(client)
    play(client, c, PARS)
    assert client.delete(f"/api/golf/courses/{c['course_id']}").status_code == 409
    detail = client.get(f"/api/golf/courses/{c['course_id']}").json()
    assert detail["you"]["best"] == 72 and detail["holes_list"][0]["you"]["average"] == 4 and detail["recent"][0]["gross"] == 72


# ---------------------------------------------------------------- the numbers, and the rest of the app

def test_summary_and_stats(client):
    assert client.get("/api/golf/summary").json()["rounds"] == 0
    c = course(client)
    for _ in range(3):
        play(client, c, [p + 1 for p in PARS], competition="Monthly medal")
    s = client.get("/api/golf/summary").json()
    assert s["rounds"] == 3 and s["this_year"]["rounds"] == 3 and s["handicap"]["estimate"] is not None
    assert s["stats"]["average"] == 90 and s["stats"]["putts"] == 36 and s["stats"]["gir"] == 0
    assert s["stats"]["plays_like"]["putts"] == 30 and s["bench"]["gir"] is not None
    st = client.get("/api/golf/stats", params={"last": 2}).json()
    assert st["rounds"] == 2 and st["front_vs_par"] == 9 and len(st["trend"]) == 2
    feed = client.get("/api/activity").json()
    assert any(a["kind"] == "golfround" and a["title"] == "Victoria Park" and "90 strokes" in a["detail"] for a in feed)
    rounds_csv = client.get("/api/export/golf-rounds.csv").text
    assert "Victoria Park" in rounds_csv and ",90,36," in rounds_csv and "Monthly medal" in rounds_csv
    assert client.get("/api/export/golf-holes.csv").text.count("Victoria Park") == 54


def test_practice(client):
    r = client.post("/api/golf/practice", json={"kind": "Putting", "minutes": 30, "drill": "Ladder", "made": 7, "attempts": 10})
    assert r.status_code == 201, r.text
    client.post("/api/golf/practice", json={"kind": "Putting", "drill": "Ladder", "made": 9, "attempts": 10})
    assert client.post("/api/golf/practice", json={"kind": "Putting", "made": 7}).status_code == 422
    p = client.get("/api/golf/practice").json()
    assert p["year"]["sessions"] == 2 and p["year"]["minutes"] == 30
    assert p["drills"] == [{"drill": "Ladder", "times": 2, "best_pct": 90, "last_pct": 90, "last": "9/10"}]
    pid = p["sessions"][0]["practice_id"]
    assert client.patch(f"/api/golf/practice/{pid}", json={"kind": None}).status_code == 422
    assert client.delete(f"/api/golf/practice/{pid}").status_code == 204
    assert any(a["kind"] == "golfpractice" for a in client.get("/api/activity").json())


def test_settings(client):
    s = client.put("/api/golf/settings", json={"official_handicap": 14.3, "target_handicap": 9.9}).json()
    assert float(s["official_handicap"]) == 14.3 and float(s["allowance"]) == 0.93
    assert client.put("/api/golf/settings", json={"allowance": None}).status_code == 422
    assert client.put("/api/golf/settings", json={"home_course_id": 999}).status_code == 404
