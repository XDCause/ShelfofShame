"""Shop Tamiya: search the imported catalogue (app/tamiya_catalog.py) and add to the wishlist."""
import logging
import re

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from . import tamiya
from .db import db
from .wishlist import fetch_wish, tamiya_product

log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def search_terms(q: str) -> list[str]:
    """Words to match. 'XF-76', 'xf76' and '81776' all find XF-76; hyphens are ignored."""
    words = []
    for w in re.findall(r"[A-Za-z0-9\-]+", q):
        item = tamiya.item_number(w) if tamiya.paint_code(w) else None
        words.append(item or w.replace("-", "").upper())
    return [w for w in words if w]


@router.get("/search")
def search(q: str = Query("", max_length=100), limit: int = Query(40, ge=1, le=100)):
    """Products whose name (or number) contains every word typed, with what you already have:
    owned_qty / owned_condition / owned_status and on_wishlist."""
    terms = search_terms(q)
    if not terms:
        return []
    # Each word must appear in the name (hyphens ignored) or be the item number.
    where = " AND ".join(
        "(replace(upper(c.title), '-', '') LIKE %s OR c.item = %s)" for _ in terms)
    params = [x for t in terms for x in (f"%{t}%", t)]
    with db() as conn:
        rows = conn.execute(f"""
            SELECT c.product_code, c.item, c.title, c.genre, c.thumb_url, c.source_url, c.brand_id,
                   COALESCE(v.qty_on_hand, 0) AS owned_qty, v.supply_id AS owned_supply_id,
                   v.condition AS owned_condition, v.stock_status AS owned_status,
                   EXISTS (SELECT 1 FROM wishlist w WHERE w.brand_id = c.brand_id
                           AND w.product_code = c.product_code) AS on_wishlist
            FROM catalog_products c
            LEFT JOIN supplies s ON s.brand_id = c.brand_id AND s.product_code = c.product_code
            LEFT JOIN v_supplies v ON v.supply_id = s.supply_id
            WHERE {where}
            ORDER BY (v.supply_id IS NULL), c.genre, c.title
            LIMIT %s""", (*params, limit)).fetchall()
    return [{**r, "name": tamiya.your_style_name(r["title"])} for r in rows]


@router.get("/info")
def info():
    """How big the catalogue is and when it was last imported."""
    with db() as conn:
        return conn.execute("SELECT count(*) AS products, max(imported_at) AS imported_at "
                            "FROM catalog_products").fetchone()


@router.post("/{product_code}/wishlist", status_code=201)
async def add_to_wishlist(product_code: str, background: BackgroundTasks):
    """One tap from a search result: add it to the wishlist straight away with your naming
    style, category, paint type and finish guessed from the catalogue title. The product page
    and photo are fetched from tamiya.com afterwards, in the background (that can take from a
    second to most of a minute), and fill in the size and photo when they arrive."""
    with db() as conn:
        row = conn.execute("SELECT brand_id, item, title, genre FROM catalog_products WHERE product_code = %s",
                           (product_code,)).fetchone()
        if row is None:
            raise HTTPException(404, f"{product_code} isn't in the catalogue.")
        info = conn.execute("SELECT title, series, description FROM product_info "
                            "WHERE brand_id = %s AND product_code = %s AND title IS NOT NULL",
                            (row["brand_id"], product_code)).fetchone()
        guess = (tamiya.suggest(info["title"], info["series"], info["description"], row["item"]) if info
                 else tamiya.suggest(row["title"], row["genre"], None, row["item"]))
        wish = conn.execute("""
            INSERT INTO wishlist (brand_id, product_code, name, category_id, paint_type, finish, size,
                                  est_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (brand_id, product_code) DO NOTHING
            RETURNING wish_id""",
            (row["brand_id"], product_code, guess["name"], category_id(conn, guess["category"]),
             guess["paint_type"], guess["finish"], guess["size"], guess["est_price"])).fetchone()
        if wish is None:
            raise HTTPException(409, "It's already on your wishlist.")
        result = fetch_wish(conn, wish["wish_id"])
    if info is None:
        background.add_task(fill_in_from_tamiya, row["item"], wish["wish_id"])
    return result


def category_id(conn, name):
    found = conn.execute("SELECT category_id FROM categories WHERE name = %s", (name or "Other",)).fetchone()         or conn.execute("SELECT category_id FROM categories WHERE name = 'Other'").fetchone()
    return found["category_id"]


async def fill_in_from_tamiya(item: str, wish_id: int):
    """Runs after the reply has gone: fetch the product page + photo (cached in product_info),
    then fill in whatever the title alone couldn't tell us. Never overwrites what's there."""
    try:
        brand_id, code, _ = await tamiya_product(item)
    except HTTPException as e:  # tamiya.com slow or down: the wishlist item is fine without it
        log.warning("Background fetch of Tamiya %s failed: %s", item, e.detail)
        return
    with db() as conn:
        info = conn.execute("SELECT title, series, description FROM product_info "
                            "WHERE brand_id = %s AND product_code = %s", (brand_id, code)).fetchone()
        guess = tamiya.suggest(info["title"], info["series"], info["description"], item)
        conn.execute("""
            UPDATE wishlist SET size = COALESCE(size, %s), paint_type = COALESCE(paint_type, %s),
                                finish = COALESCE(finish, %s), est_price = COALESCE(est_price, %s),
                                category_id = CASE WHEN category_id = %s THEN %s ELSE category_id END
            WHERE wish_id = %s""",
            (guess["size"], guess["paint_type"], guess["finish"], guess["est_price"],
             category_id(conn, "Other"), category_id(conn, guess["category"]), wish_id))
