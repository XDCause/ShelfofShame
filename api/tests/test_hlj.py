"""Bandai kits via HobbyLink Japan: parsing real (trimmed) pages, codes, and the API with a fake site."""
from pathlib import Path

import pytest

from app import hlj, tamiya

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = (FIXTURES / "hlj_banh574039.html").read_text(encoding="utf-8")
SEARCH = (FIXTURES / "hlj_search_rx78.html").read_text(encoding="utf-8")


def test_parse_the_rx78_page():
    info = hlj.parse(PAGE)
    assert info["title"] == "1/144 HGUC Revive RX-78-2 Gundam"
    assert (info["hlj_code"], info["barcode"]) == ("BANH574039-UP", "4573102574039")
    assert (info["grade"], info["scale"]) == ("HG", "1/144")
    assert (info["series"], info["item_type"], info["maker"]) == ("Gundam 0079", "High Grade Kits", "Bandai")
    assert info["released"] == "2025/04/30"
    assert info["image_url"] == "https://www.hlj.com/productimages/ban/banh574039-up_0.jpg"


def test_parse_rejects_other_pages():
    with pytest.raises(tamiya.NotFound):
        hlj.parse("<html><body><h1>Sale!</h1></body></html>")


def test_parse_search_results():
    results = hlj.parse_search(SEARCH)
    assert [r["hlj_code"] for r in results] == ["BANH574039-UP", "BANH574022-UP"]
    rx78 = results[0]
    assert rx78["title"] == "1/144 HGUC Revive RX-78-2 Gundam"
    assert rx78["path"] == "/1-144-scale-hguc-revive-rx-78-2-gundam-banh574039-up"
    assert rx78["thumb_url"].startswith("https://www.hlj.com/productthumbs/ban/banh574039-up")


@pytest.mark.parametrize("typed, expected", [
    ("G5057403", ("barcode", "4573102574039")),     # the user's code
    ("5057403", ("barcode", "4573102574039")),
    ("57403", ("barcode", "4573102574039")),
    ("4573102574039", ("barcode", "4573102574039")),
    ("BANH574039-UP", ("hlj", "BANH574039-UP")),
    ("banh574039-up", ("hlj", "BANH574039-UP")),
    ("rx-78-2 revive", ("name", "rx-78-2 revive")),
    ("4573102574038", ("name", "4573102574038")),   # bad check digit: not a barcode
    ("  ", None),
])
def test_normalise(typed, expected):
    assert hlj.normalise(typed) == expected


@pytest.mark.parametrize("title, grade", [
    ("1/144 HGUC Revive RX-78-2 Gundam", "HG"), ("1/144 HGCE Rising Freedom", "HG"),
    ("1/144 RG Zeta Gundam", "RG"), ("1/100 MG Sazabi Ver.Ka", "MG"), ("1/60 PG Unleashed RX-78-2", "PG"),
    ("1/144 Entry Grade RX-78-2", "EG"), ("1/100 RE/100 Nightingale", "RE/100"),
    ("1/100 Full Mechanics Calamity", "FM"), ("SDCS Strike Freedom", "SD"), ("Haro Pla", None),
])
def test_grades(title, grade):
    assert hlj.grade_of(title) == grade


def test_codes():
    assert hlj.bandai_barcode("57403") == "4573102574039"
    assert hlj.product_code_for("4573102574039", "BANH574039-UP") == "G5057403"
    assert hlj.product_code_for("4543112948737", "BAN948737") == "BAN948737"   # older Bandai numbering
    assert hlj.name_of("1/144 HGUC Revive RX-78-2 Gundam") == "HGUC Revive RX-78-2 Gundam"


# ---------------------------------------------------------------- the API, with a fake hlj.com
@pytest.fixture
def fake_hlj(monkeypatch):
    calls = []
    page = hlj.parse(PAGE)
    results = hlj.parse_search(SEARCH)

    def search(query):
        calls.append(("search", query))
        if query in ("4573102574039", "BANH574039-UP"):
            return [r for r in results if r["hlj_code"] == "BANH574039-UP"]
        if query == "rx-78-2 revive":
            return results
        if query == "guncannon revive":
            return [r for r in results if r["hlj_code"] == "BANH574022-UP"]
        return []

    def fetch(path):
        calls.append(("page", path))
        if "banh574022" in path:
            return {**page, "title": "1/144 HGUC Revive RX-77-2 Guncannon", "hlj_code": "BANH574022-UP",
                    "barcode": "4573102574022", "source_url": hlj.SITE + path, "image": b"\xff\xd8fake",
                    "image_type": "image/jpeg"}
        return {**page, "source_url": hlj.SITE + path, "image": b"\xff\xd8fake", "image_type": "image/jpeg"}

    monkeypatch.setattr(hlj, "search", search)
    monkeypatch.setattr(hlj, "fetch", fetch)
    monkeypatch.setattr(hlj, "PAUSE", 0)
    return calls


def test_lookup_by_the_users_code(client, fake_hlj):
    r = client.get("/api/lookup/bandai/G5057403").json()
    assert fake_hlj[0] == ("search", "4573102574039")   # searched by the box barcode
    assert (r["name"], r["grade"], r["scale"]) == ("HGUC Revive RX-78-2 Gundam", "HG", "1/144")
    assert (r["product_code"], r["barcode"], r["has_image"]) == ("G5057403", "4573102574039", True)
    assert "High Grade Kits" in r["description"] and "HLJ BANH574039-UP" in r["description"]
    assert r["source_url"].startswith("https://www.hlj.com/")
    assert "Bandai" in [b["name"] for b in client.get("/api/lookups").json()["brands"]]

    # Cached: by code, barcode or HLJ code - no more requests
    for code in ("G5057403", "4573102574039", "BANH574039-UP"):
        assert client.get(f"/api/lookup/bandai/{code}").json()["from_cache"] is True
    assert len(fake_hlj) == 2   # one search + one page


def test_a_name_with_several_matches_offers_choices(client, fake_hlj):
    r = client.get("/api/lookup/bandai/rx-78-2 revive").json()
    assert [c["hlj_code"] for c in r["choices"]] == ["BANH574039-UP", "BANH574022-UP"]
    assert ("page", "/1-144-scale-hguc-revive-rx-78-2-gundam-banh574039-up") not in fake_hlj
    picked = client.get("/api/lookup/bandai/BANH574039-UP").json()   # the pick, by its HLJ code
    assert picked["product_code"] == "G5057403"


def test_a_name_with_one_match_is_looked_up(client, fake_hlj):
    r = client.get("/api/lookup/bandai/guncannon revive").json()
    assert (r["name"], r["product_code"]) == ("HGUC Revive RX-77-2 Guncannon", "G5057402")


def test_a_page_for_a_different_barcode_is_rejected(client, fake_hlj, monkeypatch):
    real = hlj.fetch
    monkeypatch.setattr(hlj, "fetch", lambda path: {**real(path), "barcode": "4573102999995"})
    r = client.get("/api/lookup/bandai/G5057403")
    assert r.status_code == 404 and "different kit" in r.json()["detail"]


def test_nothing_found(client, fake_hlj):
    assert client.get("/api/lookup/bandai/G5099999").status_code == 404
    assert client.get("/api/lookup/bandai/%20").status_code == 422


def test_model_from_a_bandai_lookup_shows_the_photo(client, fake_hlj):
    r = client.get("/api/lookup/bandai/G5057403").json()
    m = client.post("/api/models", json={"name": r["name"], "hobby": "Gundam", "brand_id": r["brand_id"],
                                         "product_code": r["product_code"], "grade": r["grade"],
                                         "scale": r["scale"]}).json()
    assert m["has_image"] is True and m["source_url"].startswith("https://www.hlj.com/")
