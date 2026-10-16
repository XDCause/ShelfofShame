"""Hiking (a hobby module): hikes imported from GPX files - AllTrails' export, or any GPS app's - or
logged by hand.

    import    POST /hiking/import?filename=   the GPX file as the body (gpx.py works out the numbers:
              distance, moving / total time, climb, highest / lowest point, per-km splits, waypoints,
              the route for drawing, loop or one way, and the AllTrails trail link if the file has one).
              The same file twice is skipped (its sha256 is kept). The file itself is kept too.
    hikes     the list (search, year), one hike with its track, add one by hand, change, remove,
              the original GPX back; a photo per hike
    summary   this year and all time, km per month (last 12), personal bests, the latest hikes
"""
import re
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import gpx
from .db import db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["hiking"])

COLUMNS = """
SELECT hike_id, name, hiked_on, started_at, ended_at, distance_m::float8 AS distance_m, moving_s, elapsed_s,
       ascent_m::float8 AS ascent_m, descent_m::float8 AS descent_m, max_ele_m::float8 AS max_ele_m,
       min_ele_m::float8 AS min_ele_m, start_lat, start_lon, is_loop, points, trail_name, trail_url, location,
       difficulty, rating, companions, weather, notes, source, gpx_name, created_at,
       CASE WHEN photo IS NOT NULL THEN '/api/hiking/hikes/' || hike_id || '/photo?v='
            || (extract(epoch FROM photo_updated) * 1000)::bigint END AS photo_url"""


class HikeFields(BaseModel):
    trail_name: str | None = Field(None, max_length=200)
    trail_url: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=200)
    difficulty: str | None = Field(None, pattern="^(Easy|Moderate|Hard)$")
    rating: int | None = Field(None, ge=1, le=5)
    companions: str | None = Field(None, max_length=500)
    weather: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=20000)
    distance_km: float | None = Field(None, ge=0, le=1000)
    moving_min: int | None = Field(None, ge=0, le=60 * 24 * 14)
    ascent_m: float | None = Field(None, ge=0, le=20000)


class HikeIn(HikeFields):
    """A hike logged by hand (no GPS file)."""
    name: str = Field(min_length=1, max_length=200)
    hiked_on: date


class HikePatch(HikeFields):
    name: str | None = Field(None, min_length=1, max_length=200)
    hiked_on: date | None = None


def _columns(data: dict) -> dict:
    """The form's km / minutes -> the table's metres / seconds; blank text -> None."""
    data = tidy_text(data, required=("name",))
    if "distance_km" in data:
        km = data.pop("distance_km")
        data["distance_m"] = round(km * 1000, 1) if km is not None else None
    if "moving_min" in data:
        mins = data.pop("moving_min")
        data["moving_s"] = mins * 60 if mins is not None else None
    if data.get("trail_url") and not re.match(r"^https?://", data["trail_url"]):
        raise HTTPException(422, "A trail link must start with http:// or https://.")
    return data


def fetch(conn, hike_id: int) -> dict:
    """One hike with everything: the route, splits and waypoints too."""
    return found(conn.execute(COLUMNS + ", track, splits, waypoints FROM hikes WHERE hike_id = %s",
                              (hike_id,)).fetchone(), "Hike")


@router.post("/hiking/import", status_code=201)
async def import_gpx(request: Request, response: Response, filename: str | None = Query(None, max_length=255)):
    """A GPX file as the body. Answers the new hike - or, for a file imported before, that hike with
    duplicate = true (nothing changes)."""
    raw = await request.body()
    try:
        g = gpx.parse(raw)
    except gpx.GpxError as e:
        raise HTTPException(422, str(e))
    with db() as conn:
        old = conn.execute("SELECT hike_id FROM hikes WHERE gpx_hash = %s", (g["hash"],)).fetchone()
        if old:
            response.status_code = 200
            return {**fetch(conn, old["hike_id"]), "duplicate": True}
        stem = re.sub(r"[_\-]+", " ", re.sub(r"\.gpx$", "", filename or "", flags=re.I)).strip()
        # The day it was hiked, in the app's time zone (GPX times are UTC). A route without times: today.
        hiked_on = conn.execute("SELECT COALESCE((%s::timestamptz AT TIME ZONE current_setting('TimeZone'))::date, "
                                "current_date) AS d", (g["started_at"],)).fetchone()["d"]
        data = {k: g[k] for k in ("started_at", "ended_at", "distance_m", "moving_s", "elapsed_s", "ascent_m", "descent_m",
                                  "max_ele_m", "min_ele_m", "start_lat", "start_lon", "is_loop", "points", "trail_url")}
        data.update(name=(g["name"] or stem or "Hike")[:200], hiked_on=hiked_on, notes=g["description"], source="gpx",
                    gpx_name=(filename or "track.gpx")[:255], gpx_hash=g["hash"], gpx=raw,
                    track=Jsonb(g["track"]), splits=Jsonb(g["splits"]), waypoints=Jsonb(g["waypoints"]))
        hike_id = insert_row(conn, "hikes", data, "hike_id")
        return {**fetch(conn, hike_id), "duplicate": False}


@router.get("/hiking/hikes")
def list_hikes(q: str | None = Query(None, max_length=100), year: int | None = Query(None, ge=1900, le=2200)):
    """Every hike, newest first (q = search the name, trail, place, people and notes)."""
    with db() as conn:
        return conn.execute(COLUMNS + """ FROM hikes
            WHERE (%(q)s::text IS NULL OR concat_ws(' ', name, trail_name, location, companions, notes) ILIKE '%%' || %(q)s || '%%')
              AND (%(year)s::int IS NULL OR extract(year FROM hiked_on) = %(year)s)
            ORDER BY hiked_on DESC, started_at DESC NULLS LAST, hike_id DESC""",
                            {"q": (q or "").strip() or None, "year": year}).fetchall()


@router.post("/hiking/hikes", status_code=201)
def add_hike(body: HikeIn):
    with db() as conn:
        return fetch(conn, insert_row(conn, "hikes", {**_columns(body.model_dump()), "source": "manual"}, "hike_id"))


@router.get("/hiking/hikes/{hike_id}")
def get_hike(hike_id: int):
    with db() as conn:
        return fetch(conn, hike_id)


@router.patch("/hiking/hikes/{hike_id}")
def update_hike(hike_id: int, body: HikePatch):
    data = _columns(body.model_dump(exclude_unset=True))
    for required in ("name", "hiked_on"):
        if required in data and not data[required]:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        fetch(conn, hike_id)
        update_row(conn, "hikes", "hike_id", hike_id, data)
        return fetch(conn, hike_id)


@router.delete("/hiking/hikes/{hike_id}", status_code=204)
def delete_hike(hike_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM hikes WHERE hike_id = %s RETURNING hike_id", (hike_id,)).fetchone(), "Hike")
    return Response(status_code=204)


@router.get("/hiking/hikes/{hike_id}/gpx")
def download_gpx(hike_id: int):
    """The GPX file exactly as it was imported."""
    with db() as conn:
        row = found(conn.execute("SELECT gpx, gpx_name FROM hikes WHERE hike_id = %s", (hike_id,)).fetchone(), "Hike")
    if row["gpx"] is None:
        raise HTTPException(404, "This hike was logged by hand, so it has no GPX file.")
    name = re.sub(r"[^\w .-]+", "", row["gpx_name"] or "") or "hike.gpx"
    return Response(bytes(row["gpx"]), media_type="application/gpx+xml",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


add_photo_routes(router, "/hiking/hikes", "hikes", "hike_id", "Hike")


@router.get("/hiking/summary")
def summary():
    """This year and all time, km per month for the last 12 months, personal bests, the latest hikes."""
    totals = """SELECT count(*) AS hikes, COALESCE(sum(distance_m), 0)::float8 / 1000 AS km,
                       COALESCE(sum(ascent_m), 0)::float8 AS ascent_m, COALESCE(sum(COALESCE(moving_s, elapsed_s)), 0) AS seconds,
                       count(DISTINCT trail_name) FILTER (WHERE trail_name IS NOT NULL) AS trails
                FROM hikes"""
    with db() as conn:
        year = conn.execute("SELECT extract(year FROM current_date)::int AS y").fetchone()["y"]
        this_year = conn.execute(totals + " WHERE hiked_on >= date_trunc('year', current_date)").fetchone()
        all_time = conn.execute(totals).fetchone()
        months = conn.execute("""
            SELECT to_char(m, 'YYYY-MM') AS month, COALESCE(sum(h.distance_m), 0)::float8 / 1000 AS km, count(h.hike_id) AS hikes
            FROM generate_series(date_trunc('month', current_date) - interval '11 months', date_trunc('month', current_date),
                                 interval '1 month') m
            LEFT JOIN hikes h ON date_trunc('month', h.hiked_on) = m
            GROUP BY m ORDER BY m""").fetchall()

        def best(order: str, where: str = "TRUE"):
            return conn.execute(COLUMNS + f" FROM hikes WHERE {where} ORDER BY {order}, hiked_on DESC LIMIT 1").fetchone()
        bests = {
            "longest": best("distance_m DESC", "distance_m > 0"),
            "climb": best("ascent_m DESC", "ascent_m > 0"),
            "highest": best("max_ele_m DESC", "max_ele_m IS NOT NULL"),
            "fastest": best("moving_s / distance_m", "moving_s > 0 AND distance_m >= 3000"),
        }
        recent = conn.execute(COLUMNS + " FROM hikes ORDER BY hiked_on DESC, started_at DESC NULLS LAST, hike_id DESC LIMIT 5").fetchall()
    return {"year": year, "this_year": this_year, "all_time": all_time, "months": months, "bests": bests, "recent": recent}
