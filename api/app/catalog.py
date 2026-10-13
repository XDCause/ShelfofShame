"""Shop Tamiya: search the imported catalogue (app/tamiya_catalog.py), add to the wishlist, and
refresh the catalogue from Settings."""
import logging
import re
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from . import tamiya, tamiya_catalog
from .db import db, found, update_row
from .products import tamiya_product
from .settings import price_for
from .wishlist import fetch_wish

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
    where = " AND ".join("(replace(upper(c.title), '-', '') LIKE %s OR c.item = %s)" for _ in terms)
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


# ---------------------------------------------------------------------------
# Refreshing the catalogue (from Settings): ~3 minutes, in the background
# ---------------------------------------------------------------------------
REFRESH = {"running": False, "message": None, "started_at": None, "finished_at": None, "error": None}
_refresh_lock = threading.Lock()


def _refresh():
    try:
        count = tamiya_catalog.run(progress=lambda m: REFRESH.update(message=m))
        REFRESH.update(message=f"Done: {count} products")
    except Exception as e:  # shown in Settings; the old catalogue stays as it was
        log.exception("Tamiya catalogue refresh failed")
        REFRESH.update(error=f"{e.__class__.__name__}: {e}")
    finally:
        REFRESH.update(running=False, finished_at=datetime.now().astimezone().isoformat())


@router.get("/info")
def info():
    """How big the catalogue is, when it was last imported, and how a refresh is going."""
    with db() as conn:
        row = conn.execute("SELECT count(*) AS products, max(imported_at) AS imported_at "
                           "FROM catalog_products").fetchone()
    return {**row, "refresh": REFRESH}


@router.post("/refresh", status_code=202)
def refresh(background: BackgroundTasks):
    """Re-read Tamiya's product lists for new releases (2 s between pages, about 3 minutes)."""
    with _refresh_lock:
        if REFRESH["running"]:
            raise HTTPException(409, "The catalogue is already being refreshed.")
        REFRESH.update(running=True, message="Starting...", error=None, finished_at=None,
                       started_at=datetime.now().astimezone().isoformat())
    background.add_task(_refresh)
    return REFRESH


# ---------------------------------------------------------------------------
# One tap: catalogue -> wishlist
# ---------------------------------------------------------------------------
@router.post("/{product_code}/wishlist", status_code=201)
async def add_to_wishlist(product_code: str, background: BackgroundTasks):
    """One tap from a search result: add it to the wishlist straight away with your naming
    style, category, paint type, finish, size and usual price guessed from the catalogue title.
    The product page and photo are fetched from tamiya.com afterwards, in the background (that
    can take from a second to most of a minute), and fill in whatever is still empty."""
    with db() as conn:
        row = found(conn.execute("SELECT brand_id, item, title, genre FROM catalog_products "
                                 "WHERE product_code = %s", (product_code,)).fetchone(),
                    f"{product_code} in the catalogue")
        info = conn.execute("SELECT title, series, description FROM product_info "
                            "WHERE brand_id = %s AND product_code = %s AND title IS NOT NULL",
                            (row["brand_id"], product_code)).fetchone()
        source = info or {"title": row["title"], "series": row["genre"], "description": None}
        guess = tamiya.suggest(source["title"], source["series"], source["description"], row["item"])
        wish = conn.execute("""
            INSERT INTO wishlist (brand_id, product_code, name, category_id, paint_type, finish, size, est_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (brand_id, product_code) DO NOTHING
            RETURNING wish_id""",
            (row["brand_id"], product_code, guess["name"], category_id(conn, guess["category"]),
             guess["paint_type"], guess["finish"], guess["size"], price_for(conn, source["title"], guess))).fetchone()
        if wish is None:
            raise HTTPException(409, "It's already on your wishlist.")
        result = fetch_wish(conn, wish["wish_id"])
    if info is None:
        background.add_task(fill_in_from_tamiya, row["item"], wish["wish_id"])
    return result


def category_id(conn, name):
    row = conn.execute("SELECT category_id FROM categories WHERE name = %s", (name or "Other",)).fetchone() \
        or conn.execute("SELECT category_id FROM categories WHERE name = 'Other'").fetchone()
    return row["category_id"]


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
        wish = conn.execute("SELECT * FROM wishlist WHERE wish_id = %s", (wish_id,)).fetchone()
        if wish is None:  # removed in the meantime
            return
        fills = {k: guess[k] for k in ("size", "paint_type", "finish") if wish[k] is None and guess[k]}
        if wish["est_price"] is None and (price := price_for(conn, info["title"], guess)) is not None:
            fills["est_price"] = price
        if wish["category_id"] == category_id(conn, "Other") and guess["category"]:
            fills["category_id"] = category_id(conn, guess["category"])
        update_row(conn, "wishlist", "wish_id", wish_id, fills)
