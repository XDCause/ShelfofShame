"""Vinyl care (market review, 2026-11-16): who has a record, when it was cleaned, and how worn your stylus is.

    loans    /vinyl/loans             records loaned out (set on a record: PATCH loaned_to, loaned_on; empty = it's back)
    clean    POST /vinyl/records/{id}/clean   "I cleaned it" (a day, a note); DELETE /vinyl/care/{id} takes one back
    stylus   /vinyl/stylus            hours played since it was fitted, worked out from your plays (the length of the
             sides you played; a record without a tracklist counts a usual side for its size), against the hours you
             replace it at (default 800; a conical stylus lasts less, an elliptical more). "Fitted a new one" starts again.

CDs and cassettes never touch the stylus. The tables are in db/init/A06_reading_vinyl_volleyball.sql.
"""
from datetime import date

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text
from .vinyl import PHOTO, fetch_record

router = APIRouter(prefix="/api", tags=["vinyl"])

SIDE_MINUTES = {'7"': 4, '10"': 12, '12"': 20}        # a usual side, when the tracklist has no times
SOON = 0.9                                             # "nearly due" from 90% of the hours


class CleanIn(BaseModel):
    done_on: date | None = None
    note: str | None = Field(None, max_length=500)


class StylusIn(BaseModel):
    limit_hours: float = Field(gt=0, le=5000)


class FittedIn(BaseModel):
    fitted_on: date | None = None       # default today


def seconds_of(duration: str | None) -> int | None:
    """"3:41" -> 221; "1:02:03" -> 3723; blank or odd -> None (unlike vinyl_sync's guess, which would add 3.5 minutes)."""
    try:
        parts = [int(p) for p in (duration or "").split(":") if p.strip() != ""]
    except ValueError:
        return None
    total = 0
    for p in parts:
        total = total * 60 + p
    return total if 0 < total < 4 * 3600 else None


def side_letters(position: str | None) -> str:
    """"A1" -> "A", "B" -> "B", "3" -> "" (no sides)."""
    letters = ""
    for ch in (position or "").strip().upper():
        if not ch.isalpha():
            break
        letters += ch
    return letters


def play_minutes(sides: str | None, tracklist: list | None, size: str | None, discs: int | None) -> float:
    """How long a play kept the stylus in a groove: the times of the tracks on the sides played, else a usual side
    for the record's size for each side (a whole record = two sides a disc)."""
    wanted = {x.strip().upper() for x in (sides or "").replace("/", ",").replace("&", ",").split(",") if x.strip()}
    chosen = [t for t in tracklist or [] if not wanted or side_letters(t.get("position")) in wanted]
    timed = [seconds_of(t.get("duration")) for t in chosen]
    if chosen and all(timed):
        return sum(timed) / 60
    return len(wanted or range((discs or 1) * 2)) * SIDE_MINUTES.get(size or "", 20)


def stylus_status(conn) -> dict:
    """Hours played since the stylus was fitted, against when to replace it."""
    s = conn.execute("SELECT stylus_limit_hours::float8 AS limit_hours, stylus_since FROM vinyl_settings WHERE id = 1").fetchone()
    plays = conn.execute("""
        SELECT p.sides, r.tracklist, r.size, r.discs, count(*)::int AS n
        FROM vinyl_plays p JOIN vinyl_records r USING (record_id)
        WHERE r.medium = 'Vinyl' AND (%(since)s::date IS NULL OR p.played_at >= %(since)s::date)
        GROUP BY p.sides, r.record_id""", {"since": s["stylus_since"]}).fetchall()
    hours = round(sum(play_minutes(p["sides"], p["tracklist"], p["size"], p["discs"]) * p["n"] for p in plays) / 60, 1)
    left = round(s["limit_hours"] - hours, 1)
    return {"hours": hours, "limit_hours": s["limit_hours"], "since": s["stylus_since"], "hours_left": left,
            "percent": min(100, round(100 * hours / s["limit_hours"])), "due": hours >= s["limit_hours"],
            "soon": SOON * s["limit_hours"] <= hours < s["limit_hours"], "plays": sum(p["n"] for p in plays)}


@router.get("/vinyl/stylus")
def get_stylus():
    with db() as conn:
        return stylus_status(conn)


@router.put("/vinyl/stylus")
def set_stylus(body: StylusIn):
    """The hours you replace the stylus at."""
    with db() as conn:
        conn.execute("UPDATE vinyl_settings SET stylus_limit_hours = %s WHERE id = 1", (body.limit_hours,))
        return stylus_status(conn)


@router.post("/vinyl/stylus/fitted")
def stylus_fitted(body: FittedIn):
    """A new stylus: the hours start again from the day (default today)."""
    with db() as conn:
        day = body.fitted_on or conn.execute("SELECT current_date AS d").fetchone()["d"]
        conn.execute("UPDATE vinyl_settings SET stylus_since = %s WHERE id = 1", (day,))
        return stylus_status(conn)


@router.get("/vinyl/loans")
def list_loans():
    """Records out on loan, longest first."""
    with db() as conn:
        return conn.execute(f"""
            SELECT r.record_id, r.title, r.artist, r.loaned_to, r.loaned_on, (current_date - r.loaned_on) AS days, {PHOTO} AS photo_url
            FROM vinyl_records r WHERE r.loaned_to IS NOT NULL ORDER BY r.loaned_on, r.record_id""").fetchall()


@router.post("/vinyl/records/{record_id}/clean", status_code=201)
def clean_record(record_id: int, body: CleanIn):
    """You cleaned this record."""
    data = tidy_text(body.model_dump())
    with db() as conn:
        fetch_record(conn, record_id)
        data["done_on"] = data["done_on"] or conn.execute("SELECT current_date AS d").fetchone()["d"]
        insert_row(conn, "vinyl_care", {"record_id": record_id, "kind": "clean", **data}, "care_id")
        return fetch_record(conn, record_id)


@router.delete("/vinyl/care/{care_id}", status_code=204)
def delete_care(care_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM vinyl_care WHERE care_id = %s RETURNING care_id", (care_id,)).fetchone(), "Care entry")
    return Response(status_code=204)
