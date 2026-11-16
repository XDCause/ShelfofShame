"""Your day: a journal page's summary of one day's events, things logged, to-dos done and focus time."""
from app.db import db


def test_a_days_summary_gathers_events_todos_and_focus(client):
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
    client.post("/api/calendar/events", json={"title": "Volleyball", "hobby": "volleyball", "starts_on": today.isoformat(),
                                              "start_time": "19:00", "location": "Sports hall"})
    t = client.post("/api/todos", json={"title": "Order primer"}).json()
    client.post(f"/api/todos/{t['todo_id']}/done")
    s = client.post("/api/focus", json={"minutes": 10}).json()
    with db() as conn:
        conn.execute("UPDATE focus_sessions SET started_at = now() - interval '5 minutes' WHERE session_id = %s", (s["session_id"],))
    client.post(f"/api/focus/{s['session_id']}/finish")
    r = client.get(f"/api/journal/day-summary?day={today.isoformat()}")
    assert r.status_code == 200, r.text
    texts = {ln["kind"]: ln["text"] for ln in r.json()["lines"]}
    assert texts["event"] == "19:00 Volleyball (Sports hall)"
    assert texts["todo"] == "Done: Order primer"
    assert texts["focus"].startswith("Focused for 5 min")
    blocks = r.json()["blocks"]
    assert blocks[0]["type"] == "heading" and [b["type"] for b in blocks[1:]] == ["bulletListItem"] * 3


def test_a_quiet_day_says_so(client):
    r = client.get("/api/journal/day-summary?day=2020-01-01").json()
    assert r["lines"] == [] and r["blocks"][-1]["content"][0]["text"] == "Nothing logged for this day."
    assert client.get("/api/journal/day-summary").status_code == 200
    assert client.get("/api/journal/day-summary?day=nonsense").status_code == 422
