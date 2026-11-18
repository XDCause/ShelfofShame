"""Scuba diving: the logbook (A12_scuba.sql). Sites, trips, certificates, gear service and the summary are in scuba.py;
the stats in scuba_stats.py. The dive computer's analysis, the import, the planner and the conditions are in
scuba_tools.py.

    GET  /scuba/dives?site_id=&trip_id=&year=&q=      the logbook, newest first (a brief each)
    POST /scuba/dives                                 a dive (no dive_no: the next number)
    GET / PATCH / DELETE /scuba/dives/{id}            all of it + the sightings, SAC, surface interval, previous / next
    PUT  /scuba/dives/{id}/sightings                  what you saw: replaces the list
    GET  /scuba/species                               the life list

SAC (surface air consumption, litres a minute) = bar used x tank litres / minutes / (average depth / 10 + 1); the
average depth is max depth x 0.6 when the dive has none; blank when anything else is missing.
Numbers: the logbook carries on from the dives logged before the app (scuba_settings.dives_before).
"""
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row

router = APIRouter(prefix="/api", tags=["scuba"])

CURRENTS = ["none", "light", "moderate", "strong"]
Current = Literal["none", "light", "moderate", "strong"]
Entry = Literal["shore", "boat"]

# SAC in SQL, for the lists (one place for the formula); the same sum in sac() for one dive in Python.
SAC_SQL = """CASE WHEN d.start_bar IS NOT NULL AND d.end_bar IS NOT NULL AND d.tank_l IS NOT NULL AND d.minutes > 0
                    AND COALESCE(d.avg_depth, d.max_depth * 0.6) IS NOT NULL
               THEN round(((d.start_bar - d.end_bar) * d.tank_l / d.minutes
                           / (COALESCE(d.avg_depth, d.max_depth * 0.6) / 10 + 1))::numeric, 1)::float8 END"""

BRIEF_SELECT = f"""SELECT d.dive_id, d.dive_no, d.dived_on, d.time_in, d.site_id, s.name AS site_name, d.trip_id, d.max_depth,
       d.minutes, d.water_temp, d.gas_o2, d.rating, d.tags, d.samples IS NOT NULL AS has_profile, {SAC_SQL} AS sac
FROM scuba_dives d LEFT JOIN scuba_sites s USING (site_id)"""
BRIEF_ORDER = " ORDER BY d.dived_on DESC, COALESCE(d.time_in, '00:00') DESC, d.dive_id DESC"
# every column but the profile (it's big: has_profile says whether there is one; GET /scuba/dives/{id}/analysis reads it)
FULL_SELECT = f"""SELECT d.dive_id, d.dive_no, d.dived_on, d.time_in, d.site_id, d.trip_id, d.max_depth, d.avg_depth, d.minutes,
       d.water_temp, d.air_temp, d.visibility_m, d.current, d.entry, d.tags, d.gas_o2, d.tank_l, d.start_bar, d.end_bar,
       d.weight_kg, d.suit, d.buddy, d.guide, d.operator, d.rating, d.notes, d.computer, d.import_key, d.created_at,
       d.samples IS NOT NULL AS has_profile, s.name AS site_name, t.name AS trip_name, {SAC_SQL} AS sac
FROM scuba_dives d LEFT JOIN scuba_sites s USING (site_id) LEFT JOIN scuba_trips t USING (trip_id)"""
ORDER_KEY = "(d.dived_on, COALESCE(d.time_in, '00:00'::time), d.dive_id)"


def sac(start_bar, end_bar, tank_l, minutes, avg_depth, max_depth):
    """Litres of surface air a minute, or None when something is missing."""
    depth = avg_depth if avg_depth is not None else (max_depth * 0.6 if max_depth is not None else None)
    if None in (start_bar, end_bar, tank_l, depth) or not minutes:
        return None
    return round(float((start_bar - end_bar) * tank_l / minutes / (depth / 10 + 1)), 1)


def settings_row(conn) -> dict:
    return conn.execute("SELECT * FROM scuba_settings WHERE id = 1").fetchone()


def next_dive_no(conn) -> int:
    """After your highest number: the dives logged before the app, or the highest number typed in the logbook."""
    return conn.execute("""SELECT GREATEST(s.dives_before, COALESCE((SELECT max(dive_no) FROM scuba_dives), 0)) + 1 AS n
                           FROM scuba_settings s WHERE s.id = 1""").fetchone()["n"]


def tidy_tags(tags: list[str] | None) -> list[str] | None:
    if tags is None:
        return None
    out = []
    for t in tags:
        t = " ".join(t.split()).lower()
        if t and t not in out:
            out.append(t)
    return out


# ---------------------------------------------------------------- the dive

class DiveFields(BaseModel):
    time_in: time | None = None
    site_id: int | None = None
    trip_id: int | None = None
    max_depth: float | None = Field(None, ge=0, le=350)
    avg_depth: float | None = Field(None, ge=0, le=350)
    minutes: int | None = Field(None, ge=1, le=1440)
    water_temp: float | None = Field(None, ge=-3, le=40)
    air_temp: float | None = Field(None, ge=-30, le=55)
    visibility_m: int | None = Field(None, ge=0, le=100)
    current: Current | None = None
    entry: Entry | None = None
    tags: list[str] | None = Field(None, max_length=30)
    tank_l: float | None = Field(None, ge=1, le=30)
    start_bar: int | None = Field(None, ge=0, le=350)
    end_bar: int | None = Field(None, ge=0, le=350)
    weight_kg: float | None = Field(None, ge=0, le=40)
    suit: str | None = Field(None, max_length=80)
    buddy: str | None = Field(None, max_length=120)
    guide: str | None = Field(None, max_length=120)
    operator: str | None = Field(None, max_length=120)
    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=10000)


class DiveIn(DiveFields):
    dived_on: date
    dive_no: int | None = Field(None, ge=1, le=100000)
    gas_o2: int = Field(21, ge=21, le=100)


class DivePatch(DiveFields):
    dived_on: date | None = None
    dive_no: int | None = Field(None, ge=1, le=100000)
    gas_o2: int | None = Field(None, ge=21, le=100)


def _check_links(conn, data: dict):
    if data.get("site_id") is not None:
        found(conn.execute("SELECT 1 FROM scuba_sites WHERE site_id = %s", (data["site_id"],)).fetchone(), "Site")
    if data.get("trip_id") is not None:
        found(conn.execute("SELECT 1 FROM scuba_trips WHERE trip_id = %s", (data["trip_id"],)).fetchone(), "Trip")


def _check_no(conn, dive_no, dive_id=None):
    if dive_no is None:
        return
    row = conn.execute("SELECT dive_id FROM scuba_dives WHERE dive_no = %s", (dive_no,)).fetchone()
    if row and row["dive_id"] != dive_id:
        raise HTTPException(409, f"Dive number {dive_no} is already in the logbook.")


def sightings_of(conn, dive_id: int) -> list[dict]:
    return conn.execute("SELECT species, how_many, notes FROM scuba_sightings WHERE dive_id = %s ORDER BY lower(species)",
                        (dive_id,)).fetchall()


def _start(row) -> datetime | None:
    return datetime.combine(row["dived_on"], row["time_in"]) if row["time_in"] is not None else None


def surface_interval(prev, cur) -> int | None:
    """Minutes between the previous dive's end and this dive's start; None without the times, or after 48 hours."""
    a, b = _start(prev), _start(cur)
    if a is None or b is None or prev["minutes"] is None:
        return None
    gap = (b - (a + timedelta(minutes=prev["minutes"]))).total_seconds() / 60
    return round(gap) if 0 <= gap <= 48 * 60 else None


def fetch_dive(conn, dive_id: int) -> dict:
    d = found(conn.execute(FULL_SELECT + " WHERE d.dive_id = %s", (dive_id,)).fetchone(), "Dive")
    d["sightings"] = sightings_of(conn, dive_id)
    key = "(%s, COALESCE(%s::time, '00:00'::time), %s)"
    args = (d["dived_on"], d["time_in"], dive_id)
    prev = conn.execute(f"SELECT d.dive_id, d.dived_on, d.time_in, d.minutes FROM scuba_dives d WHERE {ORDER_KEY} < {key} "
                        f"ORDER BY {ORDER_KEY} DESC LIMIT 1", args).fetchone()
    nxt = conn.execute(f"SELECT d.dive_id FROM scuba_dives d WHERE {ORDER_KEY} > {key} ORDER BY {ORDER_KEY} LIMIT 1", args).fetchone()
    d["prev_id"] = prev["dive_id"] if prev else None
    d["next_id"] = nxt["dive_id"] if nxt else None
    d["surface_interval_min"] = surface_interval(prev, d) if prev else None
    return d


@router.get("/scuba/dives")
def list_dives(site_id: int | None = None, trip_id: int | None = None, year: int | None = Query(None, ge=1900, le=2200),
               q: str | None = Query(None, max_length=100)):
    where, args = [], {}
    if site_id is not None:
        where.append("d.site_id = %(site)s")
        args["site"] = site_id
    if trip_id is not None:
        where.append("d.trip_id = %(trip)s")
        args["trip"] = trip_id
    if year is not None:
        where.append("extract(year FROM d.dived_on) = %(year)s")
        args["year"] = year
    if q and q.strip():
        where.append("""(s.name ILIKE %(q)s OR s.place ILIKE %(q)s OR d.buddy ILIKE %(q)s OR d.guide ILIKE %(q)s OR d.operator ILIKE %(q)s
                        OR d.notes ILIKE %(q)s OR d.suit ILIKE %(q)s OR d.dive_no::text = %(exact)s
                        OR EXISTS (SELECT 1 FROM unnest(d.tags) t WHERE t ILIKE %(q)s)
                        OR EXISTS (SELECT 1 FROM scuba_sightings g WHERE g.dive_id = d.dive_id AND g.species ILIKE %(q)s))""")
        args["q"] = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        args["exact"] = q.strip()
    with db() as conn:
        return conn.execute(BRIEF_SELECT + (" WHERE " + " AND ".join(where) if where else "") + BRIEF_ORDER, args).fetchall()


@router.post("/scuba/dives", status_code=201)
def add_dive(body: DiveIn):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    if "tags" in data:
        data["tags"] = tidy_tags(data["tags"])
    data = {k: v for k, v in data.items() if v is not None or k == "dive_no"}
    with db() as conn:
        _check_links(conn, data)
        _check_no(conn, data.get("dive_no"))
        if data.get("dive_no") is None:
            data["dive_no"] = next_dive_no(conn)
        dive_id = insert_row(conn, "scuba_dives", data, "dive_id")
        return fetch_dive(conn, dive_id)


@router.get("/scuba/dives/{dive_id}")
def get_dive(dive_id: int):
    with db() as conn:
        return fetch_dive(conn, dive_id)


@router.patch("/scuba/dives/{dive_id}")
def update_dive(dive_id: int, body: DivePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    for name in ("dived_on", "gas_o2"):
        if name in data and data[name] is None:
            raise HTTPException(422, f"{name.replace('_', ' ').capitalize()} can't be empty.")
    if "tags" in data:
        data["tags"] = tidy_tags(data["tags"]) or []
    with db() as conn:
        found(conn.execute("SELECT 1 FROM scuba_dives WHERE dive_id = %s", (dive_id,)).fetchone(), "Dive")
        _check_links(conn, data)
        _check_no(conn, data.get("dive_no"), dive_id)
        if "dive_no" in data and data["dive_no"] is None:
            data["dive_no"] = next_dive_no(conn)
        update_row(conn, "scuba_dives", "dive_id", dive_id, data)
        return fetch_dive(conn, dive_id)


@router.delete("/scuba/dives/{dive_id}", status_code=204)
def delete_dive(dive_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM scuba_dives WHERE dive_id = %s RETURNING dive_id", (dive_id,)).fetchone(), "Dive")
    return Response(status_code=204)


# ---------------------------------------------------------------- what you saw

class SightingIn(BaseModel):
    species: str = Field(min_length=1, max_length=120)
    how_many: int | None = Field(None, ge=1, le=32000)
    notes: str | None = Field(None, max_length=500)


@router.put("/scuba/dives/{dive_id}/sightings")
def put_sightings(dive_id: int, body: list[SightingIn]):
    """Replaces what you saw on this dive. A species twice (any capitals) counts once: the first is kept."""
    seen, rows = set(), []
    for s in body:
        name = " ".join(s.species.split())
        if not name:
            raise HTTPException(422, "A sighting needs a species.")
        if name.lower() not in seen:
            seen.add(name.lower())
            rows.append((dive_id, name, s.how_many, (s.notes or "").strip() or None))
    with db() as conn:
        found(conn.execute("SELECT 1 FROM scuba_dives WHERE dive_id = %s", (dive_id,)).fetchone(), "Dive")
        conn.execute("DELETE FROM scuba_sightings WHERE dive_id = %s", (dive_id,))
        for r in rows:
            conn.execute("INSERT INTO scuba_sightings (dive_id, species, how_many, notes) VALUES (%s, %s, %s, %s)", r)
        return sightings_of(conn, dive_id)


@router.get("/scuba/species")
def species():
    """The life list: every species you've seen, how many dives, how many in all, the first and last time."""
    with db() as conn:
        return conn.execute("""
            SELECT (array_agg(g.species ORDER BY d.dived_on, d.dive_id))[1] AS species, count(*)::int AS dives,
                   COALESCE(sum(g.how_many), 0)::int AS total, min(d.dived_on) AS first_on, max(d.dived_on) AS last_on,
                   (array_agg(d.dive_id ORDER BY d.dived_on, COALESCE(d.time_in, '00:00'), d.dive_id))[1] AS first_dive_id
            FROM scuba_sightings g JOIN scuba_dives d USING (dive_id)
            GROUP BY lower(g.species) ORDER BY lower((array_agg(g.species ORDER BY d.dived_on, d.dive_id))[1])""").fetchall()
