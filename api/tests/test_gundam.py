"""Gundam kits from Good Games' official UCP interface (faked: made-up products in its layout)."""
import pytest

from app import gameology, goodgames, gundam

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def product(n, title, sku, cents, available=True, tags=("Gundam", "Model")):
    return {"id": f"gid://shopify/Product/{n}", "title": title, "url": f"https://www.goodgames.com.au/products/g{n}",
            "description": {"html": ""}, "tags": list(tags),
            "media": [{"type": "image", "url": f"https://cdn.shopify.com/s/files/g{n}.jpg?v=1"}],
            "variants": [{"id": f"gid://shopify/ProductVariant/{n}", "sku": sku, "price": {"amount": str(cents), "currency": "AUD"},
                          "availability": {"available": available}}]}


SHOP = [
    product(1, "HG 1/144 Gundam Aerial Rebuild", "4573102650962", 3250, tags=("Gundam", "Model", "Scale_1/144")),
    product(2, "Gundam HG MSN-06S SINANJU Mobile Suit", "4573102588135", 8325, available=False),
    product(3, "MG 1/100 RX-78-2 Gundam Ver 3.0 (New)", "4573102616104", 8478, available=False, tags=("Gundam", "Scale_1/100")),
    product(4, "Gundam Card Game: Starter Deck � Heavy Dominion [ST14]", "810199502694", 3200, tags=("Gundam", "TCG")),
    product(5, "1/144 HGUC Revive RX-78-2 Gundam", "4573102574039", 2995, tags=("Gundam", "Model")),
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
            return {"product": {k: v for k, v in p.items() if k != "tags"}}
        words = catalog["query"].lower().split()
        found = [p for p in SHOP if p["variants"][0]["availability"]["available"] == catalog["filters"]["available"]
                 and (all(w in p["title"].lower() for w in words) or catalog["query"] == p["variants"][0]["sku"])]
        return {"products": found, "pagination": {"has_next_page": False}}
    monkeypatch.setattr(goodgames, "_call", call)
    monkeypatch.setattr(gameology, "photo", lambda game: (PNG, "image/png"))
    gundam._found.clear()
    return asked


def test_a_product_becomes_a_gunpla_kit():
    k = goodgames.gunpla(SHOP[1])
    assert (k["name"], k["grade"], k["scale"], k["code"], k["available"], k["is_kit"]) == \
        ("MSN-06S Sinanju", "HG", None, "G5058813", False, True)
    k = goodgames.gunpla(SHOP[0])
    assert (k["name"], k["grade"], k["scale"], k["price"]) == ("Gundam Aerial Rebuild", "HG", "1/144", 32.5)
    assert goodgames.gunpla(SHOP[2])["scale"] == "1/100" and not goodgames.gunpla(SHOP[3])["is_kit"]   # the card game


def test_in_stock_now_and_a_search(client, shop):
    r = client.get("/api/gundam/kits").json()
    assert [k["name"] for k in r["kits"]] == ["Gundam Aerial Rebuild", "Revive RX-78-2 Gundam"] and r["in_stock"] == 2
    assert shop[-1][1]["filters"]["available"] is True                         # "in stock now" asks for in-stock only
    r = client.get("/api/gundam/kits?q=gundam").json()
    assert r["total"] == 4 and [k["available"] for k in r["kits"]] == [True, True, False, False]   # no card game
    calls = len(shop)
    client.get("/api/gundam/kits?q=Gundam")                                   # within the hour: from memory
    assert len(shop) == calls
    r = client.get("/api/gundam/kits?q=4573102574039").json()                 # the box barcode: that kit only
    assert [k["product_code"] for k in r["kits"]] == ["G5057403"]


def test_want_and_yours(client, shop):
    # A kit you already have (by its box code, like the HLJ lookup's) shows as yours.
    mine = client.post("/api/models", json={"name": "RX-78-2 Gundam (Revive)", "hobby": "Gundam", "brand_name": "Bandai",
                                             "product_code": "G5057403"}).json()
    r = client.get("/api/gundam/kits").json()
    revive = next(k for k in r["kits"] if k["product_code"] == "G5057403")
    assert revive["my_model"] == {"model_id": mine["model_id"], "status": "In stash"}
    # + Wanted: a Gundam model, Wanted, with grade, scale and the box photo.
    model = client.post("/api/gundam/want", json={"id": "1"}).json()
    assert (model["name"], model["hobby"], model["status"], model["grade"], model["scale"], model["product_code"], model["has_image"]) == \
        ("Gundam Aerial Rebuild", "Gundam", "Wanted", "HG", "1/144", "G5065096", True)
    assert client.post("/api/gundam/want", json={"id": "1"}).status_code == 409
    assert client.post("/api/gundam/want", json={"id": "5"}).status_code == 409              # the one you have
    assert client.get("/api/scan/4573102650962").json()["match"] == "known"
