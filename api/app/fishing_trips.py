"""Fishing: the trips - a session on the water with its catches (A13_fishing.sql). The catches, the rules check and the
photos are in fishing_catches.py; the summary, spots, species and lures in fishing.py; the stats in fishing_stats.py.

    GET    /fishing/trips?spot_id=&year=&q=     newest first (a brief each)
    POST   /fishing/trips                       a trip (started_at defaults to now; a client_key that exists returns that trip, 200). The conditions then (moon, tide, wind...)
                                                are filled in when the spot has a position (fishing_tools.snapshot)
    GET / PATCH / DELETE /fishing/trips/{id}    all of it + its catches (photos, warnings), fish per hour, previous / next
    POST   /fishing/trips/{id}/end              ended_at = now (or the body's ended_at)

A trip with no ended_at is "open": you're on the water (the phone's live page carries on with it).
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .fishing_catches import CATCH_SELECT, photo_list, rule_warnings

router = APIRouter(prefix="/api", tags=["fishing"])

Platform = Literal["shore", "jetty", "boat", "kayak", "wading"]

HOURS = "round((extract(epoch FROM (t.ended_at - t.started_at)) / 3600)::numeric, 2)::float8"   # null while it's open

BRIEF_SELECT = f"""SELECT t.trip_id, t.started_at, t.ended_at, {HOURS} AS hours, t.spot_id, s.name AS spot_name, t.platform,
       t.target, t.rating,
       (SELECT count(*) FROM fishing_catches c WHERE c.trip_id = t.trip_id)::int AS catches,
       (SELECT count(*) FROM fishing_catches c WHERE c.trip_id = t.trip_id AND c.fate = 'kept')::int AS kept,
       COALESCE((SELECT array_agg(DISTINCT COALESCE(sp.name, c.species) ORDER BY COALESCE(sp.name, c.species))
                 FROM fishing_catches c LEFT JOIN fishing_species sp USING (species_id) WHERE c.trip_id = t.trip_id),
                '{{}}') AS species,
       (SELECT jsonb_build_object('species', COALESCE(sp.name, c.species), 'length_cm', c.length_cm::float8)
        FROM fishing_catches c LEFT JOIN fishing_species sp USING (species_id)
        WHERE c.trip_id = t.trip_id AND c.length_cm IS NOT NULL ORDER BY c.length_cm DESC, c.catch_id LIMIT 1) AS best
FROM fishing_trips t LEFT JOIN fishing_spots s USING (spot_id)"""
BRIEF_ORDER = " ORDER BY t.started_at DESC, t.trip_id DESC"

FULL_SELECT = f"""SELECT t.trip_id, t.started_at, t.ended_at, {HOURS} AS hours, t.spot_id, t.platform, t.target, t.companions,
       t.conditions, t.rating, t.notes, t.client_key, t.created_at, s.name AS spot_name, s.lat AS spot_lat, s.lon AS spot_lon
FROM fishing_trips t LEFT JOIN fishing_spots s USING (spot_id)"""


def snapshot_for(conn, spot_id: int | None, started_at: datetime) -> dict | None:
    """The conditions then (moon, tide, wind, pressure...), from fishing_tools.snapshot, for a spot with a position. Anything
    wrong - the tools missing, an outside site down - leaves it None: a trip is never refused for want of weather."""
    if spot_id is None:
        return None
    try:
        from . import fishing_tools
        spot = conn.execute("SELECT * FROM fishing_spots WHERE spot_id = %s", (spot_id,)).fetchone()
        if not spot or spot["lat"] is None or spot["lon"] is None:
            return None
        return fishing_tools.snapshot(conn, spot, started_at) or None
    except Exception:       # noqa: BLE001 - deliberately everything: see above
        return None


def fill_conditions(conn, trip_id: int):
    """Take the snapshot when the trip has none yet (and its spot has a position)."""
    t = conn.execute("SELECT spot_id, started_at, conditions FROM fishing_trips WHERE trip_id = %s", (trip_id,)).fetchone()
    if t and not t["conditions"]:
        snap = snapshot_for(conn, t["spot_id"], t["started_at"])
        if snap:
            conn.execute("UPDATE fishing_trips SET conditions = %s WHERE trip_id = %s", (Jsonb(snap), trip_id))


def trip_detail(conn, trip_id: int) -> dict:
    t = found(conn.execute(FULL_SELECT + " WHERE t.trip_id = %s", (trip_id,)).fetchone(), "Trip")
    catches = conn.execute(CATCH_SELECT + " WHERE c.trip_id = %s ORDER BY COALESCE(c.caught_at, t.started_at), c.catch_id",
                           (trip_id,)).fetchall()
    photos = photo_list(conn, [c["catch_id"] for c in catches])
    for c in catches:
        c["photos"] = photos[c["catch_id"]]
        c["warnings"] = rule_warnings(conn, c)
    t["catches"] = catches
    t["fish_per_hour"] = round(len(catches) / t["hours"], 2) if t["hours"] else None
    order = "(started_at, trip_id)"
    for key, op, direction in (("prev_id", "<", "DESC"), ("next_id", ">", "ASC")):
        row = conn.execute(f"""SELECT trip_id FROM fishing_trips WHERE {order} {op} (%s, %s)
                               ORDER BY started_at {direction}, trip_id {direction} LIMIT 1""",
                           (t["started_at"], trip_id)).fetchone()
        t[key] = row["trip_id"] if row else None
    return t


@router.get("/fishing/trips")
def list_trips(spot_id: int | None = None, year: int | None = Query(None, ge=1900, le=2200), q: str | None = Query(None, max_length=100)):
    where, args = ["true"], {}
    if spot_id is not None:
        where.append("t.spot_id = %(spot)s")
        args["spot"] = spot_id
    if year is not None:
        where.append("extract(year FROM t.started_at::timestamp) = %(year)s")
        args["year"] = year
    if q and q.strip():
        args["q"] = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("""(s.name ILIKE %(q)s OR t.target ILIKE %(q)s OR t.companions ILIKE %(q)s OR t.notes ILIKE %(q)s OR EXISTS (
                            SELECT 1 FROM fishing_catches c LEFT JOIN fishing_species sp USING (species_id)
                            WHERE c.trip_id = t.trip_id AND COALESCE(sp.name, c.species) ILIKE %(q)s))""")
    with db() as conn:
        return conn.execute(BRIEF_SELECT + " WHERE " + " AND ".join(where) + BRIEF_ORDER, args).fetchall()


class TripFields(BaseModel):
    ended_at: datetime | None = None
    spot_id: int | None = None
    platform: Platform | None = None
    target: str | None = Field(None, max_length=120)
    companions: str | None = Field(None, max_length=200)
    conditions: dict | None = None
    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=10000)


class TripIn(TripFields):
    started_at: datetime | None = None          # now when it isn't given (starting on the water)
    client_key: str | None = Field(None, min_length=1, max_length=80)   # from the phone: sending it again returns the same trip


class TripPatch(TripFields):
    started_at: datetime | None = None


def _data(body: BaseModel, **kw) -> dict:
    data = tidy_text(body.model_dump(**kw))
    if data.get("conditions") is not None:
        data["conditions"] = Jsonb(data["conditions"])
    return data


def _check_spot(conn, data: dict):
    if data.get("spot_id") is not None:
        found(conn.execute("SELECT 1 FROM fishing_spots WHERE spot_id = %s", (data["spot_id"],)).fetchone(), "Spot")


@router.post("/fishing/trips", status_code=201)
def add_trip(body: TripIn, response: Response):
    data = {k: v for k, v in _data(body).items() if v is not None}
    with db() as conn:
        if data.get("client_key"):
            old = conn.execute("SELECT trip_id FROM fishing_trips WHERE client_key = %s", (data["client_key"],)).fetchone()
            if old:                                  # the same trip sent again: no duplicate
                response.status_code = 200
                return trip_detail(conn, old["trip_id"])
        _check_spot(conn, data)
        if "started_at" not in data:
            data["started_at"] = conn.execute("SELECT now() AS n").fetchone()["n"]
        response.status_code = 201
        trip_id = insert_row(conn, "fishing_trips", data, "trip_id")
        fill_conditions(conn, trip_id)
        return trip_detail(conn, trip_id)


@router.get("/fishing/trips/{trip_id}")
def get_trip(trip_id: int):
    with db() as conn:
        return trip_detail(conn, trip_id)


@router.patch("/fishing/trips/{trip_id}")
def update_trip(trip_id: int, body: TripPatch):
    data = _data(body, exclude_unset=True)
    if "started_at" in data and data["started_at"] is None:
        raise HTTPException(422, "Started at can't be empty.")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM fishing_trips WHERE trip_id = %s", (trip_id,)).fetchone(), "Trip")
        _check_spot(conn, data)
        if data.get("conditions") == {}:
            data["conditions"] = None
        update_row(conn, "fishing_trips", "trip_id", trip_id, data)
        fill_conditions(conn, trip_id)
        return trip_detail(conn, trip_id)


@router.delete("/fishing/trips/{trip_id}", status_code=204)
def delete_trip(trip_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM fishing_trips WHERE trip_id = %s RETURNING trip_id", (trip_id,)).fetchone(), "Trip")
    return Response(status_code=204)


class EndIn(BaseModel):
    ended_at: datetime | None = None


@router.post("/fishing/trips/{trip_id}/end")
def end_trip(trip_id: int, body: EndIn | None = None):
    with db() as conn:
        found(conn.execute("SELECT 1 FROM fishing_trips WHERE trip_id = %s", (trip_id,)).fetchone(), "Trip")
        ended = body.ended_at if body and body.ended_at else conn.execute("SELECT now() AS n").fetchone()["n"]
        conn.execute("UPDATE fishing_trips SET ended_at = %s WHERE trip_id = %s", (ended, trip_id))
        return trip_detail(conn, trip_id)
