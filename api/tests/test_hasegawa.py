"""Hasegawa kit lookup: parsing a real (trimmed) page, codes, and the API with a fake site."""
from pathlib import Path

import pytest

from app import hasegawa, tamiya

FIXTURE = (Path(__file__).parent / "fixtures" / "hasegawa_jt86.html").read_text(encoding="utf-8")


def test_parse_the_p40e_page():
    info = hasegawa.parse(FIXTURE)
    assert info["title"] == "P-40E WARHAWK"
    assert (info["series"], info["item"], info["scale"]) == ("JT86", "09086", "1/48")
    assert info["image_url"].endswith("jt86p.jpg")


def test_parse_rejects_other_pages():
    with pytest.raises(tamiya.NotFound):
        hasegawa.parse("<html><body><h1>News</h1></body></html>")


@pytest.mark.parametrize("typed, expected", [
    ("JT86", ("series", "JT86")), ("jt 86", ("series", "JT86")), ("09086", ("item", "09086")),
    ("HSG09086", ("item", "09086")), ("HSG-07229", ("item", "07229")), ("", None), ("hello", None),
])
def test_normalise(typed, expected):
    assert hasegawa.normalise(typed) == expected


def test_item_numbers_to_series_codes():
    assert hasegawa.series_for_item("09086") == ["JT86"]
    assert hasegawa.series_for_item("07229") == ["PT29"]
    assert hasegawa.series_for_item("21171") == []  # no known rule: ask for the series code


PAGES = {
    "JT86": {"title": "P-40E WARHAWK", "series": "JT86", "item": "09086", "scale": "1/48", "category": None},
    "PT29": {"title": "MITSUBISHI F-2B", "series": "PT29", "item": "07229", "scale": "1/48", "category": None},
}


@pytest.fixture
def fake_hasegawa(monkeypatch):
    calls = []

    def fetch(series):
        calls.append(series)
        if series not in PAGES:
            raise tamiya.NotFound(f"Hasegawa has no page for {series}.")
        return {**PAGES[series], "source_url": f"http://www.hasegawa-model.co.jp/product_g/{series.lower()}/",
                "image": b"\xff\xd8fake", "image_type": "image/jpeg"}

    monkeypatch.setattr(hasegawa, "fetch", fetch)
    return calls


def test_lookup_by_item_number(client, fake_hasegawa):
    r = client.get("/api/lookup/hasegawa/09086").json()
    assert fake_hasegawa == ["JT86"]
    assert (r["name"], r["scale"], r["product_code"], r["series_code"]) == ("P-40E Warhawk", "1/48", "HSG09086", "JT86")
    assert r["has_image"] is True
    brands = [b["name"] for b in client.get("/api/lookups").json()["brands"]]
    assert "Hasegawa" in brands  # added on first use

    # Cached: by item number, by series code, or by your product code - no second fetch
    for code in ("09086", "JT86", "HSG09086"):
        assert client.get(f"/api/lookup/hasegawa/{code}").json()["from_cache"] is True
    assert fake_hasegawa == ["JT86"]


def test_lookup_by_series_code(client, fake_hasegawa):
    r = client.get("/api/lookup/hasegawa/pt29").json()
    assert (r["name"], r["product_code"]) == ("Mitsubishi F-2B", "HSG07229")


def test_a_page_for_a_different_item_is_rejected(client, fake_hasegawa, monkeypatch):
    # Pretend JT86's page says it's some other kit: the item number check must refuse it.
    monkeypatch.setitem(PAGES, "JT86", {**PAGES["JT86"], "item": "09999"})
    assert client.get("/api/lookup/hasegawa/09086").status_code == 404


def test_unknown_numbers_and_codes(client, fake_hasegawa):
    r = client.get("/api/lookup/hasegawa/21171")
    assert r.status_code == 404 and "series code" in r.json()["detail"]
    assert client.get("/api/lookup/hasegawa/ZZ99").status_code == 404
    assert client.get("/api/lookup/hasegawa/hello").status_code == 422


def test_model_from_a_hasegawa_lookup_shows_the_photo(client, fake_hasegawa):
    r = client.get("/api/lookup/hasegawa/JT86").json()
    m = client.post("/api/models", json={"name": r["name"], "brand_id": r["brand_id"],
                                         "product_code": r["product_code"], "scale": r["scale"]}).json()
    assert m["has_image"] is True and m["brand"] == "Hasegawa"
