"""Fishing (A13_fishing.sql): the settings, the summary, spots, species (with the rules YOU typed) and the tackle box.
Trips are in fishing_trips.py, catches / rules check / photos in fishing_catches.py, the stats in fishing_stats.py; the
forecast, solunar and OpenStreetMap tools are in fishing_tools.py.

    GET / PUT /fishing/settings                 home position, the Stocked Impoundment Permit and boat registration dates, the
                                                link to the official rules
    GET  /fishing/summary                       totals, the open trip, last trip, personal bests, what's due, recent trips
    GET / POST /fishing/spots, GET / PATCH / DELETE /fishing/spots/{id}     (trips keep their place in the log when a spot goes)
    GET / POST /fishing/species, PATCH / DELETE /fishing/species/{id}       (409 while catches use it)
    GET / POST /fishing/lures, PATCH / DELETE /fishing/lures/{id}           lures and baits: what each one caught

Nothing about the rules is shipped (they change, and a wrong number could get you fined): the species list holds names only
until you type the minimum / maximum size, possession limit and closed season from the official page, and the date you checked.
"""
import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator

from .db import db, found, insert_row, tidy_text, update_row
from .fishing_trips import BRIEF_ORDER, BRIEF_SELECT

router = APIRouter(prefix="/api", tags=["fishing"])

ALERT_DAYS = 60
DEFAULT_RULES_URL = "https://www.qld.gov.au/recreation/activities/boating-fishing/rec-fishing/rules"   # as in A13
Water = Literal["salt", "estuary", "fresh"]
LureKind = Literal["lure", "soft plastic", "bait", "live bait", "fly", "jig", "other"]
MMDD = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")


def _required(data: dict, *names):
    for n in names:
        if n in data and data[n] is None:
            raise HTTPException(422, f"{n.replace('_', ' ').capitalize()} can't be empty.")


# ---------------------------------------------------------------- settings

class SettingsIn(BaseModel):
    home_lat: float | None = Field(None, ge=-90, le=90)
    home_lon: float | None = Field(None, ge=-180, le=180)
    sip_until: date | None = None
    boat_rego_until: date | None = None
    rules_url: str | None = Field(None, max_length=500)

    @field_validator("rules_url")
    @classmethod
    def _link(cls, v):
        if v is not None and v.strip() and not re.match(r"^https?://", v.strip(), re.I):
            raise ValueError("The link to the rules must start with http:// or https://.")
        return v


def settings_row(conn) -> dict:
    return conn.execute("SELECT * FROM fishing_settings WHERE id = 1").fetchone()


@router.get("/fishing/settings")
def get_settings():
    with db() as conn:
        return settings_row(conn)


@router.put("/fishing/settings")
def put_settings(body: SettingsIn):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("rules_url",))
    if "rules_url" in data and not data["rules_url"]:
        data["rules_url"] = DEFAULT_RULES_URL       # blank = back to the default link
    with db() as conn:
        if data:
            update_row(conn, "fishing_settings", "id", 1, data)
            conn.execute("UPDATE fishing_settings SET updated_at = now() WHERE id = 1")
        return settings_row(conn)


# ---------------------------------------------------------------- what's due

def _when(due: date, today: date) -> str:
    n = (due - today).days
    if n < 0:
        return f"is overdue by {-n} day{'' if n == -1 else 's'}"
    return "is due today" if n == 0 else f"is due in {n} day{'' if n == 1 else 's'}"


def alerts(conn, today: date) -> list[dict]:
    """The permit and boat registration due within 60 days (or overdue), and the species you've kept whose rules you
    haven't checked for 12 months (one line for all of them), soonest first."""
    s = settings_row(conn)
    out = []
    for kind, label, due in (("sip", "Stocked Impoundment Permit", s["sip_until"]),
                             ("boat_rego", "Boat registration", s["boat_rego_until"])):
        if due and (due - today).days <= ALERT_DAYS:
            out.append({"kind": kind, "text": f"{label} {_when(due, today)}", "due": due})
    stale = conn.execute("""
        SELECT sp.name, sp.rules_checked_on FROM fishing_species sp
        WHERE EXISTS (SELECT 1 FROM fishing_catches c WHERE c.species_id = sp.species_id AND c.fate IN ('kept', 'died'))
          AND (sp.rules_checked_on IS NULL OR sp.rules_checked_on < current_date - interval '12 months')
        ORDER BY sp.rules_checked_on NULLS FIRST, lower(sp.name)""").fetchall()
    if stale:
        names = [r["name"] for r in stale]
        due = min(r["rules_checked_on"].replace(year=r["rules_checked_on"].year + 1) if r["rules_checked_on"] else today
                  for r in stale)
        out.append({"kind": "rules", "due": due,
                    "text": f"Check the official rules for {', '.join(names)}: you keep them, and the rules you typed "
                            "have no check date or are over a year old."})
    return sorted(out, key=lambda a: (a["due"], a["kind"], a["text"]))


# ---------------------------------------------------------------- the summary

@router.get("/fishing/summary")
def summary():
    with db() as conn:
        today = conn.execute("SELECT current_date AS today").fetchone()["today"]
        t = conn.execute("""SELECT count(*)::int AS trips,
                                   COALESCE(sum(extract(epoch FROM (ended_at - started_at)) / 3600), 0)::float8 AS hours,
                                   count(*) FILTER (WHERE extract(year FROM started_at::timestamp) = extract(year FROM current_date))::int AS trips_year
                            FROM fishing_trips""").fetchone()
        c = conn.execute("""SELECT count(*)::int AS catches,
                                   count(DISTINCT COALESCE(species_id::text, lower(btrim(species))))::int AS species,
                                   count(*) FILTER (WHERE extract(year FROM COALESCE(c.caught_at, t.started_at)::timestamp)
                                                         = extract(year FROM current_date))::int AS catches_year
                            FROM fishing_catches c JOIN fishing_trips t USING (trip_id)""").fetchone()
        recent = conn.execute(BRIEF_SELECT + BRIEF_ORDER + " LIMIT 5").fetchall()
        open_trip = conn.execute(BRIEF_SELECT + " WHERE t.ended_at IS NULL" + BRIEF_ORDER + " LIMIT 1").fetchone()
        bests = conn.execute("""
            SELECT species, length_cm, weight_kg, caught_at, catch_id, trip_id FROM (
                SELECT DISTINCT ON (COALESCE(c.species_id::text, lower(btrim(c.species))))
                       COALESCE(sp.name, c.species) AS species, c.length_cm::float8 AS length_cm, c.weight_kg::float8 AS weight_kg,
                       COALESCE(c.caught_at, t.started_at) AS caught_at, c.catch_id, c.trip_id
                FROM fishing_catches c JOIN fishing_trips t USING (trip_id) LEFT JOIN fishing_species sp USING (species_id)
                WHERE c.length_cm IS NOT NULL
                ORDER BY COALESCE(c.species_id::text, lower(btrim(c.species))), c.length_cm DESC, c.catch_id) x
            ORDER BY length_cm DESC, caught_at, catch_id LIMIT 5""").fetchall()
        return {"trips": t["trips"], "catches": c["catches"], "species": c["species"], "hours": round(t["hours"], 1),
                "this_year": {"trips": t["trips_year"], "catches": c["catches_year"]},
                "last_trip": recent[0] if recent else None, "open_trip": open_trip, "personal_bests": bests,
                "alerts": alerts(conn, today), "recent": recent}


# ---------------------------------------------------------------- spots

class SpotFields(BaseModel):
    place: str | None = Field(None, max_length=120)
    water: Water | None = None
    kind: str | None = Field(None, max_length=40)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    sip_needed: bool | None = None
    notes: str | None = Field(None, max_length=5000)


class SpotIn(SpotFields):
    name: str = Field(min_length=1, max_length=120)


class SpotPatch(SpotFields):
    name: str | None = Field(None, min_length=1, max_length=120)


# fish per hour: the catches of the spot's finished trips over their hours
SPOT_SELECT = """SELECT s.spot_id, s.name, s.place, s.water, s.kind, s.lat, s.lon, s.sip_needed, s.osm, s.notes, s.created_at,
       (SELECT count(*) FROM fishing_trips t WHERE t.spot_id = s.spot_id)::int AS trips,
       (SELECT count(*) FROM fishing_catches c JOIN fishing_trips t USING (trip_id) WHERE t.spot_id = s.spot_id)::int AS catches,
       (SELECT max(t.started_at::timestamp::date) FROM fishing_trips t WHERE t.spot_id = s.spot_id) AS last_on,
       (SELECT CASE WHEN sum(h) > 0 THEN round((sum(n) / sum(h))::numeric, 2)::float8 END FROM (
            SELECT extract(epoch FROM (t.ended_at - t.started_at)) / 3600 AS h,
                   (SELECT count(*) FROM fishing_catches c WHERE c.trip_id = t.trip_id) AS n
            FROM fishing_trips t WHERE t.spot_id = s.spot_id AND t.ended_at IS NOT NULL) x) AS fish_per_hour
FROM fishing_spots s"""


def spot_detail(conn, spot_id: int) -> dict:
    s = found(conn.execute(SPOT_SELECT + " WHERE s.spot_id = %s", (spot_id,)).fetchone(), "Spot")
    s["trip_list"] = conn.execute(BRIEF_SELECT + " WHERE t.spot_id = %s" + BRIEF_ORDER, (spot_id,)).fetchall()
    s["species_caught"] = conn.execute("""
        SELECT (array_agg(COALESCE(sp.name, c.species) ORDER BY c.catch_id))[1] AS species, count(*)::int AS catches
        FROM fishing_catches c JOIN fishing_trips t USING (trip_id) LEFT JOIN fishing_species sp USING (species_id)
        WHERE t.spot_id = %s GROUP BY COALESCE(c.species_id::text, lower(btrim(c.species)))
        ORDER BY count(*) DESC, 1""", (spot_id,)).fetchall()
    return s


@router.get("/fishing/spots")
def list_spots():
    with db() as conn:
        return conn.execute(SPOT_SELECT + " ORDER BY lower(s.name), s.spot_id").fetchall()


@router.post("/fishing/spots", status_code=201)
def add_spot(body: SpotIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        return spot_detail(conn, insert_row(conn, "fishing_spots", data, "spot_id"))


@router.get("/fishing/spots/{spot_id}")
def get_spot(spot_id: int):
    with db() as conn:
        return spot_detail(conn, spot_id)


@router.patch("/fishing/spots/{spot_id}")
def update_spot(spot_id: int, body: SpotPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _required(data, "name", "sip_needed")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM fishing_spots WHERE spot_id = %s", (spot_id,)).fetchone(), "Spot")
        update_row(conn, "fishing_spots", "spot_id", spot_id, data)
        return spot_detail(conn, spot_id)


@router.delete("/fishing/spots/{spot_id}", status_code=204)
def delete_spot(spot_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM fishing_spots WHERE spot_id = %s RETURNING spot_id", (spot_id,)).fetchone(), "Spot")
    return Response(status_code=204)


# ---------------------------------------------------------------- species (and the rules you typed)

class SpeciesFields(BaseModel):
    sci_name: str | None = Field(None, max_length=120)
    water: Literal["salt", "estuary", "fresh", "any"] | None = None
    min_cm: float | None = Field(None, gt=0, lt=1000)
    max_cm: float | None = Field(None, gt=0, lt=1000)
    bag: int | None = Field(None, ge=0, le=1000)
    closed_from: str | None = None
    closed_to: str | None = None
    no_take: bool | None = None
    rules_checked_on: date | None = None
    notes: str | None = Field(None, max_length=5000)

    @field_validator("closed_from", "closed_to")
    @classmethod
    def _mmdd(cls, v):
        if v is not None and v.strip() and not MMDD.match(v.strip()):
            raise ValueError("A closed season's days are written MM-DD, like 11-01.")
        return v


class SpeciesIn(SpeciesFields):
    name: str = Field(min_length=1, max_length=120)


class SpeciesPatch(SpeciesFields):
    name: str | None = Field(None, min_length=1, max_length=120)


SPECIES_SELECT = """SELECT sp.species_id, sp.name, sp.sci_name, sp.water, sp.min_cm::float8 AS min_cm, sp.max_cm::float8 AS max_cm,
       sp.bag, sp.closed_from, sp.closed_to, sp.no_take, sp.rules_checked_on, sp.notes, sp.created_at,
       (SELECT count(*) FROM fishing_catches c WHERE c.species_id = sp.species_id)::int AS caught,
       (SELECT count(*) FROM fishing_catches c WHERE c.species_id = sp.species_id AND c.fate = 'kept')::int AS kept,
       (SELECT max(c.length_cm)::float8 FROM fishing_catches c WHERE c.species_id = sp.species_id) AS best_cm,
       (SELECT max(COALESCE(c.caught_at, t.started_at)::timestamp::date) FROM fishing_catches c JOIN fishing_trips t USING (trip_id)
        WHERE c.species_id = sp.species_id) AS last_on
FROM fishing_species sp"""


def _species_row(conn, species_id: int) -> dict:
    return found(conn.execute(SPECIES_SELECT + " WHERE sp.species_id = %s", (species_id,)).fetchone(), "Species")


@router.get("/fishing/species")
def list_species():
    with db() as conn:
        return conn.execute(SPECIES_SELECT + " ORDER BY lower(sp.name), sp.species_id").fetchall()


@router.post("/fishing/species", status_code=201)
def add_species(body: SpeciesIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        return _species_row(conn, insert_row(conn, "fishing_species", data, "species_id"))


@router.patch("/fishing/species/{species_id}")
def update_species(species_id: int, body: SpeciesPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _required(data, "name", "no_take")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM fishing_species WHERE species_id = %s", (species_id,)).fetchone(), "Species")
        update_row(conn, "fishing_species", "species_id", species_id, data)
        return _species_row(conn, species_id)


@router.delete("/fishing/species/{species_id}", status_code=204)
def delete_species(species_id: int):
    with db() as conn:
        found(conn.execute("SELECT 1 FROM fishing_species WHERE species_id = %s", (species_id,)).fetchone(), "Species")
        n = conn.execute("SELECT count(*)::int AS n FROM fishing_catches WHERE species_id = %s", (species_id,)).fetchone()["n"]
        if n:
            raise HTTPException(409, f"{n} of your catches use that species, so it can't be removed.")
        conn.execute("DELETE FROM fishing_species WHERE species_id = %s", (species_id,))
    return Response(status_code=204)


# ---------------------------------------------------------------- the tackle box

class LureFields(BaseModel):
    kind: LureKind | None = None
    brand: str | None = Field(None, max_length=80)
    colour: str | None = Field(None, max_length=60)
    size: str | None = Field(None, max_length=60)
    qty: int | None = Field(None, ge=0, le=10000)
    retired: bool | None = None
    notes: str | None = Field(None, max_length=2000)


class LureIn(LureFields):
    name: str = Field(min_length=1, max_length=120)


class LurePatch(LureFields):
    name: str | None = Field(None, min_length=1, max_length=120)


LURE_SELECT = """SELECT l.lure_id, l.name, l.kind, l.brand, l.colour, l.size, l.qty, l.retired, l.notes, l.created_at,
       (SELECT count(*) FROM fishing_catches c WHERE c.lure_id = l.lure_id)::int AS catches,
       COALESCE((SELECT array_agg(DISTINCT COALESCE(sp.name, c.species) ORDER BY COALESCE(sp.name, c.species))
                 FROM fishing_catches c LEFT JOIN fishing_species sp USING (species_id) WHERE c.lure_id = l.lure_id), '{}') AS species
FROM fishing_lures l"""


def _lure_row(conn, lure_id: int) -> dict:
    return found(conn.execute(LURE_SELECT + " WHERE l.lure_id = %s", (lure_id,)).fetchone(), "Lure")


@router.get("/fishing/lures")
def list_lures(retired: bool | None = Query(None)):
    with db() as conn:
        return conn.execute(LURE_SELECT + " WHERE %(r)s::boolean IS NULL OR l.retired = %(r)s ORDER BY l.retired, lower(l.name), l.lure_id",
                            {"r": retired}).fetchall()


@router.post("/fishing/lures", status_code=201)
def add_lure(body: LureIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        return _lure_row(conn, insert_row(conn, "fishing_lures", data, "lure_id"))


@router.patch("/fishing/lures/{lure_id}")
def update_lure(lure_id: int, body: LurePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _required(data, "name", "kind", "retired")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM fishing_lures WHERE lure_id = %s", (lure_id,)).fetchone(), "Lure")
        update_row(conn, "fishing_lures", "lure_id", lure_id, data)
        return _lure_row(conn, lure_id)


@router.delete("/fishing/lures/{lure_id}", status_code=204)
def delete_lure(lure_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM fishing_lures WHERE lure_id = %s RETURNING lure_id", (lure_id,)).fetchone(), "Lure")
    return Response(status_code=204)
