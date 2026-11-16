"""Your day (journal): what happened on one day, gathered from everywhere, as short lines for the page.

    GET /journal/day-summary?day=2026-11-16   {day, lines: [{kind, text}], blocks: [...]}
        kind: event (the calendar), did (a play, hike, session, game... from the activity feed), todo (done),
        focus (time focused), photo (photos taken: trips, hikes, the garden).
        blocks: the same as journal blocks (a heading and bullets) ready to put in the page.

It only reads. The journal page's "Your day" button puts the blocks into the page; you write around them.
(Included BEFORE journal in main.py: /journal/day-summary would otherwise be read as /journal/{id}.)
"""
from datetime import date, time

from fastapi import APIRouter

from . import activity, calendar, travel
from .db import db
from .goals_review import block

router = APIRouter(prefix="/api", tags=["journal"])

MAX_DID = 15        # a busy day (a long Steam session's achievements) stays a short summary
DID_SKIP = {"page", "supply"}          # (the journal page itself; stock bought or used)


def clock(t) -> str:
    return t.strftime("%H:%M") if t else ""


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else many or one + 's'}"


def gather(conn, day: date) -> list[dict]:
    lines = []
    events = calendar.occurrences(conn, day, day) + travel.calendar_entries(conn, day, day)
    for e in sorted(events, key=lambda e: (e["start_time"] is not None, e["start_time"] or time(0))):
        lines.append({"kind": "event", "text": " ".join(filter(None, [clock(e["start_time"]), e["title"]]))
                      + (f" ({e['location']})" if e.get("location") else "")})
    did = [a for a in activity.rows(conn, 500, day, day) if a["kind"] not in DID_SKIP]
    for a in did[:MAX_DID]:
        lines.append({"kind": "did", "text": f"{a['verb']} {a['title']}" + (f" ({a['detail']})" if a.get("detail") else "")})
    if len(did) > MAX_DID:
        lines.append({"kind": "did", "text": f"...and {len(did) - MAX_DID} more"})
    for t in conn.execute("SELECT title FROM todos WHERE done_at::date = %s ORDER BY done_at", (day,)).fetchall():
        lines.append({"kind": "todo", "text": f"Done: {t['title']}"})
    focus = conn.execute("SELECT COALESCE(sum(focused_seconds), 0)::int AS s, count(*)::int AS n FROM focus_sessions "
                         "WHERE status IN ('done', 'stopped') AND started_at::date = %s", (day,)).fetchone()
    if focus["n"]:
        lines.append({"kind": "focus", "text": f"Focused for {round(focus['s'] / 60)} min ({plural(focus['n'], 'session')})"})
    photos = conn.execute("""
        SELECT (SELECT count(*) FROM trip_photos WHERE COALESCE(day, taken_at::date) = %(d)s)
             + (SELECT count(*) FROM hike_photos WHERE taken_at::date = %(d)s)
             + (SELECT count(*) FROM garden_photos p JOIN garden_logs l USING (log_id) WHERE l.happened_on = %(d)s) AS n""",
                          {"d": day}).fetchone()["n"]
    if photos:
        lines.append({"kind": "photo", "text": f"{plural(photos, 'photo')} taken"})
    return lines


@router.get("/journal/day-summary")
def day_summary(day: date | None = None):
    with db() as conn:
        day = day or conn.execute("SELECT current_date AS d").fetchone()["d"]
        lines = gather(conn, day)
    blocks = [block("heading", f"Your day: {day.day} {day:%b}", level=3)]
    blocks += [block("bulletListItem", ln["text"]) for ln in lines] if lines else [block("paragraph", "Nothing logged for this day.")]
    return {"day": day, "lines": lines, "blocks": blocks}
