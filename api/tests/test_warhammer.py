"""Warhammer kits from Good Games' official UCP interface (faked: made-up products in its layout)."""
import pytest

from app import gameology, goodgames, warhammer

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def product(n, title, sku, cents, available=True, tags=("Warhammer 40K",), text="", image=True):
    return {"id": f"gid://shopify/Product/{n}", "title": title, "url": f"https://www.goodgames.com.au/products/p{n}",
            "description": {"html": text}, "tags": list(tags),
            "media": [{"type": "image", "url": f"https://cdn.shopify.com/s/files/p{n}.jpg?v=1"}] if image else [],
            "variants": [{"id": f"gid://shopify/ProductVariant/{n}", "sku": sku, "price": {"amount": str(cents), "currency": "AUD"},
                          "availability": {"available": available}}]}


ADMECH = "Faction_Adeptus Mechanicus"
SHOP = [
    product(1, "Combat Patrol - Adeptus Mechanicus (59-05)", "5011921203208", 19277, tags=(ADMECH, "Warhammer 40K"),
            text="<p>This set includes:- 1x Tech-Priest Manipulus- 3x Serberys Sulphurhounds (which can alternatively be built "
                 "as 3x Serberys Raiders)- 10x Skitarii Vanguard (which can alternatively be built as 10x Skitarii Rangers)</p>"),
    product(2, "Combat Patrol � Adeptus Mechanicus (59-25)", "5011921139224", 24300, available=False, tags=(ADMECH,),
            text="Contains 1x Techpriest Enginseer, 1x Onager Dunecrawler, 10x Skitarii Rangers/Vanguard and 3 Kataphron Servitors"),
    product(3, "Adeptus Mechanicus - Onager Dunecrawler (59-13)", "5011921155897", 12141, tags=(ADMECH,)),
    product(4, "Codex - Adeptus Mechanicus (59-01)", "9781804572788", 8175, tags=(ADMECH,)),           # a book
    product(5, "Adeptus Mechanicus: Thulia Ghuld (59-33)", "5011921250000", 6000, text="1 plastic miniature"),  # not tagged
    product(6, "Horus Heresy - Mechanicum Battle Group (31-87)", "5011921000000", 30000, tags=("Faction_Mechanicum",)),
    product(7, "Warhammer Collectibles: 1/18 Scale Adeptus Mechanicus Skitarii Marshal", "JT7752", 14500, tags=(ADMECH,)),
]


@pytest.fixture
def shop(monkeypatch):
    asked = []

    def call(tool, catalog):
        asked.append((tool, catalog))
        if tool == "get_product":
            n = catalog["id"].rsplit("/", 1)[-1]
            p = next((p for p in SHOP if p["id"].endswith("/" + n)), None)
            if not p:
                raise goodgames.ShopError("Good Games said no: Product not found.")
            return {"product": {k: v for k, v in p.items() if k != "tags"}}     # like the real one: no tags
        words = catalog["query"].lower().split()
        found = [p for p in SHOP if p["variants"][0]["availability"]["available"] == catalog["filters"]["available"]
                 and (all(w in p["title"].lower() for w in words) or catalog["query"] == p["variants"][0]["sku"])]
        return {"products": found, "pagination": {"has_next_page": False}}
    monkeypatch.setattr(goodgames, "_call", call)
    monkeypatch.setattr(gameology, "photo", lambda game: (PNG, "image/png"))
    warhammer._ranges.clear()
    return asked


def test_a_product_becomes_a_kit():
    k = goodgames.kit(SHOP[0])
    assert (k["name"], k["code"], k["army"], k["figures"], k["barcode"], k["price"], k["available"], k["is_kit"]) == \
        ("Combat Patrol: Adeptus Mechanicus", "59-05", "Adeptus Mechanicus", 14, "5011921203208", 192.77, True, True)   # alternatives not counted
    old = goodgames.kit(SHOP[1])
    assert old["title"] == "Combat Patrol – Adeptus Mechanicus (59-25)" and not old["available"]
    assert old["figures"] == 12                         # "3 Kataphron Servitors" has no "x", so it isn't counted
    assert goodgames.kit(SHOP[2])["name"] == "Onager Dunecrawler"
    assert not goodgames.kit(SHOP[3])["is_kit"] and not goodgames.kit(SHOP[6])["is_kit"]
    assert goodgames.kit(SHOP[4])["figures"] == 1 and goodgames.kit(SHOP[6])["barcode"] is None


def test_the_profile_names_the_app(monkeypatch):
    monkeypatch.delenv("UCP_PROFILE", raising=False)
    assert goodgames.profile() == "https://cdn.jsdelivr.net/gh/XDCause/ShelfofShame@ucp-agent-1/ucp-agent.json"
    monkeypatch.setenv("UCP_PROFILE", "https://example.com/p.json")
    assert goodgames.profile() == "https://example.com/p.json"


def test_an_armys_whole_range(client, shop):
    r = client.get("/api/warhammer/army?name=Adeptus Mechanicus").json()
    # Kits only (no codex, no collectible statue), the untagged Thulia Ghuld in, Mechanicum out; by GW code.
    assert [k["code"] for k in r["kits"]] == ["59-05", "59-13", "59-25", "59-33"]
    assert (r["total"], r["in_stock"], r["yours"]) == (4, 3, 0)
    # Asked twice within the hour: from memory.
    calls = len(shop)
    client.get("/api/warhammer/army?name=adeptus mechanicus")
    assert len(shop) == calls


def test_look_up_and_want(client, shop):
    r = client.get("/api/lookup/warhammer/combat patrol adeptus mechanicus").json()
    assert [c["code"] for c in r["choices"]] == ["59-05", "59-25"]           # in stock first
    found = client.get(f"/api/lookup/warhammer/id:{r['choices'][0]['id']}").json()
    assert (found["name"], found["product_code"], found["faction"], found["figures"], found["barcode"], found["has_image"]) == \
        ("Combat Patrol: Adeptus Mechanicus", "59-05", "Adeptus Mechanicus", 14, "5011921203208", True)
    # Looked up again by its code or barcode: from the cache (no shop call).
    calls = len(shop)
    again = client.get("/api/lookup/warhammer/5011921203208").json()
    assert again["from_cache"] and again["figures"] == 14 and len(shop) == calls
    # Scanning the box finds it too.
    assert client.get("/api/scan/5011921203208").json()["match"] == "known"
    # + Wanted: a Warhammer model, Wanted, with the army, minis and photo; then the range says it's yours.
    model = client.post("/api/warhammer/want", json={"id": "3"}).json()
    assert (model["name"], model["hobby"], model["status"], model["faction"], model["figures"], model["product_code"], model["has_image"]) == \
        ("Onager Dunecrawler", "Warhammer", "Wanted", "Adeptus Mechanicus", 1, "59-13", True)
    assert client.post("/api/warhammer/want", json={"id": "3"}).status_code == 409
    r = client.get("/api/warhammer/army?name=Adeptus Mechanicus").json()
    assert r["yours"] == 1 and next(k for k in r["kits"] if k["code"] == "59-13")["my_model"]["status"] == "Wanted"
    assert client.get("/api/warhammer/armies").json()["yours"] == ["Adeptus Mechanicus"]


def test_codes_that_dont_exist_and_shop_errors(client, shop, monkeypatch):
    assert client.get("/api/lookup/warhammer/99-99").status_code == 404
    assert client.post("/api/warhammer/want", json={"id": "999"}).status_code == 404

    def busy(tool, catalog):
        raise goodgames.ShopError("Good Games asked us to slow down - try again in a minute.")
    monkeypatch.setattr(goodgames, "_call", busy)
    r = client.get("/api/warhammer/search?q=onager")
    assert r.status_code == 502 and "slow down" in r.json()["detail"]
