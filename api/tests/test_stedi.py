"""Stedi model tools: their codes, their catalogue (made up here, in the shape their official search answers), the
lookup and the one look-up box (words search Stedi; a code like MS-106 asks Stedi)."""
import pytest

from app import products, stedi, webphoto

SD = "https://www.steditools.com"


def product(n, title, variants):
    return {"id": f"gid://shopify/Product/{n}", "title": title, "url": f"{SD}/products/p{n}", "description": {"html": "<p>A <b>tool</b>.</p>"},
            "media": [{"type": "image", "url": f"https://cdn.shopify.com/s/files/test/p{n}.jpg?v=1"}],
            "variants": [{"id": f"gid://shopify/ProductVariant/{n}{i}", "sku": sku, "title": title_, "price": {"amount": cents, "currency": "USD"},
                          "availability": {"available": ok}} for i, (sku, title_, cents, ok) in enumerate(variants)]}


CATALOGUE = [product(1, "stedi MS-106  Precision Single Blade Nipper，for models", [("MS-106", "Blue handle", 2599, True),
                                                                                 ("MS-106B", "Default Title", 1799, False)]),
             product(2, "stedi Beginner's Kit TZ-01", [("TZ-01", "Default Title", 2799, True)])]


@pytest.fixture
def fake_stedi(monkeypatch):
    asked = []

    def call(tool, catalog):
        asked.append(catalog["query"])
        words = catalog["query"].lower().split()
        return {"products": [p for p in CATALOGUE if all(w in p["title"].lower() or any(w == v["sku"].lower() for v in p["variants"])
                                                       for w in words)]}
    monkeypatch.setattr(stedi, "_call", call)
    monkeypatch.setattr(webphoto, "fetch", lambda url: (b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png"))
    return asked


def test_codes_and_names():
    assert [stedi.sku_in(x) for x in ("ms106", "MS 106", "TZ-01", f"{SD}/products/stedi-ms-106-precision-nipper")] == \
        ["MS-106", "MS-106", "TZ-01", "MS-106"]
    assert stedi.sku_in("nipper") is None
    assert stedi.nice_name("stedi MS-106  Precision，for models") == "Stedi MS-106 Precision, for models"


def test_search_and_lookup(client, fake_stedi):
    found = stedi.search("nipper")
    assert [(t["sku"], t["version"], t["price_usd"], t["available"]) for t in found] == \
        [("MS-106", "Blue handle", 25.99, True), ("MS-106B", None, 17.99, False)]
    r = client.get("/api/lookup/stedi/ms106").json()
    assert (r["product_code"], r["name"], r["series"], r["price_usd"], r["has_image"]) == \
        ("MS-106", "Stedi MS-106 Precision Single Blade Nipper, for models", "Blue handle", 25.99, True)
    assert r["description"].startswith("Model MS-106 · Blue handle · US$25.99 at steditools.com\n\nA tool.")
    assert client.get("/api/lookup/stedi/MS-106").json()["from_cache"] is True
    assert client.get("/api/lookup/stedi/ZZ-999").status_code == 404
    assert client.get("/api/lookup/stedi/hello").status_code == 422


def test_the_one_box(client, fake_stedi):
    assert products.who_to_ask("MS-106") == ["Stedi"] and products.who_to_ask("nipper") == ["Stedi search"]
    assert products.who_to_ask("XF-76") == ["Tamiya"] and products.who_to_ask("sanding sticks") == ["Stedi search"]
    words = client.get("/api/lookup/item/nipper").json()
    assert words["found"] == [] and [c["sku"] for c in words["choices"]] == ["MS-106", "MS-106B"]
    code = client.get("/api/lookup/item/TZ-01").json()
    assert [f["maker"] for f in code["found"]] == ["Stedi"] and code["found"][0]["name"] == "Stedi Beginner's Kit TZ-01"
    assert client.get("/api/lookup/item/glitter glue").status_code == 404
