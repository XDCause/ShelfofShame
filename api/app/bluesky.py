"""Blue Sky Athletics (https://blueskyathletics.com.au): the Australian stockist of Li-Ning's Way of Wade
basketball shoes (wayofwade.com.au sends you there) - also good court shoes for volleyball. A Shopify store
with the same official, read-only product search as Good Games (ucp.py): search_catalog, get_product.

    shoe(product) -> {id, name, brand, price (AUD), available, url, image, sizes: [in stock], all_sizes}
"""
import re

from . import ucp

STORE = ucp.Store("Blue Sky Athletics", "https://blueskyathletics.com.au")
ShopError = ucp.ShopError
BRAND = "Li-Ning Way of Wade"


def _call(tool: str, catalog: dict) -> dict:
    """One request to Blue Sky's product search (tests replace this)."""
    return STORE.call(tool, catalog)


def _money(p: dict) -> float | None:
    v = (p.get("variants") or [{}])[0]
    amount = (v.get("price") or {}).get("amount") or ((p.get("price_range") or {}).get("min") or {}).get("amount")
    return int(amount) / 100 if amount not in (None, "") else None


def _size(variant: dict) -> str | None:
    for o in variant.get("options") or variant.get("selected_options") or []:
        if "size" in str(o.get("name", "")).lower():
            return str(o.get("value") or o.get("label") or "").strip() or None
    title = str(variant.get("title") or "")
    return title if re.fullmatch(r"(US|AU|UK|EU)?\s*[\d.]+[A-Za-z ]*", title) else None


def _available(variant: dict) -> bool:
    return str((variant.get("availability") or {}).get("available")).lower() == "true"


def shoe(p: dict) -> dict:
    variants = p.get("variants") or []
    media = next((m.get("url") for m in (p.get("media") or []) if str(m.get("url", "")).startswith("https://cdn.shopify.com/")), None)
    sizes = [s for s in (_size(v) for v in variants if _available(v)) if s]
    return {
        "id": str(p.get("id", "")).rsplit("/", 1)[-1],
        "name": (p.get("title") or "").replace("�", "–").strip(),
        "brand": BRAND if re.search(r"(?i)\bwade\b", p.get("title") or "") else None,
        "price": _money(p),
        "available": any(_available(v) for v in variants),
        "url": p.get("url") if str(p.get("url") or "").startswith(STORE.pages) else None,
        "image": media,
        "sizes": list(dict.fromkeys(sizes)),
        "all_sizes": list(dict.fromkeys(s for s in (_size(v) for v in variants) if s)),
        "kind": "Shoes" if any("shoe" in str(o.get("name", "")).lower() for o in p.get("options") or []) else None,
    }


def search(words: str, limit: int = 20) -> list[dict]:
    """In-stock first, then sold out (the search answers one or the other)."""
    out = []
    for available in (True, False):
        r = _call("search_catalog", {"query": words, "filters": {"available": available}, "pagination": {"limit": limit}})
        # The search lists only some of a product's sizes, so which search found it says if it's in stock.
        out += [{**shoe(p), "available": available} for p in r.get("products") or []]
    seen, unique = set(), []
    for s in out:
        if s["id"] not in seen:
            seen.add(s["id"])
            unique.append(s)
    return unique


def get(product_id: str) -> dict | None:
    if not str(product_id).isdigit():
        return None
    try:
        r = _call("get_product", {"id": f"gid://shopify/Product/{product_id}"})
    except ShopError as e:
        if "not found" in str(e).lower():
            return None
        raise
    return shoe(r["product"]) if r.get("product") else None
