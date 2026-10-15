"""Good Games (https://www.goodgames.com.au): an Australian games shop (a Shopify store) with the
whole Warhammer range - Games Workshop's code in each title "(59-05)", the army as a tag
("Faction_Adeptus Mechanicus"), the box barcode, what's in the box, price and stock. Used for
Warhammer kits (warhammer.com answers apps with a CAPTCHA, so it isn't used).

The shop is read through its OFFICIAL agent interface, the Universal Commerce Protocol (UCP) over
MCP - what its robots.txt and agents.md ask apps to use instead of scraping pages:

    POST /api/ucp/mcp  {"method": "tools/call", "params": {"name": <tool>, "arguments": ...}}
        search_catalog  {query, filters: {available}, pagination: {limit, cursor}}
                        (available true = in stock only, false = sold out only: both are asked)
        get_product     {id: "gid://shopify/Product/<n>"}

Every call names this app: meta.ucp-agent.profile = the URL of ucp-agent.json (in this repo, served
as JSON by jsDelivr from the git tag ucp-agent-1), which asks only for the read-only catalogue capabilities. The app never makes
carts or checkouts - buying happens on the shop's own site.
"""
import html
import json
import os
import re
import time

import httpx

MCP = "https://www.goodgames.com.au/api/ucp/mcp"
# A fixed version (git tag) of ucp-agent.json: jsDelivr serves a tag as JSON straight away and for good
# (a branch address is cached for hours after a change). A new version of the file = a new tag here.
PROFILE = "https://cdn.jsdelivr.net/gh/XDCause/ShelfofShame@ucp-agent-1/ucp-agent.json"
HEADERS = {"User-Agent": "OffTheClock/1.0 (personal hobby tracker; https://github.com/XDCause/ShelfofShame)",
           "Content-Type": "application/json", "Accept": "application/json"}
TIMEOUT = 30
PAUSE = 0.5            # between the pages of one search
PAGE = 50
GW_CODE = re.compile(r"\(\s*(\d{2,3}-\d{1,3})\s*\)")
# Things the shop sells for an army that aren't kits to build.
NOT_KITS = re.compile(
    r"(?i)\bcodex\b|data ?cards?|datasheet|\bindex\b|\bdice\b|collectibles|\bnovel\b|black library|\(BL\d+\)|"
    r"\bjumper\b|\bjacket\b|baubles|paint set|\bbook\b|battletome|army list|\brpg\b|munchkin|\bannual\b|"
    r"\bcomm:|\btokens?\b|transfer sheet|\bt-?shirt\b|\bmug\b|art of")


class ShopError(Exception):
    """A message for the user: Good Games unreachable, or it said no."""


def profile() -> str:
    """The URL of this app's UCP agent profile (UCP_PROFILE overrides it, e.g. to try a new version)."""
    return os.environ.get("UCP_PROFILE") or PROFILE


def _call(tool: str, catalog: dict) -> dict:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": tool, "arguments": {"meta": {"ucp-agent": {"profile": profile()}}, "catalog": catalog}}}
    try:
        r = httpx.post(MCP, json=body, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise ShopError(f"Couldn't reach Good Games ({e.__class__.__name__}).") from None
    if r.status_code == 429:
        raise ShopError("Good Games asked us to slow down - try again in a minute.")
    try:
        reply = r.json()
    except ValueError:
        raise ShopError(f"Good Games didn't answer (HTTP {r.status_code}).") from None
    if "error" in reply:
        err = reply["error"]
        detail = (err.get("data") or {}).get("content") if isinstance(err.get("data"), dict) else err.get("data")
        raise ShopError(f"Good Games said no: {err.get('message')}{f' ({detail})' if detail else ''}.")
    try:
        return json.loads(reply["result"]["content"][0]["text"])
    except (KeyError, IndexError, ValueError):
        raise ShopError("Good Games sent something unexpected.") from None


def _search(query: str, available: bool, pages: int) -> list[dict]:
    out, cursor = [], None
    for page in range(pages):
        if page:
            time.sleep(PAUSE)
        r = _call("search_catalog", {"query": query, "filters": {"available": available},
                                     "pagination": {"limit": PAGE, **({"cursor": cursor} if cursor else {})}})
        out += r.get("products") or []
        more = r.get("pagination") or {}
        cursor = more.get("cursor")
        if not (str(more.get("has_next_page")).lower() == "true" and cursor):
            break
    return out


def search(query: str, pages: int = 1) -> list[dict]:
    """Products matching the words: in stock ones, then sold-out ones (each product once)."""
    seen: dict[str, dict] = {}
    for available in (True, False):
        for p in _search(query, available, pages):
            seen.setdefault(p["id"], p)
        time.sleep(PAUSE)
    return list(seen.values())


def get(product_id: str) -> dict | None:
    """One product by its number (or full Shopify id). get_product leaves out the tags (the army is
    one), so the same product is then found by its barcode / SKU in a search, which has them."""
    gid = product_id if product_id.startswith("gid://") else f"gid://shopify/Product/{int(product_id)}"
    try:
        p = _call("get_product", {"id": gid}).get("product")
    except ShopError as e:
        if "not found" in str(e).lower():
            return None
        raise
    if p and p.get("tags") is None:
        v = (p.get("variants") or [{}])[0]
        sku = str(v.get("sku") or "")
        if sku:
            time.sleep(PAUSE)
            available = str((v.get("availability") or {}).get("available")).lower() == "true"
            same = next((x for x in _search(sku, available, 1) if x["id"] == p["id"]), None)
            if same:
                return {**p, "tags": same.get("tags") or []}
    return p


def _text(html_text: str | None) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", html_text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _figures(text: str) -> int | None:
    """How many minis: "Contains 1x Techpriest Enginseer, 1x Onager..., 10x Skitarii" -> 12 (vehicles
    count too); else "10 Miniatures" / "contains 5 models". Brackets are skipped: "3x Serberys
    Sulphurhounds (which can alternatively be built as 3x Serberys Raiders)" is 3, not 6."""
    text = re.sub(r"\([^()]*\)", " ", text)
    parts = [int(n) for n in re.findall(r"(?i)\b(\d{1,3})\s*x\s+[A-Z]", text)]
    if parts:
        return sum(parts)
    m = re.search(r"(?i)\b(\d{1,3})\s+(?:plastic\s+|resin\s+)?(?:miniatures?|models?|figures?)\b", text)
    return int(m.group(1)) if m else None


def name_of(title: str, army: str | None) -> str:
    """"Adeptus Mechanicus - Onager Dunecrawler (59-13)" -> "Onager Dunecrawler";
    "Combat Patrol - Adeptus Mechanicus (59-05)" -> "Combat Patrol: Adeptus Mechanicus"."""
    name = GW_CODE.sub("", title).strip()
    if army:
        m = re.match(rf"(?i)^{re.escape(army)}\s*[-–:]\s*(.+)$", name)
        if m:
            return m.group(1).strip()
    return re.sub(r"\s+[-–]\s+", ": ", name, count=1)


def kit(p: dict) -> dict:
    """A product as the app uses it."""
    v = (p.get("variants") or [{}])[0]
    title = (p.get("title") or "").replace("�", "–").strip()       # the shop has some mis-encoded dashes
    code = GW_CODE.search(title)
    army = next((t.split("_", 1)[1].strip() for t in p.get("tags") or [] if t.startswith("Faction_")), None)
    sku = str(v.get("sku") or "")
    media = (v.get("media") or p.get("media") or [{}])[0].get("url")
    price = (v.get("price") or {}).get("amount")
    text = _text((p.get("description") or {}).get("html"))
    return {
        "id": p["id"].rsplit("/", 1)[-1],
        "title": title,
        "name": name_of(title, army),
        "code": code.group(1) if code else None,
        "army": army,
        "figures": _figures(text),
        "contents": text[:600] or None,
        "barcode": sku if re.fullmatch(r"\d{13}", sku) else None,
        "price": int(price) / 100 if price not in (None, "") else None,
        "available": str((v.get("availability") or {}).get("available")).lower() == "true",
        "url": p.get("url"),
        "image": media if media and media.startswith("https://cdn.shopify.com/") else None,
        "is_kit": not NOT_KITS.search(title),
    }


def _code_order(k: dict):
    nums = [int(n) for n in re.findall(r"\d+", k["code"] or "999-999")]
    return (nums, k["title"])


def army_range(army: str) -> list[dict]:
    """Every kit the shop lists for an army (in stock and sold out), by Games Workshop code: products
    tagged with the army, plus kits with the army in their title and a GW code (some aren't tagged)."""
    want = army.strip().lower()
    kits = [kit(p) for p in search(army, pages=4)]
    mine = [k for k in kits if k["is_kit"] and ((k["army"] or "").lower() == want
                                                or (k["code"] and want in k["title"].lower()))]
    return sorted(mine, key=_code_order)


def find(query: str) -> list[dict]:
    """Kits for a name, GW code or box barcode: the best match first (code or barcode exact, then
    titles with every word), kits before other things, in stock first."""
    q = query.strip()
    kits = [kit(p) for p in search(q)]
    words = re.findall(r"[a-z0-9]+", q.lower())

    def rank(k):
        title = k["title"].lower()
        exact = q in (k["code"], k["barcode"])
        return (not exact, not k["is_kit"], not all(w in title for w in words), not k["available"], _code_order(k))
    return sorted(kits, key=rank)
