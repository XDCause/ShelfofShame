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
import re

from . import ucp
from .hlj import grade_of, product_code_for

STORE = ucp.Store("Good Games", "https://www.goodgames.com.au")     # its official product search (ucp.py)
MCP = STORE.mcp
SHOP_PAGES = STORE.pages
ShopError = ucp.ShopError
profile = ucp.profile
PAGE = 50
GW_CODE = re.compile(r"\(\s*(\d{2,3}-\d{1,3})\s*\)")
# Things the shop sells for an army that aren't kits to build.
NOT_KITS = re.compile(
    r"(?i)\bcodex\b|data ?cards?|datasheet|\bindex\b|\bdice\b|collectibles|\bnovel\b|black library|\(BL\d+\)|"
    r"\bjumper\b|\bjacket\b|baubles|paint set|\bbook\b|battletome|army list|\brpg\b|munchkin|\bannual\b|"
    r"\bcomm:|\btokens?\b|transfer sheet|\bt-?shirt\b|\bmug\b|art of|\bcitadel\b|\bpaints?\b|\bspray\b|"
    r"\bprimer\b|brush")




def _call(tool: str, catalog: dict) -> dict:
    """One request to Good Games' product search (tests replace this)."""
    return STORE.call(tool, catalog)


def _search(query: str, available: bool, pages: int) -> list[dict]:
    out, cursor = [], None
    for page in range(pages):
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
    return list(seen.values())


def get(product_id: str) -> dict | None:
    """One product by its number (or full Shopify id). get_product leaves out the tags (the army is
    one), so the same product is then found by its barcode / SKU in a search, which has them."""
    number = product_id.rsplit("/", 1)[-1]
    if not re.fullmatch(r"\d{1,20}", number):
        return None
    gid = f"gid://shopify/Product/{number}"
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


# A unit's name: capitalised words, ending before filler words ("... Vanguard All models come unpainted").
_NOT_NAME = r"(?i:and|which|with|or|this|all|each|every|the|plus|includes?|comes?|supplied|models?|miniatures?)\b"
_NAME = r"([A-Z][A-Za-z'’/-]*(?:[ \t](?!" + _NOT_NAME + r")[A-Za-z][A-Za-z'’/-]*)*)"
UNIT = re.compile(r"(?<!\d)(\d{1,3})\s*x\s*" + _NAME)
UNIT_AFTER_AND = re.compile(r"(?:,|\band)\s+(\d{1,3})\s+" + _NAME)       # "..., 10x Skitarii and 3 Kataphron Servitors"
# Alternative builds aren't extra minis: "which can alternatively be built as 3x ...", "with an alternate assembly of 1x ...".
ALTERNATIVE = re.compile(r"(?i)\b(?:which\s+\w+\s+|with\s+an\s+)?alternat\w*.*?(?=[,.;]|\s[-–]\s|-\s*\d|$)")


def units_of(text: str | None) -> list[dict]:
    """What's in the box: "Contains 1x Techpriest Enginseer, 10x Skitarii Rangers/Vanguard" ->
    [{"unit": "Techpriest Enginseer", "count": 1}, {"unit": "Skitarii Rangers/Vanguard", "count": 10}].
    Brackets and alternative builds are skipped; a unit named twice is counted once. [] when the
    shop's text doesn't list the minis like that (then they're added by hand)."""
    text = ALTERNATIVE.sub(" ", re.sub(r"\([^()]*\)", ", ", text or ""))      # a bracket ends a unit's name
    text = re.sub(r"[ \t]+", " ", text)
    found = {}
    for pattern in (UNIT, UNIT_AFTER_AND):
        if pattern is UNIT_AFTER_AND and not found:
            break                                  # "1 Citadel 105mm base, 3 transfer sheets": not a minis list
        for n, unit in pattern.findall(text):
            unit = unit.strip(" -–/")
            if unit and 0 < int(n) <= 100:
                found.setdefault(unit, int(n))
    return [{"unit": u, "count": n} for u, n in found.items()]


def name_of(title: str, army: str | None) -> str:
    """"Adeptus Mechanicus - Onager Dunecrawler (59-13)" -> "Onager Dunecrawler";
    "Combat Patrol - Adeptus Mechanicus (59-05)" -> "Combat Patrol: Adeptus Mechanicus"."""
    name = GW_CODE.sub("", title).strip()
    if army:
        m = re.match(rf"(?i)^{re.escape(army)}\s*[-–:]\s*(.+)$", name)
        if m:
            return m.group(1).strip()
    return re.sub(r"\s+[-–]\s+", ": ", name, count=1)


def base(p: dict) -> dict:
    """What every product has: id, title, barcode, price, stock, link, picture, tags, description."""
    v = (p.get("variants") or [{}])[0]
    sku = str(v.get("sku") or "")
    media = (v.get("media") or p.get("media") or [{}])[0].get("url")
    price = (v.get("price") or {}).get("amount")
    return {
        "id": p["id"].rsplit("/", 1)[-1],
        "title": (p.get("title") or "").replace("\ufffd", "–").strip(),     # the shop has some mis-encoded dashes
        "barcode": sku if re.fullmatch(r"\d{13}", sku) else None,
        "price": int(price) / 100 if price not in (None, "") else None,
        "available": str((v.get("availability") or {}).get("available")).lower() == "true",
        "url": p["url"] if str(p.get("url") or "").startswith(SHOP_PAGES) else None,       # the shop's own pages only
        "image": media if media and media.startswith("https://cdn.shopify.com/") else None,
        "tags": p.get("tags") or [],
        "text": _text((p.get("description") or {}).get("html")),
    }


def kit(p: dict) -> dict:
    """A product as a Warhammer kit: GW code, army, minis."""
    k = base(p)
    tags, text = k.pop("tags"), k.pop("text")
    code = GW_CODE.search(k["title"])
    army = next((t.split("_", 1)[1].strip() for t in tags if t.startswith("Faction_")), None)
    units = units_of(text)
    return {**k, "name": name_of(k["title"], army), "code": code.group(1) if code else None, "army": army,
            "figures": sum(u["count"] for u in units) or _figures(text), "units": units, "contents": text[:600] or None,
            "is_kit": not NOT_KITS.search(k["title"])}


def _code_order(k: dict):
    nums = [int(n) for n in re.findall(r"\d+", k["code"] or "999-999")]
    return (nums, k["title"])


def army_range(army: str) -> list[dict]:
    """Every kit the shop lists for an army (in stock and sold out), by Games Workshop code: products
    tagged with the army, plus kits with the army in their title and a GW code (some aren't tagged)."""
    want = army.strip().lower()
    kits = [kit(p) for p in search(army, pages=3)]        # 150 results each for in stock / sold out
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


# ---- Gunpla (Bandai's Gundam kits) --------------------------------------------------------------

# Gundam things the shop sells that aren't kits to build: the card game, ready-made figures, markers, tools.
NOT_GUNPLA = re.compile(
    r"(?i)card game|\bdeck\b|booster|\btcg\b|sleeves?|playmat|assemble|gundam universe|robot spirits|ensemble|"
    r"figuarts|metal build|chogokin|\bmarkers?\b|action base|nippers?|\btool|\bdecals?\b|\bpaint\b|\bbook\b|t-?shirt")
BANDAI_BARCODES = ("4573102", "4549660", "4543112")       # Bandai Spirits, and the older Bandai prefixes


def gunpla_name(title: str) -> str:
    """"Hg 1-144 Gundam Aerial Rebuild" -> "Gundam Aerial Rebuild"; "G5063530 1/100 Mg Mbf-02Vv Gundam Astray
    Turn Red" -> "MBF-02VV Gundam Astray Turn Red"; "Gundam HG MSN-06S SINANJU Mobile Suit" -> "MSN-06S
    Sinanju" (the grade and scale have their own fields)."""
    name = re.sub(r"(?i)\b(bandai|g50\d{5}|1\s*[/-]\s*\d{2,3}(\s*scale(\s*kit)?)?|mobile suit)\b", " ", title)
    name = re.sub(r"(?i)^\s*(?:\S+\s+)?\b(HG\w*|RG|MG\w*|PG\w*|EG|SD\w*|RE/100|FM|ENTRY GRADE|MASTER GRADE|"
                  r"REAL GRADE|HIGH GRADE|PERFECT GRADE)\b",
                  lambda m: re.sub(r"(?i)^\s*gundam\s*$", "", m.group(0)[:m.start(1) - m.start(0)]), name, count=1)
    words = []
    for w in name.split():
        if re.fullmatch(r"[A-Za-z]+\d[\w-]*|[A-Za-z]+-[\w-]*\d[\w-]*", w):
            words.append(w.upper())                   # model numbers: Mbf-02Vv -> MBF-02VV
        elif w.isupper() and len(w) > 3 and w.isalpha():
            words.append(w.capitalize())              # SINANJU -> Sinanju
        else:
            words.append(w)
    return re.sub(r"\s+", " ", " ".join(words)).strip(" -–:")


def gunpla(p: dict) -> dict:
    """A product as a Gunpla kit: grade, scale, your box code (G5057403 from the barcode)."""
    k = base(p)
    tags = k.pop("tags")
    k.pop("text")
    scale = next((t.split("_", 1)[1] for t in tags if t.startswith("Scale_")), None)
    if not scale:
        m = re.search(r"\b1\s*[/-]\s*(\d{2,3})\b", k["title"])
        scale = f"1/{m.group(1)}" if m else None
    code = product_code_for(k["barcode"], "") if k["barcode"] else ""
    is_bandai = bool(k["barcode"] and k["barcode"].startswith(BANDAI_BARCODES)) or "Bandai" in tags
    return {**k, "name": gunpla_name(k["title"]), "grade": grade_of(k["title"]), "scale": scale,
            "code": code or None,
            "is_kit": not NOT_GUNPLA.search(k["title"]) and (is_bandai or "Model" in tags or "Model-DIY-Kit" in tags)}


def gunpla_search(query: str | None) -> list[dict]:
    """Gunpla for some words (in stock and sold out), or - no words - every Gundam kit in stock now.
    In stock first, then by grade and name."""
    if query and query.strip():
        products = search(query.strip(), pages=2)
    else:
        products = _search("gundam", True, 4)
    kits = [k for k in (gunpla(p) for p in products) if k["is_kit"]]
    if query and re.fullmatch(r"\d{13}|G?50\d{5}", query.strip(), re.I):          # a barcode / box code: that kit only
        q = query.strip().upper()
        exact = [k for k in kits if q in (k["barcode"], (k["code"] or "").upper(), "G" + q)]
        kits = exact or kits
    return sorted(kits, key=lambda k: (not k["available"], k["grade"] or "~", k["name"]))


# ---- Board games (to fill the holes in Gameology's range) ---------------------------------------

# A board game's tags here: "Maximum Players_5", "Recommended Age_14+", "Complexity_Medium",
# "Mechanic_Area Control", "Theme_Economic". Things with them that aren't board games: kits, cards.
GAME_TAGS = ("Maximum Players_", "Recommended Age_", "Complexity_", "Mechanic_", "Theme_")
NOT_BOARD_GAMES = re.compile(r"(?i)\bsleeves?\b|playmat|\bdeck\b|booster|\btcg\b|\bpaints?\b|\bdice set\b|organi[sz]er")
EXPANSION_WORDS = re.compile(r"(?i)\b(expansion|extension|exp\.?)\b")


def _tag_values(tags: list[str], prefix: str) -> list[str]:
    return [t[len(prefix):].strip() for t in tags if t.startswith(prefix)]


def board_game(p: dict) -> dict:
    """A product as the board-game facts Gameology's search gives (gameology.facts), as far as this
    shop has them: most players, age, a complexity word, themes as categories, mechanics; no fewest
    players, play time, BGG weight or publisher."""
    k = base(p)
    tags = k.pop("tags")
    k.pop("text")
    most = next((int(v) for v in _tag_values(tags, "Maximum Players_") if v.isdigit()), None)
    age = next((int(m.group(1)) for v in _tag_values(tags, "Recommended Age_") if (m := re.match(r"(\d+)", v))), None)
    expansion = bool(EXPANSION_WORDS.search(k["title"]))
    image = k["image"]
    return {
        "source": "goodgames", "shop_name": "Good Games", "gg_id": k["id"],
        "handle": str(p.get("handle") or ""), "title": k["title"], "name": tidy_board_title(k["title"]),
        "publisher": None, "min_players": None, "max_players": most, "play_minutes": None,
        "min_play_minutes": None, "min_age": age, "weight": None,
        "complexity": next(iter(_tag_values(tags, "Complexity_")), None),
        "categories": sorted(set(_tag_values(tags, "Theme_"))), "mechanisms": sorted(set(_tag_values(tags, "Mechanic_"))),
        "types": [], "expansion": expansion, "kind": "expansion" if expansion else None, "expansion_handles": [],
        "price": k["price"], "available": k["available"], "shop_url": k["url"],
        "image": image and image + ("&" if "?" in image else "?") + "width=600",
        "image_url": image and image + ("&" if "?" in image else "?") + "width=200",
        "is_board_game": any(t.startswith(GAME_TAGS) for t in tags) and not NOT_BOARD_GAMES.search(k["title"])
                         and not any(t.startswith(("Faction_", "Scale_")) for t in tags),
    }


def tidy_board_title(title: str) -> str:
    """"Catan Board Game (6th Edition)" -> "Catan (6th Edition)"; "Scythe - Modular Board" -> "Scythe: Modular Board"."""
    name = re.sub(r"(?i)\s+(base game|board game|card game)\b", "", title.strip())
    return re.sub(r"\s+[-–]\s+", ": ", name, count=1)


def board_games(query: str, limit: int = 8) -> list[dict]:
    """Board games with every word of the name in their title (the shop's own search is loose: "arcs"
    also finds "Joan of Arc"), in stock first, ranked like Gameology's: titles that start with your
    words first; games before expansions."""
    games = [g for g in (board_game(p) for p in search(query)) if g["is_board_game"]]
    words = re.findall(r"[a-z0-9]+", query.lower())

    def rank(g):
        title = " ".join(re.findall(r"[a-z0-9]+", g["title"].lower()))
        return (0 if title.startswith(" ".join(words)) else 1 if all(w in title for w in words) else 2,
                g["expansion"], not g["available"], len(title))
    return [g for g in sorted(games, key=rank) if rank(g)[0] < 2][:limit]
