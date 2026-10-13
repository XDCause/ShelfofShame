"""Settings: default shop, price guide, backups, CSV exports and the catalogue refresh."""
import csv
import io

import pytest

from app import catalog, settings, tamiya_catalog
from tests.conftest import FIXTURES


# ---------------------------------------------------------------- default shop
def test_default_shop_is_hobbyrama_and_can_change(client):
    assert client.get("/api/settings").json() == {"default_shop": "Hobbyrama"}
    assert client.patch("/api/settings", json={"default_shop": " Frontline Hobbies "}).json() == \
        {"default_shop": "Frontline Hobbies"}
    assert client.patch("/api/settings", json={"default_shop": ""}).json() == {"default_shop": None}


def test_buying_without_a_shop_uses_the_default(client, ids):
    wish = client.post("/api/wishlist", json={"name": "Thing", "category_id": ids["paint"]}).json()
    bought = client.post(f"/api/wishlist/{wish['wish_id']}/buy").json()
    assert client.get(f"/api/supplies/{bought['supply_id']}").json()["purchased_from"] == "Hobbyrama"
    # a typed shop still wins
    wish = client.post("/api/wishlist", json={"name": "Other thing", "category_id": ids["paint"]}).json()
    client.patch(f"/api/wishlist/{wish['wish_id']}", json={"got_it": True})
    [bought] = client.post("/api/wishlist/buy-ticked", json={"purchased_from": "Hobbyco"}).json()
    assert client.get(f"/api/supplies/{bought['supply_id']}").json()["purchased_from"] == "Hobbyco"


# ---------------------------------------------------------------- price guide
def test_price_guide_starts_with_the_users_prices(client):
    rules = client.get("/api/price-guide").json()
    assert [(r["label"], float(r["price"])) for r in rules] == [("Panel Line Accent", 10.95),
                                                                ("Acrylic paint, 10ml", 3.95)]


def test_price_guide_rules_are_used_and_editable(client, tamiya_catalogue, fake_tamiya):
    acrylic = client.get("/api/price-guide").json()[1]
    client.patch(f"/api/price-guide/{acrylic['rule_id']}", json={"price": "4.25"})
    lp = client.post("/api/price-guide", json={"label": "LP lacquer", "paint_type": "Lacquer",
                                               "size": "10 ml", "price": "6.50"}).json()
    assert lp["size"] == "10 ml"

    assert client.post("/api/catalog/T81762/wishlist").json()["est_price"] == 4.25
    assert client.post("/api/catalog/T82128/wishlist").json()["est_price"] == 6.5   # "10 ml" == "10ml"
    assert client.post("/api/catalog/T87131/wishlist").json()["est_price"] == 10.95

    assert client.delete(f"/api/price-guide/{lp['rule_id']}").status_code == 204
    assert client.delete(f"/api/price-guide/{lp['rule_id']}").status_code == 404


@pytest.mark.parametrize("body", [
    {"label": "Matches everything", "price": "1.00"},                     # no condition at all
    {"label": "Odd type", "paint_type": "Glitter", "price": "1.00"},
    {"label": "Negative", "size": "10ml", "price": "-1"},
    {"label": "", "size": "10ml", "price": "1"},
])
def test_bad_price_rules_are_refused(client, body):
    assert client.post("/api/price-guide", json=body).status_code == 422


def test_lookup_suggests_the_usual_price(client, fake_tamiya):
    r = client.get("/api/lookup/tamiya/XF-76").json()
    assert float(r["suggested"]["est_price"]) == 3.95


# ---------------------------------------------------------------- backups
@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIR", tmp_path)
    return tmp_path


def test_back_up_now_list_and_download(client, backup_dir):
    made = client.post("/api/backups")
    assert made.status_code == 201, made.text
    name = made.json()["name"]
    assert (backup_dir / name).stat().st_size > 1000          # a real pg_dump of the test database
    listing = client.get("/api/backups").json()
    assert listing["available"] and [b["name"] for b in listing["backups"]] == [name]
    assert listing["log"][0].endswith(f"OK: {name} ({round(made.json()['size'] / 1024)} KB) - from the app")

    download = client.get(f"/api/backups/{name}")
    assert download.status_code == 200 and download.content[:5] == b"PGDMP"   # pg_dump's custom format
    assert client.get("/api/backups/../../etc/passwd").status_code == 404
    assert client.get("/api/backups/hobby_inventory_20200101_000000.dump").status_code == 404


def test_only_the_newest_14_backups_are_kept(client, backup_dir):
    for day in range(1, 16):
        (backup_dir / f"hobby_inventory_202001{day:02d}_000000.dump").write_bytes(b"old")
    client.post("/api/backups")
    names = [b["name"] for b in client.get("/api/backups").json()["backups"]]
    assert len(names) == 14 and "hobby_inventory_20200101_000000.dump" not in names


def test_backups_without_the_folder(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIR", tmp_path / "missing")
    assert client.get("/api/backups").json()["available"] is False
    assert client.post("/api/backups").status_code == 503


# ---------------------------------------------------------------- CSV exports
def read_csv(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")                     # so Excel reads it as UTF-8
    return list(csv.DictReader(io.StringIO(text[1:])))


def test_csv_exports(client, make_supply, ids):
    make_supply(name="Acrylic XF1 Flat Black", unit_price="3.95")
    client.post("/api/wishlist", json={"name": "Thing ×2", "category_id": ids["paint"]})
    model = client.post("/api/models", json={"name": "Zero", "status": "In progress"}).json()
    client.post(f"/api/models/{model['model_id']}/paints", json={"text": "XF-1\tCockpit"})

    [row] = read_csv(client.get("/api/export/inventory.csv"))
    assert (row["Name"], row["Price"], row["Status"]) == ("Acrylic XF1 Flat Black", "3.95", "OK")
    assert read_csv(client.get("/api/export/wishlist.csv"))[0]["Name"] == "Thing ×2"
    assert read_csv(client.get("/api/export/models.csv"))[0]["Status"] == "In progress"
    assert read_csv(client.get("/api/export/model-paints.csv"))[0]["What it's for"] == "Cockpit"
    assert read_csv(client.get("/api/export/history.csv"))[0]["Reason"] == "added"
    assert client.get("/api/export/passwords.csv").status_code == 404


# ---------------------------------------------------------------- catalogue refresh
def test_catalogue_refresh_runs_in_the_background(client, ids, monkeypatch):
    page = (FIXTURES / "tamiya_list_e_5010.html").read_text(encoding="utf-8")
    monkeypatch.setattr(tamiya_catalog, "fetch_list", lambda client, genre, number: page)
    monkeypatch.setattr(tamiya_catalog, "DELAY_SECONDS", 0)
    monkeypatch.setattr(tamiya_catalog.time, "sleep", lambda s: None)

    started = client.post("/api/catalog/refresh")    # the test client runs the background task too
    assert started.status_code == 202
    info = client.get("/api/catalog/info").json()
    assert info["products"] == 3 and info["refresh"]["running"] is False
    assert info["refresh"]["message"] == "Done: 3 products" and info["refresh"]["error"] is None


def test_only_one_refresh_at_a_time(client, monkeypatch):
    monkeypatch.setitem(catalog.REFRESH, "running", True)
    assert client.post("/api/catalog/refresh").status_code == 409


def test_a_failed_refresh_is_reported(client, monkeypatch):
    def broken(client, genre, number):
        raise RuntimeError("tamiya.com is down")
    monkeypatch.setattr(tamiya_catalog, "fetch_list", broken)
    monkeypatch.setattr(tamiya_catalog.time, "sleep", lambda s: None)
    client.post("/api/catalog/refresh")
    refresh = client.get("/api/catalog/info").json()["refresh"]
    assert refresh["running"] is False and "tamiya.com is down" in refresh["error"]
