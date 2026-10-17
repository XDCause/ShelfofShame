"""Hiking: GPX import (the numbers worked out from the track), hikes by hand, the summary, the activity feed."""
from datetime import datetime, timedelta, timezone

from app import gpx, hiking, overpass, wikimedia

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


# A tiny JPEG-ish body is enough: the API stores what the browser sends (it checks the type and size).
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200


def test_photos_placed_by_gps_or_time(client):
    hid = client.post("/api/hiking/import", content=track(walk())).json()["hike_id"]
    # by GPS: next to the 11th point (about 1 km along)
    p = client.post(f"/api/hiking/hikes/{hid}/photos?lat={-27.5 + 10 * STEP + 0.00001}&lon=153.0001&caption=Lookout",
                    content=JPEG, headers={"Content-Type": "image/jpeg"}).json()
    assert p["located"] == "gps" and abs(p["along_m"] - 1000.7) < 2 and p["caption"] == "Lookout"
    # by time: 20 minutes in (the camera's clock has no zone: Brisbane, so 21:20 UTC = 7:20 am)
    q = client.post(f"/api/hiking/hikes/{hid}/photos?taken=2026-09-06T07:20:00",
                    content=JPEG, headers={"Content-Type": "image/jpeg"}).json()
    assert q["located"] == "time" and abs(q["along_m"] - 2001.4) < 2 and abs(q["lat"] - (-27.5 + 20 * STEP)) < 1e-5
    # neither: kept, just not on the map
    r = client.post(f"/api/hiking/hikes/{hid}/photos", content=JPEG, headers={"Content-Type": "image/jpeg"}).json()
    assert r["located"] is None and r["along_m"] is None
    assert client.post(f"/api/hiking/hikes/{hid}/photos", content=b"x", headers={"Content-Type": "text/plain"}).status_code == 415
    h = client.get(f"/api/hiking/hikes/{hid}").json()
    assert [x["photo_id"] for x in h["photos"]] == [p["photo_id"], q["photo_id"], r["photo_id"]]   # along the way
    assert h["photo_url"] == p["url"] and h["photos_count"] == 3
    img = client.get(p["url"])
    assert img.content == JPEG and "immutable" in img.headers["cache-control"]
    assert client.patch(f"/api/hiking/photos/{q['photo_id']}", json={"caption": " Summit "}).json()["caption"] == "Summit"
    assert client.delete(f"/api/hiking/photos/{r['photo_id']}").status_code == 204
    feed = client.get("/api/activity?since=2026-09-01").json()
    assert next(a for a in feed if a["kind"] == "hike")["photo_url"] == p["url"]
    client.delete(f"/api/hiking/hikes/{hid}")
    assert client.get(p["url"]).status_code == 404                 # a hike's photos go with it


OVERPASS = {"elements": [
    {"type": "node", "id": 1, "lat": -27.4955, "lon": 153.0003, "tags": {"natural": "peak", "name": "Mt Example", "ele": "412 m",
                                                                        "wikidata": "Q42"}},
    {"type": "way", "id": 2, "center": {"lat": -27.4910, "lon": 152.9999}, "tags": {"tourism": "viewpoint", "name": "Top Lookout",
                                                                                    "wikimedia_commons": "File:Lookout.jpg"}},
    {"type": "node", "id": 3, "lat": -27.4990, "lon": 153.0, "tags": {"amenity": "toilets"}},
    {"type": "node", "id": 4, "lat": -27.40, "lon": 153.2, "tags": {"natural": "peak", "name": "Far Away"}},   # not near the track
    {"type": "node", "id": 5, "lat": -27.495, "lon": 153.0, "tags": {"shop": "bakery", "name": "Not a landmark"}},
]}


def fake_wikimedia(url, params):
    if params.get("action") == "wbgetentities":
        return {"entities": {"Q42": {"claims": {"P18": [{"mainsnak": {"datavalue": {"value": "Mt Example.jpg"}}}]}}}}
    if params.get("list") == "geosearch":
        return {"query": {"geosearch": [{"title": "File:Track.jpg", "lat": -27.4977, "lon": 153.0},
                                        {"title": "File:Elsewhere.jpg", "lat": -27.49, "lon": 153.05}]}}
    pages = [{"title": t, "imageinfo": [{"mime": "image/jpeg", "thumburl": f"https://upload.wikimedia.org/{t[5:]}",
                                         "descriptionurl": f"https://commons.wikimedia.org/wiki/{t}",
                                         "extmetadata": {"Artist": {"value": "<a href='x'>Jo Walker</a>"},
                                                         "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]}
             for t in params["titles"].split("|")]
    return {"query": {"pages": pages}}


def test_landmarks_and_nearby_photos(client, monkeypatch):
    sent = []
    monkeypatch.setattr(overpass, "_post", lambda data: sent.append(data) or OVERPASS)
    monkeypatch.setattr(wikimedia, "_get", fake_wikimedia)
    h = client.post("/api/hiking/import", content=track(walk())).json()       # looked up in the background
    assert "natural" in sent[0] and "around:250," in sent[0]
    h = client.get(f"/api/hiking/hikes/{h['hike_id']}").json()
    assert h["landmarks_error"] is None and h["landmarks_at"] and h["landmarks_looking"] is False
    names = [(lm["label"], lm["name"]) for lm in h["landmarks"]]
    assert names == [("Toilets", None), ("Peak", "Mt Example"), ("Lookout", "Top Lookout")]
    peak = h["landmarks"][1]
    assert peak["ele"] == 412 and abs(peak["along_m"] - 500) < 10 and peak["off_m"] < 40
    assert peak["photo"]["thumb"].endswith("Mt Example.jpg") and peak["photo"]["author"] == "Jo Walker"
    assert h["landmarks"][2]["photo"]["licence"] == "CC BY-SA 4.0"
    assert [p["title"] for p in h["nearby_photos"]] == ["File:Track.jpg"]

    # Overpass busy: the photos are still saved, and the hike says what went wrong
    def busy(data):
        raise overpass.OverpassError("OpenStreetMap's Overpass is busy (HTTP 504).")
    monkeypatch.setattr(overpass, "_post", busy)
    assert client.post(f"/api/hiking/hikes/{h['hike_id']}/landmarks").status_code == 202
    again = client.get(f"/api/hiking/hikes/{h['hike_id']}").json()
    assert "busy" in again["landmarks_error"] and len(again["landmarks"]) == 3     # the last ones are kept
    manual = client.post("/api/hiking/hikes", json={"name": "Walk", "hiked_on": "2026-10-01"}).json()
    assert client.post(f"/api/hiking/hikes/{manual['hike_id']}/landmarks").status_code == 409


def test_overpass_query_and_parsing():
    q = overpass.query([(-27.5, 153.0), (-27.49, 153.01)], 250)
    assert q.count("around:250,-27.50000,153.00000,-27.49000,153.01000") == 6 and q.startswith("[out:json]")
    lms = overpass.landmarks(OVERPASS["elements"])
    assert [lm["kind"] for lm in lms] == ["peak", "viewpoint", "toilets", "peak"]
    assert lms[1]["lat"] == -27.4910 and lms[1]["commons"] == "File:Lookout.jpg" and lms[0]["wikidata"] == "Q42"


def test_place_by_time_is_between_points():
    tr = [[-27.5, 153.0, 100, 0, 0.0], [-27.499, 153.0, 110, 100, 111.2]]
    lat, lon, along = hiking.at_time(tr, 50)
    assert abs(lat + 27.4995) < 1e-9 and abs(along - 55.6) < 0.01
    assert hiking.at_time(tr, 5000) is None


def test_trailhead_facilities_thinned_and_photos_spread(monkeypatch):
    tr = [[-27.5 + i * STEP, 153.0, 100, i * 60, i * 100.07] for i in range(31)]
    els = [{"type": "node", "id": i, "lat": -27.5 + i * 0.00002, "lon": 153.0, "tags": {"leisure": "x", "amenity": "toilets"}}
           for i in range(5)]                                              # five toilet blocks at the start
    els += [{"type": "node", "id": 9, "lat": -27.5, "lon": 153.0015, "tags": {"tourism": "picnic_site"}},   # 150 m off
            {"type": "node", "id": 10, "lat": -27.5 + 15 * STEP, "lon": 153.0, "tags": {"amenity": "toilets"}},
            {"type": "node", "id": 11, "lat": -27.5, "lon": 153.0002, "tags": {"tourism": "camp_site", "name": "Top Camp"}}]
    monkeypatch.setattr(overpass, "_post", lambda data: {"elements": els})
    monkeypatch.setattr(wikimedia, "_get", fake_wikimedia)
    lms = hiking.find_landmarks(tr)
    assert [(lm["label"], round(lm["along_m"] / 1000)) for lm in lms] == [("Toilets", 0), ("Campsite", 0), ("Toilets", 2)]

    files = [{"title": f"File:{n}.jpg", "lat": -27.5 + (n % 31) * STEP, "lon": 153.0} for n in range(40)]
    monkeypatch.setattr(wikimedia, "near", lambda *a, **k: files)
    monkeypatch.setattr(wikimedia, "images", lambda titles: {
        t: {"thumb": "https://x/" + t, "page": "p", "author": "Moth fan" if int(t[5:-4]) < 30 else f"Hiker {t}", "licence": "CC0"}
        for t in titles})
    picked = hiking.find_nearby_photos(tr)
    assert len(picked) <= hiking.MAX_NEARBY and sum(p["author"] == "Moth fan" for p in picked) == 2
    assert picked == sorted(picked, key=lambda p: p["along_m"])


def test_hiking_gear_hikes_and_km(client):
    boots = client.post("/api/gear", json={"name": "Merrell boots", "kind": "Boots", "hobby": "hiking"}).json()
    pack = client.post("/api/gear", json={"name": "Day pack", "kind": "Backpack", "hobby": "hiking"}).json()
    ball = client.post("/api/gear", json={"name": "Ball"}).json()                       # volleyball's (the default)
    assert boots["hobby"] == "hiking" and ball["hobby"] == "volleyball"
    assert [g["name"] for g in client.get("/api/gear?hobby=hiking").json()] == ["Day pack", "Merrell boots"]
    assert [g["name"] for g in client.get("/api/gear?hobby=volleyball").json()] == ["Ball"]
    assert len(client.get("/api/gear").json()) == 3
    assert client.post("/api/gear", json={"name": "Kayak", "hobby": "kayaking"}).status_code == 422

    one = client.post("/api/hiking/hikes", json={"name": "Walk 1", "hiked_on": "2026-10-01", "distance_km": 8.5}).json()
    two = client.post("/api/hiking/hikes", json={"name": "Walk 2", "hiked_on": "2026-10-08", "distance_km": 12}).json()
    h = client.put(f"/api/hiking/hikes/{one['hike_id']}/gear", json={"gear_ids": [boots["gear_id"], pack["gear_id"]]}).json()
    assert [g["name"] for g in h["gear"]] == ["Day pack", "Merrell boots"]
    assert client.put(f"/api/hiking/hikes/{one['hike_id']}/gear", json={"gear_ids": [ball["gear_id"]]}).status_code == 422
    assert sorted(client.get(f"/api/hiking/hikes/{two['hike_id']}").json()["last_gear_ids"]) == sorted([boots["gear_id"], pack["gear_id"]])
    assert client.get(f"/api/hiking/hikes/{one['hike_id']}").json()["last_gear_ids"] == []      # nothing before it
    client.put(f"/api/hiking/hikes/{two['hike_id']}/gear", json={"gear_ids": [boots["gear_id"]]})
    b = client.get(f"/api/gear/{boots['gear_id']}").json()
    assert (b["hikes"], b["hiked_m"]) == (2, 20500)
    client.delete(f"/api/hiking/hikes/{two['hike_id']}")
    assert client.get(f"/api/gear/{boots['gear_id']}").json()["hiked_m"] == 8500
    client.patch(f"/api/gear/{pack['gear_id']}", json={"condition": "Needs replacing"})
    assert client.get("/api/volleyball/summary").json()["gear_to_replace"] == 0              # hiking gear isn't volleyball's
