"""Travel: places (to see, been, with a pin on the map) and the countries you've been to or want to. Split out of
travel.py (2026-10-22)."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import openmeteo
from .db import db, found, insert_row, tidy_text, update_row
from .travel import PLACE_KINDS, PLACE_SELECT, PLACE_STATUSES, _lit, countries, trip_detail, trip_row

router = APIRouter(prefix="/api", tags=["travel"])


class PlaceFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(PLACE_KINDS))
    status: str | None = Field(None, pattern=_lit(PLACE_STATUSES))
    trip_id: int | None = None
    country: str | None = Field(None, pattern="^[A-Za-z]{2}$")
    region: str | None = Field(None, max_length=120)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    visit_on: date | None = None
    rating: int | None = Field(None, ge=1, le=5)
    link: str | None = Field(None, max_length=1000, pattern="^https?://")
    notes: str | None = Field(None, max_length=5000)


class PlaceIn(PlaceFields):
    name: str = Field(min_length=1, max_length=200)


class PlacePatch(PlaceFields):
    name: str | None = Field(None, min_length=1, max_length=200)


@router.get("/travel/places")
def list_places(shown: Literal["Want", "Planned", "Been"] | None = None):
    with db() as conn:
        rows = conn.execute(f"SELECT * FROM ({PLACE_SELECT}) x" + (" WHERE shown = %s" if shown else "")
                            + " ORDER BY lower(name)", (shown,) if shown else ()).fetchall()
    return rows


def _place_answer(conn, place_id: int, trip_id: int | None):
    """A place's change answers with its trip (the trip panel shows it) or the place."""
    if trip_id:
        return trip_detail(conn, trip_id)
    return conn.execute(PLACE_SELECT + " WHERE p.place_id = %s", (place_id,)).fetchone()


@router.post("/travel/places", status_code=201)
def add_place(body: PlaceIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    if data.get("country"):
        data["country"] = data["country"].upper()
    with db() as conn:
        if data.get("trip_id"):
            trip = trip_row(conn, data["trip_id"])
            data["stop_order"] = conn.execute("SELECT COALESCE(max(stop_order), 0) + 1 AS n FROM trip_places WHERE trip_id = %s",
                                              (data["trip_id"],)).fetchone()["n"]
            data.setdefault("status", "Been" if trip["phase"] in ("past", "now") else "Planned")
        place_id = insert_row(conn, "trip_places", data, "place_id")
        return _place_answer(conn, place_id, data.get("trip_id"))


@router.patch("/travel/places/{place_id}")
def update_place(place_id: int, body: PlacePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "kind", "status"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.capitalize()} can't be empty.")
    if data.get("country"):
        data["country"] = data["country"].upper()
    with db() as conn:
        old = found(conn.execute("SELECT trip_id FROM trip_places WHERE place_id = %s", (place_id,)).fetchone(), "Place")
        if "trip_id" in data and data["trip_id"]:
            trip_row(conn, data["trip_id"])
        update_row(conn, "trip_places", "place_id", place_id, data)
        return _place_answer(conn, place_id, data.get("trip_id", old["trip_id"]))


@router.delete("/travel/places/{place_id}")
def delete_place(place_id: int):
    with db() as conn:
        old = found(conn.execute("DELETE FROM trip_places WHERE place_id = %s RETURNING trip_id", (place_id,)).fetchone(), "Place")
        return trip_detail(conn, old["trip_id"]) if old["trip_id"] else Response(status_code=204)


class OrderIn(BaseModel):
    place_ids: list[int] = Field(max_length=500)


@router.put("/travel/trips/{trip_id}/stops")
def order_stops(trip_id: int, body: OrderIn):
    """The trip's stops in this order (the route); any left out go after them."""
    with db() as conn:
        trip_row(conn, trip_id)
        for n, place_id in enumerate(body.place_ids, 1):
            conn.execute("UPDATE trip_places SET stop_order = %s WHERE place_id = %s AND trip_id = %s", (n, place_id, trip_id))
        return trip_detail(conn, trip_id)


@router.get("/travel/find-place")
def find_place(q: str = Query(..., min_length=2, max_length=100)):
    """Towns and cities called this (Open-Meteo's place search): name, region, country code, where it is."""
    try:
        return openmeteo.find_place(q.strip())
    except openmeteo.WeatherError as e:
        raise HTTPException(502, str(e)) from None


class CountryIn(BaseModel):
    status: Literal["Been", "Want"] = "Been"
    first_year: int | None = Field(None, ge=1900, le=2100)
    notes: str | None = Field(None, max_length=2000)


@router.get("/travel/countries")
def get_countries():
    with db() as conn:
        return countries(conn)


@router.put("/travel/countries/{code}")
def put_country(code: str, body: CountryIn):
    code = code.upper()
    if len(code) != 2 or not code.isalpha():
        raise HTTPException(422, "Countries are two-letter codes (JP, NZ).")
    with db() as conn:
        conn.execute("""INSERT INTO travel_countries (code, status, first_year, notes) VALUES (%s, %s, %s, %s)
                        ON CONFLICT (code) DO UPDATE SET status = EXCLUDED.status, first_year = EXCLUDED.first_year,
                            notes = EXCLUDED.notes""", (code, body.status, body.first_year, (body.notes or "").strip() or None))
        return countries(conn)


@router.delete("/travel/countries/{code}")
def delete_country(code: str):
    """Forget one you added (a country your trips or places went to still counts)."""
    with db() as conn:
        conn.execute("DELETE FROM travel_countries WHERE code = %s", (code.upper(),))
        return countries(conn)
