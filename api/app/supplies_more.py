"""More for Supplies (2026-10-21; from a look at paintRack, Sortly, Grocy and Homebox):

    places        storage places that nest (rack > drawer > box), each with what's in it; a QR label for each
    stocktake     the supplies to count, least recently counted first; a count sets the quantity
    shop          a shopping list for one trip: the wishlist (that shop's) and what's Low / Out or will run out soon
    attachments   receipts, manuals and warranties (a photo or a PDF) on a supply or a piece of gear
    bulk          several supplies at once: move to a place, change category, set aside, add to the wishlist, remove
    value report  what you own and what it cost, per hobby, to print (for insurance)

Included before supplies.py's router: /supplies/stocktake etc. would otherwise be read as /supplies/{supply_id}.
"""
import io
from decimal import Decimal
from typing import Literal

import segno
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from .db import GEAR_HOBBIES, db, found, stock_reason, update_row
from .settings import get_setting
from .supplies import SUPPLY_SELECT, auto_wishlist, stock_status
from .shooting import AMMO_SELECT, ammo_row
from .wishlist import ON_WISHLIST, wish_from_supplies

router = APIRouter(prefix="/api", tags=["supplies"])


# ---------------------------------------------------------------- places
class PlaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    parent_id: int | None = None


class PlacePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    parent_id: int | None = None


PLACES = """SELECT l.location_id AS id, l.name, l.parent_id, location_path(l.location_id) AS path,
       (SELECT count(*) FROM supplies s WHERE s.location_id = l.location_id)::int AS items,
       (SELECT count(*) FROM storage_locations c WHERE c.parent_id = l.location_id)::int AS children
FROM storage_locations l"""


def ancestors(conn, place_id: int) -> list[int]:
    ids, seen = [], set()
    current = place_id
    while current is not None and current not in seen:
        seen.add(current)
        ids.append(current)
        row = conn.execute("SELECT parent_id FROM storage_locations WHERE location_id = %s", (current,)).fetchone()
        current = row["parent_id"] if row else None
    return ids


@router.get("/places")
def places():
    """Every place, in path order (Paint rack, Paint rack › Drawer 1...), with how many things are in each."""
    with db() as conn:
        return conn.execute(PLACES + " ORDER BY lower(location_path(l.location_id))").fetchall()


@router.post("/places", status_code=201)
def add_place(body: PlaceIn):
    with db() as conn:
        if body.parent_id is not None:
            found(conn.execute("SELECT 1 FROM storage_locations WHERE location_id = %s", (body.parent_id,)).fetchone(), "Place")
        new_id = conn.execute("INSERT INTO storage_locations (name, parent_id) VALUES (%s, %s) RETURNING location_id",
                              (body.name.strip(), body.parent_id)).fetchone()["location_id"]
        return conn.execute(PLACES + " WHERE l.location_id = %s", (new_id,)).fetchone()


@router.patch("/places/{place_id}")
def change_place(place_id: int, body: PlacePatch):
    """Rename it, or move it inside another (not inside itself or anything in it)."""
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        if data["name"] is None:
            raise HTTPException(422, "A place needs a name.")
        data["name"] = data["name"].strip()
    with db() as conn:
        found(conn.execute("SELECT 1 FROM storage_locations WHERE location_id = %s", (place_id,)).fetchone(), "Place")
        if data.get("parent_id") is not None:
            found(conn.execute("SELECT 1 FROM storage_locations WHERE location_id = %s", (data["parent_id"],)).fetchone(), "Place")
            if place_id in ancestors(conn, data["parent_id"]):
                raise HTTPException(422, "A place can't go inside itself (or inside something that's in it).")
        update_row(conn, "storage_locations", "location_id", place_id, data)
        return conn.execute(PLACES + " WHERE l.location_id = %s", (place_id,)).fetchone()


@router.delete("/places/{place_id}", status_code=204)
def delete_place(place_id: int):
    """An empty place goes (nothing in it, no places inside it)."""
    with db() as conn:
        p = found(conn.execute(PLACES + " WHERE l.location_id = %s", (place_id,)).fetchone(), "Place")
        if p["items"] or p["children"]:
            raise HTTPException(409, f"{p['name']} still has things in it - move them first.")
        conn.execute("DELETE FROM storage_locations WHERE location_id = %s", (place_id,))
    return Response(status_code=204)


@router.get("/places/{place_id}")
def place(place_id: int):
    """One place: its path, the places inside it, and what's in it (and in the places inside it)."""
    with db() as conn:
        p = found(conn.execute(PLACES + " WHERE l.location_id = %s", (place_id,)).fetchone(), "Place")
        p["inside"] = conn.execute(PLACES + " WHERE l.parent_id = %s ORDER BY lower(l.name)", (place_id,)).fetchall()
        below = conn.execute("""WITH RECURSIVE t AS (SELECT location_id FROM storage_locations WHERE location_id = %s
                                UNION ALL SELECT l.location_id FROM storage_locations l JOIN t ON l.parent_id = t.location_id)
                                SELECT array_agg(location_id) AS ids FROM t""", (place_id,)).fetchone()["ids"]
        p["supplies"] = conn.execute(SUPPLY_SELECT + " WHERE s.location_id = ANY(%s) ORDER BY lower(s.name)", (below,)).fetchall()
        return p


class MoveIn(BaseModel):
    supply_ids: list[int] = Field(min_length=1, max_length=500)


@router.post("/places/{place_id}/move")
def move_here(place_id: int, body: MoveIn):
    with db() as conn:
        found(conn.execute("SELECT 1 FROM storage_locations WHERE location_id = %s", (place_id,)).fetchone(), "Place")
        stock_reason(conn, "edited")
        conn.execute("UPDATE supplies SET location_id = %s WHERE supply_id = ANY(%s)", (place_id, body.supply_ids))
    return place(place_id)


@router.get("/places/{place_id}/qr")
def place_qr(place_id: int, url: str = Query(..., min_length=8, max_length=300, pattern=r"^https?://")):
    """A QR code (SVG) for a place's label: it opens `url` (the place's page in the app)."""
    with db() as conn:
        found(conn.execute("SELECT 1 FROM storage_locations WHERE location_id = %s", (place_id,)).fetchone(), "Place")
    out = io.BytesIO()                                   # (the full SVG: an <img> needs its xmlns, which svg_inline leaves out)
    segno.make(url, error="m").save(out, kind="svg", scale=4, border=1, xmldecl=False)
    return Response(out.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=3600"})


# ---------------------------------------------------------------- stocktake
class CountIn(BaseModel):
    qty: int = Field(ge=0, le=100000)


@router.get("/supplies/stocktake")
def stocktake(limit: int = Query(200, ge=1, le=1000)):
    """What to count, the least recently counted first (never counted first of all)."""
    with db() as conn:
        return conn.execute(SUPPLY_SELECT + " ORDER BY s.counted_at NULLS FIRST, lower(location_path(s.location_id)) NULLS LAST, "
                            "lower(s.name) LIMIT %s", (limit,)).fetchall()


@router.post("/supplies/{supply_id}/count")
def count(supply_id: int, body: CountIn):
    """You counted it: this many. The difference goes in the stock history as a count; Low / Out goes on the wishlist."""
    with db() as conn:
        found(conn.execute("SELECT 1 FROM supplies WHERE supply_id = %s", (supply_id,)).fetchone(), "Supply")
        before = stock_status(conn, supply_id)
        stock_reason(conn, "counted")
        conn.execute("UPDATE supplies SET qty_on_hand = %s, counted_at = now() WHERE supply_id = %s", (body.qty, supply_id))
        wish_id = auto_wishlist(conn, supply_id, before)
        return {**conn.execute(SUPPLY_SELECT + " WHERE supply_id = %s", (supply_id,)).fetchone(), "auto_wish_id": wish_id}


# ---------------------------------------------------------------- shopping
@router.get("/supplies/shop")
def shop():
    """One trip's list: the wishlist (not yet got), then supplies Low / Out that aren't on it, then ones likely to run
    out within a month (from how fast you use them)."""
    with db() as conn:
        default = get_setting(conn, "default_shop") or "Hobbyrama"
        now = conn.execute("SELECT current_date AS d").fetchone()["d"]          # Brisbane's today (the API runs on UTC)
        wishes = conn.execute("""SELECT w.wish_id, w.name, w.product_code, w.qty_wanted, w.size, b.name AS brand, c.name AS category,
                                        w.est_price::float8 AS price, w.priority
                                 FROM wishlist w LEFT JOIN brands b USING (brand_id) LEFT JOIN categories c USING (category_id)
                                 WHERE NOT w.got_it ORDER BY c.name, w.name""").fetchall()
        low = conn.execute(SUPPLY_SELECT + f" WHERE v.stock_status <> 'OK' AND NOT {ON_WISHLIST} ORDER BY v.category, s.name").fetchall()
        soon = [r for r in conn.execute(SUPPLY_SELECT + " WHERE v.stock_status = 'OK' ORDER BY s.name").fetchall()
                if r["out_by"] and (r["out_by"] - now).days <= 31]
    return {"shop": default, "wishlist": wishes, "low": low, "soon": soon}


# ---------------------------------------------------------------- attachments
KINDS = ("Receipt", "Manual", "Warranty", "Other")
TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_BYTES = 10 * 1024 * 1024


def _thing(conn, thing_kind: str, thing_id: int):
    table, key = {"supply": ("supplies", "supply_id"), "gear": ("gear", "gear_id")}[thing_kind]
    found(conn.execute(f"SELECT 1 FROM {table} WHERE {key} = %s", (thing_id,)).fetchone(), thing_kind.capitalize())


@router.get("/attachments")
def attachments(thing_kind: Literal["supply", "gear"], thing_id: int):
    with db() as conn:
        return conn.execute("SELECT attachment_id, kind, name, content_type, size, created_at FROM attachments "
                            "WHERE thing_kind = %s AND thing_id = %s ORDER BY created_at", (thing_kind, thing_id)).fetchall()


@router.post("/attachments", status_code=201)
async def add_attachment(request: Request, thing_kind: Literal["supply", "gear"], thing_id: int,
                         name: str = Query(..., min_length=1, max_length=120), kind: Literal[KINDS] = "Receipt"):
    """A receipt, manual or warranty (the file is the request body): a PDF or a photo, up to 10 MB."""
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ctype not in TYPES:
        raise HTTPException(415, "Attach a PDF or a photo (JPEG, PNG, WebP, HEIC).")
    data = await request.body()
    if not data:
        raise HTTPException(422, "The file is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "That file is over 10 MB.")
    with db() as conn:
        _thing(conn, thing_kind, thing_id)
        return conn.execute("INSERT INTO attachments (thing_kind, thing_id, kind, name, content_type, data, size) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING attachment_id, kind, name, content_type, size, created_at",
                            (thing_kind, thing_id, kind, name.strip(), ctype, data, len(data))).fetchone()


@router.get("/attachments/{attachment_id}")
def get_attachment(attachment_id: int):
    with db() as conn:
        a = found(conn.execute("SELECT name, content_type, data FROM attachments WHERE attachment_id = %s",
                               (attachment_id,)).fetchone(), "Attachment")
    safe = "".join(ch for ch in a["name"] if ch.isalnum() or ch in " ._-")[:80] or "file"
    return Response(bytes(a["data"]), media_type=a["content_type"],
                    headers={"Content-Disposition": f'inline; filename="{safe}"', "Cache-Control": "private, max-age=86400"})


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM attachments WHERE attachment_id = %s RETURNING 1", (attachment_id,)).fetchone(), "Attachment")
    return Response(status_code=204)


# ---------------------------------------------------------------- bulk
class BulkIn(BaseModel):
    supply_ids: list[int] = Field(min_length=1, max_length=500)
    action: Literal["move", "category", "reserve", "wishlist", "delete"]
    value: int | None = None          # the place, category or model (move / category / reserve; none = clear it)


@router.post("/supplies/bulk")
def bulk(body: BulkIn):
    """Several supplies at once. Answers how many changed."""
    ids = list(dict.fromkeys(body.supply_ids))
    with db() as conn:
        known = [r["supply_id"] for r in conn.execute("SELECT supply_id FROM supplies WHERE supply_id = ANY(%s)", (ids,)).fetchall()]
        if len(known) != len(ids):
            raise HTTPException(422, "Some of those supplies don't exist.")
        if body.action in ("move", "category", "reserve") and body.value is not None:
            table, key = {"move": ("storage_locations", "location_id"), "category": ("categories", "category_id"),
                          "reserve": ("models", "model_id")}[body.action]
            found(conn.execute(f"SELECT 1 FROM {table} WHERE {key} = %s", (body.value,)).fetchone(), "That")
        if body.action == "category" and body.value is None:
            raise HTTPException(422, "Pick a category.")
        stock_reason(conn, "edited" if body.action != "delete" else "deleted")
        if body.action == "move":
            conn.execute("UPDATE supplies SET location_id = %s WHERE supply_id = ANY(%s)", (body.value, ids))
        elif body.action == "category":
            conn.execute("UPDATE supplies SET category_id = %s WHERE supply_id = ANY(%s)", (body.value, ids))
        elif body.action == "reserve":
            conn.execute("UPDATE supplies SET reserved_model_id = %s WHERE supply_id = ANY(%s)", (body.value, ids))
        elif body.action == "wishlist":
            wish_from_supplies(conn, "s.supply_id = ANY(%s)", (ids,), notes="Added from Supplies")
        else:
            conn.execute("UPDATE supplies SET part_of = NULL WHERE part_of = ANY(%s)", (ids,))
            conn.execute("DELETE FROM supplies WHERE supply_id = ANY(%s)", (ids,))
    return {"changed": len(ids)}


# ---------------------------------------------------------------- value report
def _money(v) -> float:
    return float(v or 0)


@router.get("/supplies/value-report")
def value_report():
    """Everything you own, what it cost, per hobby - from each hobby's own records (what you paid; supplies at their
    price each; ammunition: the rounds left at the box's price). Things without a price count as $0 and are listed."""
    with db() as conn:
        sections = []

        def add(hobby, title, rows):
            rows = [dict(r) for r in rows]
            sections.append({"hobby": hobby, "title": title, "items": rows, "count": len(rows),
                             "total": round(sum(_money(r["value"]) for r in rows), 2),
                             "unpriced": sum(1 for r in rows if r["value"] is None)})

        add("models", "Hobby supplies", conn.execute(
            "SELECT s.name, v.category AS detail, s.qty_on_hand AS qty, v.total_value AS value FROM supplies s "
            "JOIN v_supplies v USING (supply_id) WHERE s.qty_on_hand > 0 ORDER BY v.category, s.name").fetchall())
        add("models", "Model kits", conn.execute(
            "SELECT name, status AS detail, 1 AS qty, price_paid AS value FROM models WHERE status <> 'Wanted' ORDER BY name").fetchall())
        add("boardgames", "Board games", conn.execute(
            "SELECT name, NULL AS detail, 1 AS qty, price_paid AS value FROM board_games WHERE status NOT IN ('Wanted', 'Gone') "
            "ORDER BY name").fetchall())
        for hobby in GEAR_HOBBIES:                     # (every hobby that has gear: volleyball, hiking, shooting)
            add(hobby, f"{hobby.capitalize()} gear", conn.execute(
                "SELECT name, concat_ws(' · ', kind, brand) AS detail, 1 AS qty, price_paid AS value FROM gear "
                "WHERE hobby = %s AND condition NOT IN ('Wanted', 'Retired') ORDER BY name", (hobby,)).fetchall())
        add("shooting", "Rifles", conn.execute(
            "SELECT name, concat_ws(' · ', make, model, calibre) AS detail, 1 AS qty, price_paid AS value FROM rifles "
            "WHERE status = 'In use' ORDER BY name").fetchall())
        ammo = [ammo_row(a) for a in conn.execute(AMMO_SELECT + " WHERE a.status = 'Have' ORDER BY a.name").fetchall()]
        add("shooting", "Ammunition", [{"name": a["name"], "detail": " · ".join(x for x in (a["brand"], a["calibre"]) if x),
                                        "qty": max(0, a["rounds_left"]),
                                        "value": round(a["per_round"] * max(0, a["rounds_left"]), 2) if a["per_round"] is not None else None}
                                       for a in ammo])
        add("gardening", "Garden supplies", conn.execute(
            "SELECT name, kind AS detail, COALESCE(qty, 1) AS qty, price * COALESCE(qty, 1) AS value FROM garden_items "
            "WHERE status IN ('Have', 'Running low') ORDER BY kind, name").fetchall())
        now = conn.execute("SELECT current_date AS d").fetchone()["d"]
    sections = [s for s in sections if s["count"]]
    total = round(sum(s["total"] for s in sections), 2)
    return {"on": now, "total": total, "sections": sections, "unpriced": sum(s["unpriced"] for s in sections),
            "money": str(Decimal(str(total)))}
