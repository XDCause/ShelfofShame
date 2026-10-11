"""The Tamiya helpers on their own: parsing real saved pages, codes, barcodes, guesses."""
from pathlib import Path

import pytest

from app import tamiya

FIXTURES = Path(__file__).parent / "fixtures"


def page(name):
    return (FIXTURES / name).read_bytes().decode("cp932", errors="replace")


def test_parse_a_real_paint_page():
    info = tamiya.parse(page("tamiya_81701.html"))
    assert info["title"] == "ACRYLIC PAINT MINI XF-1 FLAT BLACK"
    assert info["series"] == "Tamiya Color Acrylic Paint Mini"
    assert "Contents: 10ml" in info["description"]
    assert info["image_url"].endswith("/81701/81701_1.jpg")


def test_parse_a_real_cement_page():
    info = tamiya.parse(page("tamiya_87038.html"))
    assert info["title"] == "TAMIYA EXTRA-THIN CEMENT (40ml)"


def test_parse_rejects_a_non_product_page():
    with pytest.raises(tamiya.NotFound):
        tamiya.parse("<html><body><h1>Not here</h1></body></html>")


@pytest.mark.parametrize("typed, item", [
    ("T81701", "81701"), ("81701", "81701"), (" t87038 ", "87038"),
    ("XF-76", "81776"), ("xf76", "81776"), ("XF 1", "81701"), ("X-10", "81510"), ("X-20A", "81520"),
    ("XF-999", None), ("", None),
])
def test_item_number(typed, item):
    assert tamiya.item_number(typed) == item


@pytest.mark.parametrize("title, code, expected", [
    ("ACRYLIC PAINT MINI XF-76 GRAY GREEN (IJN)", "XF-76", True),
    ("ACRYLIC PAINT MINI XF-7 FLAT RED", "XF-76", False),
    ("ACRYLIC PAINT MINI XF-76 GRAY GREEN (IJN)", "XF-7", False),
    ("ACRYLIC PAINT MINI X-10 GUN METAL", "X-1", False),
])
def test_title_mentions(title, code, expected):
    assert tamiya.title_mentions(title, code) is expected


@pytest.mark.parametrize("raw, normalised", [
    ("4950344070053", "4950344070053"),     # XF-76, read off the bottle
    ("4950344 07005 3", "4950344070053"),   # spaces ignored
    ("036000291452", "0036000291452"),      # UPC-A becomes EAN-13
    ("4950344070054", None),                # wrong check digit
    ("12345", None),
])
def test_normalise_barcode(raw, normalised):
    assert tamiya.normalise_barcode(raw) == normalised


def test_suggestions_from_titles():
    s = tamiya.suggest("ACRYLIC PAINT MINI XF-1 FLAT BLACK", "Tamiya Color Acrylic Paint Mini", "Contents: 10ml")
    assert s == {"name": "Acrylic Paint Mini XF-1 Flat Black", "category": "Paint",
                 "paint_type": "Acrylic", "finish": "Flat / Matt", "size": "10ml"}
    tape = tamiya.suggest("MASKING TAPE 10mm", "Tamiya Craft Tools", "Contents: 18m")
    assert (tape["category"], tape["size"]) == ("Masking Tape", "18m")  # length, not width
    assert tamiya.suggest("ACRYLIC PAINT MINI X-35 SEMI GLOSS CLEAR", "", None)["finish"] == "Semi-gloss"
    assert tamiya.suggest("ACRYLIC PAINT MINI X-10 GUN METAL", "", None)["finish"] == "Metallic"
    assert tamiya._nice_name("SURFACE PRIMER L (GRAY)") == "Surface Primer L (Gray)"
    assert tamiya._nice_name("ACRYLIC PAINT MINI XF-76 GRAY GREEN (IJN)") == \
        "Acrylic Paint Mini XF-76 Gray Green (IJN)"
    assert tamiya._nice_name("XF-82 OCEAN GRAY 2 (RAF)") == "XF-82 Ocean Gray 2 (RAF)"
