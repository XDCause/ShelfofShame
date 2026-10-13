"""The editable lists (brands, categories, storage locations) and the fixed choice lists."""
from fastapi import APIRouter, HTTPException, Response
from psycopg import sql
from pydantic import BaseModel, Field

from .db import (CONDITIONS, FINISHES, GUNDAM_GRADES, HOBBIES, HOBBY_BRANDS, MODEL_STATUSES, PAINT_TYPES,
                 PRIORITIES, STAGES, db, found)

router = APIRouter(prefix="/api", tags=["lookups"])

# URL name -> (table, id column)
LOOKUPS = {
    "brands": ("brands", "brand_id"),
    "categories": ("categories", "category_id"),
    "locations": ("storage_locations", "location_id"),
}
# Every table that refers to each list, so "uses" (and whether it can be removed) is right.
# product_info and catalog_products aren't here: cached photos and the Tamiya catalogue are
# deleted along with an unused brand.
LOOKUP_USERS = {
    "brands": ["supplies", "wishlist", "models", "model_paints", "mix_parts", "colour_group_members"],
    "categories": ["supplies", "wishlist"],
    "locations": ["supplies"],
}


class LookupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.get("/lookups")
def lookups():
    """Everything a form needs for its dropdowns. `uses` = how many things refer to it
    (anything in use can't be removed)."""
    result = {"paint_types": PAINT_TYPES, "finishes": FINISHES, "conditions": CONDITIONS,
              "priorities": PRIORITIES, "model_statuses": MODEL_STATUSES,
              "hobbies": HOBBIES, "stages": STAGES, "hobby_brands": HOBBY_BRANDS, "gundam_grades": GUNDAM_GRADES}
    with db() as conn:
        for kind, (table, id_col) in LOOKUPS.items():
            counts = sql.SQL(" + ").join(
                sql.SQL("(SELECT count(*) FROM {u} WHERE {u}.{id} = t.{id})").format(
                    u=sql.Identifier(user), id=sql.Identifier(id_col))
                for user in LOOKUP_USERS[kind])
            query = sql.SQL("SELECT t.{id} AS id, t.name, {counts} AS uses FROM {table} t ORDER BY t.name").format(
                id=sql.Identifier(id_col), table=sql.Identifier(table), counts=counts)
            result[kind] = conn.execute(query).fetchall()
    return result


def lookup_table(kind):
    if kind not in LOOKUPS:
        raise HTTPException(404, f"Unknown list '{kind}'. Use one of: {', '.join(LOOKUPS)}.")
    return LOOKUPS[kind]


@router.post("/lookups/{kind}", status_code=201)
def add_lookup(kind: str, body: LookupIn):
    table, id_col = lookup_table(kind)
    query = sql.SQL("INSERT INTO {table} (name) VALUES (%s) RETURNING {id} AS id, name").format(
        table=sql.Identifier(table), id=sql.Identifier(id_col))
    with db() as conn:
        return conn.execute(query, (body.name.strip(),)).fetchone()


@router.delete("/lookups/{kind}/{item_id}", status_code=204)
def delete_lookup(kind: str, item_id: int):
    """Refused (409) while anything still uses it - the foreign keys enforce that."""
    table, id_col = lookup_table(kind)
    query = sql.SQL("DELETE FROM {table} WHERE {id} = %s RETURNING {id}").format(
        table=sql.Identifier(table), id=sql.Identifier(id_col))
    with db() as conn:
        found(conn.execute(query, (item_id,)).fetchone(), "That list entry")
    return Response(status_code=204)
