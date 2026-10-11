"""Models (kits) and the paints each one needs.

A model's paint list is a checklist. Each paint is matched to your inventory by brand +
product code, so it shows as "have it" automatically while you own one; paints you don't track
can be ticked by hand (have_it).
"""
import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from psycopg import sql
from pydantic import BaseModel, Field

from . import hasegawa, tamiya
from .db import db

router = APIRouter(prefix="/api", tags=["models"])

STATUSES = ["Not started", "In progress", "On hold", "Finished"]
Status = Literal[tuple(STATUSES)]


class ModelIn(BaseModel):
    name: str = Field(min_length=1)
    brand_id: int | None = None
    product_code: str | None = None
    scale: str | None = None
    status: Status = "Not started"
    notes: str | None = None


class ModelPatch(BaseModel):
    name: str | None = Field(None, min_length=1)
    brand_id: int | None = None
    product_code: str | None = None
    scale: str | None = None
    status: Status | None = None
    notes: str | None = None


class PaintsIn(BaseModel):
    """One paint per line: "XF-76 Grey Green (IJN) <tab> The whole exterior".
    `purpose` is used for a single line typed without a tab."""
    text: str = Field(min_length=1)
    purpose: str | None = None


class PaintPatch(BaseModel):
    paint_name: str | None = Field(None, min_length=1)
    purpose: str | None = None
    have_it: bool | None = None
    sort_order: int | None = None


MODEL_SELECT = """
SELECT m.*, b.name AS brand,
       p.product_info_id, (p.image IS NOT NULL) AS has_image, p.fetched_at AS photo_updated, p.source_url,
       (SELECT count(*) FROM model_paints mp WHERE mp.model_id = m.model_id) AS paints_total,
       (SELECT count(*) FROM model_paints mp WHERE mp.model_id = m.model_id
          AND (mp.have_it OR EXISTS (SELECT 1 FROM supplies s WHERE s.brand_id = mp.brand_id
                                     AND s.product_code = mp.product_code AND s.qty_on_hand > 0))
       ) AS paints_have
FROM models m
LEFT JOIN brands b ON b.brand_id = m.brand_id
LEFT JOIN product_info p ON p.brand_id = m.brand_id AND p.product_code = m.product_code
"""

# Each paint with what your inventory says about it.
PAINTS_SELECT = """
SELECT mp.*, b.name AS brand,
       owned.supply_id, COALESCE(owned.qty_on_hand, 0) AS owned_qty, owned.condition, owned.stock_status,
       (COALESCE(owned.qty_on_hand, 0) > 0) AS in_inventory,
       (COALESCE(owned.qty_on_hand, 0) > 0 OR mp.have_it) AS have,
       EXISTS (SELECT 1 FROM wishlist w WHERE w.brand_id = mp.brand_id
               AND w.product_code = mp.product_code) AS on_wishlist,
       p.product_info_id, (p.image IS NOT NULL) AS has_image, p.fetched_at AS photo_updated
FROM model_paints mp
LEFT JOIN brands b ON b.brand_id = mp.brand_id
LEFT JOIN LATERAL (
    SELECT v.supply_id, v.qty_on_hand, v.condition, v.stock_status
    FROM supplies s JOIN v_supplies v USING (supply_id)
    WHERE s.brand_id = mp.brand_id AND s.product_code = mp.product_code
    LIMIT 1
) owned ON true
LEFT JOIN product_info p ON p.brand_id = mp.brand_id AND p.product_code = mp.product_code
WHERE mp.model_id = %s
ORDER BY mp.sort_order, mp.model_paint_id
"""


def fetch_model(conn, model_id):
    model = conn.execute(MODEL_SELECT + " WHERE m.model_id = %s", (model_id,)).fetchone()
    if model is None:
        raise HTTPException(404, f"Model {model_id} not found.")
    return {**model, "paints": conn.execute(PAINTS_SELECT, (model_id,)).fetchall()}


def write(conn, table, id_col, row_id, data):
    query = sql.SQL("UPDATE {t} SET {sets} WHERE {id} = {rid}").format(
        t=sql.Identifier(table), id=sql.Identifier(id_col), rid=sql.Placeholder("row_id"),
        sets=sql.SQL(", ").join(sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder(k)) for k in data))
    return conn.execute(query, {**data, "row_id": row_id}).rowcount


# ---------------------------------------------------------------------------
# Reading a paint list
# ---------------------------------------------------------------------------
# Between the paint and what it's for: a tab, or " - " / " – " / " — " / ": ".
SPLIT = re.compile(r"\t+|\s+[-–—]\s+|:\s+")
# Notes about buying aren't part of the name: the checklist works that out from your inventory.
BUY_NOTE = re.compile(r"\s*\((?:still\s+)?(?:to|need to)\s+buy\)", re.I)
LEADING_PAINT_CODE = re.compile(r"(XF|X)\s*-?\s*(\d{1,2})(A?)(?![\dA-Z])", re.I)


def parse_line(line):
    """'XF-76 Grey Green (IJN)<tab>The whole exterior' -> ('XF-76 Grey Green (IJN)', 'The whole exterior')"""
    parts = SPLIT.split(line.strip(), maxsplit=1)
    paint = re.sub(r"\s+", " ", BUY_NOTE.sub("", parts[0])).strip()
    purpose = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return paint, purpose


def resolve(conn, paint, tamiya_id):
    """Work out which product a typed paint is: (brand_id, product_code, display name)."""
    first = paint.split()[0] if paint.split() else ""
    m = LEADING_PAINT_CODE.match(paint)
    if m and tamiya_id:                                    # XF-76 -> Tamiya T81776
        code = "T" + tamiya.item_number(m.group(0))
        # Only the code typed ("XF-76", "xf76")? Then look the name up instead of using the code.
        return tamiya_id, code, None if tamiya.paint_code(paint) else paint
    owned = conn.execute("SELECT brand_id, product_code FROM supplies WHERE upper(product_code) = upper(%s) "
                         "LIMIT 1", (first,)).fetchone()
    if owned:                                              # a code you own, e.g. MIL3
        return owned["brand_id"], owned["product_code"], paint if paint != first else None
    if re.fullmatch(r"T?\d{5}", first, re.I) and tamiya_id:  # a Tamiya item number
        return tamiya_id, "T" + first.upper().lstrip("T"), paint if paint != first else None
    return None, None, paint                               # not linked: tick it by hand


def default_name(conn, brand_id, code, typed):
    """Just a code was typed (e.g. 'XF-76'): use your own name for it, else Tamiya's."""
    row = conn.execute("SELECT name FROM supplies WHERE brand_id = %s AND product_code = %s",
                       (brand_id, code)).fetchone()
    if row:
        return row["name"]
    info = conn.execute("SELECT title FROM product_info WHERE brand_id = %s AND product_code = %s",
                        (brand_id, code)).fetchone()
    return tamiya._nice_name(info["title"]) if info and info["title"] else typed


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
@router.get("/models")
def list_models():
    with db() as conn:
        return conn.execute(MODEL_SELECT + """
            ORDER BY CASE m.status WHEN 'In progress' THEN 0 WHEN 'Not started' THEN 1
                                   WHEN 'On hold' THEN 2 ELSE 3 END, m.created_at DESC""").fetchall()


@router.post("/models", status_code=201)
def add_model(body: ModelIn):
    data = body.model_dump()
    query = sql.SQL("INSERT INTO models ({c}) VALUES ({v}) RETURNING model_id").format(
        c=sql.SQL(", ").join(map(sql.Identifier, data)), v=sql.SQL(", ").join(map(sql.Placeholder, data)))
    with db() as conn:
        return fetch_model(conn, conn.execute(query, data).fetchone()["model_id"])


@router.get("/models/{model_id}")
def get_model(model_id: int):
    with db() as conn:
        return fetch_model(conn, model_id)


@router.patch("/models/{model_id}")
def update_model(model_id: int, body: ModelPatch):
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        if data:
            write(conn, "models", "model_id", model_id, data)
        return fetch_model(conn, model_id)


@router.delete("/models/{model_id}", status_code=204)
def delete_model(model_id: int):
    with db() as conn:
        if conn.execute("DELETE FROM models WHERE model_id = %s", (model_id,)).rowcount == 0:
            raise HTTPException(404, f"Model {model_id} not found.")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# A model's paints
# ---------------------------------------------------------------------------
@router.post("/models/{model_id}/paints", status_code=201)
def add_paints(model_id: int, body: PaintsIn):
    """Add one paint, or paste a whole list (one per line). Codes like XF-76 or ones you own
    are linked to your inventory; anything else is kept as a name you tick by hand."""
    lines = [ln for ln in body.text.splitlines() if ln.strip()]
    with db() as conn:
        fetch_model(conn, model_id)  # 404 if the model doesn't exist
        tamiya_row = conn.execute("SELECT brand_id FROM brands WHERE name = 'Tamiya'").fetchone()
        tamiya_id = tamiya_row["brand_id"] if tamiya_row else None
        order = conn.execute("SELECT COALESCE(max(sort_order), 0) AS n FROM model_paints WHERE model_id = %s",
                             (model_id,)).fetchone()["n"]
        for line in lines:
            paint, purpose = parse_line(line)
            if not paint:
                continue
            if purpose is None and len(lines) == 1:
                purpose = (body.purpose or "").strip() or None
            brand_id, code, name = resolve(conn, paint, tamiya_id)
            if name is None:
                name = default_name(conn, brand_id, code, paint)
            order += 1
            conn.execute("""
                INSERT INTO model_paints (model_id, brand_id, product_code, paint_name, purpose, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)""", (model_id, brand_id, code, name, purpose, order))
        return fetch_model(conn, model_id)


@router.patch("/model-paints/{paint_id}")
def update_paint(paint_id: int, body: PaintPatch):
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        row = conn.execute("SELECT model_id FROM model_paints WHERE model_paint_id = %s", (paint_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Paint not found.")
        if data:
            write(conn, "model_paints", "model_paint_id", paint_id, data)
        return fetch_model(conn, row["model_id"])


@router.delete("/model-paints/{paint_id}")
def delete_paint(paint_id: int):
    with db() as conn:
        row = conn.execute("DELETE FROM model_paints WHERE model_paint_id = %s RETURNING model_id",
                           (paint_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Paint not found.")
        return fetch_model(conn, row["model_id"])


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
        conn.execute("INSERT INTO brands (name) VALUES ('Hasegawa') ON CONFLICT (name) DO NOTHING")
        brand_id = conn.execute("SELECT brand_id FROM brands WHERE name = 'Hasegawa'").fetchone()["brand_id"]
        cached = conn.execute(
            "SELECT product_code, series FROM product_info WHERE brand_id = %s AND title IS NOT NULL "
            "AND (product_code = %s OR series = %s)",
            (brand_id, f"HSG{value}", value)).fetchone()

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
                found = await run_in_threadpool(hasegawa.fetch, series)
            except tamiya.NotFound:
                continue
            except tamiya.LookupFailed as e:
                raise HTTPException(502, str(e))
            # Typed an item number: the page must say it's that item, or it's the wrong kit.
            if kind == "series" or found["item"] == value:
                info = found
                break
        if info is None:
            raise HTTPException(404, f"Hasegawa has no kit page for {value}.")

        product_code = f"HSG{info['item']}" if info["item"] else f"HSG-{info['series'] or value}"
        description = " · ".join(filter(None, [f"Item no {info['series']} ({info['item']})"
                                               if info["series"] and info["item"] else None,
                                               info["scale"] and f"Scale {info['scale']}",
                                               info["category"]]))
        with db() as conn:
            conn.execute("""
                INSERT INTO product_info (brand_id, product_code, title, series, description,
                                          source_url, image, image_type)
                VALUES (%(b)s, %(code)s, %(title)s, %(series)s, %(desc)s, %(url)s, %(image)s, %(type)s)
                ON CONFLICT (brand_id, product_code) DO UPDATE SET
                    title = EXCLUDED.title, series = EXCLUDED.series, description = EXCLUDED.description,
                    source_url = EXCLUDED.source_url,
                    image = COALESCE(EXCLUDED.image, product_info.image),
                    image_type = COALESCE(EXCLUDED.image_type, product_info.image_type),
                    fetched_at = now()""",
                {"b": brand_id, "code": product_code, "title": info["title"], "series": info["series"],
                 "desc": description or None, "url": info["source_url"], "image": info["image"],
                 "type": info["image_type"]})

    with db() as conn:
        p = conn.execute("""
            SELECT product_info_id, title, series, description, source_url,
                   fetched_at AS photo_updated, (image IS NOT NULL) AS has_image
            FROM product_info WHERE brand_id = %s AND product_code = %s""", (brand_id, product_code)).fetchone()
    scale = re.search(r"Scale (1/\d+)", p["description"] or "")
    return {**p, "brand_id": brand_id, "product_code": product_code, "series_code": p["series"],
            "name": tamiya._nice_name(p["title"]), "scale": scale.group(1) if scale else None,
            "from_cache": bool(cached) and not refresh}


@router.post("/models/{model_id}/wishlist")
def wish_for_missing_paints(model_id: int):
    """Put every paint this model still needs on the wishlist. Paints without a brand + code
    can't be matched to a product, so they're reported rather than added."""
    with db() as conn:
        model = fetch_model(conn, model_id)
        paint_category = conn.execute("SELECT category_id FROM categories WHERE name = 'Paint'").fetchone()
        added, skipped = [], []
        for p in model["paints"]:
            if p["have"] or p["on_wishlist"]:
                continue
            if p["brand_id"] is None or not p["product_code"]:
                skipped.append(p["paint_name"])
                continue
            info = conn.execute("SELECT title, series, description FROM product_info "
                                "WHERE brand_id = %s AND product_code = %s",
                                (p["brand_id"], p["product_code"])).fetchone()
            guess = tamiya.suggest(info["title"], info["series"], info["description"]) \
                if info and info["title"] else {}
            conn.execute("""
                INSERT INTO wishlist (brand_id, product_code, name, category_id, paint_type, finish,
                                      size, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (brand_id, product_code) DO NOTHING""",
                (p["brand_id"], p["product_code"], p["paint_name"], paint_category["category_id"],
                 guess.get("paint_type"), guess.get("finish"), guess.get("size"),
                 f"For {model['name']}: {p['purpose']}" if p["purpose"] else f"For {model['name']}"))
            added.append(p["paint_name"])
        return {"added": added, "skipped": skipped, "model": fetch_model(conn, model_id)}
