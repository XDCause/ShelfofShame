"""Precision shooting: the arithmetic, rifles (round count, cleaning due, PTA), factory ammo (left = bought - fired),
ranges and club days, sessions and groups (MOA / MIL, velocities, a zeroing correction), DOPE, the dashboard."""
from app import shotmath


def test_arithmetic():
    assert round(shotmath.moa(29.09, 100), 2) == 1.0 and round(shotmath.mil(100, 100), 2) == 1.0
    assert round(shotmath.moa(29.09, shotmath.metres(100, "yd")), 2) == 1.09          # 100 yd is shorter than 100 m
    assert shotmath.moa(None, 100) is None and shotmath.velocity_stats([330]) is None
    v = shotmath.velocity_stats([320, 322, 318, 324])
    assert (v["n"], v["avg"], v["es"], v["sd"], v["fps"]) == (4, 321.0, 6.0, 2.6, 1053)
    rows = [{"m": 100, "elevation": 0}, {"m": 300, "elevation": 4.0}]
    assert shotmath.estimate(rows, 200) == 2.0 and shotmath.estimate(rows, 400) is None and shotmath.estimate(rows, 100) == 0


def test_rifles_ammo_sessions_and_the_dashboard(client):
    club = client.post("/api/shooting/ranges", json={"name": "Club range", "distances": "25, 50, 100 m"}).json()
    farm = client.post("/api/shooting/ranges", json={"name": "Farm", "kind": "Private property", "counts_for_club": False}).json()
    rifle = client.post("/api/shooting/rifles", json={"name": "CZ 457", "kind": "Rimfire", "calibre": ".22 LR", "scope_unit": "MIL",
                                                     "rounds_before": 500, "clean_every": 300, "pta_applied": "2026-10-01"}).json()
    assert (rifle["click"], rifle["round_count"], rifle["clean_due"]) == (0.1, 500, False)
    ammo = client.post("/api/shooting/ammo", json={"name": "Center-X", "brand": "Lapua", "calibre": ".22 LR", "bullet_gr": 40,
                                                  "velocity_ms": 327, "box_size": 50, "box_price": 12.5, "rounds_bought": 500}).json()
    assert (ammo["rounds_left"], ammo["per_round"], ammo["fps"], ammo["low"]) == (500, 0.25, 1073, False)

    s = client.post("/api/shooting/sessions", json={
        "shot_on": "2026-10-11", "kind": "Practice", "range_id": club["range_id"], "rifle_id": rifle["rifle_id"],
        "ammo_id": ammo["ammo_id"], "wind_kmh": 10, "rounds": 260,
        "groups": [{"distance": 50, "shots": 5, "size_mm": 10, "up_mm": 15, "right_mm": -5, "elevation": 0.5,
                    "velocities": [325, 328, 326], "confirms_dope": True},
                   {"distance": 100, "shots": 5, "size_mm": 30, "elevation": 2.5, "windage": 0.4, "confirms_dope": True}]})
    assert s.status_code == 201
    s = s.json()
    g = s["groups_list"][0]
    assert (g["mil"], g["angle"], g["velocity"]["avg"]) == (0.2, 0.2, 326.3)
    assert g["correction"] == "Dial 0.30 MIL down (3 clicks) and 0.10 MIL right (1 clicks)"
    assert (s["rounds"], s["groups"], s["range_name"], s["best_moa"]) == (260, 2, "Club range", 0.69)

    # rounds fired: the rifle's count, cleaning due (260 since it started logging >= nothing cleaned... clean_every 300)
    r = client.get(f"/api/shooting/rifles/{rifle['rifle_id']}").json()
    assert (r["round_count"], r["since_clean"], r["clean_due"]) == (760, 260, False)
    client.post("/api/shooting/sessions", json={"shot_on": "2026-10-12", "range_id": farm["range_id"], "rifle_id": rifle["rifle_id"],
                                               "ammo_id": ammo["ammo_id"], "groups": [{"distance": 100, "shots": 50}]})
    r = client.get(f"/api/shooting/rifles/{rifle['rifle_id']}").json()
    assert (r["round_count"], r["since_clean"], r["clean_due"]) == (810, 310, True)
    assert r["ammo"][0]["name"] == "Center-X" and r["ammo"][0]["unit"] == "MIL"
    cleaned = client.post(f"/api/shooting/rifles/{rifle['rifle_id']}/logs", json={"kind": "Cleaned"}).json()
    assert (cleaned["since_clean"], cleaned["clean_due"]) == (0, False)

    a = client.get(f"/api/shooting/ammo/{ammo['ammo_id']}").json()
    assert (a["rounds_fired"], a["rounds_left"], a["low"]) == (310, 190, False)
    a = client.post(f"/api/shooting/ammo/{ammo['ammo_id']}/box", json={"lot": "L123"}).json()
    assert (a["rounds_bought"], a["lot"]) == (550, "L123")

    # DOPE: both confirmed distances, 75 m estimated between them, wind per 10 km/h from the 100 m group
    d = client.get(f"/api/shooting/dope?rifle_id={rifle['rifle_id']}&ammo_id={ammo['ammo_id']}").json()
    assert [(x["m"], x["source"], x["elevation"]) for x in d["rows"]] == [(50, "confirmed", 0.5), (75, "estimate", 1.5), (100, "confirmed", 2.5)]
    assert d["rows"][2]["wind10"] == 0.4 and d["unit"] == "MIL"
    client.post("/api/shooting/dope", json={"rifle_id": rifle["rifle_id"], "distance": 200, "elevation": 7.1})
    d = client.get(f"/api/shooting/dope?rifle_id={rifle['rifle_id']}").json()
    assert d["rows"][-1]["source"] == "entered" and [x["m"] for x in d["rows"] if x["source"] == "estimate"] == [75, 125, 150, 175]

    client.put("/api/shooting/settings", json={"club_shoots_needed": 4, "licence_expires": "2030-01-01"})
    sm = client.get("/api/shooting/summary").json()
    assert sm["club_needed"] == 4 and sm["settings"]["licence_days"] > 0
    assert sm["all_time"]["rounds"] == 310 and [b["distance"] for b in sm["bests"]] == [50, 100]
    assert sm["pta"][0]["name"] == "CZ 457"

    feed = client.get("/api/activity").json()
    shot = next(f for f in feed if f["kind"] == "shoot" and f["ref"] == s["session_id"])
    assert shot["title"] == "Club range" and "CZ 457" in shot["detail"] and "260 rounds" in shot["detail"]

    # groups: edit, delete; a session goes; the rifle and ammo stay
    gid = s["groups_list"][1]["group_id"]
    assert client.patch(f"/api/shooting/groups/{gid}", json={"score": 98, "x_count": 4}).json()["score"] == 98
    assert len(client.delete(f"/api/shooting/groups/{gid}").json()["groups_list"]) == 1
    assert client.delete(f"/api/shooting/sessions/{s['session_id']}").status_code == 204
    assert client.get(f"/api/shooting/rifles/{rifle['rifle_id']}").json()["round_count"] == 550
    assert client.post("/api/shooting/sessions", json={"kind": "Picnic"}).status_code == 422


def test_shooting_gear(client):
    g = client.post("/api/gear", json={"name": "Harris bipod", "hobby": "shooting", "kind": "Bipod"})
    assert g.status_code == 201
    assert [x["name"] for x in client.get("/api/gear?hobby=shooting").json()] == ["Harris bipod"]


def test_group_stats():
    s = shotmath.group_stats([(0, 0), (6, 8), (0, 8)])
    assert (s["size_mm"], s["right_mm"], s["up_mm"], s["width_mm"], s["height_mm"]) == (10.0, 2.0, 5.3, 6.0, 8.0)
    assert shotmath.group_stats([]) is None


def test_shot_by_shot(client):
    rifle = client.post("/api/shooting/rifles", json={"name": "Tikka", "scope_unit": "MOA"}).json()
    s = client.post("/api/shooting/sessions", json={"rifle_id": rifle["rifle_id"], "groups": [{"distance": 100}]}).json()
    gid = s["groups_list"][0]["group_id"]
    for shot in ({"x_mm": 0, "y_mm": 0, "velocity": 800, "score": 10, "is_x": True},
                 {"x_mm": 10, "y_mm": 0, "velocity": 806, "score": 10},
                 {"x_mm": 5, "y_mm": 12, "velocity": 803, "score": 9},
                 {"x_mm": 80, "y_mm": -60, "flyer": True, "score": 6}):
        s = client.post(f"/api/shooting/groups/{gid}/shots", json=shot).json()
    g = s["groups_list"][0]
    assert [x["n"] for x in g["shot_list"]] == [1, 2, 3, 4]
    # the flyer isn't in the size or centre; everything else comes from the shots
    assert (g["shots"], g["size_mm"], g["right_mm"], g["up_mm"]) == (4, 13.0, 5.0, 4.0)
    assert (g["score"], g["x_count"], g["velocity"]["avg"], g["velocity"]["es"]) == (35, 1, 803.0, 6.0)
    assert g["spread"]["flyers"] == 1 and g["spread"]["mean_radius"] is not None and g["moa"] == 0.45
    flyer = g["shot_list"][3]["shot_id"]
    g = client.patch(f"/api/shooting/shots/{flyer}", json={"flyer": False}).json()["groups_list"][0]
    assert g["size_mm"] > 90                                  # counted now
    g = client.delete(f"/api/shooting/shots/{g['shot_list'][0]['shot_id']}").json()["groups_list"][0]
    assert [x["n"] for x in g["shot_list"]] == [1, 2, 3] and g["shots"] == 3
    assert client.post(f"/api/shooting/groups/{gid}/shots", json={"x_mm": 3}).status_code == 422   # needs both


def test_session_photos_and_videos(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path))
    s = client.post("/api/shooting/sessions", json={"groups": [{"distance": 50}]}).json()
    sid, gid = s["session_id"], s["groups_list"][0]["group_id"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 40
    s = client.post(f"/api/shooting/sessions/{sid}/photos?group_id={gid}&caption=Target", content=png,
                    headers={"Content-Type": "image/png"}).json()
    photo = s["media"][0]
    assert (photo["kind"], photo["group_id"], photo["caption"]) == ("photo", gid, "Target")
    assert client.get(photo["url"]).content == png
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 100
    s = client.post(f"/api/shooting/sessions/{sid}/videos", content=mp4,
                    headers={"Content-Type": "video/mp4", "X-File-Name": "IMG_1.MOV"}).json()
    video = s["media"][1]
    assert (video["kind"], video["original_name"], video["file_size"]) == ("video", "IMG_1.MOV", len(mp4))
    assert client.get(video["url"]).content == mp4 and len(list((tmp_path / "videos").iterdir())) == 1
    assert client.post(f"/api/shooting/sessions/{sid}/videos", content=b"not a video",
                       headers={"Content-Type": "video/mp4"}).status_code == 422
    assert client.post(f"/api/shooting/sessions/{sid}/photos?group_id=999999", content=png,
                       headers={"Content-Type": "image/png"}).status_code == 422
    assert client.patch(f"/api/shooting/media/{video['media_id']}", json={"caption": "Prone"}).json()["media"][1]["caption"] == "Prone"
    feed = client.get("/api/activity").json()
    assert next(f for f in feed if f["kind"] == "shoot" and f["ref"] == sid)["photo_url"].startswith("/api/shooting/media/")
    client.delete(f"/api/shooting/sessions/{sid}")             # its video file goes too
    assert list((tmp_path / "videos").iterdir()) == []
