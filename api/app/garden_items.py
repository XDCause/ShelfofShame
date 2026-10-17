"""Gardening: supplies and the seed bank - potting mix, fertiliser, pots, tools, pest control, grow lights,
seed packets and seedlings - what you have, what's running low, and what you want (Wishlist > Bunnings).

    GET  /garden/items?kind=&status=        your items
    POST /garden/items                      add one by hand
    POST /garden/items/bunnings {url}       add one from a Bunnings product link (bunnings.py reads that one page:
                                            name, item number, price, brand, rating, weight, category, how to use,
                                            photo). The same product twice opens the one you have. A plant only some
                                            stores sell (a 404 for Bunnings' default store) is still added, from what
                                            the link says (name, item number) - partial = true.
    POST /garden/items/from-page            what the "Send to Off the Clock" button sent from a Bunnings page in your
                                            browser (your store's price and stock; plants too): added, or the item
                                            you have updated
    POST /garden/items/{id}/bunnings        read its Bunnings page again (today's price, details); a link can be
                                            given to connect an item you added by hand
    GET / PATCH / DELETE /garden/items/{id}, and its photo
    POST /garden/items/{id}/sow             sow from a seed packet, or plant a seedling / grown plant: a new planting,
                                            one fewer left
"""
import json
import re
from datetime import date

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import bunnings
from .db import db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["gardening"])

# Must match db/init/67_garden.sql.
ITEM_KINDS = ["Seeds", "Seedling", "Plant", "Potting mix", "Fertiliser", "Pot", "Tool", "Pest control", "Grow light", "Hydroponics",
              "Watering", "Other"]
ITEM_STATUSES = ["Have", "Running low", "Wanted", "Used up"]
# Bunnings' own category words -> our kind (first match).
KIND_FROM_CATEGORY = [("seed", "Seeds"), ("potting mix", "Potting mix"), ("soil", "Potting mix"), ("fertiliser", "Fertiliser"),
                      ("plant food", "Fertiliser"), ("pots", "Pot"), ("planter", "Pot"), ("pest", "Pest control"),
                      ("weed", "Pest control"), ("hydroponic", "Hydroponics"), ("grow light", "Grow light"), ("watering", "Watering"),
                      ("hose", "Watering"), ("hand tools", "Tool"), ("garden tools", "Tool"), ("plants", "Plant")]


def _lit(values) -> str:
    return "^(" + "|".join(re.escape(v) for v in values) + ")$"


class ItemFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(ITEM_KINDS))
    status: str | None = Field(None, pattern=_lit(ITEM_STATUSES))
    qty: int | None = Field(None, ge=0, le=100000)
    brand: str | None = Field(None, max_length=120)
    guide_id: int | None = None
    sow_by: date | None = None
    notes: str | None = Field(None, max_length=5000)
    price: float | None = Field(None, ge=0)


class ItemIn(ItemFields):
    name: str = Field(min_length=1, max_length=200)


class ItemPatch(ItemFields):
    name: str | None = Field(None, min_length=1, max_length=200)


class BunningsIn(BaseModel):
    url: str = Field(min_length=10, max_length=2000)       # a link, or shared text with a link in it
    status: str = Field("Have", pattern=_lit(ITEM_STATUSES))
    kind: str | None = Field(None, pattern=_lit(ITEM_KINDS))


class LinkIn(BaseModel):
    url: str | None = Field(None, max_length=2000)


class PageIn(BaseModel):
    """From the button, through a link - so every field is limited and checked again (bunnings.from_page)."""
    page: dict
    status: str = Field("Have", pattern=_lit(ITEM_STATUSES))
    kind: str | None = Field(None, pattern=_lit(ITEM_KINDS))


class SowIn(BaseModel):
    container_id: int | None = None
    quantity: int = Field(1, ge=1, le=10000)


ITEM_SELECT = """
SELECT i.item_id, i.name, i.kind, i.status, i.qty, i.brand, i.guide_id, i.sow_by, i.notes, i.bunnings_item, i.url,
       i.price::float8 AS price, i.price_checked_at, i.rating::float8 AS rating, i.reviews, i.weight_kg::float8 AS weight_kg,
       i.category, i.description, i.how_to, i.created_at, g.name AS guide_name, i.store_name, i.store_code, i.stock, i.store_aisle,
       i.sow_by IS NOT NULL AND i.sow_by < current_date AS expired,
       CASE WHEN i.photo IS NOT NULL THEN '/api/garden/items/' || i.item_id || '/photo?v='
            || (extract(epoch FROM i.photo_updated) * 1000)::bigint END AS photo_url
FROM garden_items i LEFT JOIN garden_guides g ON g.guide_id = i.guide_id"""


def fetch_item(conn, item_id: int) -> dict:
    return found(conn.execute(ITEM_SELECT + " WHERE i.item_id = %s", (item_id,)).fetchone(), "Item")


def pot_kind(name: str) -> str | None:
    """A plant sold by pot size ("100mm Leek...", "140mm Petunia..."): small pots are seedlings, bigger ones plants."""
    m = re.match(r"^(\d+)\s?mm\b", name or "", re.I)
    return None if not m else "Plant" if int(m.group(1)) >= 130 else "Seedling"


def kind_for(category: str | None, name: str) -> str:
    text = f"{category or ''} {name}".lower()
    return next((kind for word, kind in KIND_FROM_CATEGORY if word in text), "Other")


def save_from_bunnings(conn, item_id: int, product: dict, photo: bool):
    conn.execute("""UPDATE garden_items SET bunnings_item = %(bunnings_item)s, url = %(url)s, price = %(price)s,
                    price_checked_at = now(), rating = %(rating)s, reviews = %(reviews)s, weight_kg = %(weight_kg)s,
                    category = %(category)s, description = %(description)s, how_to = %(how_to)s,
                    brand = COALESCE(brand, %(brand)s) WHERE item_id = %(id)s""", {**product, "id": item_id})
    if photo and product.get("image"):
        image, image_type = bunnings.photo(product["image"])
        if image:
            conn.execute("UPDATE garden_items SET photo = %s, photo_type = %s, photo_updated = now() WHERE item_id = %s",
                         (image, image_type, item_id))


@router.get("/garden/items")
def list_items(kind: str | None = None, status: str | None = None):
    with db() as conn:
        return conn.execute(ITEM_SELECT + """ WHERE (%(k)s::text IS NULL OR i.kind = %(k)s) AND (%(s)s::text IS NULL OR i.status = %(s)s)
            ORDER BY array_position(ARRAY['Wanted', 'Running low', 'Have', 'Used up'], i.status), i.kind, lower(i.name)""",
                            {"k": kind, "s": status}).fetchall()


@router.post("/garden/items", status_code=201)
def add_item(body: ItemIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        return fetch_item(conn, insert_row(conn, "garden_items", data, "item_id"))


@router.post("/garden/items/bunnings", status_code=201)
def add_from_bunnings(body: BunningsIn, response: Response):
    """Add a product from its Bunnings link. Already have it? That item comes back (existing = true)."""
    url = bunnings.product_url(body.url)
    if not url:
        raise HTTPException(422, "That isn't a Bunnings product link (they look like bunnings.com.au/..._p1234567).")
    item = url.rsplit("_p", 1)[1]
    with db() as conn:
        old = conn.execute("SELECT item_id FROM garden_items WHERE bunnings_item = %s", (item,)).fetchone()
        if old:
            response.status_code = 200
            return {**fetch_item(conn, old["item_id"]), "existing": True}
    try:
        product = bunnings.fetch(url)
    except bunnings.NotAtDefaultStore:
        name = bunnings.name_from_url(url)
        kind = body.kind or pot_kind(name) or kind_for(None, name)
        with db() as conn:
            item_id = insert_row(conn, "garden_items", {
                "name": name, "status": body.status, "kind": kind, "bunnings_item": item, "url": url,
                "notes": "Bunnings shows this page only for stores that sell it (plants are regional), so its price and photo "
                         "couldn't be read - open it on Bunnings with your store chosen."}, "item_id")
            return {**fetch_item(conn, item_id), "existing": False, "partial": True}
    except bunnings.BunningsError as e:
        raise HTTPException(502 if "reach" in str(e) or "answer" in str(e) else 422, str(e))
    with db() as conn:
        item_id = insert_row(conn, "garden_items", {"name": product["name"], "status": body.status,
                                                    "kind": body.kind or pot_kind(product["name"])
                                                    or kind_for(product["category"], product["name"])}, "item_id")
        save_from_bunnings(conn, item_id, product, photo=True)
        return {**fetch_item(conn, item_id), "existing": False, "partial": False}


@router.post("/garden/items/from-page")
def add_from_page(body: PageIn, response: Response):
    """What the button sent from a Bunnings product page: a new item, or the one you have (same item number)
    with today's price, stock, aisle and details from your store. Its photo is fetched from Bunnings' image server."""
    if len(json.dumps(body.page)) > 20000:
        raise HTTPException(413, "That's more than a product page sends.")
    try:
        product = bunnings.from_page(body.page)
    except bunnings.BunningsError as e:
        raise HTTPException(422, str(e))
    with db() as conn:
        old = conn.execute("SELECT item_id, price, photo IS NOT NULL AS has_photo FROM garden_items WHERE bunnings_item = %s",
                           (product["bunnings_item"],)).fetchone()
        if old:
            item_id = old["item_id"]
        else:
            kind = body.kind or pot_kind(product["name"]) or kind_for(product["category"], product["name"])
            item_id = insert_row(conn, "garden_items", {"name": product["name"], "status": body.status, "kind": kind}, "item_id")
        save_from_bunnings(conn, item_id, product, photo=not (old and old["has_photo"]))
        conn.execute("UPDATE garden_items SET store_name = %s, store_code = %s, stock = %s, store_aisle = %s WHERE item_id = %s",
                     (product["store_name"], product["store_code"], product["stock"], product["aisle"], item_id))
        response.status_code = 200 if old else 201
        return {**fetch_item(conn, item_id), "existing": bool(old), "price_before": old["price"] if old else None}


@router.post("/garden/items/{item_id}/bunnings")
def refresh_from_bunnings(item_id: int, body: LinkIn | None = None):
    """Read the item's Bunnings page again: today's price and details (and its photo if it has none).
    With a url: connect an item you added by hand to that product first."""
    with db() as conn:
        current = fetch_item(conn, item_id)
        has_photo = current["photo_url"] is not None
    url = (body.url if body and body.url else None) or current["url"]
    if not url or not bunnings.product_url(url):
        raise HTTPException(422, "Paste its Bunnings product link first.")
    try:
        product = bunnings.fetch(url)
    except bunnings.NotAtDefaultStore:
        raise HTTPException(422, "Bunnings only shows this page to stores that sell it (plants are regional), so its price "
                                 "can't be checked from here - open it on Bunnings with your store chosen.") from None
    except bunnings.BunningsError as e:
        raise HTTPException(502 if "reach" in str(e) or "answer" in str(e) else 422, str(e))
    with db() as conn:
        clash = conn.execute("SELECT item_id FROM garden_items WHERE bunnings_item = %s AND item_id <> %s",
                             (product["bunnings_item"], item_id)).fetchone()
        if clash:
            raise HTTPException(409, "Another of your items is already that Bunnings product.")
        save_from_bunnings(conn, item_id, product, photo=not has_photo)
        return {**fetch_item(conn, item_id), "price_before": current["price"]}


@router.get("/garden/items/{item_id}")
def get_item(item_id: int):
    with db() as conn:
        item = fetch_item(conn, item_id)
        item["plantings"] = conn.execute("SELECT planting_id, name, stage, started_on FROM garden_plantings WHERE item_id = %s "
                                         "ORDER BY started_on DESC", (item_id,)).fetchall()
        return item


@router.patch("/garden/items/{item_id}")
def update_item(item_id: int, body: ItemPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "kind", "status"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.capitalize()} can't be empty.")
    with db() as conn:
        fetch_item(conn, item_id)
        update_row(conn, "garden_items", "item_id", item_id, data)
        return fetch_item(conn, item_id)


@router.delete("/garden/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM garden_items WHERE item_id = %s RETURNING item_id", (item_id,)).fetchone(), "Item")
    return Response(status_code=204)


@router.post("/garden/items/{item_id}/sow", status_code=201)
def sow_from(item_id: int, body: SowIn):
    """Sow from a seed packet, or plant a seedling or a grown plant you bought: a new planting linked to the item."""
    from .garden import PlantingIn, add_planting
    with db() as conn:
        item = fetch_item(conn, item_id)
    if item["kind"] not in ("Seeds", "Seedling", "Plant"):
        raise HTTPException(422, "Only seeds, seedlings and plants can be sown or planted.")
    return add_planting(PlantingIn(name=None if item["guide_id"] else item["name"], guide_id=item["guide_id"], item_id=item_id,
                                   container_id=body.container_id, quantity=body.quantity,
                                   source={"Seeds": "Seed", "Plant": "Bought plant"}.get(item["kind"], "Seedling"),
                                   bought_from="Bunnings" if item["bunnings_item"] else None))


add_photo_routes(router, "/garden/items", "garden_items", "item_id", "Item")
