"""The to-do list: added, grouped by when, ticked off (a repeating one adds its next), put back, changed, removed;
linked to a goal and a hobby; Home's summary."""
from datetime import date, timedelta

import pytest

from app.db import db
from app.todos import next_due


def D(days):
    """A day from today - the database's today (Brisbane), as the app's; this container runs on UTC."""
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
    return (today + timedelta(days=days)).isoformat()


def add(client, **kw):
    r = client.post("/api/todos", json={"title": "Prime the Sherman", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_open_ones_come_soonest_first_in_groups(client):
    add(client, title="Someday", due_on=None)
    add(client, title="Later", due_on=D(20))
    add(client, title="This week", due_on=D(3))
    add(client, title="Today, normal", due_on=D(0))
    add(client, title="Today, high", due_on=D(0), priority="high")
    add(client, title="Overdue", due_on=D(-2))
    todos = client.get("/api/todos").json()
    assert [t["title"] for t in todos] == ["Overdue", "Today, high", "Today, normal", "This week", "Later", "Someday"]
    assert [t["bucket"] for t in todos] == ["overdue", "today", "today", "week", "later", "someday"]
    s = client.get("/api/todos/summary?limit=3").json()
    assert (s["open"], s["overdue"], s["today"]) == (6, 1, 2) and len(s["next"]) == 3


def test_ticked_off_put_back_changed_removed(client):
    t = add(client, notes="  grey primer ")
    assert t["notes"] == "grey primer" and t["priority"] == "normal" and t["repeats"] == "never"
    r = client.post(f"/api/todos/{t['todo_id']}/done").json()
    assert r["done"]["done_at"] and r["done"]["bucket"] == "done" and r["next"] is None
    assert client.get("/api/todos").json() == [] and len(client.get("/api/todos?show=done").json()) == 1
    assert client.post(f"/api/todos/{t['todo_id']}/done").json()["next"] is None       # twice: nothing more happens
    assert client.post(f"/api/todos/{t['todo_id']}/undone").json()["done_at"] is None
    changed = client.patch(f"/api/todos/{t['todo_id']}", json={"title": " Prime it ", "priority": "high", "due_on": D(1)}).json()
    assert (changed["title"], changed["priority"], changed["due_on"]) == ("Prime it", "high", D(1))
    for field in ("title", "priority", "repeats"):
        assert client.patch(f"/api/todos/{t['todo_id']}", json={field: None}).status_code == 422
    assert client.patch(f"/api/todos/{t['todo_id']}", json={"due_on": None}).json()["bucket"] == "someday"   # a day can go
    assert client.delete(f"/api/todos/{t['todo_id']}").status_code == 204
    assert client.delete(f"/api/todos/{t['todo_id']}").status_code == 404


def test_a_repeating_one_adds_its_next(client):
    t = add(client, title="Water the basil", due_on=D(0), repeats="daily", priority="high", hobby="gardening")
    r = client.post(f"/api/todos/{t['todo_id']}/done").json()
    nxt = r["next"]
    assert nxt["due_on"] == D(1) and nxt["title"] == "Water the basil" and nxt["repeats"] == "daily"
    assert (nxt["priority"], nxt["hobby"]) == ("high", "gardening")
    assert [x["todo_id"] for x in client.get("/api/todos").json()] == [nxt["todo_id"]]


@pytest.mark.parametrize("due,today,repeats,expect", [
    (date(2026, 10, 20), date(2026, 10, 20), "daily", date(2026, 10, 21)),
    (date(2026, 10, 17), date(2026, 10, 20), "daily", date(2026, 10, 21)),     # three days behind: tomorrow, not the past
    (date(2026, 10, 20), date(2026, 10, 20), "weekly", date(2026, 10, 27)),
    (date(2026, 10, 18), date(2026, 10, 20), "weekly", date(2026, 10, 25)),    # a step on from when it was due
    (None, date(2026, 10, 20), "weekly", date(2026, 10, 27)),                  # no day: a step after today
    (date(2026, 1, 31), date(2026, 1, 31), "monthly", date(2026, 2, 28)),       # no 31 February: the month's last day
    (date(2026, 12, 15), date(2026, 12, 15), "monthly", date(2027, 1, 15)),     # into the next year
])
def test_when_the_next_one_is_due(due, today, repeats, expect):
    assert next_due(due, today, repeats) == expect


def test_linked_to_a_goal_and_a_hobby(client):
    goal = client.post("/api/goals", json={"title": "Finish three kits"}).json()
    t = add(client, goal_id=goal["goal_id"], hobby="models")
    assert (t["goal_title"], t["hobby"]) == ("Finish three kits", "models")
    assert client.post("/api/todos", json={"title": "x", "hobby": "knitting"}).status_code == 422
    assert client.post("/api/todos", json={"title": "x", "goal_id": 999999}).status_code == 422
    client.delete(f"/api/goals/{goal['goal_id']}")
    assert client.get("/api/todos").json()[0]["goal_id"] is None                 # the goal gone: the to-do stays
    assert client.post("/api/todos", json={"title": ""}).status_code == 422
    assert client.post("/api/todos", json={"title": "x", "repeats": "hourly"}).status_code == 422
