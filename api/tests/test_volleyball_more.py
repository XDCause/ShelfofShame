"""Volleyball, more: serve / pass ratings, rotations, clips tagged by skill and outcome, and drill results."""
from datetime import date, timedelta

from app.db import db
from app.vbstats import best_result, rating_trend, rotation_table, week_of, weekly_volume


def game(client, **more):
    r = client.post("/api/volleyball/games", json={"opponent": "Spikers", **more})
    assert r.status_code == 201, r.text
    return r.json()["game_id"]


def test_ratings_per_game_and_overall(client):
    g = game(client, played_on="2026-10-01")
    for score in (3, 2, 3):
        r = client.post(f"/api/volleyball/games/{g}/ratings", json={"skill": "serve", "score": score})
        assert r.status_code == 201
    done = client.post(f"/api/volleyball/games/{g}/ratings", json={"skill": "pass", "score": 1}).json()
    assert done["serve"] == {"n": 3, "avg": 2.67, "counts": [0, 0, 1, 2]} and done["pass"]["avg"] == 1.0
    assert client.post(f"/api/volleyball/games/{g}/ratings", json={"skill": "serve", "score": 4}).status_code == 422
    assert client.post(f"/api/volleyball/games/{g}/ratings", json={"skill": "set", "score": 1}).status_code == 422
    assert client.post("/api/volleyball/games/99999/ratings", json={"skill": "serve", "score": 1}).status_code == 404
    last = done["entries"][-1]["rating_id"]
    assert client.delete(f"/api/volleyball/ratings/{last}").json()["pass"]["n"] == 0
    assert client.delete(f"/api/volleyball/ratings/{last}").status_code == 404
    g2 = game(client, played_on="2026-10-08")
    client.post(f"/api/volleyball/games/{g2}/ratings", json={"skill": "serve", "score": 0})
    s = client.get("/api/volleyball/ratings").json()
    assert s["serve"]["n"] == 4 and s["serve"]["avg"] == 2.0 and [x["avg"] for x in s["serve"]["games"]] == [2.67, 0.0]
    assert s["serve"]["trend"] == -2.67 and s["pass"]["n"] == 0 and s["pass"]["trend"] is None
    # deleting the game takes its ratings
    client.delete(f"/api/volleyball/games/{g2}")
    assert client.get("/api/volleyball/ratings").json()["serve"]["n"] == 3


def test_trend_helper():
    assert rating_trend([]) is None and rating_trend([{"avg": 2, "n": 3}]) is None
    games = [{"avg": 1.0, "n": 2}, {"avg": 3.0, "n": 2}]
    assert rating_trend(games) == 2.0                                   # two games: the second against the first
    many = [{"avg": 1.0, "n": 1}] * 5 + [{"avg": 2.0, "n": 1}] * 5
    assert rating_trend(many) == 1.0


def test_rotation_table_and_endpoints(client):
    rows = rotation_table([{"rotation": 1, "serving": False, "won": True}, {"rotation": 1, "serving": False, "won": False},
                           {"rotation": 1, "serving": True, "won": True}, {"rotation": 2, "serving": True, "won": False}])
    assert (rows[0]["side_out_percent"], rows[0]["point_percent"], rows[1]["point_percent"], rows[2]["side_out_percent"]) == (50, 100, 0, None)
    g = game(client)
    client.post(f"/api/volleyball/games/{g}/points", json={"rotation": 3, "serving": False, "won": True})
    out = client.post(f"/api/volleyball/games/{g}/points", json={"rotation": 3, "serving": True, "won": True}).json()
    assert len(out["points"]) == 2 and out["rotations"][2]["side_out_percent"] == 100 and out["rotations"][2]["point_percent"] == 100
    assert client.post(f"/api/volleyball/games/{g}/points", json={"rotation": 7, "serving": True, "won": True}).status_code == 422
    all_ = client.get("/api/volleyball/rotations").json()
    assert (all_["rallies"], all_["games"], all_["side_out_percent"], all_["point_percent"]) == (2, 1, 100, 100)
    after = client.delete(f"/api/volleyball/points/{out['points'][0]['point_id']}").json()
    assert len(after["points"]) == 1 and client.delete("/api/volleyball/points/99999").status_code == 404
    assert client.get("/api/volleyball/games/99999/points").status_code == 404


def video_with_file(client, title="Game"):
    video = client.post("/api/volleyball/videos", json={"title": title}).json()
    with db() as conn:
        conn.execute("UPDATE volleyball_videos SET file_name = %s, file_type = 'video/mp4', file_size = 1 WHERE video_id = %s",
                     (f"{video['video_id']}-abc.mp4", video["video_id"]))
    return video["video_id"]


def test_clips_tagged_and_filtered(client):
    v = video_with_file(client)
    a = client.post(f"/api/volleyball/videos/{v}/clips", json={"title": "Ace", "start": 1, "end": 3, "skill": "serve", "outcome": "good"}).json()
    client.post(f"/api/volleyball/videos/{v}/clips", json={"title": "Into the net", "start": 5, "end": 7, "skill": "serve", "outcome": "error"})
    client.post(f"/api/volleyball/videos/{v}/clips", json={"start": 9, "end": 10})
    assert (a["skill"], a["outcome"]) == ("serve", "good")
    assert client.post(f"/api/volleyball/videos/{v}/clips", json={"start": 1, "end": 2, "skill": "juggle"}).status_code == 422
    everything = client.get("/api/volleyball/clips").json()
    assert len(everything["clips"]) == 3 and everything["clips"][0]["file_url"].startswith("/api/volleyball/videos/")
    errors = client.get("/api/volleyball/clips?skill=serve&outcome=error").json()["clips"]
    assert [c["title"] for c in errors] == ["Into the net"]
    assert {(c["skill"], c["outcome"], c["n"]) for c in everything["counts"]} == {("serve", "good", 1), ("serve", "error", 1), (None, None, 1)}
    # retagging keeps the times; tags can be cleared
    moved = client.patch(f"/api/volleyball/clips/{a['clip_id']}", json={"skill": "attack"}).json()
    assert (moved["skill"], moved["outcome"], moved["start"]) == ("attack", "good", 1.0)
    cleared = client.patch(f"/api/volleyball/clips/{a['clip_id']}", json={"outcome": None}).json()
    assert cleared["outcome"] is None and cleared["skill"] == "attack"
    assert client.get("/api/volleyball/clips?skill=juggle").status_code == 422


def test_drill_helpers():
    assert best_result([], False) is None and best_result([3, 9, 5], False) == 9 and best_result([30, 22, 25], True) == 22
    assert week_of(date(2026, 11, 16)) == date(2026, 11, 16) and week_of(date(2026, 11, 22)) == date(2026, 11, 16)
    today = date(2026, 11, 18)
    logs = [{"done_on": date(2026, 11, 17), "reps": 30, "minutes": 10}, {"done_on": date(2026, 11, 10), "reps": 20, "minutes": None},
            {"done_on": date(2026, 11, 11), "reps": None, "minutes": 5}, {"done_on": date(2026, 1, 1), "reps": 99, "minutes": 1}]
    weeks = weekly_volume(logs, today, 3)
    assert [w["week"] for w in weeks] == [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16)]
    assert [(w["reps"], w["minutes"], w["sessions"]) for w in weeks] == [(0, 0, 0), (20, 5, 2), (30, 10, 1)]


def test_drill_logs_best_and_volume(client):
    drill = client.post("/api/volleyball/coach", json={"kind": "drill", "title": "Wall sets"}).json()
    fix = client.post("/api/volleyball/coach", json={"kind": "fix", "title": "Toss"}).json()
    n = drill["note_id"]
    assert client.post(f"/api/volleyball/coach/{n}/logs", json={}).status_code == 422          # nothing to log
    assert client.post(f"/api/volleyball/coach/{fix['note_id']}/logs", json={"reps": 5}).status_code == 404   # only drills
    yesterday = str(date.today() - timedelta(days=1))
    client.post(f"/api/volleyball/coach/{n}/logs", json={"done_on": yesterday, "result": 12, "reps": 40, "minutes": 10})
    out = client.post(f"/api/volleyball/coach/{n}/logs", json={"result": 18, "reps": 50}).json()
    assert (out["best"], out["sessions"], out["reps"], out["minutes"]) == (18.0, 2, 90, 10) and len(out["logs"]) == 2
    low = client.put(f"/api/volleyball/coach/{n}/result", json={"result_label": " seconds ", "lower_is_better": True}).json()
    assert (low["best"], low["result_label"]) == (12.0, "seconds")
    stats = client.get("/api/volleyball/drills").json()
    assert [d["title"] for d in stats["drills"]] == ["Wall sets"] and stats["drills"][0]["best"] == 12.0
    assert sum(w["reps"] for w in stats["weeks"]) == 90 and len(stats["weeks"]) == 8
    log_id = out["logs"][0]["log_id"]
    assert client.delete(f"/api/volleyball/drill-logs/{log_id}").status_code == 204
    assert client.delete(f"/api/volleyball/drill-logs/{log_id}").status_code == 404
    assert client.get(f"/api/volleyball/coach/{n}/logs").json()["sessions"] == 1
    assert client.get("/api/volleyball/coach/99999/logs").status_code == 404
