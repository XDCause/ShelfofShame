"""The focus timer: start, pause, resume, finish; the time logged against the to-do and its goal; goals counting it."""
from app.db import db


def todo(client, **kw):
    return client.post("/api/todos", json={"title": "Prime the Sherman", **kw}).json()


def test_a_session_runs_pauses_and_logs_its_time_on_the_todo_and_goal(client):
    g = client.post("/api/goals", json={"title": "Finish the Sherman"}).json()
    t = todo(client, goal_id=g["goal_id"])
    assert client.get("/api/focus/current").json() is None
    s = client.post("/api/focus", json={"todo_id": t["todo_id"], "minutes": 25}).json()
    assert (s["status"], s["goal_id"], s["label"], s["minutes"]) == ("running", g["goal_id"], "Prime the Sherman", 25)
    assert 1490 <= s["remaining_seconds"] <= 1500
    assert client.get("/api/focus/current").json()["session_id"] == s["session_id"]
    assert client.post("/api/focus", json={"minutes": 5}).status_code == 409           # one at a time
    sid = s["session_id"]
    assert client.post(f"/api/focus/{sid}/resume").status_code == 409                   # not paused
    assert client.post(f"/api/focus/{sid}/pause").json()["status"] == "paused"
    assert client.post(f"/api/focus/{sid}/pause").status_code == 409
    assert client.post(f"/api/focus/{sid}/resume").json()["status"] == "running"
    # Started 10 minutes ago, 4 of them paused: 6 minutes were focused.
    with db() as conn:
        conn.execute("UPDATE focus_sessions SET paused_seconds = 240, started_at = now() - interval '10 minutes' WHERE session_id = %s", (sid,))
    done = client.post(f"/api/focus/{sid}/finish").json()
    assert done["status"] == "stopped" and 355 <= done["focused_seconds"] <= 365
    assert client.post(f"/api/focus/{sid}/finish").json()["focused_seconds"] == done["focused_seconds"]   # again: same answer
    assert client.get("/api/focus/current").json() is None
    for key, val in (("todo_id", t["todo_id"]), ("goal_id", g["goal_id"])):
        s = client.get(f"/api/focus/summary?{key}={val}").json()
        assert (s["sessions"], s["minutes"], s["week_minutes"]) == (1, 6, 6)
    assert client.get("/api/focus/summary").status_code == 422


def test_a_session_that_runs_out_is_done_and_goals_can_count_it(client):
    g = client.post("/api/goals", json={"title": "Focus", "kind": "habit", "habit_times": 30, "source": "focus_minutes"}).json()
    s = client.post("/api/focus", json={"goal_id": g["goal_id"], "minutes": 20}).json()
    with db() as conn:
        conn.execute("UPDATE focus_sessions SET started_at = now() - interval '30 minutes' WHERE session_id = %s", (s["session_id"],))
    assert client.get("/api/focus/current").json()["remaining_seconds"] == 0       # time's up (reading changes nothing)
    done = client.post(f"/api/focus/{s['session_id']}/finish").json()
    assert (done["status"], done["focused_seconds"]) == ("done", 1200)             # (never more than planned)
    g = client.get(f"/api/goals/{g['goal_id']}").json()
    assert g["habit"]["this"] == 20 and g["habit"]["left"] == 10


def test_bad_starts_are_refused(client):
    assert client.post("/api/focus", json={"todo_id": 999}).status_code == 404
    assert client.post("/api/focus", json={"goal_id": 999}).status_code == 404
    assert client.post("/api/focus", json={"minutes": 0}).status_code == 422
    assert client.post("/api/focus/999/finish").status_code == 404
    t = todo(client)
    s = client.post("/api/focus", json={"todo_id": t["todo_id"]}).json()
    client.delete(f"/api/todos/{t['todo_id']}")                                     # the to-do goes; the session stays
    assert client.get("/api/focus/current").json()["session_id"] == s["session_id"]
