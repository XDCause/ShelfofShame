"""Gear (shared by every hobby; volleyball's for now): shoes, knee pads, balls... with condition, photo,
and where to buy it. Wanted gear (not bought yet) has no purchase date or price paid. Gear can be found at
Blue Sky Athletics (Way of Wade shoes; bluesky.py) and filled in from there.

    GET    /gear                  your gear: in use, then Wanted, then Retired
    GET    /gear/lookup?q=        Blue Sky Athletics products (gear_id = the one you have)
    POST   /gear                  add (shop_id: name / kind / brand / link / price / photo from the shop)
    POST   /gear/{id}/shop        link gear you have to a shop product
    GET / PATCH / DELETE /gear/{id}, and /gear/{id}/photo
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import bluesky, gameology
from .db import GEAR_CONDITIONS, db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["volleyball"])

Condition = Literal[tuple(GEAR_CONDITIONS)]


ShopId = Field(None, pattern=r"^[0-9]{1,20}$")


class GearIn(BaseModel):
    name: str = Field("", max_length=200)   # may be empty when shop_id is given (the shop's name is used)
    shop_id: str | None = ShopId    # picked from the shop search (Blue Sky Athletics): its facts and photo are read
    kind: str | None = None
    brand: str | None = None
    size: str | None = None
    condition: Condition = "Good"
    purchase_date: date | None = None
    price_paid: Decimal | None = Field(None, ge=0)
    notes: str | None = None


class GearPatch(BaseModel):
    name: str | None = Field(None, min_length=1)
    kind: str | None = None
    brand: str | None = None
    size: str | None = None
    condition: Condition | None = None
    purchase_date: date | None = None
    price_paid: Decimal | None = Field(None, ge=0)
    notes: str | None = None


GEAR_SELECT = """
SELECT g.gear_id, g.hobby, g.name, g.kind, g.brand, g.size, g.condition, g.purchase_date, g.price_paid,
       g.notes, g.created_at, g.updated_at, g.photo IS NOT NULL AS has_photo,
       g.shop_name, g.shop_url, g.shop_price, g.shop_id,
       CASE WHEN g.photo IS NOT NULL THEN '/api/gear/' || g.gear_id || '/photo?v='
            || (extract(epoch FROM g.photo_updated) * 1000)::bigint END AS photo_url
FROM gear g"""


def fetch_gear(conn, gear_id: int) -> dict:
    return found(conn.execute(GEAR_SELECT + " WHERE g.gear_id = %s", (gear_id,)).fetchone(), "Gear")


# ---------------------------------------------------------------------------
# Gear
# ---------------------------------------------------------------------------
@router.get("/gear")
def list_gear():
    """Your gear: in use first (worst condition first), then what you want to buy, retired last."""
    with db() as conn:
        return conn.execute(GEAR_SELECT + " ORDER BY g.condition = 'Retired', g.condition = 'Wanted', "
                            "array_position(ARRAY['Needs replacing', 'Worn', 'Good', 'New'], g.condition), "
                            "lower(g.name)").fetchall()


def not_bought_yet(data: dict) -> dict:
    """Wanted gear hasn't been bought: no purchase date or price."""
    if data.get("condition") == "Wanted":
        data.update(purchase_date=None, price_paid=None)
    return data


class ShopIn(BaseModel):
    shop_id: str = Field(pattern=r"^[0-9]{1,20}$")


def shop_product(shop_id: str) -> dict:
    """A product from Blue Sky Athletics' search (server side: the browser's word isn't trusted for facts)."""
    try:
        product = bluesky.get(shop_id)
    except bluesky.ShopError as e:
        raise HTTPException(502, str(e))
    if not product:
        raise HTTPException(404, "Blue Sky Athletics doesn't have that product any more.")
    return product


def fill_from_shop(conn, gear_id: int, product: dict):
    """The shop's facts into the empty fields, the link and price always; its photo if there's none."""
    conn.execute("""UPDATE gear SET kind = COALESCE(kind, %(kind)s), brand = COALESCE(brand, %(brand)s),
                    shop_name = %(shop)s, shop_url = %(url)s, shop_price = %(price)s, shop_id = %(id)s WHERE gear_id = %(gear)s""",
                 {**product, "shop": bluesky.STORE.name, "gear": gear_id})
    has_photo = conn.execute("SELECT photo IS NOT NULL AS has FROM gear WHERE gear_id = %s", (gear_id,)).fetchone()["has"]
    if not has_photo and product["image"]:
        image, image_type = gameology.photo({"image": product["image"] + ("&" if "?" in product["image"] else "?") + "width=600"})
        if image:
            conn.execute("UPDATE gear SET photo = %s, photo_type = %s, photo_updated = now() WHERE gear_id = %s",
                         (image, image_type, gear_id))


# Declared before /gear/{gear_id} (else "lookup" would be read as an id).
@router.get("/gear/lookup")
def gear_lookup(q: str = Query(..., min_length=2, max_length=100)):
    """Search Blue Sky Athletics (Way of Wade shoes and more): in stock first; `yours` = gear you have from it."""
    try:
        found_ = bluesky.search(q.strip())
    except bluesky.ShopError as e:
        raise HTTPException(502, str(e))
    with db() as conn:
        mine = {r["shop_id"]: r["gear_id"] for r in conn.execute(
            "SELECT shop_id, gear_id FROM gear WHERE shop_id IS NOT NULL").fetchall()}
    return [{**p, "gear_id": mine.get(p["id"])} for p in found_]


@router.post("/gear", status_code=201)
def add_gear(body: GearIn):
    data = not_bought_yet(tidy_text(body.model_dump(exclude={"shop_id"})))
    if not data.get("name") and not body.shop_id:
        raise HTTPException(422, "Give it a name.")
    product = shop_product(body.shop_id) if body.shop_id else None
    if product and not data.get("name"):
        data["name"] = product["name"]
    with db() as conn:
        gear_id = insert_row(conn, "gear", data, "gear_id")
        if product:
            fill_from_shop(conn, gear_id, product)
        return fetch_gear(conn, gear_id)


@router.post("/gear/{gear_id}/shop")
def link_gear_to_shop(gear_id: int, body: ShopIn):
    """Link gear you have to its shop product: the link and price, and its facts / photo where yours are empty."""
    product = shop_product(body.shop_id)
    with db() as conn:
        fetch_gear(conn, gear_id)
        fill_from_shop(conn, gear_id, product)
        return fetch_gear(conn, gear_id)


@router.get("/gear/{gear_id}")
def get_gear(gear_id: int):
    with db() as conn:
        return fetch_gear(conn, gear_id)


@router.patch("/gear/{gear_id}")
def update_gear(gear_id: int, body: GearPatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if "condition" in data and data["condition"] is None:
        raise HTTPException(422, "Condition can't be empty.")
    with db() as conn:
        current = fetch_gear(conn, gear_id)
        if current["condition"] == "Wanted" and data.get("condition", "Wanted") != "Wanted"                 and not data.get("purchase_date") and not current["purchase_date"]:
            data["purchase_date"] = conn.execute("SELECT current_date AS d").fetchone()["d"]   # bought: today (Brisbane)
        not_bought_yet(data)
        update_row(conn, "gear", "gear_id", gear_id, data)
        return fetch_gear(conn, gear_id)


@router.delete("/gear/{gear_id}", status_code=204)
def delete_gear(gear_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM gear WHERE gear_id = %s RETURNING gear_id", (gear_id,)).fetchone(), "Gear")
        conn.execute("DELETE FROM journal_links WHERE target_kind = 'gear' AND target_id = %s", (gear_id,))
    return Response(status_code=204)


add_photo_routes(router, "/gear", "gear", "gear_id", "Gear")
