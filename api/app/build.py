"""Working on a model: the timer (time spent) and the build log (dated notes with photos).

Only one timer runs at a time: starting one on a model stops any other, the way you can only
work on one kit at once. Starting the timer also marks a kit that's waiting as In progress.
"""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .db import db, found, update_row
from .images import photo_response, read_photo
from .models import date_status, fetch_model

router = APIRouter(prefix="/api", tags=["build"])


class StopIn(BaseModel):
    note: str | None = None


class SessionIn(BaseModel):
    """Time added by hand: `minutes` on `day` (default today)."""
    minutes: int = Field(gt=0, le=24 * 60)
    day: date | None = None
    note: str | None = None


class LogIn(BaseModel):
    text: str | None = None
    entry_date: date | None = None


class LogPatch(BaseModel):
    text: str | None = None
    entry_date: date | None = None


# ---------------------------------------------------------------------------
# Time tracking
# ---------------------------------------------------------------------------
@router.post("/models/{model_id}/timer/start")
def start_timer(model_id: int):
    with db() as conn:
        model = fetch_model(conn, model_id)
        if model["running_since"]:
            raise HTTPException(409, "The timer is already running for this model.")
        conn.execute("UPDATE model_sessions SET ended_at = now() WHERE ended_at IS NULL")  # one at a time
        conn.execute("INSERT INTO model_sessions (model_id) VALUES (%s)", (model_id,))
        if model["status"] in ("Wanted", "In stash", "On hold"):
            conn.execute("UPDATE models SET status = 'In progress' WHERE model_id = %s", (model_id,))
            date_status(conn, model_id, "In progress")
        return fetch_model(conn, model_id)


@router.post("/models/{model_id}/timer/stop")
def stop_timer(model_id: int, body: StopIn | None = None):
    with db() as conn:
        found(conn.execute("UPDATE model_sessions SET ended_at = now(), note = %s "
                           "WHERE model_id = %s AND ended_at IS NULL RETURNING session_id",
                           ((body.note or None) if body else None, model_id)).fetchone(),
              "A running timer for this model")
        return fetch_model(conn, model_id)


@router.get("/timer")
def running_timer():
    """The timer that's running anywhere (for the banner at the top of the app), or null."""
    with db() as conn:
        return conn.execute("SELECT x.model_id, m.name, x.started_at FROM model_sessions x "
                            "JOIN models m USING (model_id) WHERE x.ended_at IS NULL").fetchone()


@router.post("/models/{model_id}/sessions", status_code=201)
def add_session(model_id: int, body: SessionIn):
    """Time you forgot to time: e.g. 90 minutes yesterday evening."""
    day = body.day or date.today()
    start = datetime.combine(day, time(12, 0)).astimezone()
    with db() as conn:
        fetch_model(conn, model_id)
        conn.execute("INSERT INTO model_sessions (model_id, started_at, ended_at, note) VALUES (%s, %s, %s, %s)",
                     (model_id, start, start + timedelta(minutes=body.minutes), body.note))
        return fetch_model(conn, model_id)


@router.delete("/model-sessions/{session_id}")
def delete_session(session_id: int):
    with db() as conn:
        row = found(conn.execute("DELETE FROM model_sessions WHERE session_id = %s RETURNING model_id",
                                 (session_id,)).fetchone(), "Session")
        return fetch_model(conn, row["model_id"])


# ---------------------------------------------------------------------------
# Build log
# ---------------------------------------------------------------------------
def log_entry(conn, entry_id):
    return found(conn.execute(
        "SELECT l.entry_id, l.model_id, l.entry_date, l.text, l.created_at, "
        "COALESCE((SELECT array_agg(p.photo_id ORDER BY p.photo_id) FROM model_log_photos p WHERE p.entry_id = l.entry_id), '{}') AS photos "
        "FROM model_log l WHERE l.entry_id = %s", (entry_id,)).fetchone(), "Log entry")


@router.post("/models/{model_id}/log", status_code=201)
def add_log_entry(model_id: int, body: LogIn):
    """A dated note. Add photos to it with POST /api/model-log/{entry_id}/photos (one per request)."""
    with db() as conn:
        fetch_model(conn, model_id)
        entry_id = conn.execute(
            "INSERT INTO model_log (model_id, entry_date, text) VALUES (%s, COALESCE(%s, current_date), %s) "
            "RETURNING entry_id", (model_id, body.entry_date, (body.text or "").strip() or None)).fetchone()["entry_id"]
        return log_entry(conn, entry_id)


@router.patch("/model-log/{entry_id}")
def change_log_entry(entry_id: int, body: LogPatch):
    with db() as conn:
        log_entry(conn, entry_id)
        update_row(conn, "model_log", "entry_id", entry_id, body.model_dump(exclude_unset=True))
        return log_entry(conn, entry_id)


@router.delete("/model-log/{entry_id}", status_code=204)
def delete_log_entry(entry_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM model_log WHERE entry_id = %s RETURNING entry_id", (entry_id,)).fetchone(),
              "Log entry")
    return Response(status_code=204)


PHOTOS_PER_ENTRY = 30


@router.post("/model-log/{entry_id}/photos", status_code=201)
async def add_log_photo(entry_id: int, request: Request):
    """One more photo for a build-log entry (send several requests for several photos)."""
    image, image_type = await read_photo(request)

    def save():
        with db() as conn:
            entry = log_entry(conn, entry_id)
            if len(entry["photos"]) >= PHOTOS_PER_ENTRY:
                raise HTTPException(409, f"An entry can have up to {PHOTOS_PER_ENTRY} photos.")
            conn.execute("INSERT INTO model_log_photos (entry_id, photo, photo_type) VALUES (%s, %s, %s)",
                         (entry_id, image, image_type))
            return log_entry(conn, entry_id)
    return await run_in_threadpool(save)


# A photo never changes (it's only added or removed), so its address can be cached for good.
@router.get("/model-log-photos/{photo_id}")
def log_photo(photo_id: int):
    with db() as conn:
        row = conn.execute("SELECT photo, photo_type FROM model_log_photos WHERE photo_id = %s", (photo_id,)).fetchone()
    return photo_response(row and row["photo"], row and row["photo_type"])


@router.delete("/model-log-photos/{photo_id}", status_code=204)
def delete_log_photo(photo_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM model_log_photos WHERE photo_id = %s RETURNING photo_id", (photo_id,)).fetchone(),
              "Photo")
    return Response(status_code=204)
