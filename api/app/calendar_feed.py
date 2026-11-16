"""Your calendar in your phone's calendar app (2026-11-16, the market review: TripIt, Fantastical and TickTick all have
one): a private .ics address the phone subscribes to - the calendar's events (repeats spread out, from a month back to a
year ahead) and trips as all-day events. The phone asks for it every so often by itself.

A calendar app can't sign in, so the address carries a secret key instead: made in Settings > Calendar feed, shown
there, and replaced by "New address" (the old one stops working at once). A wrong or missing key answers 404, the same
as no feed at all, so the address can't be guessed at. The app is only reachable at home or over Tailscale, as ever.

    GET    /api/calendar/feed.ics?key=...   the feed - no sign-in (the key is the sign-in): `public` below
    GET    /api/calendar/feed               signed in: is it on, and its address
    POST   /api/calendar/feed               signed in: turn it on, or make a new key
    DELETE /api/calendar/feed               signed in: turn it off
"""
import hmac
import secrets
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Response

from .calendar import occurrences
from .db import db

router = APIRouter(prefix="/api", tags=["calendar"])
public = APIRouter(prefix="/api", tags=["calendar"])      # (main.py includes this one without the sign-in check)

KEY = "calendar_feed_key"           # in the settings table (not in settings.DEFAULTS: /api/settings never shows it)
BRISBANE = timezone(timedelta(hours=10))                   # the app's time zone (no daylight saving)
BACK, AHEAD = 30, 365


def _key(conn) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = %s", (KEY,)).fetchone()
    return row and row["value"]


def _state(key: str | None) -> dict:
    return {"on": bool(key), "path": f"/api/calendar/feed.ics?key={key}" if key else None}


@router.get("/calendar/feed")
def feed_state():
    with db() as conn:
        return _state(_key(conn))


@router.post("/calendar/feed")
def feed_on():
    """On, with a new key (a new address: the old one stops working)."""
    key = secrets.token_urlsafe(24)
    with db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                     (KEY, key))
    return _state(key)


@router.delete("/calendar/feed", status_code=204)
def feed_off():
    with db() as conn:
        conn.execute("DELETE FROM settings WHERE key = %s", (KEY,))
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# The .ics file (RFC 5545): lines of at most 75 octets, folded with CRLF + a space; text escaped.
# ---------------------------------------------------------------------------
def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\n").replace("\n", "\\n")


def fold(line: str) -> str:
    out, data = [], line.encode("utf-8")
    while len(data) > 75:
        cut = 75 if not out else 74                       # (a folded line starts with a space)
        while cut and (data[cut] & 0xC0) == 0x80:         # never cut inside a character
            cut -= 1
        out.append(data[:cut].decode("utf-8"))
        data = data[cut:]
    out.append(data.decode("utf-8"))
    return "\r\n ".join(out)


def utc(day: date, at: time) -> str:
    return datetime.combine(day, at, BRISBANE).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ics(events: list[dict], trips: list[dict], now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Off the Clock//Calendar feed//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:Off the Clock", "X-WR-TIMEZONE:Australia/Brisbane",
             "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H"]
    for e in events:
        lines += ["BEGIN:VEVENT", f"UID:event-{e['event_id']}-{e['day']:%Y%m%d}@offtheclock", f"DTSTAMP:{stamp}",
                  f"SUMMARY:{escape(e['title'])}"]
        if e["start_time"]:
            end = e["end_time"] or (datetime.combine(e["day"], e["start_time"]) + timedelta(hours=1)).time()
            end_day = e["day"] + timedelta(days=1) if end <= e["start_time"] else e["day"]   # (past midnight)
            lines += [f"DTSTART:{utc(e['day'], e['start_time'])}", f"DTEND:{utc(end_day, end)}"]
        else:
            lines += [f"DTSTART;VALUE=DATE:{e['day']:%Y%m%d}", f"DTEND;VALUE=DATE:{e['day'] + timedelta(days=1):%Y%m%d}"]
        if e.get("location"):
            lines.append(f"LOCATION:{escape(e['location'])}")
        if e.get("notes"):
            lines.append(f"DESCRIPTION:{escape(e['notes'])}")
        if e.get("hobby"):
            lines.append(f"CATEGORIES:{escape(e['hobby'])}")
        lines.append("END:VEVENT")
    for t in trips:
        last = t["end_date"] or t["start_date"]
        lines += ["BEGIN:VEVENT", f"UID:trip-{t['trip_id']}@offtheclock", f"DTSTAMP:{stamp}",
                  f"SUMMARY:{escape(('Trip: ' if t['status'] == 'Planned' else 'Trip idea: ') + t['name'])}",
                  f"DTSTART;VALUE=DATE:{t['start_date']:%Y%m%d}", f"DTEND;VALUE=DATE:{last + timedelta(days=1):%Y%m%d}"]
        if t.get("destination"):
            lines.append(f"LOCATION:{escape(t['destination'])}")
        lines += ["TRANSP:TRANSPARENT", "END:VEVENT"]          # (a trip doesn't make you "busy" all day)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


@public.get("/calendar/feed.ics")
def feed(key: str = Query("", max_length=200)):
    with db() as conn:
        want = _key(conn)
        if not want or not key or not hmac.compare_digest(key.encode(), want.encode()):
            raise HTTPException(404, "Not found.")
        today = datetime.now(BRISBANE).date()
        events = occurrences(conn, today - timedelta(days=BACK), today + timedelta(days=AHEAD))
        trips = conn.execute("SELECT trip_id, name, status, start_date, end_date, destination FROM trips "
                             "WHERE start_date IS NOT NULL AND status <> 'Cancelled' "
                             "AND coalesce(end_date, start_date) >= %s ORDER BY start_date",
                             (today - timedelta(days=BACK),)).fetchall()
    return Response(ics(events, trips, datetime.now(timezone.utc)), media_type="text/calendar; charset=utf-8",
                    headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="off-the-clock.ics"'})
