"""Supplies (your inventory) and their stock history.

Kits (76_supply_kits.sql): a supply can be part of another (part_of) - the nipper in a tool kit. A kit lists its
parts, and the parts its title says it comes with that you haven't added yet ("Includes Nipper, Hobby Knife..."):
POST /supplies/{id}/parts adds them, copying the kit's brand, where and when you bought it, condition and place.
Searching finds a part by its own name, and the kit by any of its parts' names. A part with no photo shows its kit's.
"""
import re
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .db import CONDITIONS, FINISHES, PAINT_TYPES, db, found, insert_row, stock_reason, update_row
from .wishlist import ON_WISHLIST, ON_WISHLIST_MATCH, wish_from_supplies

router = APIRouter(prefix="/api", tags=["supplies"])

PaintType = Literal[tuple(PAINT_TYPES)]
Finish = Literal[tuple(FINISHES)]
Condition = Literal[tuple(CONDITIONS)]


class SupplyIn(BaseModel):
    """A new supply. Brand, category and location are ids from GET /api/lookups."""
    brand_id: int | None = None
    product_code: str | None = None
    name: str = Field(min_length=1)
    category_id: int
    paint_type: PaintType | None = None
    finish: Finish | None = None
    size: str | None = None
    qty_on_hand: int = Field(0, ge=0)
    reorder_at: int | None = Field(None, ge=0)
    condition: Condition | None = None
    unit_price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    purchase_date: date | None = None      # shown as "Last purchased"
    purchased_from: str | None = None      # shown as "Last bought from"
    location_id: int | None = None
    notes: str | None = None
    part_of: int | None = None             # the kit it came in


class SupplyPatch(BaseModel):
    """Partial update: only the fields you send are changed."""
    brand_id: int | None = None
    product_code: str | None = None
    name: str | None = Field(None, min_length=1)
    category_id: int | None = None
    paint_type: PaintType | None = None
    finish: Finish | None = None
    size: str | None = None
    qty_on_hand: int | None = Field(None, ge=0)
    reorder_at: int | None = Field(None, ge=0)
    condition: Condition | None = None
    unit_price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    purchase_date: date | None = None
    purchased_from: str | None = None
    location_id: int | None = None
    notes: str | None = None
    part_of: int | None = None


class Adjust(BaseModel):
    """Change quantity by a relative amount, e.g. -1 = used one, +3 = bought three.
    Adding stock also sets the last-purchased date to today.

    undo = reversing a mistaken -/+: logged as 'undo', and the last-purchased date is set to
    `purchase_date` (what it was before) instead of today."""
    delta: int = Field(description="Amount to add (negative to remove)")
    undo: bool = False
    purchase_date: date | None = None
    remove_wish_id: int | None = None  # undo: the wishlist item the original change auto-added


# The models whose checklist has this supply (directly, or as part of a mix).
USED_ON = """
COALESCE((SELECT json_agg(json_build_object('model_id', m.model_id, 'name', m.name,
                                             'status', m.status) ORDER BY m.name)
          FROM models m
          WHERE s.product_code IS NOT NULL AND EXISTS (
              SELECT 1 FROM model_paints mp
              WHERE mp.model_id = m.model_id
                AND ((mp.brand_id = s.brand_id AND mp.product_code = s.product_code)
                     OR EXISTS (SELECT 1 FROM mix_parts x WHERE x.mix_id = mp.mix_id
                                AND x.brand_id = s.brand_id AND x.product_code = s.product_code)))),
         '[]'::json)"""

# The raw table gives the ids (needed for editing); the view adds names and calculated columns;
# product_info (matched on brand + code) adds the cached manufacturer photo and description.
SUPPLY_SELECT = f"""
SELECT s.*, v.item_ref, v.brand, v.category, v.location, v.stock_status, v.total_value,
       -- the photo: its own, else (a part) its kit's
       CASE WHEN p.image IS NOT NULL OR NOT COALESCE(kit.has_image, false) THEN p.product_info_id ELSE kit.info_id END AS product_info_id,
       (p.image IS NOT NULL OR COALESCE(kit.has_image, false)) AS has_image, p.description AS product_description,
       p.title AS product_title, p.source_url,
       CASE WHEN p.image IS NOT NULL OR NOT COALESCE(kit.has_image, false) THEN p.fetched_at ELSE kit.fetched_at END AS photo_updated,
       kit.kit_name, kit.kit_code,
       (SELECT count(*) FROM supplies x WHERE x.part_of = s.supply_id)::int AS part_count,
       COALESCE(p.barcode, (SELECT c.barcode FROM barcode_catalog c
                            WHERE c.brand_id = s.brand_id AND c.product_code = s.product_code
                            LIMIT 1)) AS barcode,
       {ON_WISHLIST} AS on_wishlist,
       {USED_ON} AS used_on
FROM supplies s
JOIN v_supplies v USING (supply_id)
LEFT JOIN product_info p ON p.brand_id = s.brand_id AND p.product_code = s.product_code
-- the kit it came in (a sub-select, so "supply_id" stays unambiguous for the WHERE clauses added to this)
LEFT JOIN LATERAL (SELECT k.name AS kit_name, k.product_code AS kit_code, kp.product_info_id AS info_id,
                          kp.image IS NOT NULL AS has_image, kp.fetched_at
                   FROM supplies k LEFT JOIN product_info kp ON kp.brand_id = k.brand_id AND kp.product_code = k.product_code
                   WHERE k.supply_id = s.part_of) kit ON true
"""


def fetch_supply(conn, supply_id):
    return found(conn.execute(SUPPLY_SELECT + " WHERE supply_id = %s", (supply_id,)).fetchone(),
                 f"Supply {supply_id}")


def stock_status(conn, supply_id):
    row = conn.execute("SELECT stock_status FROM v_supplies WHERE supply_id = %s", (supply_id,)).fetchone()
    return row["stock_status"] if row else None


def auto_wishlist(conn, supply_id, before):
    """If this change just took the item from OK to Low/Out, put it on the wishlist.
    Only on that change - if you take it off the wishlist while it's still low, it stays off.
    Returns the new wishlist item's id, or None."""
    after = stock_status(conn, supply_id)
    if before != "OK" or after not in ("Low", "Out"):
        return None
    note = "Added automatically: " + ("running low" if after == "Low" else "out of stock")
    added = wish_from_supplies(conn, "s.supply_id = %s", (supply_id,), notes=note)
    return added[0]["wish_id"] if added else None


@router.get("/supplies")
def list_supplies(q: str | None = None, category: str | None = None, brand: str | None = None,
                  status: Literal["OK", "Low", "Out"] | None = None, location: str | None = None):
    """Search and filter. `q` matches name, code, brand, category and notes."""
    where, params = [], {}
    if q:
        # Escape LIKE wildcards so searching for "50%" or "_" means the literal characters
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["q"] = f"%{term}%"
        where.append("(s.name ILIKE %(q)s OR s.product_code ILIKE %(q)s OR v.brand ILIKE %(q)s"
                     " OR v.category ILIKE %(q)s OR s.notes ILIKE %(q)s"
                     " OR EXISTS (SELECT 1 FROM supplies x WHERE x.part_of = s.supply_id AND x.name ILIKE %(q)s))")  # a kit, by its parts
    for column, value in (("category", category), ("brand", brand),
                          ("stock_status", status), ("location", location)):
        if value:
            params[column] = value
            where.append(f"v.{column} = %({column})s")
    query = SUPPLY_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY supply_id"
    with db() as conn:
        return conn.execute(query, params).fetchall()


# Declared before /supplies/{supply_id} so "low-stock" isn't mistaken for an id.
@router.get("/supplies/low-stock")
def low_stock():
    """Everything that is Out or Low - i.e. the shopping list."""
    with db() as conn:
        return conn.execute(SUPPLY_SELECT + " WHERE v.stock_status <> 'OK' ORDER BY v.stock_status,"
                            " v.brand, s.name").fetchall()


def kit_parts(title: str | None) -> list[str]:
    """What a kit's title says it comes with: "... Kit TZ-01 Includes Nipper, Hobby Knife, Tweezers & Sanding Sticks"
    -> ["Nipper", "Hobby Knife", "Tweezers", "Sanding Sticks"]."""
    m = re.search(r"(?i)\b(?:includes?|including|comes with)\b:?\s*(.+)$", title or "")
    if not m:
        return []
    parts = re.split(r"\s*(?:,|&|\+|/|\band\b)\s*", re.sub(r"[()\[\]]", " ", m.group(1)))
    out = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" .-")
        if 2 <= len(p) <= 60 and p.lower() not in (x.lower() for x in out):
            out.append(p[0].upper() + p[1:])
    return out[:12]


def with_parts(conn, supply: dict) -> dict:
    """A supply with its kit's parts (and the parts its title mentions that aren't added yet)."""
    supply["parts"] = conn.execute("SELECT s.supply_id, s.name, s.qty_on_hand, v.stock_status, v.category FROM supplies s "
                                   "JOIN v_supplies v USING (supply_id) WHERE s.part_of = %s ORDER BY s.supply_id",
                                   (supply["supply_id"],)).fetchall()
    have = " ".join(p["name"].lower() for p in supply["parts"])
    supply["suggested_parts"] = [] if supply["part_of"] else \
        [p for p in kit_parts(supply["product_title"] or supply["name"]) if p.lower().rstrip("s") not in have]
    return supply


def check_kit(conn, supply_id: int | None, part_of: int | None):
    """One level: a kit can't be a part, and a part can't be a kit."""
    if part_of is None:
        return
    kit = conn.execute("SELECT part_of FROM supplies WHERE supply_id = %s", (part_of,)).fetchone()
    if kit is None:
        raise HTTPException(422, "That kit isn't in your supplies.")
    if kit["part_of"] is not None:
        raise HTTPException(422, "That's itself part of a kit - pick the kit it came in.")
    if supply_id is not None and conn.execute("SELECT 1 FROM supplies WHERE part_of = %s", (supply_id,)).fetchone():
        raise HTTPException(422, "This is a kit with its own parts, so it can't be part of another.")


@router.get("/supplies/{supply_id}")
def get_supply(supply_id: int):
    with db() as conn:
        return with_parts(conn, fetch_supply(conn, supply_id))


@router.post("/supplies", status_code=201)
def create_supply(body: SupplyIn):
    with db() as conn:
        check_kit(conn, None, body.part_of)
        stock_reason(conn, "added")
        return fetch_supply(conn, insert_row(conn, "supplies", body.model_dump(), "supply_id"))


class PartIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category_id: int | None = None          # else a guess from the name (Tools, Sanding / Abrasives...), else the kit's
    qty_on_hand: int = Field(1, ge=0)
    size: str | None = Field(None, max_length=60)
    product_code: str | None = Field(None, max_length=40)
    notes: str | None = Field(None, max_length=2000)


class PartsIn(BaseModel):
    parts: list[PartIn] = Field(min_length=1, max_length=30)


GUESS = [(r"sand|grit|file|abrasive|polish", "Sanding / Abrasives"), (r"brush", "Brushes"), (r"glue|cement", "Glue / Cement"),
         (r"tape", "Masking Tape"), (r"nipper|cutter|knife|blade|tweezer|plier|scriber|chisel|drill|tool|scissor", "Tools")]


@router.post("/supplies/{supply_id}/parts", status_code=201)
def add_parts(supply_id: int, body: PartsIn):
    """Add a kit's parts as supplies of their own (in the kit), like the kit: brand, bought when and where,
    condition, place. Answers with the kit and its parts."""
    with db() as conn:
        kit = fetch_supply(conn, supply_id)
        if kit["part_of"] is not None:
            raise HTTPException(422, "This is itself part of a kit - add the parts to the kit it came in.")
        cats = {c["name"]: c["category_id"] for c in conn.execute("SELECT name, category_id FROM categories").fetchall()}
        stock_reason(conn, "added")
        for p in body.parts:
            name = p.name.strip()
            guess = next((cats.get(c) for pattern, c in GUESS if re.search(pattern, name, re.I) and cats.get(c)), None)
            insert_row(conn, "supplies", {
                "name": name, "category_id": p.category_id or guess or kit["category_id"], "brand_id": kit["brand_id"],
                "product_code": (p.product_code or "").strip() or None, "qty_on_hand": p.qty_on_hand, "size": p.size,
                "condition": kit["condition"], "purchase_date": kit["purchase_date"], "purchased_from": kit["purchased_from"],
                "location_id": kit["location_id"], "reorder_at": 0, "paint_type": "N/A" if "N/A" in PAINT_TYPES else None,
                "finish": "N/A" if "N/A" in FINISHES else None, "notes": (p.notes or "").strip() or None, "part_of": supply_id}, "supply_id")
        return with_parts(conn, fetch_supply(conn, supply_id))


@router.patch("/supplies/{supply_id}")
def update_supply(supply_id: int, body: SupplyPatch):
    data = body.model_dump(exclude_unset=True)  # only fields the client actually sent
    with db() as conn:
        if "part_of" in data:
            if data["part_of"] == supply_id:
                raise HTTPException(422, "A supply can't be part of itself.")
            check_kit(conn, supply_id, data["part_of"])
        before = stock_status(conn, supply_id)
        stock_reason(conn, "edited")
        update_row(conn, "supplies", "supply_id", supply_id, data)
        wish_id = auto_wishlist(conn, supply_id, before) if data else None  # e.g. -> Nearly empty
        return {**fetch_supply(conn, supply_id), "auto_wish_id": wish_id}


@router.post("/supplies/{supply_id}/adjust")
def adjust_quantity(supply_id: int, body: Adjust):
    """Relative change done inside the database, so two quick clicks can't overwrite each other.
    If it takes the item from OK to Low/Out it goes on the wishlist (auto_wish_id in the reply)."""
    with db() as conn:
        wish_id = None
        if body.undo:
            stock_reason(conn, "undo")
            conn.execute("UPDATE supplies SET qty_on_hand = qty_on_hand + %s WHERE supply_id = %s",
                         (body.delta, supply_id))
            if "purchase_date" in body.model_fields_set:  # put the old date back (may be empty)
                conn.execute("UPDATE supplies SET purchase_date = %s WHERE supply_id = %s",
                             (body.purchase_date, supply_id))
            if body.remove_wish_id:  # the change being undone had put it on the wishlist
                conn.execute("DELETE FROM wishlist WHERE wish_id = %s AND NOT got_it", (body.remove_wish_id,))
        else:
            before = stock_status(conn, supply_id)
            stock_reason(conn, "used" if body.delta < 0 else "bought")
            conn.execute("""
                UPDATE supplies SET qty_on_hand = qty_on_hand + %(delta)s,
                       purchase_date = CASE WHEN %(delta)s > 0 THEN current_date ELSE purchase_date END
                WHERE supply_id = %(id)s""", {"delta": body.delta, "id": supply_id})
            wish_id = auto_wishlist(conn, supply_id, before)
        return {**fetch_supply(conn, supply_id), "auto_wish_id": wish_id}


@router.post("/supplies/{supply_id}/wishlist", status_code=201)
def add_supply_to_wishlist(supply_id: int):
    """The item panel's "Add to wishlist": copy this supply onto the wishlist (any time)."""
    with db() as conn:
        fetch_supply(conn, supply_id)  # 404 if it doesn't exist
        added = wish_from_supplies(conn, "s.supply_id = %s", (supply_id,))
        if not added:
            raise HTTPException(409, "It's already on your wishlist.")
        return {**fetch_supply(conn, supply_id), "wish_id": added[0]["wish_id"]}


@router.delete("/supplies/{supply_id}/wishlist")
def remove_supply_from_wishlist(supply_id: int):
    """The item panel's "On wishlist ✕": take it back off the wishlist (unless it's already
    ticked as bought - then it's on its way into the inventory)."""
    with db() as conn:
        fetch_supply(conn, supply_id)
        gone = conn.execute(f"""
            DELETE FROM wishlist w USING supplies s
            WHERE s.supply_id = %s AND NOT w.got_it AND {ON_WISHLIST_MATCH}
            RETURNING w.wish_id""", (supply_id,)).fetchall()
        if not gone:
            raise HTTPException(409, "It's not on your wishlist, or it's already ticked as bought.")
        return fetch_supply(conn, supply_id)


@router.delete("/supplies/{supply_id}", status_code=204)
def delete_supply(supply_id: int, also_wishlist: bool = False):
    """Remove an item from the inventory (e.g. used up and not replacing it). The stock history
    keeps its name. also_wishlist=true also takes it off the wishlist (running out put it there),
    unless it's already ticked as bought."""
    with db() as conn:
        stock_reason(conn, "deleted")
        if also_wishlist:
            conn.execute(f"""
                DELETE FROM wishlist w USING supplies s
                WHERE s.supply_id = %s AND NOT w.got_it AND {ON_WISHLIST_MATCH}""", (supply_id,))
        found(conn.execute("DELETE FROM supplies WHERE supply_id = %s RETURNING supply_id",
                           (supply_id,)).fetchone(), f"Supply {supply_id}")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Stock history (recorded by a database trigger - see db/init/06_stock_history.sql)
# ---------------------------------------------------------------------------
@router.get("/supplies/{supply_id}/history")
def supply_history(supply_id: int, limit: int = Query(20, ge=1, le=500)):
    """Newest first: every quantity change for one supply, with the reason."""
    with db() as conn:
        return conn.execute(
            "SELECT movement_id, change, qty_after, reason, unit_price, created_at FROM stock_movements "
            "WHERE supply_id = %s ORDER BY created_at DESC, movement_id DESC LIMIT %s",
            (supply_id, limit)).fetchall()


@router.get("/history")
def recent_history(limit: int = Query(50, ge=1, le=500)):
    """Newest first, across all supplies (deleted items included, by name)."""
    with db() as conn:
        return conn.execute(
            "SELECT m.movement_id, m.supply_id, v.item_ref, m.item_name, m.change, m.qty_after,"
            " m.reason, m.unit_price, m.created_at FROM stock_movements m"
            " LEFT JOIN v_supplies v ON v.supply_id = m.supply_id"
            " ORDER BY m.created_at DESC, m.movement_id DESC LIMIT %s", (limit,)).fetchall()
