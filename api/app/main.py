"""Shelf of Shame API - the only thing that talks to PostgreSQL.

Interactive docs: http://localhost:8000/api/docs
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from psycopg import sql
from pydantic import BaseModel, Field

from . import wishlist
from .db import CONDITIONS, FINISHES, PAINT_TYPES, PRIORITIES, db, stock_reason

app = FastAPI(
    title="Shelf of Shame API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.include_router(wishlist.router)  # wishlist, Tamiya lookup and product photos

PaintType = Literal[tuple(PAINT_TYPES)]
Finish = Literal[tuple(FINISHES)]
Condition = Literal[tuple(CONDITIONS)]

# Lookup lists the front end can add to / remove from: URL name -> (table, id column)
LOOKUPS = {
    "brands": ("brands", "brand_id"),
    "categories": ("categories", "category_id"),
    "locations": ("storage_locations", "location_id"),
}

# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
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


class Adjust(BaseModel):
    """Change quantity by a relative amount, e.g. -1 = used one, +3 = bought three.
    Adding stock also sets the last-purchased date to today."""
    delta: int = Field(description="Amount to add (negative to remove)")


class LookupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Supplies
# ---------------------------------------------------------------------------
# The raw table gives the ids (needed for editing); the view adds names and calculated columns;
# product_info (matched on brand + code) adds the cached manufacturer photo and description.
SUPPLY_SELECT = """
SELECT s.*, v.item_ref, v.brand, v.category, v.location, v.stock_status, v.total_value,
       p.product_info_id, (p.image IS NOT NULL) AS has_image, p.description AS product_description,
       p.source_url, p.fetched_at AS photo_updated,
       COALESCE(p.barcode, (SELECT c.barcode FROM barcode_catalog c
                            WHERE c.brand_id = s.brand_id AND c.product_code = s.product_code
                            LIMIT 1)) AS barcode
FROM supplies s
JOIN v_supplies v USING (supply_id)
LEFT JOIN product_info p ON p.brand_id = s.brand_id AND p.product_code = s.product_code
"""


def fetch_supply(conn, supply_id):
    row = conn.execute(SUPPLY_SELECT + " WHERE supply_id = %s", (supply_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Supply {supply_id} not found.")
    return row


@app.get("/api/health")
def health():
    with db() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/supplies")
def list_supplies(q: str | None = None, category: str | None = None, brand: str | None = None,
                  status: Literal["OK", "Low", "Out"] | None = None,
                  location: str | None = None):
    """Search and filter. `q` matches name, code, brand, category and notes."""
    where, params = [], {}
    if q:
        # Escape LIKE wildcards so searching for "50%" or "_" means the literal characters
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["q"] = f"%{term}%"
        where.append("(s.name ILIKE %(q)s OR s.product_code ILIKE %(q)s OR v.brand ILIKE %(q)s"
                     " OR v.category ILIKE %(q)s OR s.notes ILIKE %(q)s)")
    for column, value in (("v.category", category), ("v.brand", brand),
                          ("v.stock_status", status), ("v.location", location)):
        if value:
            key = column.split(".")[1]
            params[key] = value
            where.append(f"{column} = %({key})s")
    query = SUPPLY_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY supply_id"
    with db() as conn:
        return conn.execute(query, params).fetchall()


# Declared before /api/supplies/{supply_id} so "low-stock" isn't mistaken for an id.
@app.get("/api/supplies/low-stock")
def low_stock():
    """Everything that is Out or Low - i.e. the shopping list."""
    with db() as conn:
        return conn.execute(SUPPLY_SELECT + " WHERE v.stock_status <> 'OK' ORDER BY v.stock_status,"
                            " v.brand, s.name").fetchall()


@app.get("/api/supplies/{supply_id}")
def get_supply(supply_id: int):
    with db() as conn:
        return fetch_supply(conn, supply_id)


@app.post("/api/supplies", status_code=201)
def create_supply(body: SupplyIn):
    data = body.model_dump()
    query = sql.SQL("INSERT INTO supplies ({cols}) VALUES ({vals}) RETURNING supply_id").format(
        cols=sql.SQL(", ").join(map(sql.Identifier, data)),
        vals=sql.SQL(", ").join(map(sql.Placeholder, data)),
    )
    with db() as conn:
        stock_reason(conn, "added")
        supply_id = conn.execute(query, data).fetchone()["supply_id"]
        return fetch_supply(conn, supply_id)


@app.patch("/api/supplies/{supply_id}")
def update_supply(supply_id: int, body: SupplyPatch):
    data = body.model_dump(exclude_unset=True)  # only fields the client actually sent
    with db() as conn:
        if data:
            stock_reason(conn, "edited")
            query = sql.SQL("UPDATE supplies SET {sets} WHERE supply_id = {id}").format(
                sets=sql.SQL(", ").join(
                    sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder(k)) for k in data),
                id=sql.Placeholder("supply_id"),
            )
            conn.execute(query, {**data, "supply_id": supply_id})
        return fetch_supply(conn, supply_id)


@app.post("/api/supplies/{supply_id}/adjust")
def adjust_quantity(supply_id: int, body: Adjust):
    """Relative change done inside the database, so two quick clicks can't overwrite each other."""
    with db() as conn:
        stock_reason(conn, "used" if body.delta < 0 else "bought")
        conn.execute("""
            UPDATE supplies SET qty_on_hand = qty_on_hand + %(delta)s,
                   purchase_date = CASE WHEN %(delta)s > 0 THEN current_date ELSE purchase_date END
            WHERE supply_id = %(id)s""", {"delta": body.delta, "id": supply_id})
        return fetch_supply(conn, supply_id)


@app.delete("/api/supplies/{supply_id}", status_code=204)
def delete_supply(supply_id: int):
    with db() as conn:
        stock_reason(conn, "deleted")
        if conn.execute("DELETE FROM supplies WHERE supply_id = %s", (supply_id,)).rowcount == 0:
            raise HTTPException(404, f"Supply {supply_id} not found.")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Stock history (recorded by a database trigger - see db/init/06_stock_history.sql)
# ---------------------------------------------------------------------------
@app.get("/api/supplies/{supply_id}/history")
def supply_history(supply_id: int, limit: int = Query(20, ge=1, le=500)):
    """Newest first: every quantity change for one supply, with the reason."""
    with db() as conn:
        return conn.execute(
            "SELECT movement_id, change, qty_after, reason, created_at FROM stock_movements "
            "WHERE supply_id = %s ORDER BY created_at DESC, movement_id DESC LIMIT %s",
            (supply_id, limit)).fetchall()


@app.get("/api/history")
def recent_history(limit: int = Query(50, ge=1, le=500)):
    """Newest first, across all supplies (deleted items included, by name)."""
    with db() as conn:
        return conn.execute(
            "SELECT m.movement_id, m.supply_id, v.item_ref, m.item_name, m.change, m.qty_after,"
            " m.reason, m.created_at FROM stock_movements m"
            " LEFT JOIN v_supplies v ON v.supply_id = m.supply_id"
            " ORDER BY m.created_at DESC, m.movement_id DESC LIMIT %s", (limit,)).fetchall()


# ---------------------------------------------------------------------------
# Lookup lists (brands, categories, locations) + the fixed choice lists
# ---------------------------------------------------------------------------
@app.get("/api/lookups")
def lookups():
    """Everything a form needs for its dropdowns. `uses` = how many supplies refer to it."""
    result = {"paint_types": PAINT_TYPES, "finishes": FINISHES, "conditions": CONDITIONS,
              "priorities": PRIORITIES}
    with db() as conn:
        for kind, (table, id_col) in LOOKUPS.items():
            query = sql.SQL(
                "SELECT t.{id} AS id, t.name, count(s.supply_id) AS uses FROM {table} t"
                " LEFT JOIN supplies s ON s.{id} = t.{id} GROUP BY t.{id}, t.name ORDER BY t.name"
            ).format(id=sql.Identifier(id_col), table=sql.Identifier(table))
            result[kind] = conn.execute(query).fetchall()
    return result


def lookup_table(kind):
    if kind not in LOOKUPS:
        raise HTTPException(404, f"Unknown list '{kind}'. Use one of: {', '.join(LOOKUPS)}.")
    return LOOKUPS[kind]


@app.post("/api/lookups/{kind}", status_code=201)
def add_lookup(kind: str, body: LookupIn):
    table, id_col = lookup_table(kind)
    query = sql.SQL("INSERT INTO {table} (name) VALUES (%s) RETURNING {id} AS id, name").format(
        table=sql.Identifier(table), id=sql.Identifier(id_col))
    with db() as conn:
        return conn.execute(query, (body.name.strip(),)).fetchone()


@app.delete("/api/lookups/{kind}/{item_id}", status_code=204)
def delete_lookup(kind: str, item_id: int):
    """Refused (409) while any supply still uses it - the foreign key enforces that."""
    table, id_col = lookup_table(kind)
    query = sql.SQL("DELETE FROM {table} WHERE {id} = %s").format(
        table=sql.Identifier(table), id=sql.Identifier(id_col))
    with db() as conn:
        if conn.execute(query, (item_id,)).rowcount == 0:
            raise HTTPException(404, "Not found.")
    return Response(status_code=204)
