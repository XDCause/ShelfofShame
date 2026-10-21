"""The calendar (core): what's planned, and what happened, day by day.

    planned   calendar_events (db/init/20_calendar.sql): a volleyball game every Tuesday at 7,
              a games night, a model show. Repeating events are expanded into one entry per day
              here, so the browser never has to work out repeats. Trips too (travel.calendar_entries:
              each day of a trip, its flights, check-ins...): their entries have a trip_id.
    happened  the activity feed (activity.py) for the same days: kits bought and finished,
              plays, volleyball games, journal pages...
    moods     how each day felt (journal pages' mood)

A volleyball event's day also says whether a game was logged from it (`logged_id`), so the
calendar can offer "Log the result" until you have.

Repeats: weekly (every repeat_every weeks), fortnightly, weekdays (the repeat_days, 0 = Monday, every repeat_every
weeks), monthly (the same date; the month's last day when it's shorter), monthly_nth (the same weekday of the same
week: the 2nd Saturday; a 5th one means the last), yearly (birthdays: 29 February is the 28th in other years).
Also here: dated to-dos (due, or planned for a time), goals ending, and Queensland's public holidays
(calendar_more.py: search, quick add, weather, balance, the year, what to bring, moving a day).
"""
import calendar as months
from datetime import date, time, timedelta

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from psycopg.types.json import Jsonb

from . import activity, journal, travel
from .db import MODULE_IDS, REPEATS, db, found, insert_row, update_row
from .holidays import holidays_between

router = APIRouter(prefix="/api", tags=["calendar"])

Hobby = Literal[tuple(MODULE_IDS)]
Repeats = Literal[tuple(REPEATS)]
MAX_DAYS = 400   # one request covers at most this many days (a month view asks for ~6 weeks)
Weekday = Field(ge=0, le=6)


class CheckItem(BaseModel):
    text: str = Field(min_length=1, max_length=120)
    done: bool = False


class EventIn(BaseModel):
    title: str = Field(min_length=1)
    hobby: Hobby | None = None
    starts_on: date
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    notes: str | None = None
    repeats: Repeats = "never"
    repeat_until: date | None = None
    repeat_every: int = Field(1, ge=1, le=12)
    repeat_days: list[int] | None = Field(None, min_length=1, max_length=7)
    countdown: bool = False
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    checklist: list[CheckItem] = Field([], max_length=60)


class EventPatch(BaseModel):
    title: str | None = Field(None, min_length=1)
    hobby: Hobby | None = None
    starts_on: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    notes: str | None = None
    repeats: Repeats | None = None
    repeat_until: date | None = None
    repeat_every: int | None = Field(None, ge=1, le=12)
    repeat_days: list[int] | None = Field(None, min_length=1, max_length=7)
    countdown: bool | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    checklist: list[CheckItem] | None = Field(None, max_length=60)


def tidy(data: dict, old: dict | None = None) -> dict:
    """Checks across fields, and the shapes the table wants (a sorted set of weekdays, the checklist as JSON)."""
    if "repeat_days" in data and data["repeat_days"] is not None:
        if any(not 0 <= d <= 6 for d in data["repeat_days"]):
            raise HTTPException(422, "Weekdays are 0 (Monday) to 6 (Sunday).")
        data["repeat_days"] = sorted(set(data["repeat_days"]))
    repeats = data.get("repeats", old and old["repeats"])
    days = data["repeat_days"] if "repeat_days" in data else old and old["repeat_days"]
    if repeats == "weekdays" and not days:
        raise HTTPException(422, "Pick the days it's on.")
    if ("lat" in data) != ("lon" in data) or (data.get("lat") is None) != (data.get("lon") is None):
        raise HTTPException(422, "A place needs both a latitude and a longitude.")
    if "checklist" in data:
        data["checklist"] = Jsonb([dict(i) for i in data["checklist"] or []])
    for required in ("repeat_every", "countdown"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    return data


def _monthly(first: date, day: date) -> bool:
    """The same date each month (a month too short for it: its last day)."""
    last = months.monthrange(day.year, day.month)[1]
    return day.day == min(first.day, last)


def _monthly_nth(first: date, day: date) -> bool:
    """The same weekday in the same week of the month (week 5 = the last one)."""
    if day.weekday() != first.weekday():
        return False
    nth = (first.day - 1) // 7 + 1
    if nth == 5:
        return day.day + 7 > months.monthrange(day.year, day.month)[1]
    return (day.day - 1) // 7 + 1 == nth


def _yearly(first: date, day: date) -> bool:
    if first.month == 2 and first.day == 29 and not months.isleap(day.year):
        return day.month == 2 and day.day == 28
    return (day.month, day.day) == (first.month, first.day)


def on_day(event: dict, day: date) -> bool:
    """Whether a repeating event (from its first day on) falls on this day."""
    first, kind, every = event["starts_on"], event["repeats"], event.get("repeat_every") or 1
    if kind == "weekly":
        return (day - first).days % (7 * every) == 0
    if kind == "fortnightly":
        return (day - first).days % 14 == 0
    if kind == "weekdays":
        week = ((day - timedelta(days=day.weekday())) - (first - timedelta(days=first.weekday()))).days // 7
        return day.weekday() in (event.get("repeat_days") or []) and week % every == 0
    if kind == "monthly":
        return ((day.year - first.year) * 12 + day.month - first.month) % every == 0 and _monthly(first, day)
    if kind == "monthly_nth":
        return _monthly_nth(first, day)
    if kind == "yearly":
        return _yearly(first, day)
    return day == first


class SkipIn(BaseModel):
    day: date


def days_of(event: dict, start: date, end: date) -> list[date]:
    """The days between start and end (inclusive) that an event is on."""
    first = event["starts_on"]
    if event["repeats"] == "never":
        days = [first] if start <= first <= end else []
    else:
        day, last = max(start, first), min(end, event["repeat_until"] or end)
        days = []
        while day <= last:
            if on_day(event, day):
                days.append(day)
            day += timedelta(days=1)
    return [d for d in days if d not in event["skipped"]]


def occurrences(conn, start: date, end: date) -> list[dict]:
    """Every event on every day between start and end, in time order."""
    events = conn.execute(
        "SELECT * FROM calendar_events WHERE starts_on <= %(end)s "
        "AND (repeats <> 'never' OR starts_on >= %(start)s) "
        "AND (repeat_until IS NULL OR repeat_until >= %(start)s)", {"start": start, "end": end}).fetchall()
    logged = {(g["event_id"], g["played_on"]): g["game_id"] for g in conn.execute(
        "SELECT event_id, played_on, game_id FROM volleyball_games WHERE event_id IS NOT NULL "
        "AND played_on BETWEEN %s AND %s", (start, end)).fetchall()}
    result = []
    for e in events:
        for day in days_of(e, start, end):
            result.append({
                "event_id": e["event_id"], "day": day, "title": e["title"], "hobby": e["hobby"],
                "start_time": e["start_time"], "end_time": e["end_time"], "location": e["location"],
                "notes": e["notes"], "repeats": e["repeats"], "repeat_until": e["repeat_until"],
                "repeat_every": e["repeat_every"], "repeat_days": e["repeat_days"], "countdown": e["countdown"],
                "lat": float(e["lat"]) if e["lat"] is not None else None, "lon": float(e["lon"]) if e["lon"] is not None else None,
                "checklist": e["checklist"],
                "starts_on": e["starts_on"], "logged_id": logged.get((e["event_id"], day)),
            })
    return sorted(result, key=_order)


def _order(o: dict):
    """By day, then time (all-day first), then title."""
    return o["day"], o["start_time"] or time(0), o["title"].lower()


def fetch_event(conn, event_id: int) -> dict:
    return found(conn.execute("SELECT *, lat::float AS lat, lon::float AS lon FROM calendar_events WHERE event_id = %s",
                              (event_id,)).fetchone(), "Event")


def todos_between(conn, start: date, end: date) -> list[dict]:
    """To-dos due, or planned for (time-blocked), between two days - open ones, and ones done in that time."""
    return conn.execute(
        "SELECT todo_id, title, hobby, due_on, plan_on, plan_time, plan_minutes, priority, done_at IS NOT NULL AS done "
        "FROM todos WHERE (due_on BETWEEN %(s)s AND %(e)s OR plan_on BETWEEN %(s)s AND %(e)s) "
        "AND (done_at IS NULL OR done_at::date BETWEEN %(s)s AND %(e)s) ORDER BY COALESCE(plan_on, due_on), plan_time NULLS LAST, title",
        {"s": start, "e": end}).fetchall()


def goals_between(conn, start: date, end: date) -> list[dict]:
    """Goals whose time ends between two days (their target date)."""
    return conn.execute("SELECT goal_id, title, hobby, target_date AS day, status FROM goals "
                        "WHERE target_date BETWEEN %s AND %s AND status IN ('active', 'done') ORDER BY target_date, title",
                        (start, end)).fetchall()


@router.get("/calendar")
def calendar(start: date, end: date):
    """Everything between two days (inclusive): `events` planned, what `happened`, moods, `todos` (due or planned),
    `goals` ending and Queensland's public `holidays`."""
    if end < start or (end - start).days > MAX_DAYS:
        raise HTTPException(422, f"The end must be after the start, and at most {MAX_DAYS} days later.")
    with db() as conn:
        events = sorted(occurrences(conn, start, end) + travel.calendar_entries(conn, start, end), key=_order)
        return {"events": events, "happened": activity.rows(conn, 2000, start, end),
                "moods": journal.moods_between(conn, start, end), "todos": todos_between(conn, start, end),
                "goals": goals_between(conn, start, end), "holidays": holidays_between(start, end)}


@router.get("/calendar/upcoming")
def upcoming(days: int = Query(60, ge=1, le=MAX_DAYS), limit: int = Query(5, ge=1, le=100)):
    """The next few events from today, soonest first (for Home's "Coming up")."""
    today = date.today()
    with db() as conn:
        end = today + timedelta(days=days)
        return sorted(occurrences(conn, today, end) + travel.calendar_entries(conn, today, end, first_day_only=True),
                      key=_order)[:limit]


@router.post("/calendar/events", status_code=201)
def add_event(body: EventIn):
    data = tidy(body.model_dump())
    data["title"] = data["title"].strip()
    with db() as conn:
        return fetch_event(conn, insert_row(conn, "calendar_events", data, "event_id"))


@router.get("/calendar/events/{event_id}")
def get_event(event_id: int):
    with db() as conn:
        return fetch_event(conn, event_id)


@router.patch("/calendar/events/{event_id}")
def update_event(event_id: int, body: EventPatch):
    data = body.model_dump(exclude_unset=True)
    for required in ("title", "starts_on", "repeats"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        data = tidy(data, fetch_event(conn, event_id))
        update_row(conn, "calendar_events", "event_id", event_id, data)
        return fetch_event(conn, event_id)


@router.post("/calendar/events/{event_id}/skip")
def skip_day(event_id: int, body: SkipIn):
    """A repeating event isn't on this one day (the others stay)."""
    with db() as conn:
        event = fetch_event(conn, event_id)
        if body.day not in days_of(event, body.day, body.day):
            raise HTTPException(409, "The event isn't on that day.")
        conn.execute("UPDATE calendar_events SET skipped = array_append(skipped, %s) WHERE event_id = %s",
                     (body.day, event_id))
        return fetch_event(conn, event_id)


@router.delete("/calendar/events/{event_id}", status_code=204)
def delete_event(event_id: int):
    """Delete an event (every day of it). Games logged from it keep their details."""
    with db() as conn:
        found(conn.execute("DELETE FROM calendar_events WHERE event_id = %s RETURNING event_id",
                           (event_id,)).fetchone(), "Event")
    return Response(status_code=204)
