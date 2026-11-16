"""Habit freezes and the weekly review."""
from datetime import timedelta

from app import goals
from app.db import db


def D(days):
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
    return (today + timedelta(days=days)).isoformat()


def habit(client):
    """A twice-a-week habit begun three weeks ago, done twice in the week before last."""
    g = client.post("/api/goals", json={"title": "Draw", "kind": "habit", "habit_times": 2, "started_on": D(-21)}).json()
    for _ in range(2):
        client.post(f"/api/goals/{g['goal_id']}/updates", json={"day": D(-14), "text": "Drew"})
    return client.get(f"/api/goals/{g['goal_id']}").json()


def test_a_freeze_keeps_the_streak_alive(client):
    g = habit(client)
    assert g["habit"]["streak"] == 0                                    # last week was missed
    f = client.post(f"/api/goals/{g['goal_id']}/freezes", json={"day": D(-7)})
    assert f.status_code == 201, f.text
    h = f.json()["habit"]
    assert h["streak"] == 1 and len(h["freezes"]["days"]) == 1
    assert [p["frozen"] for p in h["periods"][-3:]] == [False, True, False]
    assert client.post(f"/api/goals/{g['goal_id']}/freezes", json={"day": D(-7)}).status_code == 409   # that week is frozen
    with db() as conn:
        fid = conn.execute("SELECT freeze_id FROM habit_freezes").fetchone()["freeze_id"]
    assert client.delete(f"/api/goal-freezes/{fid}").json()["habit"]["streak"] == 0
    assert client.delete(f"/api/goal-freezes/{fid}").status_code == 404


def test_freezes_are_limited_and_only_for_habits(client, monkeypatch):
    g = habit(client)
    assert client.post(f"/api/goals/{g['goal_id']}/freezes", json={"day": D(1)}).status_code == 422     # not the future
    assert client.post(f"/api/goals/{g['goal_id']}/freezes", json={"day": D(-400)}).status_code == 422
    monkeypatch.setattr(goals, "FREEZES_PER_MONTH", 0)
    assert client.post(f"/api/goals/{g['goal_id']}/freezes", json={"day": D(-7)}).status_code == 409
    plain = client.post("/api/goals", json={"title": "Read"}).json()
    assert client.post(f"/api/goals/{plain['goal_id']}/freezes", json={}).status_code == 422
    assert client.post("/api/goals/999/freezes", json={}).status_code == 404


def test_the_weekly_review_and_saving_it(client):
    g = client.post("/api/goals", json={"title": "Draw", "kind": "habit", "habit_times": 2, "started_on": D(-30)}).json()
    quiet = client.post("/api/goals", json={"title": "Old goal", "started_on": D(-60)}).json()
    client.post(f"/api/goals/{g['goal_id']}/updates", json={"text": "Drew"})
    t = client.post("/api/todos", json={"title": "Buy primer", "goal_id": g["goal_id"]}).json()
    client.post(f"/api/todos/{t['todo_id']}/done")
    r = client.get("/api/goals/weekly-review").json()
    assert r["current"] and r["week_start"] <= D(0) <= r["week_end"]
    by = {x["goal_id"]: x for x in r["goals"]}
    assert by[g["goal_id"]]["moved"] and by[g["goal_id"]]["todos_done"] == 1 and by[g["goal_id"]]["habit"]["this"] == 1
    assert not by[quiet["goal_id"]]["moved"] and quiet["goal_id"] in r["slipping"]
    assert r["totals"]["todos_done"] == 1 and r["saved_page_id"] is None
    old = client.get(f"/api/goals/weekly-review?week={D(-14)}").json()
    assert not old["current"] and old["week_end"] < r["week_start"]
    saved = client.post("/api/goals/weekly-review", json={"note": "Good week.\nMore drawing."})
    assert saved.status_code == 201, saved.text
    page = client.get(f"/api/journal/{saved.json()['page_id']}").json()
    assert page["title"] == r["title"] and "weekly review" in page["tags"]
    assert "Good week." in page["text"] and "Draw:" in page["text"]
    assert client.get("/api/goals/weekly-review").json()["saved_page_id"] == page["page_id"]
