"""Scuba diving (A12_scuba.sql): the settings, the summary (what's due, when you can fly), sites, trips, certification
cards and the service log of your scuba gear. The logbook is in scuba_dives.py, the stats in scuba_stats.py, the planner,
profile analysis, import, conditions and OpenStreetMap in scuba_tools.py.

    GET / PUT /scuba/settings                  your planning defaults, the dives logged before the app, medical / insurance dates
    GET  /scuba/summary                        totals, last dive, the no-fly time, what's due soon, recent dives
    GET / POST /scuba/sites, GET / PATCH / DELETE /scuba/sites/{id}     (a dive keeps its place in the logbook when its site goes)
    GET / POST /scuba/trips, GET / PATCH / DELETE /scuba/trips/{id}
    GET / POST /scuba/certs, PATCH / DELETE /scuba/certs/{id}
    GET  /scuba/gear                           the gear pages' scuba gear + when each was last serviced and is next due
    GET / POST /scuba/gear/{gear_id}/service, DELETE /scuba/service/{id}      (gear itself: POST /gear with hobby 'scuba')

The no-fly time is DAN's guideline (a rule of thumb, not medical advice): 12 hours after a single dive, 18 hours after
repeat dives on a day or dives on consecutive days. A dive with no start time counts as ending at the end of its day.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import gear as gear_module
from .db import db, found, insert_row, tidy_text, update_row
from .scuba_dives import BRIEF_ORDER, BRIEF_SELECT, next_dive_no, settings_row

router = APIRouter(prefix="/api", tags=["scuba"])

ALERT_DAYS = 60


def _required(data: dict, *names):
    for n in names:
        if n in data and data[n] is None:
            raise HTTPException(422, f"{n.replace('_', ' ').capitalize()} can't be empty.")


# ---------------------------------------------------------------- settings

class SettingsIn(BaseModel):
    gas_o2: int | None = Field(None, ge=21, le=100)
    tank_l: float | None = Field(None, ge=1, le=30)
    start_bar: int | None = Field(None, ge=50, le=300)
    sac_l_min: float | None = Field(None, ge=5, le=60)
    gf_low: int | None = Field(None, ge=10, le=100)
    gf_high: int | None = Field(None, ge=10, le=100)
    ppo2_max: float | None = Field(None, ge=1.0, le=1.6)
    dives_before: int | None = Field(None, ge=0, le=100000)
    minutes_before: int | None = Field(None, ge=0, le=10000000)
    medical_due: date | None = None
    insurance_until: date | None = None
    home_lat: float | None = Field(None, ge=-90, le=90)
    home_lon: float | None = Field(None, ge=-180, le=180)


NOT_EMPTY = ("gas_o2", "tank_l", "start_bar", "sac_l_min", "gf_low", "gf_high", "ppo2_max", "dives_before", "minutes_before")


@router.get("/scuba/settings")
def get_settings():
    with db() as conn:
        return settings_row(conn)


@router.put("/scuba/settings")
def put_settings(body: SettingsIn):
    data = body.model_dump(exclude_unset=True)
    _required(data, *NOT_EMPTY)
    with db() as conn:
        if data:
            update_row(conn, "scuba_settings", "id", 1, data)
            conn.execute("UPDATE scuba_settings SET updated_at = now() WHERE id = 1")
        return settings_row(conn)


# ---------------------------------------------------------------- no-fly time

def no_fly_until(rows: list[dict], now: datetime) -> datetime | None:
    """When it's safe to fly: 12 h after the end of the last dive, 18 h if it was a repeat dive that day or dives were
    on 2+ consecutive days (DAN's guideline); None when that time has passed. Rows: dived_on, time_in, minutes."""
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: (r["dived_on"], r["time_in"] or time.max))
    last = rows[-1]
    start = datetime.combine(last["dived_on"], last["time_in"] if last["time_in"] is not None else time(23, 59))
    end = start + timedelta(minutes=last["minutes"] or 0)
    days = {r["dived_on"] for r in rows}
    repeat = sum(1 for r in rows if r["dived_on"] == last["dived_on"]) >= 2
    consecutive = last["dived_on"] - timedelta(days=1) in days
    until = end + timedelta(hours=18 if repeat or consecutive else 12)
    return until if until > now else None


# ---------------------------------------------------------------- what's due

def due_services(conn) -> list[dict]:
    """The latest service of each kind (annual service, visual, hydro...) of each piece of gear that has a next date."""
    return conn.execute("""
        SELECT * FROM (
            SELECT DISTINCT ON (s.gear_id, lower(s.what)) s.gear_id, g.name AS gear_name, s.what, s.done_on, s.next_due
            FROM scuba_gear_service s JOIN gear g USING (gear_id)
            WHERE g.hobby = 'scuba' AND g.condition NOT IN ('Wanted', 'Retired')
            ORDER BY s.gear_id, lower(s.what), s.done_on DESC, s.service_id DESC) x
        WHERE next_due IS NOT NULL ORDER BY next_due, gear_name""").fetchall()


def _when(due: date, today: date) -> str:
    n = (due - today).days
    if n < 0:
        return f"is overdue by {-n} day{'' if n == -1 else 's'}"
    return "is due today" if n == 0 else f"is due in {n} day{'' if n == 1 else 's'}"


def alerts(conn, today: date) -> list[dict]:
    """Medical, insurance, cards and gear service due within 60 days (or overdue), soonest first."""
    s = settings_row(conn)
    items = []
    if s["medical_due"]:
        items.append(("medical", "Dive medical", s["medical_due"]))
    if s["insurance_until"]:
        items.append(("insurance", "Dive insurance", s["insurance_until"]))
    for c in conn.execute("SELECT agency, name, expires_on FROM scuba_certs WHERE expires_on IS NOT NULL").fetchall():
        items.append(("cert", f"{c['agency']} {c['name']} card", c["expires_on"]))
    for d in due_services(conn):
        items.append(("service", f"{d['gear_name']}: {d['what'].lower()}", d["next_due"]))
    out = [{"kind": k, "text": f"{label} {_when(due, today)}", "due": due}
           for k, label, due in items if (due - today).days <= ALERT_DAYS]
    return sorted(out, key=lambda a: (a["due"], a["kind"], a["text"]))


# ---------------------------------------------------------------- the summary

@router.get("/scuba/summary")
def summary():
    with db() as conn:
        s = settings_row(conn)
        now = conn.execute("SELECT localtimestamp AS now, current_date AS today").fetchone()
        t = conn.execute("""SELECT count(*)::int AS n, COALESCE(sum(minutes), 0)::int AS minutes, max(max_depth) AS deepest,
                                   max(minutes) AS longest,
                                   count(*) FILTER (WHERE extract(year FROM dived_on) = extract(year FROM current_date))::int AS this_year
                            FROM scuba_dives""").fetchone()
        recent = conn.execute(BRIEF_SELECT + BRIEF_ORDER + " LIMIT 5").fetchall()
        recent_rows = conn.execute("""SELECT dived_on, time_in, minutes FROM scuba_dives
                                      WHERE dived_on >= (SELECT max(dived_on) FROM scuba_dives) - 1""").fetchall()
        return {"dives": s["dives_before"] + t["n"], "minutes": s["minutes_before"] + t["minutes"], "dives_logged": t["n"],
                "deepest": t["deepest"], "longest": t["longest"], "last_dive": recent[0] if recent else None,
                "next_no": next_dive_no(conn),
                "sites": conn.execute("SELECT count(*)::int AS n FROM scuba_sites").fetchone()["n"],
                "species": conn.execute("SELECT count(DISTINCT lower(species))::int AS n FROM scuba_sightings").fetchone()["n"],
                "this_year": t["this_year"],
                "no_fly_until": no_fly_until(recent_rows, now["now"]),
                "alerts": alerts(conn, now["today"]), "recent": recent}


# ---------------------------------------------------------------- sites

class SiteFields(BaseModel):
    place: str | None = Field(None, max_length=120)
    country: str | None = Field(None, max_length=80)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    kind: str | None = Field(None, max_length=40)
    entry: str | None = Field(None, pattern=r"^(shore|boat)$")
    depth_min: float | None = Field(None, ge=0, le=350)
    depth_max: float | None = Field(None, ge=0, le=350)
    notes: str | None = Field(None, max_length=5000)


class SiteIn(SiteFields):
    name: str = Field(min_length=1, max_length=120)


class SitePatch(SiteFields):
    name: str | None = Field(None, min_length=1, max_length=120)


SITE_SELECT = """SELECT s.site_id, s.name, s.place, s.country, s.lat, s.lon, s.kind, s.entry, s.depth_min, s.depth_max, s.osm,
       s.notes, s.created_at, (SELECT count(*) FROM scuba_dives d WHERE d.site_id = s.site_id)::int AS dives,
       (SELECT max(d.dived_on) FROM scuba_dives d WHERE d.site_id = s.site_id) AS last_on,
       (SELECT max(d.max_depth) FROM scuba_dives d WHERE d.site_id = s.site_id) AS deepest
FROM scuba_sites s"""


def site_detail(conn, site_id: int) -> dict:
    s = found(conn.execute(SITE_SELECT + " WHERE s.site_id = %s", (site_id,)).fetchone(), "Site")
    s["recent_dives"] = conn.execute(BRIEF_SELECT + " WHERE d.site_id = %s" + BRIEF_ORDER, (site_id,)).fetchall()
    s["species_seen"] = conn.execute("""
        SELECT (array_agg(g.species ORDER BY d.dived_on))[1] AS species, count(*)::int AS dives
        FROM scuba_sightings g JOIN scuba_dives d USING (dive_id) WHERE d.site_id = %s
        GROUP BY lower(g.species) ORDER BY count(*) DESC, 1""", (site_id,)).fetchall()
    c = conn.execute("""SELECT round(avg(water_temp), 1)::float8 AS avg_temp, round(avg(visibility_m), 1)::float8 AS avg_vis
                        FROM scuba_dives WHERE site_id = %s""", (site_id,)).fetchone()
    s["avg_temp"], s["avg_vis"] = c["avg_temp"], c["avg_vis"]
    return s


@router.get("/scuba/sites")
def list_sites():
    with db() as conn:
        return conn.execute(SITE_SELECT + " ORDER BY lower(s.name), s.site_id").fetchall()


@router.post("/scuba/sites", status_code=201)
def add_site(body: SiteIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        return site_detail(conn, insert_row(conn, "scuba_sites", data, "site_id"))


@router.get("/scuba/sites/{site_id}")
def get_site(site_id: int):
    with db() as conn:
        return site_detail(conn, site_id)


@router.patch("/scuba/sites/{site_id}")
def update_site(site_id: int, body: SitePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _required(data, "name")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM scuba_sites WHERE site_id = %s", (site_id,)).fetchone(), "Site")
        update_row(conn, "scuba_sites", "site_id", site_id, data)
        return site_detail(conn, site_id)


@router.delete("/scuba/sites/{site_id}", status_code=204)
def delete_site(site_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM scuba_sites WHERE site_id = %s RETURNING site_id", (site_id,)).fetchone(), "Site")
    return Response(status_code=204)


# ---------------------------------------------------------------- trips

class TripFields(BaseModel):
    place: str | None = Field(None, max_length=120)
    operator: str | None = Field(None, max_length=120)
    end_on: date | None = None
    notes: str | None = Field(None, max_length=5000)


class TripIn(TripFields):
    name: str = Field(min_length=1, max_length=120)
    start_on: date


class TripPatch(TripFields):
    name: str | None = Field(None, min_length=1, max_length=120)
    start_on: date | None = None


TRIP_SELECT = """SELECT t.trip_id, t.name, t.place, t.operator, t.start_on, t.end_on, t.notes, t.created_at,
       (SELECT count(*) FROM scuba_dives d WHERE d.trip_id = t.trip_id)::int AS dives,
       (SELECT COALESCE(sum(d.minutes), 0) FROM scuba_dives d WHERE d.trip_id = t.trip_id)::int AS minutes,
       (SELECT max(d.max_depth) FROM scuba_dives d WHERE d.trip_id = t.trip_id) AS deepest
FROM scuba_trips t"""


def trip_detail(conn, trip_id: int) -> dict:
    t = found(conn.execute(TRIP_SELECT + " WHERE t.trip_id = %s", (trip_id,)).fetchone(), "Trip")
    t["dive_list"] = conn.execute(BRIEF_SELECT + " WHERE d.trip_id = %s" + BRIEF_ORDER, (trip_id,)).fetchall()
    t["totals"] = {"dives": t["dives"], "minutes": t["minutes"], "deepest": t["deepest"],
                   "sites": len({d["site_id"] for d in t["dive_list"] if d["site_id"] is not None})}
    return t


@router.get("/scuba/trips")
def list_trips():
    with db() as conn:
        return conn.execute(TRIP_SELECT + " ORDER BY t.start_on DESC, t.trip_id DESC").fetchall()


@router.post("/scuba/trips", status_code=201)
def add_trip(body: TripIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        return trip_detail(conn, insert_row(conn, "scuba_trips", data, "trip_id"))


@router.get("/scuba/trips/{trip_id}")
def get_trip(trip_id: int):
    with db() as conn:
        return trip_detail(conn, trip_id)


@router.patch("/scuba/trips/{trip_id}")
def update_trip(trip_id: int, body: TripPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _required(data, "name", "start_on")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM scuba_trips WHERE trip_id = %s", (trip_id,)).fetchone(), "Trip")
        update_row(conn, "scuba_trips", "trip_id", trip_id, data)
        return trip_detail(conn, trip_id)


@router.delete("/scuba/trips/{trip_id}", status_code=204)
def delete_trip(trip_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM scuba_trips WHERE trip_id = %s RETURNING trip_id", (trip_id,)).fetchone(), "Trip")
    return Response(status_code=204)


# ---------------------------------------------------------------- certification cards

class CertFields(BaseModel):
    cert_no: str | None = Field(None, max_length=60)
    certified_on: date | None = None
    instructor: str | None = Field(None, max_length=120)
    expires_on: date | None = None
    notes: str | None = Field(None, max_length=2000)


class CertIn(CertFields):
    agency: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)


class CertPatch(CertFields):
    agency: str | None = Field(None, min_length=1, max_length=40)
    name: str | None = Field(None, min_length=1, max_length=120)


@router.get("/scuba/certs")
def list_certs():
    with db() as conn:
        return conn.execute("SELECT * FROM scuba_certs ORDER BY certified_on DESC NULLS LAST, cert_id DESC").fetchall()


@router.post("/scuba/certs", status_code=201)
def add_cert(body: CertIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("agency", "name"))
    with db() as conn:
        cert_id = insert_row(conn, "scuba_certs", data, "cert_id")
        return conn.execute("SELECT * FROM scuba_certs WHERE cert_id = %s", (cert_id,)).fetchone()


@router.patch("/scuba/certs/{cert_id}")
def update_cert(cert_id: int, body: CertPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("agency", "name"))
    _required(data, "agency", "name")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM scuba_certs WHERE cert_id = %s", (cert_id,)).fetchone(), "Card")
        update_row(conn, "scuba_certs", "cert_id", cert_id, data)
        return conn.execute("SELECT * FROM scuba_certs WHERE cert_id = %s", (cert_id,)).fetchone()


@router.delete("/scuba/certs/{cert_id}", status_code=204)
def delete_cert(cert_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM scuba_certs WHERE cert_id = %s RETURNING cert_id", (cert_id,)).fetchone(), "Card")
    return Response(status_code=204)


# ---------------------------------------------------------------- gear service

class ServiceIn(BaseModel):
    done_on: date
    what: str = Field(min_length=1, max_length=120)
    done_by: str | None = Field(None, max_length=120)
    cost: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=2)
    next_due: date | None = None
    notes: str | None = Field(None, max_length=2000)


def _scuba_gear(conn, gear_id: int) -> dict:
    g = found(conn.execute(gear_module.GEAR_SELECT + " WHERE g.gear_id = %s", (gear_id,)).fetchone(), "Gear")
    if g["hobby"] != "scuba":
        raise HTTPException(404, "That isn't scuba gear.")
    return g


@router.get("/scuba/gear")
def scuba_gear():
    """Scuba gear (in use first), each with its last service, when the next is due (the soonest of its kinds of
    service: a tank's visual and hydro test) and the dives since the last service (all of them if never serviced)."""
    with db() as conn:
        gear = conn.execute(gear_module.GEAR_SELECT + " WHERE g.hobby = 'scuba' ORDER BY "
                            "(g.condition IN ('Wanted', 'Retired')), g.condition = 'Wanted', lower(g.name), g.gear_id").fetchall()
        due = {}
        for d in due_services(conn):
            due.setdefault(d["gear_id"], d["next_due"])           # (sorted soonest first)
        for g in gear:
            last = conn.execute("""SELECT service_id, done_on, what, done_by, next_due FROM scuba_gear_service
                                   WHERE gear_id = %s ORDER BY done_on DESC, service_id DESC LIMIT 1""", (g["gear_id"],)).fetchone()
            g["last_service"] = last
            g["next_due"] = due.get(g["gear_id"])
            g["services"] = conn.execute("SELECT count(*)::int AS n FROM scuba_gear_service WHERE gear_id = %s", (g["gear_id"],)).fetchone()["n"]
            since = last["done_on"] if last else None
            g["dives_since_service"] = conn.execute(
                "SELECT count(*)::int AS n FROM scuba_dives WHERE %s::date IS NULL OR dived_on > %s::date", (since, since)).fetchone()["n"]
        return gear


@router.get("/scuba/gear/{gear_id}/service")
def list_service(gear_id: int):
    with db() as conn:
        _scuba_gear(conn, gear_id)
        return conn.execute("SELECT * FROM scuba_gear_service WHERE gear_id = %s ORDER BY done_on DESC, service_id DESC",
                            (gear_id,)).fetchall()


@router.post("/scuba/gear/{gear_id}/service", status_code=201)
def add_service(gear_id: int, body: ServiceIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("what",))
    with db() as conn:
        _scuba_gear(conn, gear_id)
        service_id = insert_row(conn, "scuba_gear_service", {**data, "gear_id": gear_id}, "service_id")
        return conn.execute("SELECT * FROM scuba_gear_service WHERE service_id = %s", (service_id,)).fetchone()


@router.delete("/scuba/service/{service_id}", status_code=204)
def delete_service(service_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM scuba_gear_service WHERE service_id = %s RETURNING service_id", (service_id,)).fetchone(), "Service")
    return Response(status_code=204)
