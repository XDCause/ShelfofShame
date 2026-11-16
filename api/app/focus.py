"""Focus timer (core): a stretch of focused work (25 minutes, or what you pick) on a to-do or a goal.

The start time is kept here, not in the browser, so a reload (or your phone) still shows the timer running. Only one
session runs at a time. When the time is up, the page finishes it (POST .../finish); the time then counts against
the goal / the to-do. A session stopped early counts what you did. Goals can also count it: goal source "focus_minutes".

    GET  /focus/current              the running (or paused) session with seconds left, or null. Never changes anything.
    GET  /focus/summary              ?todo_id= or ?goal_id=: minutes focused in all, this week, and the latest sessions
    POST /focus                      {todo_id | goal_id, minutes, label}: start (a to-do's goal comes with it)
    POST /focus/{id}/pause           pause the clock
    POST /focus/{id}/resume          carry on
    POST /focus/{id}/finish          done (the whole time was used) or stopped (some of it): logs what was focused
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .db import db, found, insert_row

router = APIRouter(prefix="/api", tags=["focus"])

GRACE_SECONDS = 3        # the page finishes a session the moment its clock hits 0: a hair before the server agrees

SELECT = "SELECT s.*, t.title AS todo_title, g.title AS goal_title FROM focus_sessions s " \
         "LEFT JOIN todos t USING (todo_id) LEFT JOIN goals g ON g.goal_id = s.goal_id"


class FocusIn(BaseModel):
    todo_id: int | None = Field(None, ge=1, le=2_000_000_000)
    goal_id: int | None = Field(None, ge=1, le=2_000_000_000)
    minutes: int = Field(25, ge=1, le=480)
    label: str | None = Field(None, max_length=120)


def active_seconds(s: dict, now: datetime) -> int:
    """Seconds actually focused so far: the clock minus the time spent paused (a paused session stops at its pause)."""
    end = s["ended_at"] or (s["paused_at"] if s["status"] == "paused" and s["paused_at"] else now)
    return max(0, int((end - s["started_at"]).total_seconds()) - s["paused_seconds"])


def shaped(s: dict, now: datetime) -> dict:
    used = active_seconds(s, now)
    s = dict(s)
    s["elapsed_seconds"] = s["focused_seconds"] if s["focused_seconds"] is not None else min(used, s["minutes"] * 60)
    s["remaining_seconds"] = max(0, s["minutes"] * 60 - used)
    return s


def now_of(conn) -> datetime:
    return conn.execute("SELECT now() AS n").fetchone()["n"]


def fetch(conn, session_id: int) -> dict:
    return found(conn.execute(SELECT + " WHERE s.session_id = %s", (session_id,)).fetchone(), "Focus session")


def current(conn) -> dict | None:
    return conn.execute(SELECT + " WHERE s.status IN ('running', 'paused') ORDER BY s.started_at DESC LIMIT 1").fetchone()


@router.get("/focus/current")
def get_current():
    """The session that's running (or paused). `remaining_seconds` is 0 when its time is up (the page then finishes it)."""
    with db() as conn:
        s = current(conn)
        return shaped(s, now_of(conn)) if s else None


@router.get("/focus/summary")
def summary(todo_id: int | None = Query(None, ge=1, le=2_000_000_000), goal_id: int | None = Query(None, ge=1, le=2_000_000_000)):
    """Time focused on one to-do or goal (finished sessions only): all-time, this week (from Monday), and the latest."""
    if (todo_id is None) == (goal_id is None):
        raise HTTPException(422, "Give a todo_id or a goal_id.")
    col, val = ("s.todo_id", todo_id) if todo_id is not None else ("s.goal_id", goal_id)
    with db() as conn:
        rows = conn.execute(SELECT + f" WHERE {col} = %s AND s.status IN ('done', 'stopped') ORDER BY s.started_at DESC", (val,)).fetchall()
        week = conn.execute("SELECT date_trunc('week', current_date)::date AS d").fetchone()["d"]
    total = sum(r["focused_seconds"] or 0 for r in rows)
    this_week = sum(r["focused_seconds"] or 0 for r in rows if r["started_at"].date() >= week)
    return {"sessions": len(rows), "minutes": round(total / 60), "week_minutes": round(this_week / 60),
            "latest": [{"session_id": r["session_id"], "started_at": r["started_at"], "minutes": round((r["focused_seconds"] or 0) / 60),
                        "status": r["status"], "label": r["label"], "todo_title": r["todo_title"]} for r in rows[:8]]}


@router.post("/focus", status_code=201)
def start(body: FocusIn):
    data = body.model_dump()
    if data["label"] is not None:
        data["label"] = data["label"].strip() or None
    with db() as conn:
        if current(conn):
            raise HTTPException(409, "A focus session is already running. Finish it first.")
        if data["todo_id"]:
            todo = found(conn.execute("SELECT goal_id, title FROM todos WHERE todo_id = %s", (data["todo_id"],)).fetchone(), "To-do")
            data["goal_id"] = data["goal_id"] or todo["goal_id"]
            data["label"] = data["label"] or todo["title"][:120]
        if data["goal_id"]:
            goal = found(conn.execute("SELECT title FROM goals WHERE goal_id = %s", (data["goal_id"],)).fetchone(), "Goal")
            data["label"] = data["label"] or goal["title"][:120]
        session_id = insert_row(conn, "focus_sessions", data, "session_id")
        return shaped(fetch(conn, session_id), now_of(conn))


def _live(conn, session_id: int, wanted: tuple[str, ...], said: str) -> dict:
    s = fetch(conn, session_id)
    if s["status"] not in wanted:
        raise HTTPException(409, said)
    return s


@router.post("/focus/{session_id}/pause")
def pause(session_id: int):
    with db() as conn:
        _live(conn, session_id, ("running",), "That session isn't running.")
        conn.execute("UPDATE focus_sessions SET status = 'paused', paused_at = now() WHERE session_id = %s", (session_id,))
        return shaped(fetch(conn, session_id), now_of(conn))


@router.post("/focus/{session_id}/resume")
def resume(session_id: int):
    with db() as conn:
        _live(conn, session_id, ("paused",), "That session isn't paused.")
        conn.execute("UPDATE focus_sessions SET status = 'running', "
                     "paused_seconds = paused_seconds + extract(epoch FROM now() - paused_at)::int, paused_at = NULL "
                     "WHERE session_id = %s", (session_id,))
        return shaped(fetch(conn, session_id), now_of(conn))


@router.post("/focus/{session_id}/finish")
def finish(session_id: int):
    """Done when the whole time was used, stopped when it's cut short; either way what was focused is kept.
    Finishing one that's already finished just answers with it (the page and a second tab may both ask)."""
    with db() as conn:
        s = fetch(conn, session_id)
        if s["status"] in ("done", "stopped"):
            return shaped(s, now_of(conn))
        now = now_of(conn)
        planned = s["minutes"] * 60
        used = min(active_seconds(s, now), planned)
        status: Literal["done", "stopped"] = "done" if used >= planned - GRACE_SECONDS else "stopped"
        used = planned if status == "done" else used       # (the page asks a moment before the server's clock agrees)
        conn.execute("UPDATE focus_sessions SET status = %s, ended_at = now(), focused_seconds = %s WHERE session_id = %s",
                     (status, used, session_id))
        return shaped(fetch(conn, session_id), now_of(conn))
