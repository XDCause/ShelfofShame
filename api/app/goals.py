"""Goals (core): what you're aiming for, in as much detail as you like - why it matters, the plan,
steps to tick off, a number to track and dated progress notes.

    GET    /goals                    every goal (pinned, then active by target day, then paused, done, dropped)
    POST   /goals                    a new goal (steps: a list of texts, optional)
    GET    /goals/{id}               one goal with its steps and progress notes
    PATCH  /goals/{id}               change it; status done fills done_on (today), leaving done clears it
    DELETE /goals/{id}
    POST   /goals/{id}/steps         {text}
    PATCH  /goal-steps/{id}          {text, done}
    DELETE /goal-steps/{id}
    PUT    /goals/{id}/steps/order   {step_ids} in the new order
    POST   /goals/{id}/updates       {day, text, value} - a value moves the goal's current value
    DELETE /goal-updates/{id}

progress (0-1) = how far the number has moved from start to target when there is one, else the steps
ticked, else none.
"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from .db import MODULE_IDS, db, found, insert_row, tidy_text, update_row

router = APIRouter(prefix="/api", tags=["goals"])

Status = Literal["active", "paused", "done", "dropped"]
STATUSES = ["active", "paused", "done", "dropped"]


class GoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    hobby: str | None = Field(None, max_length=40)
    why: str | None = Field(None, max_length=5000)
    details: str | None = Field(None, max_length=50000)
    status: Status = "active"
    target_date: date | None = None
    unit: str | None = Field(None, max_length=40)
    start_value: float | None = None
    target_value: float | None = None
    current_value: float | None = None
    pinned: bool = False
    started_on: date | None = None
    steps: list[str] = Field(default_factory=list, max_length=100)


class GoalPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    hobby: str | None = Field(None, max_length=40)
    why: str | None = Field(None, max_length=5000)
    details: str | None = Field(None, max_length=50000)
    status: Status | None = None
    target_date: date | None = None
    unit: str | None = Field(None, max_length=40)
    start_value: float | None = None
    target_value: float | None = None
    current_value: float | None = None
    pinned: bool | None = None
    started_on: date | None = None
    done_on: date | None = None


class StepIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class StepPatch(BaseModel):
    text: str | None = Field(None, min_length=1, max_length=500)
    done: bool | None = None


class StepOrder(BaseModel):
    step_ids: list[int] = Field(max_length=100)


class UpdateIn(BaseModel):
    day: date | None = None
    text: str | None = Field(None, max_length=10000)
    value: float | None = None


GOAL_SELECT = """
SELECT g.*,
       (SELECT count(*) FROM goal_steps s WHERE s.goal_id = g.goal_id) AS steps_total,
       (SELECT count(*) FROM goal_steps s WHERE s.goal_id = g.goal_id AND s.done) AS steps_done,
       (SELECT s.text FROM goal_steps s WHERE s.goal_id = g.goal_id AND NOT s.done ORDER BY s.sort_order, s.step_id LIMIT 1) AS next_step,
       (SELECT max(u.day) FROM goal_updates u WHERE u.goal_id = g.goal_id) AS last_update,
       CASE WHEN g.status = 'active' THEN g.target_date - current_date END AS days_left
FROM goals g"""
ORDER = """ ORDER BY g.pinned DESC, array_position(ARRAY['active', 'paused', 'done', 'dropped'], g.status),
            g.target_date NULLS LAST, g.done_on DESC NULLS LAST, lower(g.title)"""


def progress(g: dict) -> float | None:
    """0-1: the number from start to target if both are set, else the steps ticked, else None."""
    if g["target_value"] is not None and g["current_value"] is not None:
        start = float(g["start_value"] or 0)
        span = float(g["target_value"]) - start
        if span:
            return max(0.0, min(1.0, (float(g["current_value"]) - start) / span))
        return 1.0 if float(g["current_value"]) == start else 0.0
    if g["steps_total"]:
        return g["steps_done"] / g["steps_total"]
    return None


def shaped(g: dict) -> dict:
    g = dict(g)
    for k in ("start_value", "target_value", "current_value"):
        if g[k] is not None:
            g[k] = float(g[k])
    g["progress"] = progress(g)
    return g


def today(conn) -> date:
    """Today where you are (the database runs on Brisbane time; this container on UTC)."""
    return conn.execute("SELECT current_date AS d").fetchone()["d"]


def fetch(conn, goal_id: int) -> dict:
    g = shaped(found(conn.execute(GOAL_SELECT + " WHERE g.goal_id = %s", (goal_id,)).fetchone(), "Goal"))
    g["steps"] = conn.execute("SELECT * FROM goal_steps WHERE goal_id = %s ORDER BY sort_order, step_id", (goal_id,)).fetchall()
    g["updates"] = [{**u, "value": float(u["value"]) if u["value"] is not None else None} for u in conn.execute(
        "SELECT * FROM goal_updates WHERE goal_id = %s ORDER BY day DESC, created_at DESC", (goal_id,)).fetchall()]
    return g


def check_hobby(data: dict):
    if data.get("hobby") and data["hobby"] not in MODULE_IDS:
        raise HTTPException(422, f"Unknown hobby: {data['hobby']}.")


@router.get("/goals")
def list_goals(status: Status | None = None):
    with db() as conn:
        rows = conn.execute(GOAL_SELECT + (" WHERE g.status = %s" if status else "") + ORDER,
                            (status,) if status else ()).fetchall()
        goals = [shaped(g) for g in rows]
        return {"goals": goals, "statuses": STATUSES,
                "counts": {s: sum(1 for g in goals if g["status"] == s) for s in STATUSES}}


@router.post("/goals", status_code=201)
def add_goal(body: GoalIn):
    data = tidy_text(body.model_dump(exclude={"steps"}), required=("title",))
    check_hobby(data)
    if data["started_on"] is None:
        data.pop("started_on")
    steps = [s.strip() for s in body.steps if s and s.strip()]
    with db() as conn:
        if data["status"] == "done":
            data["done_on"] = today(conn)
        goal_id = insert_row(conn, "goals", data, "goal_id")
        for i, text in enumerate(steps):
            conn.execute("INSERT INTO goal_steps (goal_id, text, sort_order) VALUES (%s, %s, %s)", (goal_id, text, i))
        return fetch(conn, goal_id)


@router.get("/goals/{goal_id}")
def get_goal(goal_id: int):
    with db() as conn:
        return fetch(conn, goal_id)


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    for field in ("title", "status", "pinned", "started_on"):
        if field in data and data[field] is None:
            raise HTTPException(422, f"{field} can't be empty.")
    check_hobby(data)
    with db() as conn:
        goal = fetch(conn, goal_id)
        if data.get("status") == "done" and goal["status"] != "done":
            data.setdefault("done_on", today(conn))
        elif "status" in data and data["status"] != "done":
            data["done_on"] = None
        update_row(conn, "goals", "goal_id", goal_id, data)
        return fetch(conn, goal_id)


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int):
    with db() as conn:
        if not conn.execute("DELETE FROM goals WHERE goal_id = %s", (goal_id,)).rowcount:
            raise HTTPException(404, "Goal not found.")
    return Response(status_code=204)


@router.post("/goals/{goal_id}/steps", status_code=201)
def add_step(goal_id: int, body: StepIn):
    with db() as conn:
        fetch(conn, goal_id)
        conn.execute("""INSERT INTO goal_steps (goal_id, text, sort_order)
                        VALUES (%s, %s, (SELECT COALESCE(max(sort_order) + 1, 0) FROM goal_steps WHERE goal_id = %s))""",
                     (goal_id, body.text.strip(), goal_id))
        return fetch(conn, goal_id)


def _step_goal(conn, step_id: int) -> int:
    return found(conn.execute("SELECT goal_id FROM goal_steps WHERE step_id = %s", (step_id,)).fetchone(), "Step")["goal_id"]


@router.patch("/goal-steps/{step_id}")
def update_step(step_id: int, body: StepPatch):
    data = body.model_dump(exclude_unset=True)
    if any(data.get(k, 0) is None for k in ("text", "done")):
        raise HTTPException(422, "A step needs its text and done.")
    with db() as conn:
        goal_id = _step_goal(conn, step_id)
        if "text" in data:
            data["text"] = data["text"].strip()
        if "done" in data:
            data["done_on"] = today(conn) if data["done"] else None
        update_row(conn, "goal_steps", "step_id", step_id, data)
        return fetch(conn, goal_id)


@router.delete("/goal-steps/{step_id}")
def delete_step(step_id: int):
    with db() as conn:
        goal_id = _step_goal(conn, step_id)
        conn.execute("DELETE FROM goal_steps WHERE step_id = %s", (step_id,))
        return fetch(conn, goal_id)


@router.put("/goals/{goal_id}/steps/order")
def order_steps(goal_id: int, body: StepOrder):
    with db() as conn:
        fetch(conn, goal_id)
        mine = {r["step_id"] for r in conn.execute("SELECT step_id FROM goal_steps WHERE goal_id = %s", (goal_id,)).fetchall()}
        if set(body.step_ids) != mine or len(body.step_ids) != len(mine):
            raise HTTPException(422, "Send every step of this goal once.")
        for i, step_id in enumerate(body.step_ids):
            conn.execute("UPDATE goal_steps SET sort_order = %s WHERE step_id = %s", (i, step_id))
        return fetch(conn, goal_id)


def _latest_value(conn, goal_id: int):
    """The goal's current value follows its latest progress note that has a number."""
    row = conn.execute("""SELECT value FROM goal_updates WHERE goal_id = %s AND value IS NOT NULL
                          ORDER BY day DESC, created_at DESC LIMIT 1""", (goal_id,)).fetchone()
    if row:
        conn.execute("UPDATE goals SET current_value = %s WHERE goal_id = %s", (row["value"], goal_id))


@router.post("/goals/{goal_id}/updates", status_code=201)
def add_update(goal_id: int, body: UpdateIn):
    text = (body.text or "").strip() or None
    if text is None and body.value is None:
        raise HTTPException(422, "Write something or give a number.")
    with db() as conn:
        fetch(conn, goal_id)
        conn.execute("INSERT INTO goal_updates (goal_id, day, text, value) VALUES (%s, COALESCE(%s, current_date), %s, %s)",
                     (goal_id, body.day, text, body.value))
        if body.value is not None:
            _latest_value(conn, goal_id)
        return fetch(conn, goal_id)


@router.delete("/goal-updates/{update_id}")
def delete_update(update_id: int):
    with db() as conn:
        row = found(conn.execute("DELETE FROM goal_updates WHERE update_id = %s RETURNING goal_id, value", (update_id,)).fetchone(),
                    "Progress note")
        if row["value"] is not None:
            _latest_value(conn, row["goal_id"])
        return fetch(conn, row["goal_id"])
