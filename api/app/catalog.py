"""Shop Tamiya: search the imported catalogue (app/tamiya_catalog.py) and add to the wishlist."""
import re

from fastapi import APIRouter, HTTPException, Query

from . import tamiya
from .db import db
from .wishlist import fetch_wish, tamiya_product

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
async def add_to_wishlist(product_code: str):
    """One tap from a search result: fetch the product's details + photo (once, cached), then
    add it to the wishlist with your naming style, category, paint type, finish and size."""
    with db() as conn:
        row = conn.execute("SELECT item FROM catalog_products WHERE product_code = %s",
                           (product_code,)).fetchone()
    if row is None:
        raise HTTPException(404, f"{product_code} isn't in the catalogue.")

    brand_id, code, _ = await tamiya_product(row["item"])  # tamiya.com, only the first time
    with db() as conn:
        info = conn.execute("SELECT title, series, description FROM product_info "
                            "WHERE brand_id = %s AND product_code = %s", (brand_id, code)).fetchone()
        guess = tamiya.suggest(info["title"], info["series"], info["description"])
        category = conn.execute(
            "SELECT category_id FROM categories WHERE name = %s", (guess["category"] or "Other",)).fetchone() \
            or conn.execute("SELECT category_id FROM categories WHERE name = 'Other'").fetchone()
        wish = conn.execute("""
            INSERT INTO wishlist (brand_id, product_code, name, category_id, paint_type, finish, size)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (brand_id, product_code) DO NOTHING
            RETURNING wish_id""",
            (brand_id, code, guess["name"], category["category_id"], guess["paint_type"],
             guess["finish"], guess["size"])).fetchone()
        if wish is None:
            raise HTTPException(409, "It's already on your wishlist.")
        return fetch_wish(conn, wish["wish_id"])
