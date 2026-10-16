"""Warhammer kits from Good Games (goodgames.py, the shop's official UCP interface).

    GET  /warhammer/search?q=        kits for a name, GW code (59-05) or box barcode
    GET  /warhammer/army?name=       an army's whole range in the shop (in stock and sold out), kept an hour
    GET  /warhammer/armies           the armies of your Warhammer kits (for quick picks)
    GET  /lookup/warhammer/{code}    one kit for a model: name, army, minis, GW code, barcode and box
                                     photo, cached in product_info (brand Games Workshop, product code =
                                     the GW code). `code` = GW code, barcode, a name ({"choices": [...]}
                                     when it isn't exact) or "id:<product number>" (a pick from the choices)
    POST /warhammer/want {id}        add a kit to your models as Wanted (with its photo)

Each kit carries `my_model` ({model_id, status}) when one of your models has its code.
"""
import re
import time

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import gameology, goodgames
from .db import db, ensure_brand
from .models import ModelIn, add_model
from .products import UPSERT_INFO

router = APIRouter(prefix="/api", tags=["warhammer"])

RANGE_FOR = 3600                       # seconds an army's range is kept
_ranges: dict[str, tuple[float, list[dict]]] = {}
BRAND = "Games Workshop"
# Offered as quick picks next to your own armies.
ARMIES = ["Adeptus Mechanicus", "Space Marines", "Astra Militarum", "Adepta Sororitas", "Adeptus Custodes",
          "Chaos Space Marines", "Death Guard", "Necrons", "Orks", "T'au Empire", "Tyranids", "Aeldari",
          "Leagues of Votann", "Stormcast Eternals", "Skaven", "Seraphon", "Soulblight Gravelords"]


class WantIn(BaseModel):
    id: str = Field(pattern=r"^\d{1,20}$")


def product_code_for(k: dict) -> str:
    return k["code"] or k["barcode"] or f"GG{k['id']}"


def _shop(fn, *args):
    try:
        return fn(*args)
    except goodgames.ShopError as e:
        raise HTTPException(502, str(e))


def _with_mine(kits: list[dict]) -> list[dict]:
    with db() as conn:
        rows = conn.execute("""
            SELECT m.model_id, m.status, m.product_code FROM models m JOIN brands b ON b.brand_id = m.brand_id
            WHERE b.name = %s AND m.product_code IS NOT NULL""", (BRAND,)).fetchall()
    mine = {r["product_code"]: {"model_id": r["model_id"], "status": r["status"]} for r in rows}
    for k in kits:
        k["product_code"] = product_code_for(k)
        k["my_model"] = mine.get(k["product_code"]) or (mine.get(k["barcode"]) if k["barcode"] else None)
    return kits


@router.get("/warhammer/search")
async def search(q: str = Query(min_length=2, max_length=120)):
    kits = await run_in_threadpool(_shop, goodgames.find, q)
    return {"kits": _with_mine(kits[:30])}


@router.get("/warhammer/army")
async def army(name: str = Query(min_length=2, max_length=60), refresh: bool = False):
    key = name.strip().lower()
    held = _ranges.get(key)
    if held and not refresh and time.time() - held[0] < RANGE_FOR:
        kits, fetched = held[1], held[0]
    else:
        kits = await run_in_threadpool(_shop, goodgames.army_range, name)
        fetched = time.time()
        for old in [k for k, (t, _) in _ranges.items() if fetched - t >= RANGE_FOR]:
            del _ranges[old]                      # (kept small: only ranges still fresh)
        _ranges[key] = (fetched, kits)
    kits = _with_mine([dict(k) for k in kits])
    return {"army": name.strip(), "kits": kits, "total": len(kits), "in_stock": sum(k["available"] for k in kits),
            "yours": sum(1 for k in kits if k["my_model"]), "fetched_at": fetched}


@router.get("/warhammer/armies")
def armies():
    with db() as conn:
        yours = [r["faction"] for r in conn.execute(
            "SELECT DISTINCT faction FROM models WHERE hobby = 'Warhammer' AND faction IS NOT NULL ORDER BY faction")]
    return {"yours": yours, "others": [a for a in ARMIES if a.lower() not in {y.lower() for y in yours}]}


def store(brand: str, code: str, k: dict, series: str | None, description: str) -> int:
    """Keep a Good Games product in product_info under your brand + code: its title, the shop's page,
    the box photo (600 px, Shopify's CDN only) and its barcode (if no other product has it, so
    scanning the box finds it). Shared with the Gundam tab (gundam.py)."""
    image, image_type = (None, None)
    if k["image"]:
        image, image_type = gameology.photo({"image": k["image"] + ("&" if "?" in k["image"] else "?") + "width=600"})
    with db() as conn:
        brand_id = ensure_brand(conn, brand)
        conn.execute(UPSERT_INFO, {"brand_id": brand_id, "code": code, "title": k["title"], "series": series,
                                   "description": description, "source_url": k["url"], "image": image,
                                   "image_type": image_type, "kit_paints": None})
        if k["barcode"]:
            conn.execute("""
                UPDATE product_info SET barcode = %(b)s WHERE brand_id = %(id)s AND product_code = %(c)s
                AND NOT EXISTS (SELECT 1 FROM product_info WHERE barcode = %(b)s)""",
                         {"b": k["barcode"], "id": brand_id, "c": code})
    return brand_id


def shop_price(k: dict) -> str | None:
    return k["price"] is not None and f"Good Games ${k['price']:.2f}{'' if k['available'] else ' (sold out)'}" or None


def _store(k: dict) -> tuple[int, str]:
    code = product_code_for(k)
    description = " · ".join(filter(None, [k["code"] and f"GW {k['code']}", k["army"],
                                           k["figures"] and f"{k['figures']} minis", shop_price(k)]))
    brand_id = store(BRAND, code, k, k["army"], description)
    if k.get("units"):                     # what's in the box, for setting up its minis (minis.py)
        with db() as conn:
            conn.execute("UPDATE product_info SET kit_units = %s WHERE brand_id = %s AND product_code = %s",
                         (Jsonb(k["units"]), brand_id, code))
    return brand_id, code


def _found(brand_id: int, code: str, k: dict | None, cached: bool) -> dict:
    with db() as conn:
        p = conn.execute("""
            SELECT product_info_id, title, series, description, source_url, barcode,
                   fetched_at AS photo_updated, (image IS NOT NULL) AS has_image
            FROM product_info WHERE brand_id = %s AND product_code = %s""", (brand_id, code)).fetchone()
    figures = re.search(r"(\d+) minis", p["description"] or "")
    return {**p, "brand_id": brand_id, "product_code": code, "faction": p["series"],
            "name": k["name"] if k else goodgames.name_of(p["title"], p["series"]),
            "figures": k["figures"] if k else (int(figures.group(1)) if figures else None),
            "price": k and k["price"], "available": k and k["available"], "from_cache": cached}


def _pick(code: str):
    """The product for a lookup: an id pick, else an exact code / barcode match; several choices for a name."""
    if code.startswith("id:"):
        p = goodgames.get(code[3:])
        if not p:
            raise HTTPException(404, "Good Games doesn't have that product any more.")
        return goodgames.kit(p)
    kits = goodgames.find(code)
    exact = [k for k in kits if code in (k["code"], k["barcode"])]
    if exact:
        return exact[0]
    if re.fullmatch(r"\d{2,3}-\d{1,3}|\d{13}", code):
        raise HTTPException(404, f"Good Games has no kit with the code {code}.")
    kits = [k for k in kits if k["is_kit"]]
    words = re.findall(r"[a-z0-9]+", code.lower())
    every_word = [k for k in kits if all(w in k["title"].lower() for w in words)]
    kits = every_word or kits                 # "combat patrol adeptus mechanicus": not the other armies' patrols
    if not kits:
        raise HTTPException(404, f"Good Games has no Warhammer kit matching “{code}”.")
    return kits if len(kits) > 1 else kits[0]


@router.get("/lookup/warhammer/{code:path}")
async def lookup(code: str, refresh: bool = False):
    code = code.strip()
    if len(code) < 2:
        raise HTTPException(422, "Type the kit's name, its Games Workshop code (e.g. 59-05) or the box barcode.")
    if not refresh and not code.startswith("id:"):
        with db() as conn:
            brand_id = ensure_brand(conn, BRAND)
            cached = conn.execute("SELECT product_code FROM product_info WHERE brand_id = %s AND title IS NOT NULL "
                                  "AND (product_code = %s OR barcode = %s)", (brand_id, code, code)).fetchone()
        if cached:
            return _found(brand_id, cached["product_code"], None, True)
    picked = await run_in_threadpool(_shop, _pick, code)
    if isinstance(picked, list):
        return {"choices": _with_mine(picked[:12])}
    brand_id, product_code = await run_in_threadpool(_store, picked)
    return _found(brand_id, product_code, picked, False)


@router.post("/warhammer/want", status_code=201)
async def want(body: WantIn):
    """Add a kit from the shop to your models as Wanted."""
    p = await run_in_threadpool(_shop, goodgames.get, body.id)
    if not p:
        raise HTTPException(404, "Good Games doesn't have that product any more.")
    k = goodgames.kit(p)
    if _with_mine([dict(k)])[0]["my_model"]:
        raise HTTPException(409, f"{k['name']} is already in your models.")
    brand_id, code = await run_in_threadpool(_store, k)
    return add_model(ModelIn(name=k["name"], hobby="Warhammer", status="Wanted", brand_id=brand_id, product_code=code,
                             faction=k["army"], figures=k["figures"] or 1))
