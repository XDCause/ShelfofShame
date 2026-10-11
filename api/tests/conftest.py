"""Shared test setup. Run the suite with .\\run_tests.ps1 from the project folder.

The tests run against a separate, freshly built database (hobby_inventory_test) and never
touch your real data. tamiya.com is replaced by a fake, so tests are fast and offline.
"""
import os

import pytest

if not os.environ.get("POSTGRES_DB", "").endswith("_test"):
    pytest.exit("Refusing to run: POSTGRES_DB must be a *_test database (use run_tests.ps1).",
                returncode=2)

from fastapi.testclient import TestClient  # noqa: E402

from app import tamiya  # noqa: E402
from app.db import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Every test starts with the seeded lookup lists and nothing else."""
    with db() as conn:
        conn.execute("TRUNCATE stock_movements, wishlist, barcode_catalog, product_info, supplies "
                     "RESTART IDENTITY CASCADE")
        conn.execute("DELETE FROM brands WHERE name NOT IN ('Tamiya', 'Milliput', 'Microscale', 'Other')")
        conn.execute("DELETE FROM categories WHERE name LIKE 'Test %'")
        conn.execute("DELETE FROM storage_locations WHERE name LIKE 'Test %'")
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def ids():
    """Ids of seeded lookup rows the tests use."""
    with db() as conn:
        one = lambda q: conn.execute(q).fetchone()["id"]  # noqa: E731
        return {
            "tamiya": one("SELECT brand_id AS id FROM brands WHERE name = 'Tamiya'"),
            "milliput": one("SELECT brand_id AS id FROM brands WHERE name = 'Milliput'"),
            "paint": one("SELECT category_id AS id FROM categories WHERE name = 'Paint'"),
            "glue": one("SELECT category_id AS id FROM categories WHERE name = 'Glue / Cement'"),
            "other_location": one("SELECT location_id AS id FROM storage_locations WHERE name = 'Other'"),
        }


@pytest.fixture
def make_supply(client, ids):
    """Create a supply through the API; keyword arguments override the defaults."""
    def make(**overrides):
        body = {"brand_id": ids["tamiya"], "product_code": "T81701", "name": "Acrylic XF1 Flat Black",
                "category_id": ids["paint"], "paint_type": "Acrylic", "finish": "Flat / Matt",
                "size": "10ml", "qty_on_hand": 1, "reorder_at": 0, "unit_price": "3.95"}
        body.update(overrides)
        r = client.post("/api/supplies", json=body)
        assert r.status_code == 201, r.text
        return r.json()
    return make


FAKE_PRODUCTS = {
    "81776": {"title": "ACRYLIC PAINT MINI XF-76 GRAY GREEN (IJN)",
              "series": "Tamiya Color Acrylic Paint Mini", "description": "Contents: 10ml"},
    "81701": {"title": "ACRYLIC PAINT MINI XF-1 FLAT BLACK",
              "series": "Tamiya Color Acrylic Paint Mini", "description": "Contents: 10ml"},
    "87038": {"title": "TAMIYA EXTRA-THIN CEMENT (40ml)", "series": "Cement & Putty No.38",
              "description": None},
}


@pytest.fixture
def fake_tamiya(monkeypatch):
    """Stand-in for tamiya.fetch. Returns the list of item numbers it was asked for."""
    calls = []

    def fetch(item):
        calls.append(item)
        if item not in FAKE_PRODUCTS:
            raise tamiya.NotFound(f"Tamiya has no product page for item {item}.")
        return {**FAKE_PRODUCTS[item],
                "source_url": f"https://www.tamiya.com/english/products/{item}/index.html",
                "image": b"\xff\xd8fake-jpeg", "image_type": "image/jpeg"}

    monkeypatch.setattr(tamiya, "fetch", fetch)
    return calls
