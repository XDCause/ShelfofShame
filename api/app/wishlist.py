"""Wishlist, Tamiya product lookup, and product photos.

A wishlist item is something you want, not something you own: it lives in its own table and
only becomes a supply when you mark it bought ("move to inventory").
"""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from psycopg import sql
from pydantic import BaseModel, Field

from . import tamiya
from .db import FINISHES, PAINT_TYPES, PRIORITIES, db, stock_reason

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
    purchased_from: str | None = None


# Wishlist rows with names, photo info, and how many you already own of the same item.
WISH_SELECT = """
SELECT w.*, b.name AS brand, c.name AS category,
       p.product_info_id, (p.image IS NOT NULL) AS has_image, p.source_url, p.description,
       p.fetched_at AS photo_updated,
       COALESCE(owned.qty, 0) AS owned_qty
FROM wishlist w
JOIN categories c ON c.category_id = w.category_id
LEFT JOIN brands b ON b.brand_id = w.brand_id
LEFT JOIN product_info p ON p.brand_id = w.brand_id AND p.product_code = w.product_code
LEFT JOIN LATERAL (
    SELECT sum(s.qty_on_hand) AS qty FROM supplies s
    WHERE s.brand_id = w.brand_id AND s.product_code = w.product_code
) owned ON true
"""
WISH_ORDER = """
ORDER BY w.got_it, CASE w.priority WHEN 'High' THEN 0 WHEN 'Normal' THEN 1 ELSE 2 END, w.created_at
"""


def fetch_wish(conn, wish_id):
    row = conn.execute(WISH_SELECT + " WHERE w.wish_id = %s", (wish_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Wishlist item {wish_id} not found.")
    return row


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------
@router.get("/wishlist")
def list_wishlist(show: Literal["all", "needed", "got"] = "all"):
    where = {"all": "", "needed": " WHERE NOT w.got_it", "got": " WHERE w.got_it"}[show]
    with db() as conn:
        return conn.execute(WISH_SELECT + where + WISH_ORDER).fetchall()


@router.post("/wishlist", status_code=201)
def add_wish(body: WishIn):
    data = body.model_dump()
    query = sql.SQL("INSERT INTO wishlist ({cols}) VALUES ({vals}) RETURNING wish_id").format(
        cols=sql.SQL(", ").join(map(sql.Identifier, data)),
        vals=sql.SQL(", ").join(map(sql.Placeholder, data)),
    )
    with db() as conn:
        return fetch_wish(conn, conn.execute(query, data).fetchone()["wish_id"])


@router.patch("/wishlist/{wish_id}")
def update_wish(wish_id: int, body: WishPatch):
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        if data:
            query = sql.SQL("UPDATE wishlist SET {sets} WHERE wish_id = {id}").format(
                sets=sql.SQL(", ").join(
                    sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder(k)) for k in data),
                id=sql.Placeholder("wish_id"),
            )
            conn.execute(query, {**data, "wish_id": wish_id})
        return fetch_wish(conn, wish_id)


@router.delete("/wishlist/{wish_id}", status_code=204)
def delete_wish(wish_id: int):
    with db() as conn:
        if conn.execute("DELETE FROM wishlist WHERE wish_id = %s", (wish_id,)).rowcount == 0:
            raise HTTPException(404, f"Wishlist item {wish_id} not found.")
    return Response(status_code=204)


def move_to_inventory(conn, wish, purchased_from):
    """Turn one wishlist row into stock, then remove it from the wishlist.

    If you already own the same brand + code, its quantity goes up instead of creating a
    duplicate (the UNIQUE rule on supplies would refuse a duplicate anyway).
    """
    stock_reason(conn, "bought (wishlist)")
    existing = None
    if wish["brand_id"] is not None and wish["product_code"]:
        existing = conn.execute(
            "SELECT supply_id FROM supplies WHERE brand_id = %s AND product_code = %s",
            (wish["brand_id"], wish["product_code"])).fetchone()

    if existing:
        supply_id = existing["supply_id"]
        conn.execute("""
            UPDATE supplies SET qty_on_hand = qty_on_hand + %(qty)s, condition = 'Sealed',
                   purchase_date = current_date,
                   purchased_from = COALESCE(%(shop)s, purchased_from),
                   unit_price = COALESCE(%(price)s, unit_price)
            WHERE supply_id = %(id)s""",
            {"qty": wish["qty_wanted"], "shop": purchased_from, "price": wish["est_price"],
             "id": supply_id})
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
            RETURNING supply_id""", {**wish, "shop": purchased_from}).fetchone()["supply_id"]

    conn.execute("DELETE FROM wishlist WHERE wish_id = %s", (wish["wish_id"],))
    supply = conn.execute(
        "SELECT supply_id, item_ref, name, qty_on_hand FROM v_supplies WHERE supply_id = %s",
        (supply_id,)).fetchone()
    return {**supply, "merged": existing is not None}


def clean_shop(body: Buy | None):
    """The shop name, or None if it wasn't given."""
    if body is None or body.purchased_from is None:
        return None
    return body.purchased_from.strip() or None


@router.post("/wishlist/{wish_id}/buy")
def buy_one(wish_id: int, body: Buy | None = None):
    """Bought it: add to inventory and remove from the wishlist."""
    with db() as conn:
        wish = conn.execute("SELECT * FROM wishlist WHERE wish_id = %s", (wish_id,)).fetchone()
        if wish is None:
            raise HTTPException(404, f"Wishlist item {wish_id} not found.")
        return move_to_inventory(conn, wish, clean_shop(body))


# "Is this supply already on the wishlist?" - same brand + code, or same name if it has no code.
ON_WISHLIST = """EXISTS (SELECT 1 FROM wishlist w
                  WHERE (w.brand_id = s.brand_id AND w.product_code = s.product_code)
                     OR (s.product_code IS NULL AND w.name = s.name))"""


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
        wishes = conn.execute("SELECT * FROM wishlist WHERE got_it ORDER BY wish_id").fetchall()
        return [move_to_inventory(conn, w, clean_shop(body)) for w in wishes]


# ---------------------------------------------------------------------------
# Tamiya lookup + photos
# ---------------------------------------------------------------------------
async def tamiya_product(item: str, refresh: bool = False):
    """Make sure product_info has this Tamiya item: from the cache, or fetched once from
    tamiya.com. Returns (brand_id, product_code, from_cache)."""
    product_code = "T" + item if item[0].isdigit() else item  # your convention: T81701

    with db() as conn:
        brand = conn.execute("SELECT brand_id FROM brands WHERE name = 'Tamiya'").fetchone()
        if brand is None:
            raise HTTPException(409, "Add 'Tamiya' to your brands list first.")
        cached = conn.execute(
            "SELECT title FROM product_info WHERE brand_id = %s AND product_code = %s",
            (brand["brand_id"], product_code)).fetchone()

    # A row with no title is just a photo or barcode you added yourself: still worth fetching.
    from_cache = cached is not None and cached["title"] is not None and not refresh
    if not from_cache:
        # Network call outside the database transaction, in a worker thread so the API
        # keeps answering other requests while tamiya.com responds.
        try:
            info = await run_in_threadpool(tamiya.fetch, item)
        except tamiya.NotFound as e:
            raise HTTPException(404, str(e))
        except tamiya.LookupFailed as e:
            raise HTTPException(502, str(e))
        with db() as conn:
            conn.execute("""
                INSERT INTO product_info (brand_id, product_code, title, series, description,
                                          source_url, image, image_type)
                VALUES (%(brand_id)s, %(code)s, %(title)s, %(series)s, %(description)s,
                        %(source_url)s, %(image)s, %(image_type)s)
                ON CONFLICT (brand_id, product_code) DO UPDATE SET
                    title = EXCLUDED.title, series = EXCLUDED.series,
                    description = EXCLUDED.description, source_url = EXCLUDED.source_url,
                    image = COALESCE(EXCLUDED.image, product_info.image),
                    image_type = COALESCE(EXCLUDED.image_type, product_info.image_type),
                    fetched_at = now()""",
                {**info, "brand_id": brand["brand_id"], "code": product_code})
    return brand["brand_id"], product_code, from_cache


def describe_product(conn, brand_id, product_code):
    """Everything the add form needs for one brand + code: photo/description, suggested field
    values, and whether you already own it or have it on the wishlist.

    Suggestions prefer your own details (inventory, then wishlist) over the manufacturer's,
    so a re-scanned item comes back named the way you named it.
    """
    p = conn.execute("""
        SELECT product_info_id, title, series, description, source_url, barcode,
               fetched_at AS photo_updated, (image IS NOT NULL) AS has_image
        FROM product_info WHERE brand_id = %s AND product_code = %s""",
        (brand_id, product_code)).fetchone() or {
        "product_info_id": None, "title": None, "series": None, "description": None,
        "source_url": None, "barcode": None, "photo_updated": None, "has_image": False}

    fields = "name, category_id, paint_type, finish, size"
    yours = (conn.execute(f"SELECT {fields} FROM supplies WHERE brand_id = %s AND product_code = %s",
                          (brand_id, product_code)).fetchone()
             or conn.execute(f"SELECT {fields} FROM wishlist WHERE brand_id = %s AND product_code = %s",
                             (brand_id, product_code)).fetchone())
    if yours:
        suggested = dict(yours)
    elif p["title"]:
        guess = tamiya.suggest(p["title"], p["series"], p["description"])
        category = conn.execute("SELECT category_id FROM categories WHERE name = %s",
                                (guess.pop("category"),)).fetchone()
        suggested = {**guess, "category_id": category["category_id"] if category else None}
    else:
        suggested = {}

    owned_row = conn.execute(
        "SELECT supply_id, qty_on_hand FROM supplies WHERE brand_id = %s AND product_code = %s",
        (brand_id, product_code)).fetchone()
    owned = owned_row["qty_on_hand"] if owned_row else 0
    on_wishlist = conn.execute(
        "SELECT wish_id FROM wishlist WHERE brand_id = %s AND product_code = %s",
        (brand_id, product_code)).fetchone()
    return {
        **p,
        "brand_id": brand_id,
        "product_code": product_code,
        "suggested": suggested,
        "owned_qty": owned,
        "supply_id": owned_row["supply_id"] if owned_row else None,  # your inventory item, if any
        "on_wishlist_id": on_wishlist["wish_id"] if on_wishlist else None,
    }


@router.get("/lookup/tamiya/{code}")
async def lookup_tamiya(code: str, refresh: bool = False):
    """Product details for a Tamiya item number (81701 or T81701) or Mini paint colour code
    (XF-76), for filling in the form.

    Served from the product_info cache when we have it; otherwise fetched once from tamiya.com.
    """
    item = tamiya.item_number(code)
    if item is None:
        raise HTTPException(422, "Enter a Tamiya item number (81776) or paint code (XF-76).")
    brand_id, product_code, from_cache = await tamiya_product(item, refresh)
    with db() as conn:
        result = {**describe_product(conn, brand_id, product_code), "from_cache": from_cache}
    # Typed a colour code? Double-check Tamiya's page is really that colour.
    paint = tamiya.paint_code(code)
    if paint and not tamiya.title_mentions(result["title"], paint):
        result["warning"] = (f"Tamiya's page for item {item} doesn't mention {paint}. "
                             "Check this is the right product.")
    return result


@router.get("/scan/{raw}")
async def scan(raw: str):
    """Identify a product from its barcode number.

    match = "known"   - a barcode you've saved before (any brand): reliable
            "catalog" - found in the imported barcode catalogue (app/catalog_import.py), then
                        details fetched from tamiya.com: reliable
            "tamiya"  - a Tamiya barcode whose digits matched a real item number: a GUESS that
                        works for some products (e.g. cement) - check the photo/name
            "unknown" - not recognised. For Tamiya barcodes brand_id is set to Tamiya, so the
                        form can ask for the item number printed on the label.
    The barcode is only stored when you save the item (PUT /api/product-barcode).
    """
    barcode = tamiya.normalise_barcode(raw)
    if barcode is None:
        raise HTTPException(422, "That isn't a valid barcode number (the check digit doesn't match).")

    with db() as conn:
        known = conn.execute("SELECT brand_id, product_code FROM product_info WHERE barcode = %s",
                             (barcode,)).fetchone()
        if known:
            return {**describe_product(conn, known["brand_id"], known["product_code"]),
                    "barcode": barcode, "match": "known"}
        listed = conn.execute("SELECT product_code FROM barcode_catalog WHERE barcode = %s",
                              (barcode,)).fetchone()
        tamiya_brand = conn.execute("SELECT brand_id FROM brands WHERE name = 'Tamiya'").fetchone()

    if listed and tamiya_brand:
        brand_id, product_code, _ = await tamiya_product(tamiya.item_number(listed["product_code"]))
        with db() as conn:
            return {**describe_product(conn, brand_id, product_code),
                    "barcode": barcode, "match": "catalog"}

    unknown = {"barcode": barcode, "match": "unknown", "suggested": {}, "brand_id": None}
    if not tamiya.is_tamiya_barcode(barcode) or tamiya_brand is None:
        return unknown
    unknown["brand_id"] = tamiya_brand["brand_id"]

    try:
        brand_id, product_code, _ = await tamiya_product(tamiya.guess_item_from_barcode(barcode))
    except HTTPException as e:
        if e.status_code == 404:  # those digits aren't an item number for this product
            return unknown
        raise
    with db() as conn:
        return {**describe_product(conn, brand_id, product_code),
                "barcode": barcode, "match": "tamiya"}


class BarcodeIn(BaseModel):
    brand_id: int
    product_code: str = Field(min_length=1)
    barcode: str


@router.put("/product-barcode")
def set_barcode(body: BarcodeIn):
    """Remember which brand + code a barcode belongs to, so scanning it works next time."""
    barcode = tamiya.normalise_barcode(body.barcode)
    if barcode is None:
        raise HTTPException(422, "That isn't a valid barcode number.")
    with db() as conn:
        conn.execute("""
            INSERT INTO product_info (brand_id, product_code, barcode) VALUES (%s, %s, %s)
            ON CONFLICT (brand_id, product_code) DO UPDATE SET barcode = EXCLUDED.barcode""",
            (body.brand_id, body.product_code.strip(), barcode))
        return describe_product(conn, body.brand_id, body.product_code.strip())


PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def save_photo(brand_id, product_code, image, image_type):
    with db() as conn:
        return conn.execute("""
            INSERT INTO product_info (brand_id, product_code, image, image_type)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (brand_id, product_code) DO UPDATE SET
                image = EXCLUDED.image, image_type = EXCLUDED.image_type, fetched_at = now()
            RETURNING product_info_id""", (brand_id, product_code, image, image_type)).fetchone()


@router.put("/product-photo")
async def upload_photo(request: Request, brand_id: int, product_code: str):
    """Your own photo for any brand + product code (phone camera, saved image, ...).

    Send the image itself as the request body with its Content-Type, e.g. image/jpeg.
    Replaces any existing photo for that item, including one fetched from tamiya.com.
    """
    image_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if image_type not in PHOTO_TYPES:
        raise HTTPException(415, "Photos must be JPEG, PNG, WebP or GIF.")
    image = await request.body()
    if not image:
        raise HTTPException(422, "No photo was sent.")
    if len(image) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "That photo is over 5 MB.")
    code = product_code.strip()
    if not code:
        raise HTTPException(422, "The item needs a product code to attach a photo to.")
    # Database work is blocking, so run it in a worker thread from this async endpoint.
    return await run_in_threadpool(save_photo, brand_id, code, image, image_type)


@router.delete("/product-photo", status_code=204)
def delete_photo(brand_id: int, product_code: str):
    with db() as conn:
        conn.execute("UPDATE product_info SET image = NULL, image_type = NULL "
                     "WHERE brand_id = %s AND product_code = %s", (brand_id, product_code.strip()))
    return Response(status_code=204)


@router.get("/product-images/{product_info_id}")
def product_image(product_info_id: int):
    with db() as conn:
        row = conn.execute("SELECT image, image_type FROM product_info WHERE product_info_id = %s",
                           (product_info_id,)).fetchone()
    if row is None or row["image"] is None:
        raise HTTPException(404, "No photo for that product.")
    # Photos never change once fetched, so let the browser keep them for a day.
    return Response(content=bytes(row["image"]), media_type=row["image_type"] or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})
