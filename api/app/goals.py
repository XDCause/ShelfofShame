"""Goals (core): what you're aiming for, in as much detail as you like - why it matters, the plan, a number to track
(or one the app counts for you), the to-dos that get you there, dated progress notes - and whether you're on track.

    timeframe: 'year' (a year's goals - New Year's goals) or 'three_years' (period_start .. + 2), or none.
    A goal for a set time aims for the end of it (31 December) unless you pick another day.
    kind: 'target' (reach a number, or finish its to-dos) or 'habit' (habit_times a habit_every week / month).
    source: what the goal counts by itself (goal_sources.py: books finished, km hiked, a chess rating...); none = you
    give the number (a progress note with a number moves it).
    parent_id: a bigger goal this one feeds into (a year's goal under a 3-year goal); a goal with no number or to-dos
    of its own moves with the goals inside it.

    GET    /goals                    every goal (pinned, then active by target day, then paused, done, dropped)
    POST   /goals                    a new goal (steps: texts that become its to-dos, optional)
    GET    /goals/sources            what a goal can count by itself
    GET    /goals/nudges             goals that haven't moved in 3 weeks, and whether it's time for the monthly check-in
    POST   /goals/checkin-seen       the monthly check-in dismissed (until next month)
    GET    /goals/{id}               one goal with its to-dos, progress notes, history (for the chart), the goals inside it
    PATCH  /goals/{id}               change it; status done fills done_on (today), leaving done clears it
    DELETE /goals/{id}               (its to-dos stay on your list, no longer under a goal)
    POST   /goals/{id}/updates       {day, text, value} - a value moves the goal's current value (or, for a habit
                                     with no source, a note counts as one time)
    DELETE /goal-updates/{id}

progress (0-1): the number from start to target; else the to-dos ticked; else the goals inside it, on average. A
habit: this week's / month's times out of its aim. pace (a target with a day to reach it): where you'd be by today
if you went evenly - ahead, on track or behind, and how much a month it takes from here.
"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import goal_sources
from .db import MODULE_IDS, db, found, insert_row, tidy_text, update_row

router = APIRouter(prefix="/api", tags=["goals"])

Status = Literal["active", "paused", "done", "dropped"]
Timeframe = Literal["year", "three_years"]
Kind = Literal["target", "habit", "milestone"]       # milestone: yes or no - done, or not yet (no number, no pace)
Every = Literal["week", "month"]
YEARS = {"year": 1, "three_years": 3}
STATUSES = ["active", "paused", "done", "dropped"]
STALE_DAYS = 21              # a goal that hasn't moved this long gets a nudge on Home (user, 2026-10-21: 3 weeks)
ON_TRACK = 0.05              # within 5% of where an even pace would be = on track


class GoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    hobby: str | None = Field(None, max_length=40)
    why: str | None = Field(None, max_length=5000)
    details: str | None = Field(None, max_length=50000)
    status: Status = "active"
    target_date: date | None = None
    unit: str | None = Field(None, max_length=40)
    start_value: float | None = Field(None, ge=-1e12, le=1e12)
    target_value: float | None = Field(None, ge=-1e12, le=1e12)
    current_value: float | None = Field(None, ge=-1e12, le=1e12)
    pinned: bool = False
    started_on: date | None = None
    timeframe: Timeframe | None = None
    period_start: int | None = Field(None, ge=2000, le=2200)     # the year; empty = this year
    kind: Kind = "target"
    source: str | None = Field(None, max_length=40)
    habit_times: int | None = Field(None, ge=1, le=1000)
    habit_every: Every | None = None
    parent_id: int | None = Field(None, ge=1, le=2_000_000_000)
    steps: list[str] = Field(default_factory=list, max_length=100)     # become the goal's to-dos


class GoalPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    hobby: str | None = Field(None, max_length=40)
    why: str | None = Field(None, max_length=5000)
    details: str | None = Field(None, max_length=50000)
    status: Status | None = None
    target_date: date | None = None
    unit: str | None = Field(None, max_length=40)
    start_value: float | None = Field(None, ge=-1e12, le=1e12)
    target_value: float | None = Field(None, ge=-1e12, le=1e12)
    current_value: float | None = Field(None, ge=-1e12, le=1e12)
    pinned: bool | None = None
    started_on: date | None = None
    done_on: date | None = None
    timeframe: Timeframe | None = None
    period_start: int | None = Field(None, ge=2000, le=2200)
    kind: Kind | None = None
    source: str | None = Field(None, max_length=40)
    habit_times: int | None = Field(None, ge=1, le=1000)
    habit_every: Every | None = None
    parent_id: int | None = Field(None, ge=1, le=2_000_000_000)


class UpdateIn(BaseModel):
    day: date | None = None
    text: str | None = Field(None, max_length=10000)
    value: float | None = Field(None, ge=-1e12, le=1e12)


GOAL_SELECT = """
SELECT g.*, p.title AS parent_title,
       (SELECT count(*)::int FROM todos t WHERE t.goal_id = g.goal_id) AS todos_total,
       (SELECT count(*)::int FROM todos t WHERE t.goal_id = g.goal_id AND t.done_at IS NOT NULL) AS todos_done,
       (SELECT t.title FROM todos t WHERE t.goal_id = g.goal_id AND t.done_at IS NULL
        ORDER BY t.due_on NULLS LAST, t.priority = 'high' DESC, t.created_at LIMIT 1) AS next_step,
       (SELECT max(t.done_at)::date FROM todos t WHERE t.goal_id = g.goal_id) AS last_todo_done,
       (SELECT max(u.day) FROM goal_updates u WHERE u.goal_id = g.goal_id) AS last_update,
       (SELECT count(*)::int FROM goals c WHERE c.parent_id = g.goal_id) AS children,
       CASE WHEN g.status = 'active' THEN g.target_date - current_date END AS days_left
FROM goals g LEFT JOIN goals p ON p.goal_id = g.parent_id"""
ORDER = """ ORDER BY g.pinned DESC, array_position(ARRAY['active', 'paused', 'done', 'dropped'], g.status),
            g.target_date NULLS LAST, g.done_on DESC NULLS LAST, lower(g.title)"""


def today(conn) -> date:
    """Today where you are (the database runs on Brisbane time; this container on UTC)."""
    return conn.execute("SELECT current_date AS d").fetchone()["d"]


def start_day(g: dict) -> date:
    """When the goal's time began: 1 January of its first year, or the day you started it."""
    return date(g["period_start"], 1, 1) if g["timeframe"] else g["started_on"]


def fraction(start, target, current) -> float | None:
    """0-1: how far current has moved from start to target (either way: losing 5 kg works too)."""
    if target is None or current is None:
        return None
    start = float(start or 0)
    span = float(target) - start
    if not span:
        return 1.0 if float(current) == start else 0.0
    return max(0.0, min(1.0, (float(current) - start) / span))


def period_of(day: date, every: str) -> date:
    """The week (from Monday) or month a day falls in, by its first day."""
    return day - timedelta(days=day.weekday()) if every == "week" else day.replace(day=1)


def next_period(day: date, every: str) -> date:
    return day + timedelta(days=7) if every == "week" else (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def habit(conn, g: dict, now: date) -> dict:
    """A habit's weeks / months: how many times in each (from its source, else one per progress note), this one's
    count, the streak of ones that reached the aim (this one counts once it has), and the last 12."""
    every, times = g["habit_every"] or "week", g["habit_times"] or 1
    first = period_of(start_day(g), every)
    if g["source"] in goal_sources.SOURCES:
        events = goal_sources.counted(conn, g["source"], first, now)
    else:
        events = [(r["day"], 1.0) for r in conn.execute(
            "SELECT day FROM goal_updates WHERE goal_id = %s AND day >= %s AND day <= %s", (g["goal_id"], first, now)).fetchall()]
    counts: dict[date, float] = {}
    for d, a in events:
        counts[period_of(d, every)] = counts.get(period_of(d, every), 0) + a
    periods, p, current = [], first, period_of(now, every)
    while p <= current:
        periods.append({"start": p, "count": round(counts.get(p, 0), 2), "met": counts.get(p, 0) >= times})
        p = next_period(p, every)
    this = periods[-1] if periods else {"start": current, "count": 0, "met": False}
    streak = 0
    for i, per in enumerate(reversed(periods)):
        if per["met"]:
            streak += 1
        elif i > 0:                        # this week not there yet doesn't break the streak
            break
    done_periods = periods[:-1]
    return {"every": every, "times": times, "this": this["count"], "left": max(0, round(times - this["count"], 2)),
            "met": this["met"], "streak": streak, "periods": periods[-12:],
            "rate": round(sum(p["met"] for p in done_periods) / len(done_periods), 3) if done_periods else None,
            "last_day": max((d for d, _ in events), default=None)}


def pace(g: dict, now: date) -> dict | None:
    """Where an even pace would have you by today, and whether you're ahead / on track / behind (needs a day to
    reach it and some way to measure progress). For a number: how much a month (or week, near the end) it takes."""
    if g["kind"] != "target" or g["status"] != "active" or g["progress"] is None or not g["target_date"] or g["upcoming"]:
        return None
    begin, end = start_day(g), g["target_date"]
    total = (end - begin).days
    if total <= 0:
        return None
    elapsed = max(0.0, min(1.0, (now - begin).days / total))
    diff = g["progress"] - elapsed
    status = "done" if g["progress"] >= 1 else "ahead" if diff >= ON_TRACK else "on_track" if diff >= -ON_TRACK else "behind"
    out = {"status": status, "elapsed": round(elapsed, 3), "expected": None, "per_month": None, "per_week": None}
    if g["target_value"] is not None and g["current_value"] is not None:
        start = float(g["start_value"] or 0)
        out["expected"] = round(start + (float(g["target_value"]) - start) * elapsed, 2)
        left, days = float(g["target_value"]) - float(g["current_value"]), (end - now).days
        if status != "done" and days > 0:
            out["per_month"] = round(left / max(days / 30.44, 1 / 30.44), 2)
            out["per_week"] = round(left / max(days / 7, 1 / 7), 2)
    return out


def shaped(conn, g: dict, now: date) -> dict:
    """A goal with its numbers worked out: a counted one's start / now (and history), progress, pace, a habit's
    weeks, and when it last moved."""
    g = dict(g)
    for k in ("start_value", "target_value", "current_value"):
        if g[k] is not None:
            g[k] = float(g[k])
    source = goal_sources.SOURCES.get(g["source"]) if g["source"] else None
    g["source_label"] = source[0] if source else None
    g["start_day"] = start_day(g)
    # Upcoming: active, but its time hasn't begun (a 2027 goal, now) - no pace, no nudges, not in a bigger goal's
    # average yet. It becomes active by itself on its first day: nothing to change.
    g["upcoming"] = g["status"] == "active" and g["start_day"] > now
    g["series"], moved = None, [g["last_update"], g["last_todo_done"]]
    if source and g["kind"] == "target":
        m = goal_sources.measure(conn, g["source"], start_day(g), min(now, g["target_date"] or now))
        g["current_value"] = m["current"]
        if g["start_value"] is None:
            g["start_value"] = m["start"]
        g["series"], g["auto_start"], g["source_latest"], g["history"] = m["series"], m["start"], m["latest"], m["history"]
        moved.append(m["last_day"])
    g["habit"] = habit(conn, g, now) if g["kind"] == "habit" else None
    if g["habit"]:
        moved.append(g["habit"]["last_day"])
        g["progress"] = min(1.0, g["habit"]["this"] / g["habit"]["times"])
    elif g["kind"] == "milestone":                 # done or not: only its to-dos (if any) show the steps
        g["progress"] = 1.0 if g["status"] == "done" else g["todos_done"] / g["todos_total"] if g["todos_total"] else None
    elif g["target_value"] is not None and g["current_value"] is not None:
        g["progress"] = fraction(g["start_value"], g["target_value"], g["current_value"])
    elif g["todos_total"]:
        g["progress"] = g["todos_done"] / g["todos_total"]
    else:
        g["progress"] = None                       # (a bigger goal can take its goals' average: see with_children)
    g["pace"] = pace(g, now)
    g["last_moved"] = max((d for d in moved if d), default=None)
    since = max(g["last_moved"] or g["started_on"], g["started_on"])
    quiet_kind = g["kind"] == "milestone" and not g["todos_total"]      # (a yes / no with no steps has nothing to move)
    g["still_for"] = (now - since).days if g["status"] == "active" and not g["upcoming"] and not quiet_kind else None
    return g


def with_children(goals: list[dict], now: date) -> list[dict]:
    """A goal with nothing of its own to measure moves with the goals inside it (their average)."""
    inside: dict[int, list] = {}
    for g in goals:
        if g["parent_id"]:
            inside.setdefault(g["parent_id"], []).append(g)
    for g in goals:
        kids = [k["progress"] for k in inside.get(g["goal_id"], []) if k["progress"] is not None and not k["upcoming"]]
        if g["progress"] is None and kids and g["kind"] == "target":
            g["progress"] = sum(kids) / len(kids)
            g["progress_from"] = "goals"
            g["pace"] = pace(g, now)
    return goals


def fetch(conn, goal_id: int) -> dict:
    now = today(conn)
    g = shaped(conn, found(conn.execute(GOAL_SELECT + " WHERE g.goal_id = %s", (goal_id,)).fetchone(), "Goal"), now)
    kids = [shaped(conn, k, now) for k in conn.execute(GOAL_SELECT + " WHERE g.parent_id = %s" + ORDER, (goal_id,)).fetchall()]
    with_children([g, *kids], now)
    g["goals"] = [{k: c[k] for k in ("goal_id", "title", "status", "progress", "pace", "hobby", "period_start", "timeframe",
                                     "upcoming", "start_day", "habit", "kind")}
                  for c in kids]
    g["todos"] = conn.execute("""SELECT t.*, NULL AS goal_title,
                                        CASE WHEN t.done_at IS NOT NULL THEN 'done' WHEN t.due_on IS NULL THEN 'someday'
                                             WHEN t.due_on < current_date THEN 'overdue' WHEN t.due_on = current_date THEN 'today'
                                             WHEN t.due_on <= current_date + 6 THEN 'week' ELSE 'later' END AS bucket
                                 FROM todos t WHERE t.goal_id = %s
                                 ORDER BY t.done_at IS NOT NULL, t.done_at DESC, t.due_on NULLS LAST, t.priority = 'high' DESC, t.created_at""",
                              (goal_id,)).fetchall()
    g["updates"] = [{**u, "value": float(u["value"]) if u["value"] is not None else None} for u in conn.execute(
        "SELECT * FROM goal_updates WHERE goal_id = %s ORDER BY day DESC, created_at DESC", (goal_id,)).fetchall()]
    if g["series"] is None and g["kind"] == "target" and g["target_value"] is not None:     # a number you give: its notes
        points = sorted((u["day"], u["value"]) for u in g["updates"] if u["value"] is not None)
        first = min([start_day(g)] + [d for d, _ in points])          # (a note can be from before the goal began)
        start = [(first, g["start_value"])] if g["start_value"] is not None else []
        g["series"] = start + points if points or start else None
        if start:
            g["start_day"] = first
        if g["series"] and g["current_value"] is not None and g["series"][-1][1] != g["current_value"]:
            g["series"].append((today(conn), g["current_value"]))      # "Now" typed in: where the line ends
    return g


def period_end(timeframe: str, start: int) -> date:
    return date(start + YEARS[timeframe] - 1, 12, 31)


def tidy_timeframe(conn, data: dict, old: dict | None = None):
    """A year / 3-year goal needs its first year (this year if not given); no timeframe, no year. Its
    target day follows the end of the period, unless you'd set a different one."""
    if "timeframe" not in data and "period_start" not in data:
        return
    timeframe = data.get("timeframe", old["timeframe"] if old else None)
    if timeframe is None:
        data["timeframe"] = data["period_start"] = None
        return
    start = data.get("period_start") or (old["period_start"] if old and old["timeframe"] else None) or today(conn).year
    data["timeframe"], data["period_start"] = timeframe, start
    old_end = period_end(old["timeframe"], old["period_start"]) if old and old["timeframe"] else None
    if "target_date" not in data and (old is None or old["target_date"] in (None, old_end)):
        data["target_date"] = period_end(timeframe, start)


def check(conn, data: dict, goal: dict | None = None):
    """A known hobby and source; a habit's how-often; a bigger goal that's real, not itself, and not inside another
    (one level: a year's goals under a 3-year one)."""
    if data.get("hobby") and data["hobby"] not in MODULE_IDS:
        raise HTTPException(422, f"Unknown hobby: {data['hobby']}.")
    if data.get("source"):
        if data["source"] not in goal_sources.SOURCES:
            raise HTTPException(422, f"Unknown thing to count: {data['source']}.")
        _, unit, hobby, _, _ = goal_sources.SOURCES[data["source"]]
        if goal is None or goal["source"] != data["source"]:     # a new thing to count: its unit, and its own start
            if not data.get("unit"):
                data["unit"] = unit
            if "start_value" not in data:
                data["start_value"] = None             # where it started is worked out from the records
            if hobby and not data.get("hobby") and not (goal and goal["hobby"]):
                data["hobby"] = hobby
    kind = data.get("kind") or (goal["kind"] if goal else "target")
    if kind == "habit":                                # (a habit needs its how-often: once a week unless you say)
        data["habit_every"] = data.get("habit_every") or (goal or {}).get("habit_every") or "week"
        data["habit_times"] = data.get("habit_times") or (goal or {}).get("habit_times") or 1
    if data.get("parent_id"):
        parent = conn.execute("SELECT goal_id, parent_id FROM goals WHERE goal_id = %s", (data["parent_id"],)).fetchone()
        if not parent:
            raise HTTPException(422, "That bigger goal doesn't exist.")
        if goal and parent["goal_id"] == goal["goal_id"]:
            raise HTTPException(422, "A goal can't be inside itself.")
        if parent["parent_id"]:
            raise HTTPException(422, "That goal is already inside another one - pick the bigger one.")
        if goal and goal["children"]:
            raise HTTPException(422, "This goal has goals inside it, so it can't go inside another.")


@router.get("/goals")
def list_goals(status: Status | None = None):
    with db() as conn:
        now = today(conn)
        rows = conn.execute(GOAL_SELECT + ORDER).fetchall()
        goals = with_children([shaped(conn, g, now) for g in rows], now)      # (all of them: a parent needs its goals)
        for g in goals:
            g.pop("history", None)                     # (the list doesn't draw charts: a goal's own page has it)
        shown = [g for g in goals if not status or g["status"] == status]
        return {"goals": shown, "statuses": STATUSES, "this_year": now.year,
                "counts": {**{s: sum(1 for g in goals if g["status"] == s and not g["upcoming"]) for s in STATUSES},
                           "upcoming": sum(1 for g in goals if g["upcoming"])}}


@router.get("/goals/sources")
def sources():
    return goal_sources.catalogue()


@router.get("/goals/nudges")
def nudges():
    """Home's line about goals: active ones that haven't moved in 3 weeks (oldest first), and - in the first week
    of a month with no progress notes yet, unless dismissed - a prompt to check in on them all."""
    with db() as conn:
        now = today(conn)
        goals = [shaped(conn, g, now) for g in conn.execute(GOAL_SELECT + " WHERE g.status = 'active'" + ORDER).fetchall()]
        stale = sorted(({"goal_id": g["goal_id"], "title": g["title"], "hobby": g["hobby"], "days": g["still_for"]}
                        for g in goals if g["still_for"] is not None and g["still_for"] >= STALE_DAYS),
                       key=lambda x: -x["days"])
        month = now.strftime("%Y-%m")
        seen = conn.execute("SELECT value FROM settings WHERE key = 'goals_checkin_seen'").fetchone()
        noted = conn.execute("SELECT 1 FROM goal_updates WHERE day >= %s", (now.replace(day=1),)).fetchone()
        checkin = bool(goals) and now.day <= 7 and not noted and (not seen or seen["value"] != month)
        return {"stale": stale, "checkin": checkin, "month": month}


@router.post("/goals/checkin-seen", status_code=204)
def checkin_seen():
    with db() as conn:
        month = today(conn).strftime("%Y-%m")
        conn.execute("""INSERT INTO settings (key, value) VALUES ('goals_checkin_seen', %s)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""", (month,))
    return Response(status_code=204)


@router.post("/goals", status_code=201)
def add_goal(body: GoalIn):
    data = tidy_text(body.model_dump(exclude={"steps"}), required=("title",))
    if data["started_on"] is None:
        data.pop("started_on")
    steps = [s.strip()[:200] for s in body.steps if s and s.strip()]
    with db() as conn:
        check(conn, data)
        if data["status"] == "done":
            data["done_on"] = today(conn)
        if data["target_date"] is None:
            data.pop("target_date")
        tidy_timeframe(conn, data)
        goal_id = insert_row(conn, "goals", data, "goal_id")
        for i, text in enumerate(steps):          # in order: each a moment later than the one before
            conn.execute("INSERT INTO todos (title, goal_id, hobby, created_at) VALUES (%s, %s, %s, now() + %s * interval '1 millisecond')",
                         (text, goal_id, data.get("hobby"), i))
        return fetch(conn, goal_id)


@router.get("/goals/{goal_id}")
def get_goal(goal_id: int):
    with db() as conn:
        return fetch(conn, goal_id)


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    for field in ("title", "status", "pinned", "started_on", "kind"):
        if field in data and data[field] is None:
            raise HTTPException(422, f"{field} can't be empty.")
    with db() as conn:
        goal = fetch(conn, goal_id)
        check(conn, data, goal)
        if goal["source"] and data.get("source", goal["source"]) and "current_value" in data:
            data.pop("current_value")              # (a counted goal's "now" comes from the records)
        tidy_timeframe(conn, data, goal)
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


def _latest_value(conn, goal_id: int):
    """The goal's current value follows its latest progress note that has a number."""
    row = conn.execute("""SELECT value FROM goal_updates WHERE goal_id = %s AND value IS NOT NULL
                          ORDER BY day DESC, created_at DESC LIMIT 1""", (goal_id,)).fetchone()
    if row:
        conn.execute("UPDATE goals SET current_value = %s WHERE goal_id = %s", (row["value"], goal_id))


@router.post("/goals/{goal_id}/updates", status_code=201)
def add_update(goal_id: int, body: UpdateIn):
    text = (body.text or "").strip() or None
    with db() as conn:
        goal = fetch(conn, goal_id)
        manual_habit = goal["kind"] == "habit" and not goal["source"]
        if text is None and body.value is None and not manual_habit:      # (a habit's "Did it" needs no words)
            raise HTTPException(422, "Write something or give a number.")
        conn.execute("INSERT INTO goal_updates (goal_id, day, text, value) VALUES (%s, COALESCE(%s, current_date), %s, %s)",
                     (goal_id, body.day, text if text or body.value is not None else "Did it", body.value))
        if body.value is not None and not goal["source"]:
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
