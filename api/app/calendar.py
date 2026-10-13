"""The calendar (core): what's planned, and what happened, day by day.

    planned   calendar_events (db/init/20_calendar.sql): a volleyball game every Tuesday at 7,
              a games night, a model show. Repeating events are expanded into one entry per day
              here, so the browser never has to work out repeats.
    happened  the activity feed (activity.py) for the same days: kits bought and finished,
              plays, volleyball games, journal pages...
    moods     how each day felt (journal pages' mood)

A volleyball event's day also says whether a game was logged from it (`logged_id`), so the
calendar can offer "Log the result" until you have.
"""
from datetime import date, time, timedelta

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import activity, journal
from .db import MODULE_IDS, REPEATS, db, found, insert_row, update_row

router = APIRouter(prefix="/api", tags=["calendar"])

Hobby = Literal[tuple(MODULE_IDS)]
Repeats = Literal[tuple(REPEATS)]
STEP = {"never": None, "weekly": 7, "fortnightly": 14}
MAX_DAYS = 400   # one request covers at most this many days (a month view asks for ~6 weeks)


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


class SkipIn(BaseModel):
    day: date


def days_of(event: dict, start: date, end: date) -> list[date]:
    """The days between start and end (inclusive) that an event is on."""
    first, step = event["starts_on"], STEP[event["repeats"]]
    if step is None:
        days = [first] if start <= first <= end else []
    else:
        last = min(end, event["repeat_until"] or end)
        day = first if first >= start else first + timedelta(days=-(-(start - first).days // step) * step)
        days = []
        while day <= last:
            days.append(day)
            day += timedelta(days=step)
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
                "starts_on": e["starts_on"], "logged_id": logged.get((e["event_id"], day)),
            })
    return sorted(result, key=lambda o: (o["day"], o["start_time"] or time(0), o["title"].lower()))


def fetch_event(conn, event_id: int) -> dict:
    return found(conn.execute("SELECT * FROM calendar_events WHERE event_id = %s", (event_id,)).fetchone(),
                 "Event")


@router.get("/calendar")
def calendar(start: date, end: date):
    """Everything between two days (inclusive): `events` planned and what `happened`."""
    if end < start or (end - start).days > MAX_DAYS:
        raise HTTPException(422, f"The end must be after the start, and at most {MAX_DAYS} days later.")
    with db() as conn:
        return {"events": occurrences(conn, start, end), "happened": activity.rows(conn, 2000, start, end),
                "moods": journal.moods_between(conn, start, end)}


@router.get("/calendar/upcoming")
def upcoming(days: int = Query(60, ge=1, le=MAX_DAYS), limit: int = Query(5, ge=1, le=100)):
    """The next few events from today, soonest first (for Home's "Coming up")."""
    today = date.today()
    with db() as conn:
        return occurrences(conn, today, today + timedelta(days=days))[:limit]


@router.post("/calendar/events", status_code=201)
def add_event(body: EventIn):
    data = body.model_dump()
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
        fetch_event(conn, event_id)
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
