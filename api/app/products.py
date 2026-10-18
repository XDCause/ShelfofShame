"""Products: looking things up (Tamiya, Hasegawa, Trumpeter, Bandai via HLJ), barcodes, and product photos.

product_info is the cache: one row per brand + product code with the manufacturer's title,
description and photo (or your own photo), a barcode once you've linked one, and for Tamiya
kits the paint list from the kit's page.
"""
import asyncio
import re
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import hasegawa, hlj, tamiya, trumpeter
from .db import brand_id as brand_named, db, ensure_brand
from .images import photo_response, read_photo
from .settings import price_for

router = APIRouter(prefix="/api", tags=["products"])

UPSERT_INFO = """
INSERT INTO product_info (brand_id, product_code, title, series, description, source_url,
                          image, image_type, kit_paints)
VALUES (%(brand_id)s, %(code)s, %(title)s, %(series)s, %(description)s, %(source_url)s,
        %(image)s, %(image_type)s, %(kit_paints)s)
ON CONFLICT (brand_id, product_code) DO UPDATE SET
    title = EXCLUDED.title, series = EXCLUDED.series, description = EXCLUDED.description,
    source_url = EXCLUDED.source_url,
    image = COALESCE(EXCLUDED.image, product_info.image),
    image_type = COALESCE(EXCLUDED.image_type, product_info.image_type),
    kit_paints = COALESCE(EXCLUDED.kit_paints, product_info.kit_paints),
    fetched_at = now()"""


async def tamiya_product(item: str, refresh: bool = False):
    """Make sure product_info has this Tamiya item: from the cache, or fetched once from
    tamiya.com. Returns (brand_id, product_code, from_cache)."""
    product_code = tamiya.product_code(item)  # your convention: T81701

    with db() as conn:
        tamiya_id = brand_named(conn, "Tamiya")
        if tamiya_id is None:
            raise HTTPException(409, "Add 'Tamiya' to your brands list first.")
        cached = conn.execute("SELECT title FROM product_info WHERE brand_id = %s AND product_code = %s",
                              (tamiya_id, product_code)).fetchone()

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
            conn.execute(UPSERT_INFO, {**info, "brand_id": tamiya_id, "code": product_code,
                                       "kit_paints": Jsonb(info.get("kit_paints") or [])})
    return tamiya_id, product_code, from_cache


def suggestion(conn, brand_id, product_code, title, series, description) -> dict:
    """Best-guess field values for a product, with category as an id and your usual price."""
    guess = tamiya.suggest(title, series, description, product_code)
    category = conn.execute("SELECT category_id FROM categories WHERE name = %s",
                            (guess.pop("category") or "Other",)).fetchone()
    return {**guess, "category_id": category["category_id"] if category else None,
            "est_price": price_for(conn, title, guess)}


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
        suggested = suggestion(conn, brand_id, product_code, p["title"], p["series"], p["description"])
    else:
        suggested = {}

    owned = conn.execute("SELECT supply_id, qty_on_hand FROM supplies WHERE brand_id = %s AND product_code = %s",
                         (brand_id, product_code)).fetchone()
    on_wishlist = conn.execute("SELECT wish_id FROM wishlist WHERE brand_id = %s AND product_code = %s",
                               (brand_id, product_code)).fetchone()
    return {
        **p,
        "brand_id": brand_id,
        "product_code": product_code,
        "suggested": suggested,
        "owned_qty": owned["qty_on_hand"] if owned else 0,
        "supply_id": owned["supply_id"] if owned else None,  # your inventory item, if any
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


@router.get("/lookup/hasegawa/{code}")
async def lookup_hasegawa(code: str, refresh: bool = False):
    """A Hasegawa kit by series code (JT86) or item number (09086 / HSG09086): name, scale and
    box photo from hasegawa-model.co.jp. Cached in product_info under product code HSG<item>."""
    parsed = hasegawa.normalise(code)
    if parsed is None:
        raise HTTPException(422, "Enter the series code (e.g. JT86) or item number (e.g. 09086) from the box.")
    kind, value = parsed

    with db() as conn:
        # Add Hasegawa to your brands the first time you look one of their kits up.
        hasegawa_id = ensure_brand(conn, "Hasegawa")
        cached = conn.execute(
            "SELECT product_code, series FROM product_info WHERE brand_id = %s AND title IS NOT NULL "
            "AND (product_code = %s OR series = %s)", (hasegawa_id, f"HSG{value}", value)).fetchone()

    if cached and not refresh:
        product_code = cached["product_code"]
    else:
        if kind == "series":
            candidates = [value]
        elif cached and cached["series"]:
            candidates = [cached["series"]]
        else:
            candidates = hasegawa.series_for_item(value)
            if not candidates:
                raise HTTPException(404, f"Can't work out the page for item {value} from the number alone. "
                                         "Enter the series code printed next to it on the box (e.g. JT86).")
        info = None
        for series in candidates:
            try:
                page = await run_in_threadpool(hasegawa.fetch, series)
            except tamiya.NotFound:
                continue
            except tamiya.LookupFailed as e:
                raise HTTPException(502, str(e))
            # Typed an item number: the page must say it's that item, or it's the wrong kit.
            if kind == "series" or page["item"] == value:
                info = page
                break
        if info is None:
            raise HTTPException(404, f"Hasegawa has no kit page for {value}.")

        product_code = f"HSG{info['item']}" if info["item"] else f"HSG-{info['series'] or value}"
        description = " · ".join(filter(None, [
            f"Item no {info['series']} ({info['item']})" if info["series"] and info["item"] else None,
            info["scale"] and f"Scale {info['scale']}", info["category"]]))
        with db() as conn:
            conn.execute(UPSERT_INFO, {**info, "brand_id": hasegawa_id, "code": product_code,
                                       "description": description or None, "kit_paints": None})

    with db() as conn:
        p = conn.execute("""
            SELECT product_info_id, title, series, description, source_url,
                   fetched_at AS photo_updated, (image IS NOT NULL) AS has_image
            FROM product_info WHERE brand_id = %s AND product_code = %s""", (hasegawa_id, product_code)).fetchone()
    scale = re.search(r"Scale (1/\d+)", p["description"] or "")
    return {**p, "brand_id": hasegawa_id, "product_code": product_code, "series_code": p["series"],
            "name": tamiya.nice_name(p["title"]), "scale": scale.group(1) if scale else None,
            "from_cache": bool(cached) and not refresh}


@router.get("/lookup/trumpeter/{code}")
async def lookup_trumpeter(code: str, refresh: bool = False):
    """A Trumpeter kit or tool by the 5-digit item number on the box (00968, TRU00968): name, scale, kind, parts,
    box photo and barcode from trumpeter-china.com. Cached in product_info under product code TRU<item>; the
    box's barcode (from their page) is remembered so scanning it finds the product."""
    item = trumpeter.normalise(code)
    if item is None:
        raise HTTPException(422, "Enter the 5-digit item number from the box (e.g. 00968).")
    product_code = f"TRU{item}"
    with db() as conn:
        trumpeter_id = ensure_brand(conn, "Trumpeter")       # added to your brands the first time
        cached = conn.execute("SELECT title FROM product_info WHERE brand_id = %s AND product_code = %s AND title IS NOT NULL",
                              (trumpeter_id, product_code)).fetchone()
    if not cached or refresh:
        try:
            info = await run_in_threadpool(trumpeter.fetch, item)
        except tamiya.NotFound as e:
            raise HTTPException(404, str(e))
        except tamiya.LookupFailed as e:
            raise HTTPException(502, str(e))
        with db() as conn:
            conn.execute(UPSERT_INFO, {"brand_id": trumpeter_id, "code": product_code, "title": info["title"],
                                       "series": info["item_type"], "description": trumpeter.describe(info),
                                       "source_url": info["source_url"], "image": info["image"],
                                       "image_type": info["image_type"], "kit_paints": None})
            if info["barcode"]:                               # theirs, from the page - unless another product has it
                conn.execute("""UPDATE product_info SET barcode = %s WHERE brand_id = %s AND product_code = %s AND barcode IS NULL
                                AND NOT EXISTS (SELECT 1 FROM product_info WHERE barcode = %s)""",
                             (info["barcode"], trumpeter_id, product_code, info["barcode"]))
    with db() as conn:
        p = describe_product(conn, trumpeter_id, product_code)
    scale = re.search(r"Scale (1/\d+)", p["description"] or "")
    kind = p["series"] or ""
    return {**p, "brand_id": trumpeter_id, "product_code": product_code, "name": p["title"],
            "scale": scale.group(1) if scale else None, "item_type": kind or None,
            "is_tool": any(w in kind.lower() for w in trumpeter.TOOL_TYPES), "from_cache": bool(cached) and not refresh}


def who_to_ask(code: str) -> list[str]:
    """Whose site to ask for what was typed in Add a supply: a paint code (XF-76) or T81776 is Tamiya's, TRU00968
    Trumpeter's; a plain 3-5 digit number could be either's (both use 5-digit numbers), so both."""
    c = code.strip().upper()
    if re.match(r"TR(U|UMPETER)?[\s-]?\d", c):
        return ["Trumpeter"]
    if re.fullmatch(r"\d{3,5}", c):
        return ["Tamiya", "Trumpeter"]
    return ["Tamiya"]


@router.get("/lookup/item/{code}")
async def lookup_item(code: str):
    """Add a supply's one look-up box: asks each maker it could be (at the same time) and gives back what each
    found - two when both makers have the number, for you to pick - and why the others didn't. A 404 only when
    nobody has it (so a "not at Tamiya" isn't an error in the browser when Trumpeter has it)."""
    async def ask(maker):
        try:
            r = await (lookup_trumpeter(code) if maker == "Trumpeter" else lookup_tamiya(code))
            return {"maker": maker, **r}
        except HTTPException as e:
            return {"maker": maker, "status": e.status_code, "message": e.detail}
    answers = await asyncio.gather(*(ask(m) for m in who_to_ask(code)))
    found = [a for a in answers if "status" not in a]
    missed = [a for a in answers if "status" in a]
    if not found:
        unreachable = [a for a in missed if a["status"] not in (404, 409, 422)]
        raise HTTPException(unreachable[0]["status"] if unreachable else max(a["status"] for a in missed),
                            " ".join(dict.fromkeys(a["message"] for a in missed)))
    return {"found": found, "missed": missed}


def _bandai_cached(conn, bandai_id, kind, value):
    """A kit already looked up: by your code (G5057403), its barcode, or HLJ's code."""
    keys = {"barcode": (hlj.product_code_for(value, ""), value, None),
            "hlj": (value, None, f"%{value.lower()}")}.get(kind)
    if keys is None:
        return None
    return conn.execute(
        "SELECT product_code FROM product_info WHERE brand_id = %s AND title IS NOT NULL "
        "AND (product_code = %s OR barcode = %s OR source_url LIKE %s)", (bandai_id, *keys)).fetchone()


def _bandai_page(kind, value):
    """Search HLJ, open the matching kit page and check it's the kit asked for (blocking: runs
    in a thread). Returns the page, or a list of choices when a name matches several kits."""
    results = hlj.search(value)
    if kind == "hlj":
        results = [r for r in results if r["hlj_code"] == value]
    if not results:
        raise tamiya.NotFound(f"HLJ has no Bandai kit for {value}.")
    if kind == "name" and len(results) > 1:
        return results[:12]
    time.sleep(hlj.PAUSE)
    page = hlj.fetch(results[0]["path"])
    # A code or barcode was typed: the page's own barcode must be that one, or it's another kit.
    if kind == "barcode" and page["barcode"] != value:
        raise tamiya.NotFound(f"HLJ's page for {value} is a different kit ({page['title']}).")
    return page


@router.get("/lookup/bandai/{code:path}")
async def lookup_bandai(code: str, refresh: bool = False):
    """A Bandai kit from HobbyLink Japan: name, grade, scale, barcode and box photo. `code` can be
    your code from the box (G5057403 / 5057403), the box barcode, HLJ's code (BANH574039-UP) or
    a name ("rx-78-2 revive"). A name matching several kits returns {"choices": [...]} to pick
    from (look the pick up again by its hlj_code). Cached in product_info, product code G50xxxxx."""
    parsed = hlj.normalise(code)
    if parsed is None:
        raise HTTPException(422, "Enter the code from the box (e.g. G5057403), its barcode, or the kit's name.")
    kind, value = parsed
    with db() as conn:
        bandai_id = ensure_brand(conn, "Bandai")
        cached = None if refresh else _bandai_cached(conn, bandai_id, kind, value)

    if cached:
        product_code = cached["product_code"]
    else:
        try:
            page = await run_in_threadpool(_bandai_page, kind, value)
        except tamiya.NotFound as e:
            raise HTTPException(404, str(e))
        except tamiya.LookupFailed as e:
            raise HTTPException(502, str(e))
        if isinstance(page, list):
            return {"choices": page}
        product_code = hlj.product_code_for(page["barcode"], page["hlj_code"])
        description = " · ".join(filter(None, [page["item_type"], page["series"],
                                               page["released"] and f"Released {page['released']}",
                                               f"HLJ {page['hlj_code']}"]))
        with db() as conn:
            conn.execute(UPSERT_INFO, {**page, "brand_id": bandai_id, "code": product_code,
                                       "description": description, "kit_paints": None})
            if page["barcode"]:  # remember the box barcode (unless another product already has it)
                conn.execute("""
                    UPDATE product_info SET barcode = %(b)s WHERE brand_id = %(id)s AND product_code = %(c)s
                    AND NOT EXISTS (SELECT 1 FROM product_info WHERE barcode = %(b)s)""",
                             {"b": page["barcode"], "id": bandai_id, "c": product_code})

    with db() as conn:
        p = conn.execute("""
            SELECT product_info_id, title, series, description, source_url, barcode,
                   fetched_at AS photo_updated, (image IS NOT NULL) AS has_image
            FROM product_info WHERE brand_id = %s AND product_code = %s""", (bandai_id, product_code)).fetchone()
    return {**p, "brand_id": bandai_id, "product_code": product_code, "name": hlj.name_of(p["title"]),
            "grade": hlj.grade_of(p["title"]), "scale": hlj.scale_of(p["title"]), "from_cache": bool(cached)}


# ---------------------------------------------------------------------------
# Barcodes
# ---------------------------------------------------------------------------
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
        tamiya_id = brand_named(conn, "Tamiya")

    async def from_tamiya(item, match):
        found_id, product_code, _ = await tamiya_product(item)
        with db() as conn:
            return {**describe_product(conn, found_id, product_code), "barcode": barcode, "match": match}

    if listed and tamiya_id:
        return await from_tamiya(tamiya.item_number(listed["product_code"]), "catalog")

    unknown = {"barcode": barcode, "match": "unknown", "suggested": {}, "brand_id": None}
    if not tamiya.is_tamiya_barcode(barcode) or tamiya_id is None:
        return unknown
    unknown["brand_id"] = tamiya_id
    try:
        return await from_tamiya(tamiya.guess_item_from_barcode(barcode), "tamiya")
    except HTTPException as e:
        if e.status_code == 404:  # those digits aren't an item number for this product
            return unknown
        raise


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
    code = body.product_code.strip()
    with db() as conn:
        conn.execute("""
            INSERT INTO product_info (brand_id, product_code, barcode) VALUES (%s, %s, %s)
            ON CONFLICT (brand_id, product_code) DO UPDATE SET barcode = EXCLUDED.barcode""",
            (body.brand_id, code, barcode))
        return describe_product(conn, body.brand_id, code)


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------
@router.put("/product-photo")
async def upload_photo(request: Request, brand_id: int, product_code: str):
    """Your own photo for any brand + product code (phone camera, saved image, ...).

    Send the image itself as the request body with its Content-Type, e.g. image/jpeg.
    Replaces any existing photo for that item, including one fetched from tamiya.com.
    """
    image, image_type = await read_photo(request)
    code = product_code.strip()
    if not code:
        raise HTTPException(422, "The item needs a product code to attach a photo to.")

    def save():
        with db() as conn:
            return conn.execute("""
                INSERT INTO product_info (brand_id, product_code, image, image_type)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (brand_id, product_code) DO UPDATE SET
                    image = EXCLUDED.image, image_type = EXCLUDED.image_type, fetched_at = now()
                RETURNING product_info_id""", (brand_id, code, image, image_type)).fetchone()
    # Database work is blocking, so run it in a worker thread from this async endpoint.
    return await run_in_threadpool(save)


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
    return photo_response(row and row["image"], row and row["image_type"])
