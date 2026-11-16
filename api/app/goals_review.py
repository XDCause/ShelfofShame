"""Habit freezes and the weekly review (core, beside goals.py).

A freeze: a week (or month) of a habit goal that you couldn't do. It doesn't add to the streak, but doesn't break it
either. A few a month (goals.FREEZES_PER_MONTH). Freezing a day freezes the week / month it falls in.

    POST   /goals/{id}/freezes        {day}: freeze that day's week / month (day empty = today); answers with the goal
    DELETE /goal-freezes/{id}         take a freeze back; answers with the goal
    GET    /goals/weekly-review       ?week=<any day in it>: the week Monday-Sunday (this one by default): what each
                                      goal did, streaks, what's slipping, time focused, and the page saved for it, if any
    POST   /goals/weekly-review       {week, note}: save the review (with your note) as a journal page

(Included BEFORE goals in main.py: /goals/weekly-review would otherwise be read as /goals/{id}.)
"""
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import goal_sources, goals, journal
from .db import db, found

router = APIRouter(prefix="/api", tags=["goals"])

SLIPPING_DAYS = 14          # a goal that hasn't moved this long is slipping (goals.py nudges at 21)
FREEZE_LOOKBACK = 62        # a freeze can be for a day this far back


class FreezeIn(BaseModel):
    day: date | None = None


class ReviewIn(BaseModel):
    week: date | None = None
    note: str = Field("", max_length=20000)


@router.post("/goals/{goal_id}/freezes", status_code=201)
def add_freeze(goal_id: int, body: FreezeIn):
    with db() as conn:
        g = found(conn.execute("SELECT * FROM goals WHERE goal_id = %s", (goal_id,)).fetchone(), "Goal")
        now = goals.today(conn)
        day = body.day or now
        if g["kind"] != "habit":
            raise HTTPException(422, "Only a habit (a goal that repeats every week or month) can be frozen.")
        if day > now or day < now - timedelta(days=FREEZE_LOOKBACK):
            raise HTTPException(422, f"Pick a day from the last {FREEZE_LOOKBACK} days, up to today.")
        every = g["habit_every"] or "week"
        used = conn.execute("SELECT day FROM habit_freezes WHERE goal_id = %s", (goal_id,)).fetchall()
        if any(goals.period_of(r["day"], every) == goals.period_of(day, every) for r in used):
            raise HTTPException(409, f"That {every} is already frozen.")
        if sum(1 for r in used if (r["day"].year, r["day"].month) == (day.year, day.month)) >= goals.FREEZES_PER_MONTH:
            raise HTTPException(409, f"You've used all {goals.FREEZES_PER_MONTH} freezes for that month.")
        conn.execute("INSERT INTO habit_freezes (goal_id, day) VALUES (%s, %s)", (goal_id, day))
        return goals.fetch(conn, goal_id)


@router.delete("/goal-freezes/{freeze_id}")
def remove_freeze(freeze_id: int):
    with db() as conn:
        row = found(conn.execute("DELETE FROM habit_freezes WHERE freeze_id = %s RETURNING goal_id", (freeze_id,)).fetchone(), "Freeze")
        return goals.fetch(conn, row["goal_id"])


def week_of(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def title_of(start: date, end: date) -> str:
    months = f"{start.day} {start:%b}" if start.month != end.month else f"{start.day}"
    return f"Weekly review: {months} - {end.day} {end:%b %Y}"


def count_in(conn, g: dict, start: date, end: date) -> float | None:
    """What a goal's source counted in the week (books finished, km hiked...), or None when it has no source."""
    if g["source"] not in goal_sources.SOURCES:
        return None
    return round(sum(a for d, a in goal_sources.counted(conn, g["source"], start, end) if d <= end), 2)


def review(conn, week: date | None) -> dict:
    now = goals.today(conn)
    start, end = week_of(week or now)
    rows = conn.execute(goals.GOAL_SELECT + " WHERE g.status = 'active'" + goals.ORDER).fetchall()
    shaped = goals.with_children([goals.shaped(conn, r, now) for r in rows], now)
    out, todos_done, focus_total = [], 0, 0
    for g in shaped:
        if g["upcoming"]:
            continue
        gid = g["goal_id"]
        notes = conn.execute("SELECT count(*)::int AS n FROM goal_updates WHERE goal_id = %s AND day BETWEEN %s AND %s",
                             (gid, start, end)).fetchone()["n"]
        todos = conn.execute("SELECT count(*)::int AS n FROM todos WHERE goal_id = %s AND done_at::date BETWEEN %s AND %s",
                             (gid, start, end)).fetchone()["n"]
        focus = round(conn.execute("SELECT COALESCE(sum(focused_seconds), 0)::int AS s FROM focus_sessions WHERE goal_id = %s "
                                   "AND status IN ('done', 'stopped') AND started_at::date BETWEEN %s AND %s",
                                   (gid, start, end)).fetchone()["s"] / 60)
        counted = count_in(conn, g, start, end)
        h = g["habit"]
        last = h["periods"][-2] if h and len(h["periods"]) > 1 else None
        moved = bool(notes or todos or focus or counted)
        slipping = (not moved and g["still_for"] is not None and g["still_for"] >= SLIPPING_DAYS) \
            or bool(h and last and not last["met"] and not last["frozen"] and not h["met"])
        todos_done += todos
        focus_total += focus
        out.append({"goal_id": gid, "title": g["title"], "hobby": g["hobby"], "kind": g["kind"], "unit": g["unit"],
                    "progress": g["progress"], "moved": moved, "notes": notes, "todos_done": todos, "focus_minutes": focus,
                    "counted": counted, "slipping": slipping, "still_for": g["still_for"],
                    "habit": {k: h[k] for k in ("every", "times", "this", "met", "streak", "this_frozen", "freezes")} if h else None})
    free = conn.execute("SELECT count(*)::int AS n FROM todos WHERE goal_id IS NULL AND done_at::date BETWEEN %s AND %s",
                        (start, end)).fetchone()["n"]
    page = conn.execute("SELECT page_id FROM journal_pages WHERE title = %s ORDER BY created_at DESC LIMIT 1",
                        (title_of(start, end),)).fetchone()
    return {"week_start": start, "week_end": end, "current": start <= now <= end, "title": title_of(start, end),
            "goals": out, "slipping": [g["goal_id"] for g in out if g["slipping"]],
            "totals": {"goals": len(out), "moved": sum(g["moved"] for g in out), "todos_done": todos_done + free,
                       "focus_minutes": focus_total, "streaks": sum(1 for g in out if g["habit"] and g["habit"]["streak"] > 0)},
            "saved_page_id": page["page_id"] if page else None}


@router.get("/goals/weekly-review")
def get_review(week: date | None = None):
    with db() as conn:
        return review(conn, week)


def block(kind: str, text: str, **props) -> dict:
    """A journal block (BlockNote's shape) holding one line of plain text."""
    return {"type": kind, "props": props, "content": [{"type": "text", "text": text, "styles": {}}] if text else [], "children": []}


def lines_of(r: dict) -> list[str]:
    """The review as short bullet lines (what each goal did, what's slipping)."""
    lines = []
    for g in r["goals"]:
        bits = []
        if g["habit"]:
            h = g["habit"]
            bits.append(f"{h['this']:g} of {h['times']} this {h['every']}" + (", frozen" if h["this_frozen"] else "")
                        + (f", streak {h['streak']}" if h["streak"] else ""))
        if g["counted"]:
            bits.append(f"{g['counted']:g} {g['unit'] or ''}".strip())
        if g["todos_done"]:
            bits.append(f"{g['todos_done']} to-do{'s' if g['todos_done'] != 1 else ''} done")
        if g["notes"]:
            bits.append(f"{g['notes']} note{'s' if g['notes'] != 1 else ''}")
        if g["focus_minutes"]:
            bits.append(f"{g['focus_minutes']} min focused")
        lines.append(f"{g['title']}: " + (", ".join(bits) if bits else "quiet this week") + (" (slipping)" if g["slipping"] else ""))
    return lines


@router.post("/goals/weekly-review", status_code=201)
def save_review(body: ReviewIn):
    """The review as a journal page (tag "weekly review", on the week's last day, or today if the week isn't over)."""
    with db() as conn:
        r = review(conn, body.week)
        now = goals.today(conn)
    t = r["totals"]
    content = [block("heading", r["title"].replace("Weekly review: ", "Week of "), level=2),
               block("paragraph", f"{t['moved']} of {t['goals']} goals moved, {t['todos_done']} to-dos done"
                     + (f", {t['focus_minutes']} minutes focused" if t["focus_minutes"] else "") + ".")]
    content += [block("bulletListItem", line) for line in lines_of(r)]
    note = body.note.strip()
    if note:
        content.append(block("heading", "My notes", level=3))
        content += [block("paragraph", para.strip()) for para in note.split("\n") if para.strip()]
    page = journal.add_page(journal.PageIn(title=r["title"], content=content, tags=["weekly review"],
                                           entry_date=min(r["week_end"], now)))
    return {"page_id": page["page_id"], "title": r["title"]}
