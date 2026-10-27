"""Stand-ins for every outside website, for the walk-through's throwaway copy (OUTSIDE_SITES=stand-ins).

The browser walk-through runs often (every change); asking the real sites each time is unfair on small shops
(Good Games asked us to slow down) and makes the walk-through depend on other people's servers. So its copy
answers from made-up data instead - the same idea as the API tests' fakes (api/tests/conftest.py). Each real
site is still looked at once a week by the site check (sitecheck.py), and whenever you use the feature yourself.

install() replaces each outside module's network calls (or the function that makes them) with answers in the
same shape the real site gives. Only main.py calls it, and only with OUTSIDE_SITES=stand-ins.
"""
import logging

from . import (bluesky, bookseries, bunnings, chesscom, exophase, frankfurter, gameology, goodgames, hasegawa, hlj, linkpeek, openlibrary,
               openmeteo, overpass, stedi, steam, steamhunters, tamiya, trumpeter, webphoto, wikimedia)

log = logging.getLogger("stand_ins")
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")
NOT_ASKED = "isn't asked in the walk-through (a stand-in copy)"


def _shopify(n, title, sku, cents, store, available=True, tags=(), text="", options=None, variants=None):
    return {"id": f"gid://shopify/Product/{n}", "title": title, "url": f"{store}/products/p{n}",
            "description": {"html": text}, "tags": list(tags),
            "media": [{"type": "image", "url": f"https://cdn.shopify.com/s/files/stand-in/p{n}.jpg?v=1"}],
            **({"options": options} if options else {}),
            "variants": variants or [{"id": f"gid://shopify/ProductVariant/{n}", "sku": sku,
                                      "price": {"amount": str(cents), "currency": "AUD"}, "availability": {"available": available}}]}


GG = "https://www.goodgames.com.au"
ADMECH = "Faction_Adeptus Mechanicus"
GOOD_GAMES = [
    _shopify(1, "Combat Patrol - Adeptus Mechanicus (59-05)", "5011921203208", 19277, GG, tags=(ADMECH, "Warhammer 40K"),
             text="<p>This set includes:- 1x Tech-Priest Manipulus- 3x Serberys Sulphurhounds- 10x Skitarii Vanguard</p>"),
    _shopify(2, "Adeptus Mechanicus - Onager Dunecrawler (59-13)", "5011921155897", 12141, GG, tags=(ADMECH, "Warhammer 40K")),
    _shopify(3, "Adeptus Mechanicus - Skitarii Rangers (59-10)", "5011921155880", 6500, GG, tags=(ADMECH, "Warhammer 40K")),
    _shopify(11, "HG 1/144 Gundam Aerial Rebuild", "4573102650962", 3250, GG, tags=("Gundam", "Model", "Scale_1/144")),
    _shopify(12, "1/144 HGUC Revive RX-78-2 Gundam", "4573102574039", 2995, GG, tags=("Gundam", "Model")),
    _shopify(13, "MG 1/100 RX-78-2 Gundam Ver 3.0 (New)", "4573102616104", 8478, GG, tags=("Gundam", "Scale_1/100")),
    _shopify(14, "RG 1/144 RX-78-2 Gundam", "4573102616111", 4500, GG, tags=("Gundam", "Model", "Scale_1/144")),
    _shopify(21, "Catan", "029877030712", 6995, GG, tags=("Board Games", "Players_3-4")),
]
BS = "https://blueskyathletics.com.au"
SD = "https://www.steditools.com"
STEDI = [_shopify(41, "stedi MS-106 Precision Single Blade Nipper for Plastic Model Building", "MS-106", 2599, SD),
         _shopify(42, "stedi Beginner's Model tool Kit TZ-01 Includes Nipper, Hobby Knife, Tweezers & Sanding Sticks", "TZ-01", 2799, SD)]


def _shoe(n, title, cents, sizes):
    return _shopify(n, title, None, cents, BS, options=[{"name": "Shoe size", "values": [{"label": s} for s, _ in sizes]}],
                    variants=[{"id": f"gid://shopify/ProductVariant/{n}{i}", "title": s, "price": {"amount": cents, "currency": "AUD"},
                               "availability": {"available": ok}, "options": [{"name": "Shoe size", "label": s}]}
                              for i, (s, ok) in enumerate(sizes)])


BLUE_SKY = [_shoe(31, 'Way of Wade 12 "Avocado"', 28999, [("9", True), ("10", False), ("11", True)]),
            _shoe(32, 'Way of Wade 11 "Cement"', 24999, [("10", True)])]


def _ucp(products, shop_error):
    """A Shopify store's catalogue (search_catalog / get_product), like the real UCP answers."""
    def call(tool, catalog):
        if tool == "get_product":
            p = next((p for p in products if p["id"] == catalog["id"] or p["id"].endswith("/" + catalog["id"].rsplit("/", 1)[-1])), None)
            if not p:
                raise shop_error("The shop said no: Product not found.")
            return {"product": p}
        words = (catalog.get("query") or "").lower().split()
        want = (catalog.get("filters") or {}).get("available")
        found = [p for p in products if all(w in p["title"].lower() or w in " ".join(p["tags"]).lower() for w in words)
                 and (want is None or any(v["availability"]["available"] for v in p["variants"]) == want)]
        return {"products": found, "pagination": {"has_next_page": False}}
    return call


TAMIYA = {
    "81702": {"title": "ACRYLIC PAINT MINI XF-2 FLAT WHITE", "series": "Tamiya Color Acrylic Paint Mini", "description": "Contents: 10ml"},
    "81701": {"title": "ACRYLIC PAINT MINI XF-1 FLAT BLACK", "series": "Tamiya Color Acrylic Paint Mini", "description": "Contents: 10ml"},
    "81776": {"title": "ACRYLIC PAINT MINI XF-76 GRAY GREEN (IJN)", "series": "Tamiya Color Acrylic Paint Mini", "description": "Contents: 10ml"},
    "87038": {"title": "TAMIYA EXTRA-THIN CEMENT (40ml)", "series": "Cement & Putty No.38", "description": None},
    "08888": {"title": "STAND-IN TAMIYA TOOL", "series": "Craft Tools", "description": None},   # both makers (made up)
}
HASEGAWA = {
    "JT86": {"title": "P-40E WARHAWK", "series": "JT86", "item": "09086", "scale": "1/48", "category": None},
    "PT29": {"title": "MITSUBISHI F-2B", "series": "PT29", "item": "07229", "scale": "1/48", "category": None},
}
TRUMPETER = {
    "00968": {"title": "German Leopard2A6 MBT", "item": "00968", "barcode": "9580208009681", "scale": "1/16",
              "item_type": "Plastic Model Armor Kit", "is_tool": False, "size": "Length 705.8mm", "parts": "1700+",
              "etched": "4 pcs", "released": "2026-09", "features": None, "intro": None},
    "08005": {"title": "Masking Tape Cutter", "item": "08005", "barcode": None, "scale": None, "item_type": "Modeling Tools",
              "is_tool": True, "size": None, "parts": None, "etched": None, "released": "2021-01", "features": None, "intro": None},
    "08888": {"title": "Stand-in Trumpeter Tool", "item": "08888", "barcode": None, "scale": None, "item_type": "Modeling Tools",
              "is_tool": True, "size": None, "parts": None, "etched": None, "released": None, "features": None, "intro": None},
}
FORECAST = {"daily": {"time": ["2026-01-10", "2026-01-11", "2026-01-12"], "temperature_2m_max": [29, 31, 27],
                      "temperature_2m_min": [19, 20, 18], "precipitation_sum": [0, 2, 0], "precipitation_probability_max": [10, 40, 5],
                      "wind_gusts_10m_max": [25, 30, 20], "uv_index_max": [9, 10, 8], "weather_code": [1, 63, 3]}}


def _refuse(error, what):
    def no(*_a, **_k):
        raise error(f"{what} {NOT_ASKED}.")
    return no


class _AnyText(dict):
    """SteamHunters' hidden-achievement texts: a made-up one for whichever achievement is asked about."""
    def get(self, name, default=None):
        return f"(Stand-in) How to unlock {name}."


def install():
    """Swap every outside site for a stand-in (see the module's docstring)."""
    # Model kits and paints
    def tamiya_fetch(item):
        if item not in TAMIYA:
            raise tamiya.NotFound(f"Tamiya has no product page for item {item}.")
        return {"kit_paints": [], **TAMIYA[item], "source_url": f"https://www.tamiya.com/english/products/{item}/index.html",
                "image": PNG, "image_type": "image/png"}
    tamiya.fetch = tamiya_fetch

    def hasegawa_fetch(series):
        if series not in HASEGAWA:
            raise tamiya.NotFound(f"Hasegawa has no page for {series}.")
        return {**HASEGAWA[series], "source_url": f"http://www.hasegawa-model.co.jp/product_g/{series.lower()}/",
                "image": PNG, "image_type": "image/png"}
    hasegawa.fetch = hasegawa_fetch
    def trumpeter_fetch(item, photo=True):
        if item not in TRUMPETER:
            raise tamiya.NotFound(f"Trumpeter's site has nothing for item {item}.")
        return {**TRUMPETER[item], "source_url": f"https://www.trumpeter-china.com/index.php?g=home&m=product&a=show&id={item}&l=en",
                "image": PNG if photo else None, "image_type": "image/png" if photo else None}
    trumpeter.fetch = trumpeter_fetch
    hlj.search = lambda query: []
    hlj.fetch = _refuse(tamiya.NotFound, "HobbyLink Japan")
    # Shops (Shopify catalogues) and their photos
    goodgames._call = _ucp(GOOD_GAMES, goodgames.ShopError)
    bluesky._call = _ucp(BLUE_SKY, bluesky.ShopError)
    stedi._call = _ucp(STEDI, stedi.ShopError)
    gameology._get = _refuse(gameology.ShopError, "Gameology")
    gameology.photo = lambda game: (PNG, "image/png")
    # Video games
    steam._get = _refuse(steam.SteamError, "Steam")
    steam.store_search = lambda term: [{"type": "app", "id": 367520, "name": "Hollow Knight", "tiny_image": None,
                                        "price": {"final": 2295}}] if "hollow" in term else []
    steam.find_app = lambda name: None
    steam.store_items = lambda ids: {i: {"name": "Hollow Knight" if i == 367520 else f"App {i}", "header": None} for i in ids}
    steam.schema = lambda app_id: [{"name": "ACH_1", "displayName": "Falsehood", "description": "Defeat the False Knight", "icon": None},
                                   {"name": "ACH_2", "displayName": "Test of Resolve", "description": "Defeat Hornet", "icon": None}]
    steam.global_percentages = lambda app_id: {"ACH_1": 71.2, "ACH_2": 58.9}

    def private(steam_id):
        raise steam.FriendsPrivate("Your Steam friends list is private, so it can't be read (a stand-in in the walk-through).")
    steam.friend_ids = private
    steam.summaries = lambda ids: {}
    steamhunters._get = _refuse(steamhunters.Unavailable, "SteamHunters")
    steamhunters.game = lambda app_id: {"sh_median_minutes": 2994, "sh_players_perfected": 5685, "sh_players_started": 90000}
    steamhunters.unobtainable = lambda app_id: set()
    steamhunters.dlc_names = lambda app_id: []
    steamhunters.descriptions = lambda app_id: _AnyText()     # every hidden achievement gets a made-up text
    exophase._get = _refuse(exophase.Unavailable, "Exophase")
    exophase.search = lambda words, environment: []          # Epic / Ubisoft "find a game": nothing found
    chesscom._get = _refuse(chesscom.ChessError, "chess.com")
    # Books
    openlibrary._get = lambda params: []
    bookseries._wikidata = lambda query: []
    # Hiking and gardening
    overpass._post = lambda data: {"elements": []}
    wikimedia._get = lambda url, params: {}
    bunnings._get = _refuse(bunnings.BunningsError, "Bunnings")
    # "Add from a link": a product page, as the stand-in shop's (robots.txt: allowed)
    linkpeek._get = lambda url, limit=None: (url, "" if url.endswith("/robots.txt") else
        '<html><head><title>Stand-in shop</title><meta property="og:title" content="Stand-in Knee Pads">'
        '<meta property="product:price:amount" content="39.95"></head><body></body></html>')
    bunnings.photo = lambda image: (PNG, "image/png")
    openmeteo._get = lambda url, params: ({"results": [{"name": "Brisbane", "admin1": "Queensland", "country": "Australia",
                                                        "latitude": -27.47, "longitude": 153.03, "country_code": "AU"}]}
                                          if "geocoding" in url else FORECAST)
    # Exchange rates (units of each currency for 1 AUD)
    frankfurter._get = lambda url, params: {"amount": 1.0, "base": "AUD", "date": "2026-10-19",
                                            "rates": {"JPY": 100.0, "NZD": 1.1, "USD": 0.65, "EUR": 0.6}}
    # A photo from a web address
    webphoto.fetch = lambda url: (PNG, "image/png")
    log.warning("Outside websites are stand-ins (OUTSIDE_SITES=stand-ins): nothing is fetched from them.")
