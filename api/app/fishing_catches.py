"""Fishing: the catches, the rules check and the catch photos (A13_fishing.sql). Trips are in fishing_trips.py, the rest
(settings, summary, spots, species, lures) in fishing.py, the stats in fishing_stats.py.

    POST   /fishing/trips/{id}/catches      a catch -> the catch + warnings. A client_key that exists already returns that
                                            catch (200): the phone on the water queues writes and may send one twice
    PATCH / DELETE /fishing/catches/{id}    (PATCH answers like POST)
    POST   /fishing/catches/{id}/photos     the body is the image (the browser shrinks it first) -> {photo_id, url}
    GET    /fishing/photos/{id}             (cached a year: a new photo is a new id)       DELETE /fishing/photos/{id}

The rules are the ones YOU typed on the species page (nothing is shipped: they change, and a wrong number could get you
fined). Logging a kept fish checks it against them and WARNS - it never blocks: under the minimum, over the maximum, no-take,
inside the closed season, more than the possession limit kept that day. The answer is the catch's own fields plus
"warnings" (a list of sentences), and "catch" (the same row again, for callers that like it nested).
"""
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .images import photo_response, read_photo

router = APIRouter(prefix="/api", tags=["fishing"])

Fate = Literal["released", "kept", "tagged", "died"]
KEPT_FATES = ("kept", "died")                 # the fates that count against the rules

# When it was caught: its own time, or the start of the trip it belongs to.
CAUGHT_AT = "COALESCE(c.caught_at, t.started_at)"

CATCH_SELECT = f"""SELECT c.catch_id, c.trip_id, c.species_id, c.species, COALESCE(sp.name, c.species) AS species_name,
       c.caught_at, {CAUGHT_AT} AS at, c.length_cm::float8 AS length_cm, c.weight_kg::float8 AS weight_kg, c.fate, c.lure_id,
       c.bait, COALESCE(l.name, c.bait) AS lure_name, c.method, c.depth_m::float8 AS depth_m, c.lat, c.lon, c.client_key,
       c.notes, c.created_at
FROM fishing_catches c JOIN fishing_trips t USING (trip_id)
LEFT JOIN fishing_species sp USING (species_id) LEFT JOIN fishing_lures l USING (lure_id)"""


def photo_list(conn, catch_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {i: [] for i in catch_ids}
    if catch_ids:
        for p in conn.execute("""SELECT photo_id, catch_id, '/api/fishing/photos/' || photo_id AS url FROM fishing_photos
                                 WHERE catch_id = ANY(%s) ORDER BY photo_id""", (catch_ids,)).fetchall():
            out[p["catch_id"]].append({"photo_id": p["photo_id"], "url": p["url"]})
    return out


# ---------------------------------------------------------------- the rules you typed

def _text_number(n) -> str:
    n = float(n)
    return str(int(n)) if n == int(n) else str(n)


def in_closed_season(day: date, closed_from: str | None, closed_to: str | None) -> bool:
    """Is the day inside the yearly closed season ('MM-DD' to 'MM-DD', both days included; a season such as 11-01 to
    02-15 wraps over New Year)?"""
    if not closed_from or not closed_to:
        return False
    md = f"{day.month:02d}-{day.day:02d}"
    if closed_from <= closed_to:
        return closed_from <= md <= closed_to
    return md >= closed_from or md <= closed_to


def rule_warnings(conn, catch: dict) -> list[str]:
    """What the rules you typed say about this catch (a row from CATCH_SELECT, or anything with catch_id / species_id /
    fate / length_cm / at). Only a kept or died fish is checked. Every sentence names the rule and says it is as you typed it."""
    if catch.get("fate") not in KEPT_FATES or catch.get("species_id") is None:
        return []
    sp = conn.execute("SELECT * FROM fishing_species WHERE species_id = %s", (catch["species_id"],)).fetchone()
    if sp is None:
        return []
    checked = f"on {sp['rules_checked_on']}" if sp["rules_checked_on"] else "(no check date)"
    tail = f" - the rule is as you typed it {checked}: check the official rules."
    name, length = sp["name"], catch.get("length_cm")
    out = []
    if sp["no_take"]:
        out.append(f"{name} is marked no-take" + tail)
    if length is not None and sp["min_cm"] is not None and float(length) < float(sp["min_cm"]):
        out.append(f"{length:g} cm is under the {_text_number(sp['min_cm'])} cm minimum size for {name}" + tail)
    if length is not None and sp["max_cm"] is not None and float(length) > float(sp["max_cm"]):
        out.append(f"{length:g} cm is over the {_text_number(sp['max_cm'])} cm maximum size for {name}" + tail)
    at = catch.get("at")
    day = conn.execute("SELECT %s::timestamptz::timestamp::date AS d", (at,)).fetchone()["d"] if at else None
    if day and in_closed_season(day, sp["closed_from"], sp["closed_to"]):
        out.append(f"{name} is in its closed season ({sp['closed_from']} to {sp['closed_to']}, as MM-DD)" + tail)
    if day and sp["bag"] is not None and not sp["no_take"]:
        others = conn.execute(f"""SELECT count(*)::int AS n FROM fishing_catches c JOIN fishing_trips t USING (trip_id)
                                  WHERE c.species_id = %s AND c.fate = ANY(%s) AND ({CAUGHT_AT})::timestamp::date = %s
                                    AND (%s::timestamptz IS NULL OR ({CAUGHT_AT}, c.catch_id) < (%s::timestamptz, %s))""",
                              (sp["species_id"], list(KEPT_FATES), day, at, at, catch.get("catch_id") or 2**31 - 1)).fetchone()["n"]
        if others + 1 > sp["bag"]:
            out.append(f"That is {others + 1} {name} kept on {day}; the possession limit is {sp['bag']}" + tail)
    return out


def catch_answer(conn, catch_id: int) -> dict:
    """The catch with its photos and warnings (the shape of POST / PATCH, and of a trip's catches)."""
    c = found(conn.execute(CATCH_SELECT + " WHERE c.catch_id = %s", (catch_id,)).fetchone(), "Catch")
    c["photos"] = photo_list(conn, [catch_id])[catch_id]
    c["warnings"] = rule_warnings(conn, c)
    return {**c, "catch": {k: v for k, v in c.items() if k != "warnings"}}


# ---------------------------------------------------------------- the catch

class CatchFields(BaseModel):
    species_id: int | None = None
    species: str | None = Field(None, max_length=120)
    caught_at: datetime | None = None
    length_cm: float | None = Field(None, gt=0, lt=1000)
    weight_kg: float | None = Field(None, gt=0, lt=1000)
    lure_id: int | None = None
    bait: str | None = Field(None, max_length=120)
    method: str | None = Field(None, max_length=60)
    depth_m: float | None = Field(None, ge=0, le=2000)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    notes: str | None = Field(None, max_length=5000)


class CatchIn(CatchFields):
    fate: Fate = "released"
    client_key: str | None = Field(None, min_length=1, max_length=80)


class CatchPatch(CatchFields):
    fate: Fate | None = None


def _check_links(conn, data: dict):
    if data.get("species_id") is not None:
        found(conn.execute("SELECT 1 FROM fishing_species WHERE species_id = %s", (data["species_id"],)).fetchone(), "Species")
    if data.get("lure_id") is not None:
        found(conn.execute("SELECT 1 FROM fishing_lures WHERE lure_id = %s", (data["lure_id"],)).fetchone(), "Lure")


def _needs_a_fish(data: dict):
    if not data.get("species_id") and not (data.get("species") or "").strip():
        raise HTTPException(422, "Say what you caught: pick a species or type a name.")


@router.post("/fishing/trips/{trip_id}/catches")
def add_catch(trip_id: int, body: CatchIn, response: Response):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None})
    with db() as conn:
        found(conn.execute("SELECT 1 FROM fishing_trips WHERE trip_id = %s", (trip_id,)).fetchone(), "Trip")
        if data.get("client_key"):
            old = conn.execute("SELECT catch_id FROM fishing_catches WHERE client_key = %s", (data["client_key"],)).fetchone()
            if old:                                  # the same catch sent again: no duplicate
                response.status_code = 200
                return catch_answer(conn, old["catch_id"])
        _needs_a_fish(data)
        _check_links(conn, data)
        response.status_code = 201
        return catch_answer(conn, insert_row(conn, "fishing_catches", {**data, "trip_id": trip_id}, "catch_id"))


@router.patch("/fishing/catches/{catch_id}")
def update_catch(catch_id: int, body: CatchPatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if "fate" in data and data["fate"] is None:
        raise HTTPException(422, "Fate can't be empty.")
    with db() as conn:
        old = found(conn.execute("SELECT species_id, species FROM fishing_catches WHERE catch_id = %s", (catch_id,)).fetchone(), "Catch")
        _check_links(conn, data)
        _needs_a_fish({"species_id": data.get("species_id", old["species_id"]), "species": data.get("species", old["species"])})
        update_row(conn, "fishing_catches", "catch_id", catch_id, data)
        return catch_answer(conn, catch_id)


@router.delete("/fishing/catches/{catch_id}", status_code=204)
def delete_catch(catch_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM fishing_catches WHERE catch_id = %s RETURNING catch_id", (catch_id,)).fetchone(), "Catch")
    return Response(status_code=204)


# ---------------------------------------------------------------- photos

@router.post("/fishing/catches/{catch_id}/photos", status_code=201)
async def add_photo(catch_id: int, request: Request):
    image, image_type = await read_photo(request)
    with db() as conn:
        found(conn.execute("SELECT 1 FROM fishing_catches WHERE catch_id = %s", (catch_id,)).fetchone(), "Catch")
        photo_id = insert_row(conn, "fishing_photos", {"catch_id": catch_id, "image": image, "image_type": image_type}, "photo_id")
    return {"photo_id": photo_id, "catch_id": catch_id, "url": f"/api/fishing/photos/{photo_id}"}


@router.get("/fishing/photos/{photo_id}")
def get_photo(photo_id: int):
    """A photo never changes (a new one gets a new id), so it's cached for a year."""
    with db() as conn:
        row = found(conn.execute("SELECT image, image_type FROM fishing_photos WHERE photo_id = %s", (photo_id,)).fetchone(), "Photo")
    return photo_response(row["image"], row["image_type"])


@router.delete("/fishing/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM fishing_photos WHERE photo_id = %s RETURNING photo_id", (photo_id,)).fetchone(), "Photo")
    return Response(status_code=204)
