"""The wishlist: things you want, not things you own.

A wishlist item lives in its own table and only becomes a supply when you mark it bought
("move to inventory").
"""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from .db import FINISHES, PAINT_TYPES, PRIORITIES, db, found, insert_row, stock_reason, update_row
from .settings import get_setting

router = APIRouter(prefix="/api", tags=["wishlist"])

PaintType = Literal[tuple(PAINT_TYPES)]
Finish = Literal[tuple(FINISHES)]
Priority = Literal[tuple(PRIORITIES)]


class WishIn(BaseModel):
    brand_id: int | None = None
    product_code: str | None = None
    name: str = Field(min_length=1)
    category_id: int
    paint_type: PaintType | None = None
    finish: Finish | None = None
    size: str | None = None
    qty_wanted: int = Field(1, ge=1)
    est_price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    priority: Priority = "Normal"
    notes: str | None = None


class WishPatch(BaseModel):
    """Partial update; send just {"got_it": true} to tick an item off."""
    brand_id: int | None = None
    product_code: str | None = None
    name: str | None = Field(None, min_length=1)
    category_id: int | None = None
    paint_type: PaintType | None = None
    finish: Finish | None = None
    size: str | None = None
    qty_wanted: int | None = Field(None, ge=1)
    est_price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    priority: Priority | None = None
    notes: str | None = None
    got_it: bool | None = None


class Buy(BaseModel):
    purchased_from: str | None = None  # blank = your default shop (Settings)


# A wishlist row w is "this supply" s: same brand + code, or the same name when there's no code.
ON_WISHLIST_MATCH = """((w.brand_id = s.brand_id AND w.product_code = s.product_code)
                     OR (s.product_code IS NULL AND w.name = s.name))"""
ON_WISHLIST = f"EXISTS (SELECT 1 FROM wishlist w WHERE {ON_WISHLIST_MATCH})"

# Wishlist rows with names, photo info, and how many you already own of the same item.
WISH_SELECT = """
SELECT w.*, b.name AS brand, c.name AS category,
       p.product_info_id, (p.image IS NOT NULL) AS has_image, p.source_url, p.description,
       p.fetched_at AS photo_updated,
       cp.thumb_url AS catalog_thumb,           -- small Tamiya picture until the real photo arrives
       COALESCE(owned.qty_on_hand, 0) AS owned_qty,
       owned.supply_id AS owned_supply_id,      -- the matching inventory item, if any
       owned.condition AS owned_condition,      -- e.g. Nearly empty: why it's on the wishlist
       owned.stock_status AS owned_status       -- OK / Low / Out
FROM wishlist w
JOIN categories c ON c.category_id = w.category_id
LEFT JOIN brands b ON b.brand_id = w.brand_id
LEFT JOIN product_info p ON p.brand_id = w.brand_id AND p.product_code = w.product_code
LEFT JOIN catalog_products cp ON cp.brand_id = w.brand_id AND cp.product_code = w.product_code
LEFT JOIN LATERAL (
    -- Same matching as ON_WISHLIST: brand + code, or the name when there's no code.
    SELECT v.supply_id, v.qty_on_hand, v.condition, v.stock_status
    FROM supplies s JOIN v_supplies v USING (supply_id)
    WHERE (s.brand_id = w.brand_id AND s.product_code = w.product_code)
       OR (w.product_code IS NULL AND s.product_code IS NULL AND s.name = w.name)
    ORDER BY v.qty_on_hand DESC
    LIMIT 1
) owned ON true
"""
WISH_ORDER = """
ORDER BY w.got_it, CASE w.priority WHEN 'High' THEN 0 WHEN 'Normal' THEN 1 ELSE 2 END, w.created_at
"""


def fetch_wish(conn, wish_id):
    return found(conn.execute(WISH_SELECT + " WHERE w.wish_id = %s", (wish_id,)).fetchone(),
                 f"Wishlist item {wish_id}")


def wish_from_supplies(conn, where, params=(), notes=None):
    """Copy supplies onto the wishlist (skipping ones already there): same details, 1 wanted,
    the last price paid as the expected price. Returns [{wish_id, name}] for those added."""
    return conn.execute(f"""
        INSERT INTO wishlist (brand_id, product_code, name, category_id, paint_type, finish,
                              size, qty_wanted, est_price, notes)
        SELECT s.brand_id, s.product_code, s.name, s.category_id, s.paint_type, s.finish,
               s.size, 1, s.unit_price, %s
        FROM supplies s JOIN v_supplies v USING (supply_id)
        WHERE ({where}) AND NOT {ON_WISHLIST}
        RETURNING wish_id, name""", (notes, *params)).fetchall()


@router.get("/wishlist")
def list_wishlist(show: Literal["all", "needed", "got"] = "all"):
    where = {"all": "", "needed": " WHERE NOT w.got_it", "got": " WHERE w.got_it"}[show]
    with db() as conn:
        return conn.execute(WISH_SELECT + where + WISH_ORDER).fetchall()


@router.post("/wishlist", status_code=201)
def add_wish(body: WishIn):
    with db() as conn:
        return fetch_wish(conn, insert_row(conn, "wishlist", body.model_dump(), "wish_id"))


@router.patch("/wishlist/{wish_id}")
def update_wish(wish_id: int, body: WishPatch):
    with db() as conn:
        update_row(conn, "wishlist", "wish_id", wish_id, body.model_dump(exclude_unset=True))
        return fetch_wish(conn, wish_id)


@router.delete("/wishlist/{wish_id}", status_code=204)
def delete_wish(wish_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM wishlist WHERE wish_id = %s RETURNING wish_id", (wish_id,)).fetchone(),
              f"Wishlist item {wish_id}")
    return Response(status_code=204)


def move_to_inventory(conn, wish, shop):
    """Turn one wishlist row into stock, then remove it from the wishlist.

    If you already own the same brand + code, its quantity goes up instead of creating a
    duplicate (the UNIQUE rule on supplies would refuse a duplicate anyway).
    """
    stock_reason(conn, "bought (wishlist)")
    existing = None
    if wish["brand_id"] is not None and wish["product_code"]:
        existing = conn.execute("SELECT supply_id FROM supplies WHERE brand_id = %s AND product_code = %s",
                                (wish["brand_id"], wish["product_code"])).fetchone()

    if existing:
        supply_id = existing["supply_id"]
        conn.execute("""
            UPDATE supplies SET qty_on_hand = qty_on_hand + %(qty)s, condition = 'Sealed',
                   purchase_date = current_date,
                   purchased_from = COALESCE(%(shop)s, purchased_from),
                   unit_price = COALESCE(%(price)s, unit_price)
            WHERE supply_id = %(id)s""",
            {"qty": wish["qty_wanted"], "shop": shop, "price": wish["est_price"], "id": supply_id})
    else:
        # New stock follows your conventions: reorder at 0, Sealed, bought today, location Other.
        supply_id = conn.execute("""
            INSERT INTO supplies (brand_id, product_code, name, category_id, paint_type, finish,
                                  size, qty_on_hand, reorder_at, condition, unit_price,
                                  purchase_date, purchased_from, location_id, notes)
            VALUES (%(brand_id)s, %(product_code)s, %(name)s, %(category_id)s, %(paint_type)s,
                    %(finish)s, %(size)s, %(qty_wanted)s, 0, 'Sealed', %(est_price)s,
                    current_date, %(shop)s,
                    (SELECT location_id FROM storage_locations WHERE name = 'Other'),
                    %(notes)s)
            RETURNING supply_id""", {**wish, "shop": shop}).fetchone()["supply_id"]

    conn.execute("DELETE FROM wishlist WHERE wish_id = %s", (wish["wish_id"],))
    supply = conn.execute("SELECT supply_id, item_ref, name, qty_on_hand FROM v_supplies WHERE supply_id = %s",
                          (supply_id,)).fetchone()
    return {**supply, "merged": existing is not None}


def shop_name(conn, body: Buy | None):
    """The shop it was bought from: as typed, else your default shop."""
    typed = (body.purchased_from or "").strip() if body else ""
    return typed or get_setting(conn, "default_shop")


@router.post("/wishlist/{wish_id}/buy")
def buy_one(wish_id: int, body: Buy | None = None):
    """Bought it: add to inventory and remove from the wishlist."""
    with db() as conn:
        wish = found(conn.execute("SELECT * FROM wishlist WHERE wish_id = %s", (wish_id,)).fetchone(),
                     f"Wishlist item {wish_id}")
        return move_to_inventory(conn, wish, shop_name(conn, body))


@router.post("/wishlist/restock")
def wish_for_restock():
    """Put everything that needs attention - Out, or Low (e.g. your last bottle is nearly
    empty) - onto the wishlist, skipping ones already there."""
    with db() as conn:
        added = wish_from_supplies(conn, "v.stock_status IN ('Out', 'Low')")
    return {"added": len(added), "names": [r["name"] for r in added]}


@router.post("/wishlist/buy-ticked")
def buy_ticked(body: Buy | None = None):
    """Move every ticked item to inventory in one go (all or nothing: one transaction)."""
    with db() as conn:
        shop = shop_name(conn, body)
        wishes = conn.execute("SELECT * FROM wishlist WHERE got_it ORDER BY wish_id").fetchall()
        return [move_to_inventory(conn, w, shop) for w in wishes]
