"""Trumpeter look-ups: parsing their search and product pages (made-up pages in the same shape - no copied
pages in the repo), the item number, and the lookup route (trumpeter.fetch faked)."""
import pytest

from app import tamiya, trumpeter

SEARCH = """<html><body><div class="con_left"><a href="/index.php?g=home&m=product&a=show&id=11&l=en">
【 2015-02-09】 Some Hot Ship 03708</a></div>
<div class="con_right"><a href="/index.php?g=home&amp;m=product&amp;a=show&amp;id=4217&amp;l=en">Test Tank Kit 00968</a></div></body></html>"""

PAGE = """<html><body><div class="con_right"><table><tr><td><img src="/Uploads/202609/abc.jpg" id="bigpicimg" width="300"/></td>
<td><table><tr><td><h3>Test Tank Kit 00968</h3></td></tr><tr><td>Model:00968</td></tr></table></td></tr></table>
<p style="text-indent:2em;">A made-up tank for the tests.</p>
<table class="ke-zeroborder"><tbody>
<tr><td>Item No</td><td>&nbsp;&nbsp; 00968</td></tr>
<tr><td>Item\n  Name</td><td>&nbsp; Test Tank Kit</td></tr>
<tr><td>Bar Code</td><td>&nbsp; 9580208009681</td></tr>
<tr><td>Scale</td><td>&nbsp; 1:16</td></tr>
<tr><td>Item Type</td><td>&nbsp; Plastic Model Armor Kit</td></tr>
<tr><td>Model Brief</td><td>Length: 705.8mm&nbsp; Width: mm</td></tr>
<tr><td>Total Parts</td><td>1700+</td></tr>
<tr><td>Film Parts</td><td>n/a</td></tr>
<tr><td>Released Date</td><td>2026-09</td></tr>
</tbody></table></div></body></html>"""


def test_normalise():
    assert [trumpeter.normalise(c) for c in ("00968", "968", "TRU00968", "tr-00968", " 08005 ")] == ["00968"] * 4 + ["08005"]
    assert trumpeter.normalise("XF-1") is None and trumpeter.normalise("1234567") is None


def test_search_page_picks_the_item_not_the_hot_products():
    assert trumpeter.page_id_in(SEARCH, "00968") == 4217
    with pytest.raises(tamiya.NotFound):
        trumpeter.page_id_in(SEARCH, "01234")


def test_parse_a_product_page():
    p = trumpeter.parse(PAGE)
    assert (p["title"], p["item"], p["barcode"], p["scale"], p["item_type"], p["is_tool"]) == \
        ("Test Tank Kit", "00968", "9580208009681", "1/16", "Plastic Model Armor Kit", False)
    assert (p["size"], p["parts"], p["released"], p["intro"]) == ("Length 705.8mm", "1700+", "2026-09", "A made-up tank for the tests.")
    assert p["image_url"] == "https://www.trumpeter-china.com/Uploads/202609/abc.jpg"
    assert trumpeter.describe(p).startswith("Item no 00968 · Scale 1/16 · Plastic Model Armor Kit · Length 705.8mm · 1700+ parts")
    tool = trumpeter.parse(PAGE.replace("Plastic Model Armor Kit", "Modeling Tools").replace("1:16", ""))
    assert tool["is_tool"] and tool["scale"] is None
    with pytest.raises(tamiya.NotFound):
        trumpeter.parse("<html><body><h3>News</h3></body></html>")


@pytest.fixture
def fake_trumpeter(monkeypatch):
    asked = []

    def fetch(item, photo=True):
        asked.append(item)
        if item == "00968":
            return {**trumpeter.parse(PAGE), "source_url": "https://www.trumpeter-china.com/x", "image": None, "image_type": None}
        raise tamiya.NotFound(f"Trumpeter's site has nothing for item {item}.")
    monkeypatch.setattr(trumpeter, "fetch", fetch)
    return asked


def test_lookup_route(client, fake_trumpeter):
    r = client.get("/api/lookup/trumpeter/968")
    assert r.status_code == 200
    k = r.json()
    assert (k["product_code"], k["name"], k["scale"], k["item_type"], k["is_tool"], k["barcode"], k["from_cache"]) == \
        ("TRU00968", "Test Tank Kit", "1/16", "Plastic Model Armor Kit", False, "9580208009681", False)
    assert client.get("/api/lookup/trumpeter/TRU00968").json()["from_cache"] is True     # asked once
    assert fake_trumpeter == ["00968"]
    assert client.get("/api/scan/9580208009681").json()["product_code"] == "TRU00968"   # its box barcode now scans
    assert client.get("/api/lookup/trumpeter/01234").status_code == 404
    assert client.get("/api/lookup/trumpeter/XF-1").status_code == 422


def test_one_box_asks_both_makers(client, fake_trumpeter, monkeypatch):
    from app import products
    assert products.who_to_ask("XF-76") == ["Tamiya"] and products.who_to_ask("T81776") == ["Tamiya"]
    assert products.who_to_ask("TRU00968") == ["Trumpeter"] and products.who_to_ask("00968") == ["Tamiya", "Trumpeter"]
    asked = []

    def tamiya_fetch(item):
        asked.append(item)
        if item == "00968":       # made up: both makers have it
            return {"title": "TEST TAMIYA THING", "series": "Craft Tools", "description": None, "source_url": "x",
                    "image": None, "image_type": None, "kit_paints": []}
        raise tamiya.NotFound(f"Tamiya has no product page for item {item}.")
    monkeypatch.setattr(tamiya, "fetch", tamiya_fetch)
    both = client.get("/api/lookup/item/00968").json()
    assert [f["maker"] for f in both["found"]] == ["Tamiya", "Trumpeter"] and both["missed"] == []
    assert {f["product_code"] for f in both["found"]} == {"T00968", "TRU00968"}
    one = client.get("/api/lookup/item/968").json()          # Tamiya has no 968; Trumpeter's is 00968
    assert [f["maker"] for f in one["found"]] == ["Trumpeter"] and one["missed"][0]["status"] == 404
    assert client.get("/api/lookup/item/01234").status_code == 404
