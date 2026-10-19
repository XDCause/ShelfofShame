"""Stedi (https://www.steditools.com): model tools - nippers, knives, sanding sticks, kits - that the user builds
Gunpla with. A Shopify store with the same official, read-only product search as Good Games and Blue Sky
(ucp.py: search_catalog). Checked 2026-10-19: robots.txt allows product pages; its notes to "agents" (install a
shopping skill, check out for the buyer...) are ignored - this only ever searches the public catalogue.

Every product has a model code as its SKU (MS-106 single-blade nipper, TZ-01 beginner's kit); a product with
several versions (a handle colour, a blade) has a variant per SKU. Prices are the store's, in US dollars.

    search(words)  -> [tool]   a tool = {sku, name, version, price_usd, available, url, image, description}
    by_sku(code)   -> tool or None (their search for the code, then the variant whose SKU is exactly it)
    sku_in(text)   -> "MS-106" from "ms106", "MS 106" or a product link (.../stedi-ms-106-precision-...), else None
"""
import html
import re

from . import ucp

STORE = ucp.Store("Stedi", "https://www.steditools.com")
ShopError = ucp.ShopError
SKU = re.compile(r"(?i)\b([A-Z]{2,3})[\s-]?(\d{2,4})([A-Z]?)\b")      # MS-106, MS-106B


def _call(tool: str, catalog: dict) -> dict:
    """One request to Stedi's product search (tests and the walk-through replace this)."""
    return STORE.call(tool, catalog)


def sku_in(text: str | None) -> str | None:
    t = (text or "").strip()
    if t.startswith(STORE.pages):
        t = t.rsplit("/", 1)[-1].replace("-", " ")
    m = SKU.search(t)
    return f"{m.group(1).upper()}-{m.group(2)}{m.group(3).upper()}" if m else None


def _plain(raw: str | None, limit: int = 1500) -> str | None:
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)          # "A <b>tool</b>." -> "A tool."
    return text[:limit] or None


def nice_name(title: str) -> str:
    """'stedi MS-106 Precision Single Blade Nipper for ...' -> 'Stedi MS-106 Precision Single Blade Nipper for ...'
    (their titles come in lower case, with doubled spaces and full-width commas)."""
    t = re.sub(r"\s+", " ", (title or "").replace("，", ", ")).strip()
    return re.sub(r"(?i)^stedi\b", "Stedi", t)[:200]


def _image(*sources) -> str | None:
    for media in sources:
        for m in media or []:
            url = str(m.get("url") or "")
            if url.startswith("https://cdn.shopify.com/"):
                return url
    return None


def tools(p: dict) -> list[dict]:
    """One catalogue product -> a tool per variant (each its own SKU)."""
    out = []
    for v in p.get("variants") or []:
        raw = str(v.get("sku") or "").strip()
        sku = sku_in(raw) or raw.upper()[:30]          # their code, tidied; one in another shape kept as it is
        if not sku:
            continue
        amount = (v.get("price") or {}).get("amount")
        version = str(v.get("title") or "").strip()
        out.append({
            "sku": sku, "name": nice_name(p.get("title") or ""),
            "version": None if version.lower() in ("", "default title") else version[:120],
            "price_usd": int(amount) / 100 if str(amount or "").isdigit() or isinstance(amount, int) else None,   # cents
            "available": str((v.get("availability") or {}).get("available")).lower() == "true",
            "url": p.get("url") if str(p.get("url") or "").startswith(STORE.pages) else None,
            "image": _image(v.get("media"), p.get("media")),
            "description": _plain((v.get("description") or p.get("description") or {}).get("html")),
        })
    return out


def search(words: str, limit: int = 20) -> list[dict]:
    found = _call("search_catalog", {"query": words.strip()[:100]})
    out, seen = [], set()
    for p in found.get("products") or []:
        for t in tools(p):
            if t["sku"] not in seen:
                seen.add(t["sku"])
                out.append(t)
    return out[:limit]


def by_sku(code: str) -> dict | None:
    sku = sku_in(code)
    if not sku:
        return None
    return next((t for t in search(sku) if t["sku"] == sku), None)
