"""Shop Tamiya: the catalogue list-page parser, search, and one-tap add to the wishlist."""
from pathlib import Path

from app.db import db
from app.tamiya_catalog import parse_list, product_code

FIXTURE = (Path(__file__).parent / "fixtures" / "tamiya_list_e_5010.html").read_text(encoding="utf-8")


def test_parse_a_real_list_page():
    products, total = parse_list(FIXTURE)
    assert total == 193
    first = products[0]
    assert (first["item"], first["title"], first["genre"]) == ("87240", "TAMIYA MASKING TAPE 40mm BLUE", "Finishing Materials")
    assert first["thumb_url"].startswith("https://") and first["thumb_url"].endswith("87240_s.jpg")
    assert product_code("87240") == "T87240" and product_code("00XF1") == "T00XF1"


CATALOGUE = [
    ("87131", "PANEL LINE ACCENT COLOR (BLACK)", "Finishing Materials"),
    ("87132", "PANEL LINE ACCENT COLOR (BROWN)", "Finishing Materials"),
    ("87133", "PANEL LINE ACCENT COLOR (GRAY)", "Finishing Materials"),
    ("81776", "ACRYLIC PAINT MINI XF-76 GRAY GREEN (IJN)", "Paints"),
]


def load_catalogue(ids):
    with db() as conn:
        for item, title, genre in CATALOGUE:
            conn.execute("INSERT INTO catalog_products (brand_id, product_code, item, title, genre) "
                         "VALUES (%s, %s, %s, %s, %s)", (ids["tamiya"], "T" + item, item, title, genre))


def names(client, q):
    return [r["title"] for r in client.get("/api/catalog/search", params={"q": q}).json()]


def test_search_needs_every_word(client, ids):
    load_catalogue(ids)
    assert names(client, "panel line black") == ["PANEL LINE ACCENT COLOR (BLACK)"]
    assert len(names(client, "panel line")) == 3
    assert names(client, "") == []


def test_search_by_paint_code_or_number(client, ids):
    load_catalogue(ids)
    for q in ("XF-76", "xf76", "81776", "gray green"):
        assert names(client, q) == ["ACRYLIC PAINT MINI XF-76 GRAY GREEN (IJN)"], q
    r = client.get("/api/catalog/search", params={"q": "xf76"}).json()[0]
    assert r["name"] == "Acrylic XF76 Gray Green (IJN)"  # your naming style


def test_search_shows_what_you_already_have(client, ids, make_supply):
    load_catalogue(ids)
    make_supply(product_code="T87133", name="Panel Line Gray", qty_on_hand=1, condition="Nearly empty")
    rows = {r["product_code"]: r for r in client.get("/api/catalog/search", params={"q": "panel line"}).json()}
    gray = rows["T87133"]
    assert (gray["owned_qty"], gray["owned_condition"], gray["owned_status"]) == (1, "Nearly empty", "Low")
    assert rows["T87131"]["owned_supply_id"] is None
    # owned items come first
    assert client.get("/api/catalog/search", params={"q": "panel line"}).json()[0]["product_code"] == "T87133"


def test_one_tap_add_to_wishlist(client, ids, fake_tamiya, monkeypatch):
    from tests.conftest import FAKE_PRODUCTS
    monkeypatch.setitem(FAKE_PRODUCTS, "87131", {"title": "PANEL LINE ACCENT COLOR (BLACK)",
                                                "series": "Finishing Materials", "description": "Contents: 40ml"})
    load_catalogue(ids)
    r = client.post("/api/catalog/T87131/wishlist")
    assert r.status_code == 201
    wish = r.json()  # straight away, from the catalogue title alone
    assert (wish["name"], wish["category"], wish["size"]) == ("Panel Line Accent Color (Black)", "Weathering", None)
    assert wish["has_image"] is False and wish["catalog_thumb"] is None  # (no thumb_url in this test catalogue)
    # ...then tamiya.com is fetched in the background and fills in the size and photo
    assert fake_tamiya == ["87131"]
    [later] = [w for w in client.get("/api/wishlist").json() if w["wish_id"] == wish["wish_id"]]
    assert (later["size"], later["has_image"]) == ("40ml", True)
    assert client.get("/api/catalog/search", params={"q": "panel line black"}).json()[0]["on_wishlist"] is True

    assert client.post("/api/catalog/T87131/wishlist").status_code == 409
    assert client.post("/api/catalog/T99999/wishlist").status_code == 404


def test_add_still_works_when_tamiya_is_down(client, ids, fake_tamiya):
    load_catalogue(ids)  # 87132 isn't in FAKE_PRODUCTS, so the background fetch fails
    r = client.post("/api/catalog/T87132/wishlist")
    assert r.status_code == 201 and r.json()["name"] == "Panel Line Accent Color (Brown)"
    assert fake_tamiya == ["87132"]
    assert [w["name"] for w in client.get("/api/wishlist").json()] == ["Panel Line Accent Color (Brown)"]
