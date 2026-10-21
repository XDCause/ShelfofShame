"""More for the wishlist (2026-10-21; from a look at GiftList, Swym, Keepa / CamelCamelCamel, Qapital).

What you want lives in five places - kind 'wish' (the supplies wishlist), 'model', 'game', 'gear', 'garden' (rows marked
Wanted) - so everything here is keyed by (kind, ref) (89_wishlist_more.sql):

    extras    GET /wanted/extras: per item - its hobby, how long it's been on the list, what it's for (a build / a goal),
              a target price and whether the last price is under it, money saved for it, in stock or not
    for       PUT /wanted/{kind}/{ref}: what it's for, target price, its link
    save      POST /wanted/{kind}/{ref}/save: put money aside for it (or take some back)
    prices    POST / GET /wanted/{kind}/{ref}/prices: a price you saw; the history
    check     POST /wanted/{kind}/{ref}/check: ask its shop now (Blue Sky gear; Good Games board games)
    got       POST /wanted/{kind}/{ref}/got: bought - it becomes yours (In stash / Owned / Good / Have, or the supplies
              wishlist's move to inventory) and goes in the history; /ungot undoes that (not for supplies)
    history   GET /wanted/history: what you've bought from the list
    link      POST /wanted/from-link (read a product page: linkpeek.py) and /wanted/from-link/save (add it as wanted)

The weekly site check also refreshes wanted Blue Sky gear's price and stock (refresh_weekly). Good Games is paused there
(the user's call: a small shop), so a board game is only checked when you ask.
"""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import bluesky, goodgames, linkpeek
from .db import GEAR_HOBBIES, db, found, insert_row
from .ucp import ShopError

router = APIRouter(prefix="/api", tags=["wishlist"])

Kind = Literal["wish", "model", "game", "gear", "garden"]
# kind -> (table, id column, "wanted" test, owned change, its hobby (SQL), created column, price column)
TABLES = {
    "wish": ("wishlist", "wish_id", "NOT got_it", None, "'models'", "created_at", "est_price"),
    "model": ("models", "model_id", "status = 'Wanted'", "status = 'In stash'", "'models'", "created_at", "price_paid"),
    "game": ("board_games", "game_id", "status = 'Wanted'", "status = 'Owned'", "'boardgames'", "created_at", "shop_price"),
    "gear": ("gear", "gear_id", "condition = 'Wanted'", "condition = 'New'", "hobby", "created_at", "shop_price"),
    "garden": ("garden_items", "item_id", "status = 'Wanted'", "status = 'Have'", "'gardening'", "created_at", "price"),
}
WANTED_BACK = {"model": "status = 'Wanted'", "game": "status = 'Wanted'", "gear": "condition = 'Wanted'", "garden": "status = 'Wanted'"}


def _row(conn, kind: str, ref: int) -> dict:
    table, key, *_ = TABLES[kind]
    return found(conn.execute(f"SELECT * FROM {table} WHERE {key} = %s", (ref,)).fetchone(), "That wanted thing")


def _ensure(conn, kind: str, ref: int):
    conn.execute("INSERT INTO wanted_extras (kind, ref) VALUES (%s, %s) ON CONFLICT DO NOTHING", (kind, ref))


def record_price(conn, kind: str, ref: int, price, source: str):
    """A price seen - kept unless it's the same as the last one from the same source today."""
    if price is None:
        return
    last = conn.execute("SELECT price, source, seen_at::date = current_date AS today FROM wanted_prices "
                        "WHERE kind = %s AND ref = %s ORDER BY seen_at DESC, price_id DESC LIMIT 1", (kind, ref)).fetchone()   # (Brisbane's today)
    if last and Decimal(str(last["price"])) == Decimal(str(price)).quantize(Decimal("0.01")) and last["source"] == source \
            and last["today"]:
        return
    conn.execute("INSERT INTO wanted_prices (kind, ref, price, source) VALUES (%s, %s, %s, %s)", (kind, ref, price, source))


# ---------------------------------------------------------------- extras
@router.get("/wanted/extras")
def extras():
    """Everything extra about every wanted thing, keyed "kind:ref"."""
    out = {}
    with db() as conn:
        for kind, (table, key, wanted, _, hobby, created, price_col) in TABLES.items():
            rows = conn.execute(f"""
                SELECT t.{key} AS ref, {hobby} AS hobby, t.{created}::date AS added, current_date - t.{created}::date AS days,
                       t.{price_col}::float8 AS price, e.for_model_id, e.for_goal_id, e.target_price::float8 AS target_price,
                       e.saved::float8 AS saved, e.in_stock, e.stock_checked, e.link,
                       (SELECT name FROM models m WHERE m.model_id = e.for_model_id) AS for_model,
                       (SELECT title FROM goals g WHERE g.goal_id = e.for_goal_id) AS for_goal,
                       lp.price::float8 AS last_price, lp.source AS last_source, lp.seen_at AS last_seen,
                       (SELECT min(price)::float8 FROM wanted_prices p WHERE p.kind = %(k)s AND p.ref = t.{key}) AS lowest_price,
                       (SELECT count(*) FROM wanted_prices p WHERE p.kind = %(k)s AND p.ref = t.{key})::int AS prices
                FROM {table} t
                LEFT JOIN wanted_extras e ON e.kind = %(k)s AND e.ref = t.{key}
                LEFT JOIN LATERAL (SELECT price, source, seen_at FROM wanted_prices p WHERE p.kind = %(k)s AND p.ref = t.{key}
                                   ORDER BY seen_at DESC, price_id DESC LIMIT 1) lp ON true
                WHERE {wanted}""", {"k": kind}).fetchall()   # (its own columns: got_it, status, condition)
            for r in rows:
                now = r["last_price"] if r["last_price"] is not None else r["price"]
                r["below_target"] = r["target_price"] is not None and now is not None and now <= r["target_price"]
                cost = r["target_price"] or now
                r["save_for"] = cost
                out[f"{kind}:{r['ref']}"] = {**r, "kind": kind}
    return out


class ExtrasIn(BaseModel):
    for_model_id: int | None = None
    for_goal_id: int | None = None
    target_price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    link: str | None = Field(None, max_length=2000, pattern=r"^https?://")


@router.put("/wanted/{kind}/{ref}")
def set_extras(kind: Kind, ref: int, body: ExtrasIn):
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        _row(conn, kind, ref)
        if data.get("for_model_id") is not None:
            found(conn.execute("SELECT 1 FROM models WHERE model_id = %s", (data["for_model_id"],)).fetchone(), "Model")
        if data.get("for_goal_id") is not None:
            found(conn.execute("SELECT 1 FROM goals WHERE goal_id = %s", (data["for_goal_id"],)).fetchone(), "Goal")
        _ensure(conn, kind, ref)
        for col, value in data.items():
            conn.execute(f"UPDATE wanted_extras SET {col} = %s WHERE kind = %s AND ref = %s", (value, kind, ref))
    return extras().get(f"{kind}:{ref}")


class SaveIn(BaseModel):
    amount: Decimal = Field(ge=-100000, le=100000, max_digits=10, decimal_places=2)


@router.post("/wanted/{kind}/{ref}/save")
def save_for(kind: Kind, ref: int, body: SaveIn):
    """Money put aside for it (a negative amount takes some back; never below $0)."""
    with db() as conn:
        _row(conn, kind, ref)
        _ensure(conn, kind, ref)
        conn.execute("UPDATE wanted_extras SET saved = greatest(0, saved + %s) WHERE kind = %s AND ref = %s", (body.amount, kind, ref))
    return extras().get(f"{kind}:{ref}")


class PriceIn(BaseModel):
    price: Decimal = Field(ge=0, le=1000000, max_digits=10, decimal_places=2)
    source: str = Field("you", min_length=1, max_length=60)


@router.post("/wanted/{kind}/{ref}/prices", status_code=201)
def add_price(kind: Kind, ref: int, body: PriceIn):
    with db() as conn:
        _row(conn, kind, ref)
        conn.execute("INSERT INTO wanted_prices (kind, ref, price, source) VALUES (%s, %s, %s, %s)",
                     (kind, ref, body.price, body.source.strip()))
    return extras().get(f"{kind}:{ref}")


@router.get("/wanted/{kind}/{ref}/prices")
def prices(kind: Kind, ref: int):
    with db() as conn:
        _row(conn, kind, ref)
        return conn.execute("SELECT price::float8 AS price, source, seen_at FROM wanted_prices WHERE kind = %s AND ref = %s "
                            "ORDER BY seen_at, price_id", (kind, ref)).fetchall()   # (the same moment: the order they came)


# ---------------------------------------------------------------- asking the shop
def _check(conn, kind: str, row: dict) -> dict | None:
    """The shop's price and stock for one wanted thing, or None if it isn't from a shop the app can ask."""
    if kind == "gear" and row.get("shop_id") and (row.get("shop_name") or "").startswith("Blue Sky"):
        p = bluesky.get(row["shop_id"])
        return p and {"price": p["price"], "available": p["available"], "source": "Blue Sky Athletics"}
    if kind == "game" and row.get("shop_handle"):
        for p in goodgames.board_games(row["name"], limit=8):
            if p.get("handle") == row["shop_handle"]:
                return {"price": p["price"], "available": p["available"], "source": "Good Games"}
        return {"price": None, "available": False, "source": "Good Games"}       # not listed: not in stock
    return None


@router.post("/wanted/{kind}/{ref}/check")
def check_now(kind: Kind, ref: int):
    """Ask its shop now: the price (kept in its history) and whether it's in stock."""
    with db() as conn:
        row = _row(conn, kind, ref)
    try:
        got = _check(None, kind, row)
    except ShopError as e:
        raise HTTPException(502, str(e)) from None
    if got is None:
        raise HTTPException(409, "The app can't ask this one's shop (add a price you saw instead).")
    with db() as conn:
        _ensure(conn, kind, ref)
        conn.execute("UPDATE wanted_extras SET in_stock = %s, stock_checked = now() WHERE kind = %s AND ref = %s",
                     (got["available"], kind, ref))
        record_price(conn, kind, ref, got["price"], got["source"])
    return extras().get(f"{kind}:{ref}")


def refresh_weekly() -> int:
    """Wanted Blue Sky gear: its price and stock, once a week (with the site check). Good Games is paused there, so its
    board games wait to be asked. Answers how many were checked."""
    with db() as conn:
        rows = conn.execute("SELECT * FROM gear WHERE condition = 'Wanted' AND shop_id IS NOT NULL AND shop_name LIKE 'Blue Sky%%'").fetchall()
    done = 0
    for row in rows:
        try:
            got = _check(None, "gear", row)
        except ShopError:
            continue
        if got:
            with db() as conn:
                _ensure(conn, "gear", row["gear_id"])
                conn.execute("UPDATE wanted_extras SET in_stock = %s, stock_checked = now() WHERE kind = 'gear' AND ref = %s",
                             (got["available"], row["gear_id"]))
                record_price(conn, "gear", row["gear_id"], got["price"], "weekly check")
            done += 1
    return done


# ---------------------------------------------------------------- bought
class GotIn(BaseModel):
    paid: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    shop: str | None = Field(None, max_length=120)


def remember(conn, kind: str, ref, name: str, hobby: str | None, shop: str | None, expected, paid, wanted_on):
    conn.execute("INSERT INTO wanted_history (kind, ref, name, hobby, shop, expected, paid, wanted_on) "
                 "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (kind, ref, name, hobby, shop, expected, paid, wanted_on))


@router.post("/wanted/{kind}/{ref}/got")
def got(kind: Kind, ref: int, body: GotIn | None = None):
    """Bought: it's yours now (a kit In stash, a game Owned, gear New, a garden thing Have; a supply moves to your
    supplies), bought today at the price you paid (else the one you expected), and it's in the history."""
    body = body or GotIn()
    table, key, wanted, owned, hobby_sql, created, price_col = TABLES[kind]
    with db() as conn:
        row = _row(conn, kind, ref)
        if not conn.execute(f"SELECT 1 FROM {table} WHERE {key} = %s AND {wanted}", (ref,)).fetchone():
            raise HTTPException(409, "That isn't on your wishlist any more.")
        hobby = conn.execute(f"SELECT {hobby_sql} AS h FROM {table} WHERE {key} = %s", (ref,)).fetchone()["h"]
        expected = row.get(price_col)
        paid = body.paid if body.paid is not None else expected
        shop = (body.shop or "").strip() or None
        if kind == "wish":
            from .wishlist import move_to_inventory
            from .settings import get_setting
            shop = shop or get_setting(conn, "default_shop")
            move_to_inventory(conn, {**row, "est_price": paid if paid is not None else row["est_price"]}, shop)   # (it remembers it)
        else:
            extra = {"model": ", purchase_date = current_date, price_paid = COALESCE(%(paid)s, price_paid), "
                              "purchased_from = COALESCE(%(shop)s, purchased_from)",
                     "game": ", purchase_date = current_date, price_paid = COALESCE(%(paid)s, price_paid)",
                     "gear": ", purchase_date = current_date, price_paid = COALESCE(%(paid)s, price_paid)",
                     "garden": ""}[kind]
            conn.execute(f"UPDATE {table} SET {owned}{extra} WHERE {key} = %(ref)s", {"paid": paid, "shop": shop, "ref": ref})
            remember(conn, kind, ref, row["name"], hobby, shop, expected, paid, row[created])
        conn.execute("DELETE FROM wanted_extras WHERE kind = %s AND ref = %s", (kind, ref))
    return {"kind": kind, "ref": ref, "name": row["name"], "paid": paid}


@router.post("/wanted/{kind}/{ref}/ungot")
def ungot(kind: Literal["model", "game", "gear", "garden"], ref: int):
    """Undo "bought" (a mistaken tick): wanted again, out of the history."""
    table, key, *_ = TABLES[kind]
    with db() as conn:
        _row(conn, kind, ref)
        conn.execute(f"UPDATE {table} SET {WANTED_BACK[kind]} WHERE {key} = %s", (ref,))
        conn.execute("DELETE FROM wanted_history WHERE history_id = (SELECT max(history_id) FROM wanted_history "
                     "WHERE kind = %s AND ref = %s)", (kind, ref))
    return Response(status_code=204)


@router.get("/wanted/history")
def history(limit: int = Query(200, ge=1, le=1000)):
    """What you've bought from your wishlist, newest first, with what you expected and paid."""
    with db() as conn:
        return conn.execute("SELECT history_id, kind, ref, name, hobby, shop, expected::float8 AS expected, paid::float8 AS paid, "
                            "wanted_on, bought_on, bought_on - wanted_on AS waited FROM wanted_history "
                            "ORDER BY bought_on DESC, history_id DESC LIMIT %s", (limit,)).fetchall()


# ---------------------------------------------------------------- from a link
class LinkIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000, pattern=r"^https?://")


@router.post("/wanted/from-link")
def from_link(body: LinkIn):
    """Read the product page you pasted: its name, price and picture (nothing is saved yet)."""
    try:
        return linkpeek.peek(body.url)
    except linkpeek.LinkError as e:
        raise HTTPException(422, str(e)) from None


class LinkSave(BaseModel):
    url: str = Field(min_length=8, max_length=2000, pattern=r"^https?://")
    kind: Literal["wish", "model", "game", "gear", "garden"]
    name: str = Field(min_length=1, max_length=200)
    price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    hobby: Literal[tuple(GEAR_HOBBIES)] | None = None       # gear's hobby
    category_id: int | None = None                         # a supply's category
    site: str | None = Field(None, max_length=120)


@router.post("/wanted/from-link/save", status_code=201)
def save_link(body: LinkSave):
    """Add what the link showed as something you want - a supply, a kit, a board game, gear or a garden thing - with
    its price (in its price history) and its link. Answers {kind, ref} (the picture is added by the page after)."""
    name, site = body.name.strip(), (body.site or "").strip() or None
    with db() as conn:
        if body.kind == "wish":
            if body.category_id is None:
                raise HTTPException(422, "Pick the supply's category.")
            found(conn.execute("SELECT 1 FROM categories WHERE category_id = %s", (body.category_id,)).fetchone(), "Category")
            ref = insert_row(conn, "wishlist", {"name": name, "category_id": body.category_id, "est_price": body.price,
                                                "notes": f"From {site or 'a link'}"}, "wish_id")
        elif body.kind == "model":
            ref = insert_row(conn, "models", {"name": name, "status": "Wanted", "price_paid": body.price, "purchased_from": site}, "model_id")
        elif body.kind == "game":
            ref = insert_row(conn, "board_games", {"name": name, "status": "Wanted", "shop_price": body.price, "shop_url": body.url,
                                                   "shop_name": site}, "game_id")
        elif body.kind == "gear":
            ref = insert_row(conn, "gear", {"name": name, "hobby": body.hobby or "volleyball", "condition": "Wanted",
                                            "shop_price": body.price, "shop_url": body.url, "shop_name": site}, "gear_id")
        else:
            ref = insert_row(conn, "garden_items", {"name": name, "status": "Wanted", "price": body.price, "url": body.url
                                                    if body.url.startswith("https://") else None}, "item_id")
        _ensure(conn, body.kind, ref)
        conn.execute("UPDATE wanted_extras SET link = %s WHERE kind = %s AND ref = %s", (body.url, body.kind, ref))
        record_price(conn, body.kind, ref, body.price, site or "the link")
    return {"kind": body.kind, "ref": ref}
