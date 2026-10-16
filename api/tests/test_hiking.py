"""Hiking: GPX import (the numbers worked out from the track), hikes by hand, the summary, the activity feed."""
from datetime import datetime, timedelta, timezone

from app import gpx

STEP = 0.0009            # degrees of latitude: about 100 m


def track(points, name="Mt Example Loop", link="https://www.alltrails.com/trail/australia/example/mt-example-loop",
          extra="", segments=None):
    """A GPX file: points = [(lat, lon, ele, seconds from 7:00 UTC)], or several segments."""
    start = datetime(2026, 9, 5, 21, 0, tzinfo=timezone.utc)          # 7 am on the 6th in Brisbane

    def pt(lat, lon, ele, s):
        ele_xml = f"<ele>{ele}</ele>" if ele is not None else ""
        time_xml = f"<time>{(start + timedelta(seconds=s)).isoformat().replace('+00:00', 'Z')}</time>" if s is not None else ""
        return f'<trkpt lat="{lat}" lon="{lon}">{ele_xml}{time_xml}</trkpt>'
    segs = segments or [points]
    body = "".join("<trkseg>" + "".join(pt(*p) for p in s) + "</trkseg>" for s in segs)
    return (f'<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="AllTrails" '
            f'xmlns="http://www.topografix.com/GPX/1/1"><metadata><name>{name}</name>'
            f'<link href="{link}"><text>AllTrails</text></link><desc>Up the ridge and back.</desc></metadata>'
            f'{extra}<trk><name>{name}</name><type>hiking</type>{body}</trk></gpx>').encode()


def walk(n=31, climb=10, every=60, lat=-27.5, lon=153.0):
    """n points due north, ~100 m apart, a minute apart, climbing `climb` m each."""
    return [(round(lat + i * STEP, 6), lon, 100 + i * climb, i * every) for i in range(n)]


def test_measure_distance_time_climb_and_splits():
    g = gpx.parse(track(walk()))
    assert abs(g["distance_m"] - 3000 * 1.0007) < 15                       # 30 steps of ~100.07 m
    assert g["moving_s"] == g["elapsed_s"] == 30 * 60
    assert abs(g["ascent_m"] - 300) < 1 and g["descent_m"] == 0
    assert (g["max_ele_m"], g["min_ele_m"]) == (400, 100)
    assert g["name"] == "Mt Example Loop" and g["description"] == "Up the ridge and back."
    assert g["trail_url"].startswith("https://www.alltrails.com/")
    assert [s["km"] for s in g["splits"]] == [1, 2, 3]
    assert all(590 <= s["seconds"] <= 610 for s in g["splits"])
    assert g["is_loop"] is False and g["points"] == 31 and len(g["track"]) == 31
    assert g["track"][0][3] == 0 and g["track"][-1][3] == 1800


def test_stops_noise_and_pauses():
    # standing still for 10 minutes (GPS wobbles 2 m up and down) isn't moving and isn't climbing
    pts = walk(11, climb=0)
    still = [(pts[-1][0], pts[-1][1], 100 + (2 if i % 2 else 0), pts[-1][3] + 60 * (i + 1)) for i in range(10)]
    g = gpx.parse(track(pts + still))
    assert g["moving_s"] == 600 and g["elapsed_s"] == 1200
    assert g["ascent_m"] == 0 and g["descent_m"] == 0
    # two segments (a pause): the gap between them isn't walked
    a, b = walk(6), walk(6, lat=-27.4)
    b = [(la, lo, e, s + 3600) for la, lo, e, s in b]
    g = gpx.parse(track(None, segments=[a, b]))
    assert abs(g["distance_m"] - 1000 * 1.0007) < 10


def test_loop_route_without_times_and_waypoints():
    out = walk(8, climb=0)
    back = [(la, lo + 0.0002, e, None) for la, lo, e, _ in reversed(out)]
    pts = [(la, lo, e, None) for la, lo, e, _ in out] + back
    wpt = '<wpt lat="-27.4973" lon="153.0"><ele>140</ele><name>Lookout</name></wpt>'
    g = gpx.parse(track(pts, extra=wpt))
    assert g["is_loop"] is True and g["moving_s"] is None and g["started_at"] is None
    assert g["waypoints"] == [{"name": "Lookout", "lat": -27.4973, "lon": 153.0, "ele": 140.0}]
    assert g["splits"][0]["seconds"] is None


def test_long_tracks_are_thinned_for_drawing():
    g = gpx.parse(track(walk(4000, climb=0, every=5)))
    assert g["points"] == 4000 and len(g["track"]) <= gpx.KEEP + 2
    assert g["track"][-1][4] == round(g["distance_m"], 1)


def test_bad_files():
    for raw, word in [(b"not xml", "valid XML"), (b"<kml></kml>", "isn't a GPX"),
                      (b'<?xml version="1.0"?><!DOCTYPE gpx [<!ENTITY a "x">]><gpx></gpx>', "declarations"),
                      (b'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg></trkseg></trk></gpx>', "no track")]:
        try:
            gpx.parse(raw)
            raise AssertionError("parsed")
        except gpx.GpxError as e:
            assert word in str(e)


def test_import_list_edit_and_download(client):
    raw = track(walk())
    r = client.post("/api/hiking/import?filename=Mt_Example_Loop.gpx", content=raw)
    assert r.status_code == 201
    h = r.json()
    assert h["duplicate"] is False and h["source"] == "gpx" and h["name"] == "Mt Example Loop"
    assert h["hiked_on"] == "2026-09-06"                         # Brisbane's day, not UTC's
    assert h["trail_url"].startswith("https://www.alltrails.com/") and h["notes"] == "Up the ridge and back."
    assert len(h["track"]) == 31 and len(h["splits"]) == 3
    again = client.post("/api/hiking/import?filename=copy.gpx", content=raw)
    assert again.status_code == 200 and again.json()["duplicate"] is True and again.json()["hike_id"] == h["hike_id"]
    assert client.post("/api/hiking/import", content=b"<gpx/>").status_code == 422

    hid = h["hike_id"]
    e = client.patch(f"/api/hiking/hikes/{hid}", json={"rating": 5, "difficulty": "Hard", "companions": "Sam",
                                                       "trail_name": " Mt Example ", "location": "Somewhere"}).json()
    assert (e["rating"], e["difficulty"], e["trail_name"]) == (5, "Hard", "Mt Example")
    assert client.patch(f"/api/hiking/hikes/{hid}", json={"name": " "}).status_code == 422
    assert client.patch(f"/api/hiking/hikes/{hid}", json={"trail_url": "alltrails.com/x"}).status_code == 422
    assert client.patch(f"/api/hiking/hikes/{hid}", json={"difficulty": "Extreme"}).status_code == 422

    listed = client.get("/api/hiking/hikes?q=sam").json()
    assert [x["hike_id"] for x in listed] == [hid] and "track" not in listed[0]
    assert client.get("/api/hiking/hikes?q=nobody").json() == []
    assert len(client.get("/api/hiking/hikes?year=2026").json()) == 1

    d = client.get(f"/api/hiking/hikes/{hid}/gpx")
    assert d.content == raw and "Mt_Example_Loop.gpx" in d.headers["content-disposition"]

    assert client.delete(f"/api/hiking/hikes/{hid}").status_code == 204
    assert client.get(f"/api/hiking/hikes/{hid}").status_code == 404


def test_by_hand_summary_and_activity(client):
    h = client.post("/api/hiking/hikes", json={"name": "Coastal walk", "hiked_on": "2026-10-01", "distance_km": 8.5,
                                               "moving_min": 150, "ascent_m": 220, "rating": 4}).json()
    assert (h["distance_m"], h["moving_s"], h["ascent_m"], h["source"]) == (8500, 9000, 220, "manual")
    assert client.get(f"/api/hiking/hikes/{h['hike_id']}/gpx").status_code == 404
    client.post("/api/hiking/import", content=track(walk()))
    s = client.get("/api/hiking/summary").json()
    assert s["all_time"]["hikes"] == 2 and abs(s["all_time"]["km"] - 11.5) < 0.1
    assert s["bests"]["longest"]["name"] == "Coastal walk" and s["bests"]["climb"]["name"] == "Mt Example Loop"
    assert s["bests"]["highest"]["name"] == "Mt Example Loop"
    assert len(s["months"]) == 12 and len(s["recent"]) == 2
    feed = client.get("/api/activity?since=2026-09-01&until=2026-10-31").json()
    hikes = [a for a in feed if a["kind"] == "hike"]
    assert {a["title"] for a in hikes} == {"Coastal walk", "Mt Example Loop"}
    coastal = next(a for a in hikes if a["title"] == "Coastal walk")
    assert coastal["verb"] == "Hiked" and coastal["detail"] == "8.5 km · 220 m up · 2 h 30 min"
    cal = client.get("/api/calendar?start=2026-09-06&end=2026-09-06").json()
    assert [a["title"] for a in cal["happened"] if a["kind"] == "hike"] == ["Mt Example Loop"]
