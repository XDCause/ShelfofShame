"""Barcode scanning, the Tamiya lookup (with a fake tamiya.com), and photos."""
from app.db import db

XF76 = "4950344070053"


def test_bad_check_digit_is_refused(client):
    r = client.get("/api/scan/4950344070054")
    assert r.status_code == 422


def test_unknown_non_tamiya_barcode(client):
    r = client.get("/api/scan/036000291452").json()  # 12-digit UPC-A
    assert r["match"] == "unknown" and r["barcode"] == "0036000291452" and r["brand_id"] is None


def test_unknown_tamiya_barcode_asks_for_the_code(client, ids, fake_tamiya):
    r = client.get(f"/api/scan/{XF76}").json()
    # The digits (07005) aren't an item number, so the guess fails and Tamiya is suggested
    assert fake_tamiya == ["07005"]
    assert r["match"] == "unknown" and r["brand_id"] == ids["tamiya"]


def test_catalogue_identifies_a_paint_never_seen_before(client, ids, fake_tamiya, make_supply):
    with db() as conn:
        conn.execute("INSERT INTO barcode_catalog (barcode, brand_id, product_code, source) "
                     "VALUES (%s, %s, 'T81776', 'test')", (XF76, ids["tamiya"]))
    r = client.get(f"/api/scan/{XF76}").json()
    assert r["match"] == "catalog" and r["product_code"] == "T81776"
    assert r["suggested"]["name"] == "Acrylic XF76 Gray Green (IJN)"
    assert r["suggested"]["category_id"] == ids["paint"] and r["has_image"] is True
    assert r["supply_id"] is None and r["owned_qty"] == 0

    # Second time: served from the cache, tamiya.com not asked again
    client.get(f"/api/scan/{XF76}")
    assert fake_tamiya == ["81776"]

    # Once you own it, the scan finds your item and prefers your own naming
    s = make_supply(product_code="T81776", name="Acrylic XF76 Grey Green")
    r = client.get(f"/api/scan/{XF76}").json()
    assert r["supply_id"] == s["supply_id"] and r["owned_qty"] == 1
    assert r["suggested"]["name"] == "Acrylic XF76 Grey Green"
    assert client.get(f"/api/supplies/{s['supply_id']}").json()["barcode"] == XF76


def test_saved_barcode_is_recognised_for_any_brand(client, ids, make_supply):
    s = make_supply(brand_id=ids["milliput"], product_code="MIL3", name="Silver Grey Epoxy Putty")
    barcode = "5012345678900"
    r = client.put("/api/product-barcode", json={"brand_id": ids["milliput"], "product_code": "MIL3",
                                                 "barcode": barcode})
    assert r.status_code == 200
    r = client.get(f"/api/scan/{barcode}").json()
    assert r["match"] == "known" and r["supply_id"] == s["supply_id"]
    assert r["suggested"]["name"] == "Silver Grey Epoxy Putty"

    # The same barcode can't belong to two items
    r = client.put("/api/product-barcode", json={"brand_id": ids["tamiya"], "product_code": "T81701",
                                                 "barcode": barcode})
    assert r.status_code == 409


def test_lookup_accepts_paint_codes_and_checks_the_title(client, fake_tamiya, monkeypatch):
    r = client.get("/api/lookup/tamiya/xf76").json()
    assert r["product_code"] == "T81776" and "warning" not in r
    assert client.get("/api/lookup/tamiya/XF-999").status_code == 422

    # If Tamiya's page were for a different colour, the user is warned
    from tests.conftest import FAKE_PRODUCTS
    monkeypatch.setitem(FAKE_PRODUCTS, "81707", {"title": "ACRYLIC PAINT MINI XF-70 DARK GREEN 2",
                                                "series": "x", "description": None})
    assert "doesn't mention XF-7" in client.get("/api/lookup/tamiya/XF-7").json()["warning"]


def test_photo_upload_replace_serve_and_remove(client, ids, make_supply):
    s = make_supply()
    url = f"/api/product-photo?brand_id={ids['tamiya']}&product_code=T81701"
    assert client.put(url, content=b"hello", headers={"Content-Type": "text/plain"}).status_code == 415

    png = b"\x89PNG\r\n\x1a\nfake"
    assert client.put(url, content=png, headers={"Content-Type": "image/png"}).status_code == 200
    s = client.get(f"/api/supplies/{s['supply_id']}").json()
    assert s["has_image"] is True
    photo = client.get(f"/api/product-images/{s['product_info_id']}")
    assert photo.content == png and photo.headers["content-type"] == "image/png"

    assert client.delete(url).status_code == 204
    assert client.get(f"/api/supplies/{s['supply_id']}").json()["has_image"] is False
