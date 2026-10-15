"""Gundam kits (Gunpla) from Good Games - the same official UCP interface as the Warhammer tab
(goodgames.py). Bandai is the only maker, so this is the Gundam tab's whole shop:

    GET  /gundam/kits?q=       kits for a name, box code (G5057403) or barcode, in stock and sold out;
                               no q = every Gundam kit in stock now. Kept an hour in memory.
    POST /gundam/want {id}     add one to your models as a Wanted Gundam kit (grade, scale, box photo)

Kits carry your box code (G50xxxxx from the Bandai Spirits barcode - the same code the HLJ lookup
gives, so kits you already have show as yours) and `my_model`.
"""
import time

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from . import goodgames
from .db import db
from .models import ModelIn, add_model
from .warhammer import WantIn, _shop, shop_price, store

router = APIRouter(prefix="/api", tags=["gundam"])

BRAND = "Bandai"
KEEP_FOR = 3600
_found: dict[str, tuple[float, list[dict]]] = {}


def code_for(k: dict) -> str:
    return k["code"] or k["barcode"] or f"GG{k['id']}"


def _with_mine(kits: list[dict]) -> list[dict]:
    with db() as conn:
        rows = conn.execute("""
            SELECT m.model_id, m.status, m.product_code, pi.barcode FROM models m
            JOIN brands b ON b.brand_id = m.brand_id
            LEFT JOIN product_info pi ON pi.brand_id = m.brand_id AND pi.product_code = m.product_code
            WHERE b.name = %s AND m.product_code IS NOT NULL""", (BRAND,)).fetchall()
    mine = {}
    for r in rows:
        mine[r["product_code"].upper()] = {"model_id": r["model_id"], "status": r["status"]}
        if r["barcode"]:
            mine[r["barcode"]] = mine[r["product_code"].upper()]
    for k in kits:
        k["product_code"] = code_for(k)
        k["my_model"] = mine.get(k["product_code"].upper()) or (mine.get(k["barcode"]) if k["barcode"] else None)
    return kits


@router.get("/gundam/kits")
async def kits(q: str | None = Query(None, max_length=120), refresh: bool = False):
    key = (q or "").strip().lower()
    held = _found.get(key)
    if held and not refresh and time.time() - held[0] < KEEP_FOR:
        found, fetched = held[1], held[0]
    else:
        found = await run_in_threadpool(_shop, goodgames.gunpla_search, q)
        fetched = time.time()
        for old in [k for k, (t, _) in _found.items() if fetched - t >= KEEP_FOR]:
            del _found[old]                       # (kept small: only searches still fresh)
        _found[key] = (fetched, found)
    found = _with_mine([dict(k) for k in found])
    return {"query": q.strip() if q else None, "kits": found, "total": len(found),
            "in_stock": sum(k["available"] for k in found), "fetched_at": fetched}


@router.post("/gundam/want", status_code=201)
async def want(body: WantIn):
    """Add a Gundam kit from the shop to your models as Wanted."""
    p = await run_in_threadpool(_shop, goodgames.get, body.id)
    if not p:
        raise HTTPException(404, "Good Games doesn't have that product any more.")
    k = goodgames.gunpla(p)
    if _with_mine([dict(k)])[0]["my_model"]:
        raise HTTPException(409, f"{k['name']} is already in your models.")
    code = code_for(k)
    description = " · ".join(filter(None, [k["grade"], k["scale"], shop_price(k)]))
    brand_id = await run_in_threadpool(store, BRAND, code, k, k["grade"], description)
    return add_model(ModelIn(name=k["name"], hobby="Gundam", status="Wanted", brand_id=brand_id, product_code=code,
                             grade=k["grade"], scale=k["scale"]))
