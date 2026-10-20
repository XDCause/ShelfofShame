"""To-do list (core): the small things to get done, under the big goals.

A to-do has a title, maybe notes, a due day, high priority, a hobby, a goal it moves forward, and can repeat (daily,
weekly, monthly): ticking a repeating one done adds the next, due one step after it was due (or after today, if it had
no day). Open ones come grouped by when: overdue, today, this week, later, no day.

    GET    /todos?show=open|done&limit=  open: soonest first (overdue, today, this week, later, no day; high priority
                                         first within a day); done: most recently done first
    GET    /todos/summary                counts for Home (open, overdue, today) + the next few
    POST   /todos                        a new one
    PATCH  /todos/{id}                   change it
    POST   /todos/{id}/done              tick it off (a repeating one adds its next)
    POST   /todos/{id}/undone            put it back
    DELETE /todos/{id}

(The tick boxes in journal pages are to-dos too: /journal/todos. The To-do page shows both.)
"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .db import MODULE_IDS, db, found, insert_row, tidy_text, update_row

router = APIRouter(prefix="/api", tags=["todos"])

Priority = Literal["normal", "high"]
Repeats = Literal["never", "daily", "weekly", "monthly"]

SELECT = """SELECT t.*, g.title AS goal_title,
       CASE WHEN t.done_at IS NOT NULL THEN 'done'
            WHEN t.due_on IS NULL THEN 'someday'
            WHEN t.due_on < current_date THEN 'overdue'
            WHEN t.due_on = current_date THEN 'today'
            WHEN t.due_on <= current_date + 6 THEN 'week'
            ELSE 'later' END AS bucket
FROM todos t LEFT JOIN goals g USING (goal_id)"""
OPEN_ORDER = """ORDER BY CASE WHEN t.due_on IS NULL THEN 1 ELSE 0 END, t.due_on, t.priority = 'high' DESC, t.created_at"""


class TodoIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    due_on: date | None = None
    priority: Priority = "normal"
    hobby: str | None = Field(None, max_length=40)
    goal_id: int | None = Field(None, ge=1, le=2_000_000_000)
    repeats: Repeats = "never"


class TodoPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    due_on: date | None = None
    priority: Priority | None = None
    hobby: str | None = Field(None, max_length=40)
    goal_id: int | None = Field(None, ge=1, le=2_000_000_000)
    repeats: Repeats | None = None


def check(conn, data: dict):
    if data.get("hobby") and data["hobby"] not in MODULE_IDS:
        raise HTTPException(422, f"Unknown hobby: {data['hobby']}.")
    if data.get("goal_id") and not conn.execute("SELECT 1 FROM goals WHERE goal_id = %s", (data["goal_id"],)).fetchone():
        raise HTTPException(422, "That goal doesn't exist.")


def fetch(conn, todo_id: int) -> dict:
    return found(conn.execute(SELECT + " WHERE t.todo_id = %s", (todo_id,)).fetchone(), "To-do")


def step(day: date, repeats: str) -> date:
    if repeats == "daily":
        return day + timedelta(days=1)
    if repeats == "weekly":
        return day + timedelta(days=7)
    month, year = day.month % 12 + 1, day.year + (day.month == 12)        # monthly: the same day next month...
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))                           # ...or that month's last day


def next_due(due: date | None, today: date, repeats: str) -> date:
    """The next one's day: steps on from when it was due (or today, with no day) until it's after today - a daily one
    three days behind comes back tomorrow, not in the past."""
    nxt = step(due or today, repeats)
    while nxt <= today:
        nxt = step(nxt, repeats)
    return nxt


@router.get("/todos")
def list_todos(show: Literal["open", "done"] = "open", limit: int = Query(200, ge=1, le=1000)):
    with db() as conn:
        if show == "done":
            return conn.execute(SELECT + " WHERE t.done_at IS NOT NULL ORDER BY t.done_at DESC LIMIT %s", (limit,)).fetchall()
        return conn.execute(SELECT + " WHERE t.done_at IS NULL " + OPEN_ORDER + " LIMIT %s", (limit,)).fetchall()


@router.get("/todos/summary")
def summary(limit: int = Query(8, ge=1, le=50)):
    """Home's card: how many are open / overdue / due today, and the next few."""
    with db() as conn:
        counts = conn.execute("""SELECT count(*)::int AS open,
                                        count(*) FILTER (WHERE due_on < current_date)::int AS overdue,
                                        count(*) FILTER (WHERE due_on = current_date)::int AS today
                                 FROM todos WHERE done_at IS NULL""").fetchone()
        nxt = conn.execute(SELECT + " WHERE t.done_at IS NULL " + OPEN_ORDER + " LIMIT %s", (limit,)).fetchall()
    return {**counts, "next": nxt}


@router.post("/todos", status_code=201)
def add_todo(body: TodoIn):
    data = tidy_text(body.model_dump(), required=("title",))
    with db() as conn:
        check(conn, data)
        todo_id = insert_row(conn, "todos", data, "todo_id")
        return fetch(conn, todo_id)


@router.patch("/todos/{todo_id}")
def update_todo(todo_id: int, body: TodoPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    for required in ("title", "priority", "repeats"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.capitalize()} can't be empty.")
    with db() as conn:
        fetch(conn, todo_id)
        check(conn, data)
        update_row(conn, "todos", "todo_id", todo_id, data)
        return fetch(conn, todo_id)


@router.post("/todos/{todo_id}/done")
def done(todo_id: int):
    """Ticked off. A repeating one adds its next (returned as `next`), with the same details."""
    with db() as conn:
        t = fetch(conn, todo_id)
        if t["done_at"]:
            return {"done": t, "next": None}
        conn.execute("UPDATE todos SET done_at = now() WHERE todo_id = %s", (todo_id,))
        nxt = None
        if t["repeats"] != "never":
            today = conn.execute("SELECT current_date AS d").fetchone()["d"]
            nid = insert_row(conn, "todos", {k: t[k] for k in ("title", "notes", "priority", "hobby", "goal_id", "repeats")}
                             | {"due_on": next_due(t["due_on"], today, t["repeats"])}, "todo_id")
            nxt = fetch(conn, nid)
        return {"done": fetch(conn, todo_id), "next": nxt}


@router.post("/todos/{todo_id}/undone")
def undone(todo_id: int):
    """Back on the list (a repeating one's next stays: it's its own to-do now)."""
    with db() as conn:
        fetch(conn, todo_id)
        conn.execute("UPDATE todos SET done_at = NULL WHERE todo_id = %s", (todo_id,))
        return fetch(conn, todo_id)


@router.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM todos WHERE todo_id = %s RETURNING todo_id", (todo_id,)).fetchone(), "To-do")
    return Response(status_code=204)
