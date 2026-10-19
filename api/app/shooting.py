"""Precision shooting: your rifles (and scopes), factory ammunition, ranges and the licence / club details
(73_shooting.sql). Sessions, groups, DOPE and the dashboard are in shooting_sessions.py; the arithmetic in shotmath.py.

    GET  /shooting/lists                  the choices (kinds, actions, positions...)
    GET / PUT /shooting/settings          licence expiry, club shoots needed a year, default cleaning interval
    GET / POST /shooting/ranges, PATCH / DELETE /shooting/ranges/{id}
    GET / POST /shooting/rifles           with each rifle's round count, rounds since it was cleaned, cleaning due
    GET / PATCH / DELETE /shooting/rifles/{id} (+ /photo); its care log, sessions and how each ammo groups in it
    POST /shooting/rifles/{id}/logs       cleaned / zeroed / scope change... (at its round count now)
    DELETE /shooting/rifle-logs/{id}
    GET / POST /shooting/ammo             with rounds fired and left (bought - fired), cost a round, running low
    GET / PATCH / DELETE /shooting/ammo/{id} (+ /photo); POST /shooting/ammo/{id}/box  bought another box
No serial or registration numbers are kept: the app has no login, and anyone on your Wi-Fi can open it.
Written for Queensland (a Permit to Acquire per firearm; a yearly club-shoot count for a sporting genuine reason) -
but no legal numbers are built in: you set them (settings), as your club and QPS Weapons Licensing say.
"""
from datetime import date

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["shooting"])

RANGE_KINDS = ["Club range", "Public range", "Private property", "Indoor"]
RIFLE_KINDS = ["Rimfire", "Centrefire", "Air"]
ACTIONS = ["Bolt", "Semi-auto", "Lever", "Single shot", "Pump", "Break", "PCP / spring"]
SCOPE_UNITS = ["MOA", "MIL"]
RIFLE_STATUSES = ["In use", "Wanted", "Sold"]
AMMO_STATUSES = ["Have", "Wanted", "Used up"]
BC_MODELS = ["G1", "G7"]
SESSION_KINDS = ["Practice", "Match", "Zeroing", "Ammo test", "Load development", "Fun"]
POSITIONS = ["Bench", "Prone", "Sitting", "Kneeling", "Standing", "Barricade"]
LOG_KINDS = ["Cleaned", "Zeroed", "Scope change", "Repair", "Part", "Note"]


def _lit(values) -> str:
    return "^(" + "|".join(v.replace("(", r"\(").replace(")", r"\)") for v in values) + ")$"


@router.get("/shooting/lists")
def lists():
    return {"range_kinds": RANGE_KINDS, "rifle_kinds": RIFLE_KINDS, "actions": ACTIONS, "scope_units": SCOPE_UNITS,
            "rifle_statuses": RIFLE_STATUSES, "ammo_statuses": AMMO_STATUSES, "bc_models": BC_MODELS,
            "session_kinds": SESSION_KINDS, "positions": POSITIONS, "log_kinds": LOG_KINDS}


# ---------------------------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------------------------
class SettingsIn(BaseModel):
    licence_expires: date | None = None
    licence_note: str | None = Field(None, max_length=200)
    club_shoots_needed: int | None = Field(None, ge=0, le=365)
    clean_every: int | None = Field(None, ge=1, le=100000)


def settings(conn) -> dict:
    s = conn.execute("SELECT licence_expires, licence_note, club_shoots_needed, clean_every, "
                     "licence_expires - current_date AS licence_days FROM shooting_settings WHERE id = 1").fetchone()
    return s


@router.get("/shooting/settings")
def get_settings():
    with db() as conn:
        return settings(conn)


@router.put("/shooting/settings")
def put_settings(body: SettingsIn):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    if "clean_every" in data and data["clean_every"] is None:
        raise HTTPException(422, "Clean every can't be empty.")
    with db() as conn:
        if data:
            update_row(conn, "shooting_settings", "id", 1, data)
            conn.execute("UPDATE shooting_settings SET updated_at = now() WHERE id = 1")
        return settings(conn)


# ---------------------------------------------------------------------------------------------
# Ranges
# ---------------------------------------------------------------------------------------------
class RangeFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(RANGE_KINDS))
    distances: str | None = Field(None, max_length=200)
    counts_for_club: bool | None = None
    notes: str | None = Field(None, max_length=5000)


class RangeIn(RangeFields):
    name: str = Field(min_length=1, max_length=120)


class RangePatch(RangeFields):
    name: str | None = Field(None, min_length=1, max_length=120)


RANGE_SELECT = """SELECT r.range_id, r.name, r.kind, r.distances, r.counts_for_club, r.notes,
       (SELECT count(*) FROM shooting_sessions s WHERE s.range_id = r.range_id)::int AS sessions,
       (SELECT max(s.shot_on) FROM shooting_sessions s WHERE s.range_id = r.range_id) AS last_shot_on
FROM shooting_ranges r"""


@router.get("/shooting/ranges")
def list_ranges():
    with db() as conn:
        return conn.execute(RANGE_SELECT + " ORDER BY last_shot_on DESC NULLS LAST, lower(r.name)").fetchall()


@router.post("/shooting/ranges", status_code=201)
def add_range(body: RangeIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        range_id = insert_row(conn, "shooting_ranges", data, "range_id")
        return conn.execute(RANGE_SELECT + " WHERE r.range_id = %s", (range_id,)).fetchone()


@router.patch("/shooting/ranges/{range_id}")
def update_range(range_id: int, body: RangePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "kind", "counts_for_club"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM shooting_ranges WHERE range_id = %s", (range_id,)).fetchone(), "Range")
        update_row(conn, "shooting_ranges", "range_id", range_id, data)
        return conn.execute(RANGE_SELECT + " WHERE r.range_id = %s", (range_id,)).fetchone()


@router.delete("/shooting/ranges/{range_id}", status_code=204)
def delete_range(range_id: int):
    """Remove a range; its sessions stay (with no range)."""
    with db() as conn:
        found(conn.execute("DELETE FROM shooting_ranges WHERE range_id = %s RETURNING range_id", (range_id,)).fetchone(), "Range")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Rifles
# ---------------------------------------------------------------------------------------------
class RifleFields(BaseModel):
    make: str | None = Field(None, max_length=120)
    model: str | None = Field(None, max_length=120)
    calibre: str | None = Field(None, max_length=60)
    kind: str | None = Field(None, pattern=_lit(RIFLE_KINDS))
    action: str | None = Field(None, pattern=_lit(ACTIONS))
    barrel_in: float | None = Field(None, gt=0, le=60)
    twist: str | None = Field(None, max_length=20)
    scope: str | None = Field(None, max_length=200)
    scope_unit: str | None = Field(None, pattern=_lit(SCOPE_UNITS))
    click: float | None = Field(None, gt=0, le=10)
    zero_m: int | None = Field(None, ge=1, le=3000)
    sight_height_mm: float | None = Field(None, ge=0, le=500)
    rounds_before: int | None = Field(None, ge=0, le=10_000_000)
    clean_every: int | None = Field(None, ge=1, le=100000)
    status: str | None = Field(None, pattern=_lit(RIFLE_STATUSES))
    purchase_date: date | None = None
    price_paid: float | None = Field(None, ge=0)
    pta_applied: date | None = None        # Queensland Permit to Acquire
    pta_approved: date | None = None
    pta_expires: date | None = None
    notes: str | None = Field(None, max_length=5000)


class RifleIn(RifleFields):
    name: str = Field(min_length=1, max_length=120)


class RiflePatch(RifleFields):
    name: str | None = Field(None, min_length=1, max_length=120)


# Round count = before logging here + every session's rounds (a session's own count, else its groups' shots).
SESSION_ROUNDS = "COALESCE(s.rounds, (SELECT sum(g.shots) FROM shooting_groups g WHERE g.session_id = s.session_id), 0)"
RIFLE_SELECT = f"""
WITH fired AS (SELECT s.rifle_id, sum({SESSION_ROUNDS})::int AS rounds, count(*)::int AS sessions, max(s.shot_on) AS last_shot_on
               FROM shooting_sessions s WHERE s.rifle_id IS NOT NULL GROUP BY s.rifle_id),
     cleaned AS (SELECT DISTINCT ON (rifle_id) rifle_id, done_on, at_rounds FROM rifle_logs WHERE kind = 'Cleaned'
                 ORDER BY rifle_id, done_on DESC, log_id DESC)
SELECT r.rifle_id, r.name, r.make, r.model, r.calibre, r.kind, r.action, r.barrel_in::float8 AS barrel_in, r.twist, r.scope,
       r.scope_unit, r.click::float8 AS click, r.zero_m, r.sight_height_mm::float8 AS sight_height_mm, r.rounds_before,
       r.clean_every, r.status, r.purchase_date, r.price_paid::float8 AS price_paid, r.notes, r.created_at,
       r.pta_applied, r.pta_approved, r.pta_expires, r.pta_expires - current_date AS pta_days,
       COALESCE(f.rounds, 0) AS rounds_logged, r.rounds_before + COALESCE(f.rounds, 0) AS round_count,
       COALESCE(f.sessions, 0) AS sessions, f.last_shot_on, c.done_on AS cleaned_on,
       r.rounds_before + COALESCE(f.rounds, 0) - COALESCE(c.at_rounds, r.rounds_before) AS since_clean,
       COALESCE(r.clean_every, st.clean_every) AS clean_interval,
       CASE WHEN r.photo IS NOT NULL THEN '/api/shooting/rifles/' || r.rifle_id || '/photo?v='
            || (extract(epoch FROM r.photo_updated) * 1000)::bigint END AS photo_url
FROM rifles r CROSS JOIN shooting_settings st
LEFT JOIN fired f ON f.rifle_id = r.rifle_id LEFT JOIN cleaned c ON c.rifle_id = r.rifle_id"""


def rifle_row(r: dict) -> dict:
    r["clean_due"] = r["status"] == "In use" and r["since_clean"] >= r["clean_interval"]
    return r


def fetch_rifle(conn, rifle_id: int) -> dict:
    return rifle_row(found(conn.execute(RIFLE_SELECT + " WHERE r.rifle_id = %s", (rifle_id,)).fetchone(), "Rifle"))


@router.get("/shooting/rifles")
def list_rifles():
    with db() as conn:
        return [rifle_row(r) for r in conn.execute(RIFLE_SELECT + " ORDER BY r.status <> 'In use', r.status, "
                                                   "f.last_shot_on DESC NULLS LAST, lower(r.name)").fetchall()]


@router.post("/shooting/rifles", status_code=201)
def add_rifle(body: RifleIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    if data.get("scope_unit") and "click" not in data:
        data["click"] = 0.1 if data["scope_unit"] == "MIL" else 0.25
    with db() as conn:
        return fetch_rifle(conn, insert_row(conn, "rifles", data, "rifle_id"))


@router.get("/shooting/rifles/{rifle_id}")
def get_rifle(rifle_id: int):
    """A rifle with its care log, latest sessions, and how each ammo it's shot groups in it."""
    from .shooting_sessions import ammo_in_rifle
    with db() as conn:
        r = fetch_rifle(conn, rifle_id)
        r["logs"] = conn.execute("SELECT log_id, kind, done_on, at_rounds, notes FROM rifle_logs WHERE rifle_id = %s "
                                 "ORDER BY done_on DESC, log_id DESC", (rifle_id,)).fetchall()
        r["recent"] = conn.execute(f"""SELECT s.session_id, s.shot_on, s.kind, rg.name AS range_name, a.name AS ammo_name,
                {SESSION_ROUNDS}::int AS rounds FROM shooting_sessions s LEFT JOIN shooting_ranges rg ON rg.range_id = s.range_id
                LEFT JOIN ammo a ON a.ammo_id = s.ammo_id WHERE s.rifle_id = %s ORDER BY s.shot_on DESC, s.session_id DESC LIMIT 8""",
                                   (rifle_id,)).fetchall()
        r["ammo"] = ammo_in_rifle(conn, rifle_id, r["scope_unit"])
        return r


@router.patch("/shooting/rifles/{rifle_id}")
def update_rifle(rifle_id: int, body: RiflePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "kind", "scope_unit", "rounds_before", "status"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        fetch_rifle(conn, rifle_id)
        update_row(conn, "rifles", "rifle_id", rifle_id, data)
        return fetch_rifle(conn, rifle_id)


@router.delete("/shooting/rifles/{rifle_id}", status_code=204)
def delete_rifle(rifle_id: int):
    """Remove a rifle; its sessions stay (with no rifle); its care log and DOPE go with it."""
    with db() as conn:
        found(conn.execute("DELETE FROM rifles WHERE rifle_id = %s RETURNING rifle_id", (rifle_id,)).fetchone(), "Rifle")
    return Response(status_code=204)


class LogIn(BaseModel):
    kind: str = Field("Cleaned", pattern=_lit(LOG_KINDS))
    done_on: date | None = None
    notes: str | None = Field(None, max_length=5000)


@router.post("/shooting/rifles/{rifle_id}/logs", status_code=201)
def add_rifle_log(rifle_id: int, body: LogIn):
    """Cleaned, zeroed... noted at the rifle's round count now (so "rounds since cleaned" starts again)."""
    with db() as conn:
        r = fetch_rifle(conn, rifle_id)
        data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=())
        insert_row(conn, "rifle_logs", {**data, "rifle_id": rifle_id, "at_rounds": r["round_count"]}, "log_id")
        return fetch_rifle(conn, rifle_id)


@router.delete("/shooting/rifle-logs/{log_id}", status_code=204)
def delete_rifle_log(log_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM rifle_logs WHERE log_id = %s RETURNING log_id", (log_id,)).fetchone(), "Log entry")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Ammunition (factory)
# ---------------------------------------------------------------------------------------------
class AmmoFields(BaseModel):
    brand: str | None = Field(None, max_length=120)
    calibre: str | None = Field(None, max_length=60)
    bullet_gr: float | None = Field(None, gt=0, le=2000)
    bullet_type: str | None = Field(None, max_length=80)
    bc: float | None = Field(None, gt=0, lt=2)
    bc_model: str | None = Field(None, pattern=_lit(BC_MODELS))
    velocity_ms: float | None = Field(None, gt=0, le=2000)
    lot: str | None = Field(None, max_length=80)
    box_size: int | None = Field(None, gt=0, le=100000)
    box_price: float | None = Field(None, ge=0)
    rounds_bought: int | None = Field(None, ge=0, le=10_000_000)
    bought_from: str | None = Field(None, max_length=120)
    status: str | None = Field(None, pattern=_lit(AMMO_STATUSES))
    notes: str | None = Field(None, max_length=5000)


class AmmoIn(AmmoFields):
    name: str = Field(min_length=1, max_length=120)


class AmmoPatch(AmmoFields):
    name: str | None = Field(None, min_length=1, max_length=120)


AMMO_SELECT = f"""
WITH fired AS (SELECT s.ammo_id, sum({SESSION_ROUNDS})::int AS rounds, count(*)::int AS sessions, max(s.shot_on) AS last_shot_on
               FROM shooting_sessions s WHERE s.ammo_id IS NOT NULL GROUP BY s.ammo_id)
SELECT a.ammo_id, a.name, a.brand, a.calibre, a.bullet_gr::float8 AS bullet_gr, a.bullet_type, a.bc::float8 AS bc, a.bc_model,
       a.velocity_ms::float8 AS velocity_ms, a.lot, a.box_size, a.box_price::float8 AS box_price, a.rounds_bought, a.bought_from,
       a.status, a.notes, a.created_at, COALESCE(f.rounds, 0) AS rounds_fired, a.rounds_bought - COALESCE(f.rounds, 0) AS rounds_left,
       COALESCE(f.sessions, 0) AS sessions, f.last_shot_on,
       CASE WHEN a.box_price IS NOT NULL AND a.box_size > 0 THEN round(a.box_price / a.box_size, 3)::float8 END AS per_round,
       CASE WHEN a.photo IS NOT NULL THEN '/api/shooting/ammo/' || a.ammo_id || '/photo?v='
            || (extract(epoch FROM a.photo_updated) * 1000)::bigint END AS photo_url
FROM ammo a LEFT JOIN fired f ON f.ammo_id = a.ammo_id"""


def ammo_row(a: dict) -> dict:
    a["low"] = a["status"] == "Have" and a["rounds_left"] < (a["box_size"] or 50)
    a["fps"] = round(a["velocity_ms"] / 0.3048) if a["velocity_ms"] else None
    return a


def fetch_ammo(conn, ammo_id: int) -> dict:
    return ammo_row(found(conn.execute(AMMO_SELECT + " WHERE a.ammo_id = %s", (ammo_id,)).fetchone(), "Ammunition"))


@router.get("/shooting/ammo")
def list_ammo():
    with db() as conn:
        return [ammo_row(a) for a in conn.execute(AMMO_SELECT + " ORDER BY a.status = 'Used up', a.status = 'Wanted', "
                                                  "f.last_shot_on DESC NULLS LAST, lower(a.name)").fetchall()]


@router.post("/shooting/ammo", status_code=201)
def add_ammo(body: AmmoIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        return fetch_ammo(conn, insert_row(conn, "ammo", data, "ammo_id"))


@router.get("/shooting/ammo/{ammo_id}")
def get_ammo(ammo_id: int):
    """Ammunition with how it groups in each rifle it's been shot from (and its chronograph numbers)."""
    from .shooting_sessions import rifles_for_ammo
    with db() as conn:
        a = fetch_ammo(conn, ammo_id)
        a["rifles"] = rifles_for_ammo(conn, ammo_id)
        return a


@router.patch("/shooting/ammo/{ammo_id}")
def update_ammo(ammo_id: int, body: AmmoPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "rounds_bought", "status"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        fetch_ammo(conn, ammo_id)
        update_row(conn, "ammo", "ammo_id", ammo_id, data)
        return fetch_ammo(conn, ammo_id)


class BoxIn(BaseModel):
    rounds: int | None = Field(None, ge=1, le=100000)      # blank = one box (its box size)
    lot: str | None = Field(None, max_length=80)


@router.post("/shooting/ammo/{ammo_id}/box")
def bought_box(ammo_id: int, body: BoxIn):
    """Bought more: adds a box (or the rounds you say) to what you've bought; a new lot number if it changed."""
    with db() as conn:
        a = fetch_ammo(conn, ammo_id)
        rounds = body.rounds or a["box_size"]
        if not rounds:
            raise HTTPException(422, "How many rounds? (Set its box size to add a box at a time.)")
        conn.execute("UPDATE ammo SET rounds_bought = rounds_bought + %s, status = 'Have', lot = COALESCE(%s, lot) WHERE ammo_id = %s",
                     (rounds, (body.lot or "").strip() or None, ammo_id))
        return fetch_ammo(conn, ammo_id)


@router.delete("/shooting/ammo/{ammo_id}", status_code=204)
def delete_ammo(ammo_id: int):
    """Remove ammunition; its sessions stay (with no ammo noted)."""
    with db() as conn:
        found(conn.execute("DELETE FROM ammo WHERE ammo_id = %s RETURNING ammo_id", (ammo_id,)).fetchone(), "Ammunition")
    return Response(status_code=204)


add_photo_routes(router, "/shooting/rifles", "rifles", "rifle_id", "Rifle")
add_photo_routes(router, "/shooting/ammo", "ammo", "ammo_id", "Ammunition")
