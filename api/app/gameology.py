"""Gameology (https://www.gameology.com.au): an Australian board game shop (a Shopify store) whose
product tags carry BoardGameGeek's facts: players, play time, age, weight (complexity) and BGG's
categories / mechanisms / types. Used to find a board game by name and fill it in, with its box
photo and the shop's price.

    search(name)     GET /search/suggest.json   the store's own search box (what its pages use):
                     products with title, maker, price, picture and tags in one request
    product(handle)  GET /products/<handle>.js  one product (for adding a game and its photo)
    photo(game)      the product picture from Shopify's CDN, 600 px wide, checked like any download

robots.txt allows the store's product pages for crawlers. Only what you ask for is fetched (a
search as you type a name, one product when you add a game) with a User-Agent that says who's
asking. BGG's average rating and rank aren't in the tags.
"""
import re

import httpx

from .images import fetched_photo

SITE = "https://www.gameology.com.au"
HEADERS = {"User-Agent": "OffTheClock/1.0 (personal hobby tracker; https://github.com/XDCause/ShelfofShame)",
           "Accept": "application/json"}
TIMEOUT = 20
PAUSE = 1.0          # between products when several are checked in a row
GAME_TYPES = ("board game", "card game", "dice game", "party game", "puzzle", "family game", "war game")


class ShopError(Exception):
    """A message for the user: Gameology unreachable..."""


def _get(path: str, params: dict | None = None):
    try:
        r = httpx.get(SITE + path, params=params, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError as e:
        raise ShopError(f"Couldn't reach Gameology ({e.__class__.__name__}).") from None
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise ShopError(f"Gameology didn't answer (HTTP {r.status_code}).")
    return r.json()


def _tag(tags: list[str], name: str) -> list[str]:
    """Every value of a "BGG <name>: value" tag."""
    prefix = f"BGG {name}:".lower()
    return [t.split(":", 1)[1].strip() for t in tags if t.lower().startswith(prefix)]


def _number(values: list[str]) -> float | None:
    for v in values:
        try:
            return float(v)
        except ValueError:
            continue
    return None


def _image(url: str | None, width: int) -> str | None:
    if not url:
        return None
    url = "https:" + url if url.startswith("//") else url
    return url + ("&" if "?" in url else "?") + f"width={width}"


def facts(p: dict) -> dict:
    """A product -> a board game: the BGG facts from its tags, the shop's details. A weight under 1
    is the shop's "not rated" and over 5 a mistake (BGG's scale is 1-5): both are left out."""
    tags = p.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    low, high = _number(_tag(tags, "Min Players")), _number(_tag(tags, "Max Players"))
    t_low, t_high = _number(_tag(tags, "Min Play Time")), _number(_tag(tags, "Max Play Time"))
    weight = _number(_tag(tags, "Weight"))
    price = p.get("price")
    if isinstance(price, int):                        # the .js answer is in cents, the search's in dollars
        price = price / 100
    picture = p.get("featured_image")
    if isinstance(picture, dict):                     # the search gives {url: ...}, the .js a plain URL
        picture = picture.get("url")
    picture = picture or p.get("image")
    return {
        "handle": p["handle"],
        "name": tidy_title(p["title"]),
        "title": p["title"],
        "publisher": None if (p.get("vendor") or "").startswith("(") else p.get("vendor"),
        "min_players": int(low) if low else None,
        "max_players": int(high) if high else None,
        "play_minutes": int(t_high or t_low) if (t_high or t_low) else None,
        "min_play_minutes": int(t_low) if t_low else None,
        "min_age": int(m) if (m := _number(_tag(tags, "Min Age"))) else None,
        "weight": round(weight, 2) if weight and 1 <= weight <= 5 else None,
        "categories": sorted(set(_tag(tags, "Category")) - {"Expansion for Base-game"}),
        "mechanisms": sorted(set(_tag(tags, "Mechanism"))),
        "types": sorted({t.replace(" Games", "") for t in _tag(tags, "Type")}),
        "expansion": "Expansion for Base-game" in _tag(tags, "Category"),
        "kind": kind_of(tags),
        "expansion_handles": [t.split(":", 1)[1].strip() for t in tags if t.lower().startswith("expansion:")],
        "price": float(price) if price not in (None, "") else None,
        "available": p.get("available"),
        "shop_url": f"{SITE}/products/{p['handle']}",
        "image": _image(picture, 600),
        "image_url": _image(picture, 200),
    }


def kind_of(tags: list[str]) -> str | None:
    """The shop's "Board Game BEA" tag: Base Game -> game, Expansion -> expansion, Board Game
    Accessorie(s) -> other; else BGG's "Expansion for Base-game" category; else not known."""
    bea = " ".join(t.split(":", 1)[1] for t in tags if t.lower().startswith("board game bea:")).lower()
    if "accessor" in bea:
        return "other"
    if "expansion" in bea or "Expansion for Base-game" in _tag(tags, "Category"):
        return "expansion"
    if "base game" in bea:
        return "game"
    return None


def tidy_title(title: str) -> str:
    """"CATAN 6th Edition Base Game" -> "Catan 6th Edition"; "Wingspan Board Game" -> "Wingspan"."""
    name = re.sub(r"\s+(Base Game|Board Game|Card Game)$", "", title.strip(), flags=re.I)
    return " ".join(w.capitalize() if w.isupper() and len(w) > 3 else w for w in name.split())


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def search(name: str, limit: int = 8) -> list[dict]:
    """Board games matching a name, best first: titles that start with your words, then titles with
    every word in them, then the rest (the store's search is loose). Accessories and other
    non-games are left out."""
    # Only board games, matched on the title: a plain search also matches descriptions and brings
    # Magic cards ("Rootbound Crag" for "root").
    query = f'{name.replace(chr(34), "")} product_type:"Board Games"'
    data = _get("/search/suggest.json", {"q": query, "resources[type]": "product", "resources[limit]": 10,
                                          "resources[options][fields]": "title,product_type",
                                          # sold-out games in their place: "last" put them after the 10
                                          # the store returns, so they never showed
                                          "resources[options][unavailable_products]": "show"}) or {}
    products = data.get("resources", {}).get("results", {}).get("products", [])
    games = [facts(p) for p in products if any(t in (p.get("type") or "").lower() for t in GAME_TYPES)]
    words = _key(name).split()
    def rank(g):
        title = _key(g["title"])
        return (0 if title.startswith(" ".join(words)) else 1 if all(w in title for w in words) else 2,
                g["expansion"], g["min_players"] is None, len(title))     # games with BGG's facts first
    return sorted(games, key=rank)[:limit]


def product(handle: str) -> dict | None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,200}", handle):
        return None
    p = _get(f"/products/{handle}.js")
    return facts(p) if p else None


def photo(game: dict) -> tuple[bytes | None, str | None]:
    """The product's picture (600 px wide) - only from Shopify's CDN."""
    url = game.get("image") or ""
    if not url.startswith("https://cdn.shopify.com/"):
        return None, None
    try:
        r = httpx.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError:
        return None, None
    if r.url.host != "cdn.shopify.com":            # a redirect somewhere else: not taken
        return None, None
    return fetched_photo(r)
