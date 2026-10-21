"""More for Supplies (88_supplies_more.sql, api/app/supplies_more.py, supplies.py): places that nest, QR labels, shelf
life, the usage forecast, stocktake, shopping, attachments, bulk changes, the value report, maintenance to-dos."""
from datetime import date, timedelta

from app.db import db

TODAY = date.today()


def place(client, name, parent=None):
    r = client.post("/api/places", json={"name": name, "parent_id": parent})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- places
def test_places_nest_and_show_their_path(client, make_supply):
    rack = place(client, "Test rack")
    drawer = place(client, "Drawer 2", rack["id"])
    other = place(client, "Drawer 2", place(client, "Test chest")["id"])          # the same name beside other siblings
    assert drawer["path"] == "Test rack › Drawer 2" and other["path"] == "Test chest › Drawer 2"
    assert client.post("/api/places", json={"name": "drawer 2", "parent_id": rack["id"]}).status_code == 409
    s = make_supply(location_id=drawer["id"])
    assert client.get(f"/api/supplies/{s['supply_id']}").json()["location_path"] == "Test rack › Drawer 2"
    whole = client.get(f"/api/places/{rack['id']}").json()                           # what's in it, and in its drawers
    assert [x["name"] for x in whole["inside"]] == ["Drawer 2"] and [x["supply_id"] for x in whole["supplies"]] == [s["supply_id"]]
    assert client.patch(f"/api/places/{rack['id']}", json={"parent_id": drawer["id"]}).status_code == 422   # not inside itself
    assert client.delete(f"/api/places/{drawer['id']}").status_code == 409                                   # still has things
    box = place(client, "Test box")
    moved = client.post(f"/api/places/{box['id']}/move", json={"supply_ids": [s["supply_id"]]}).json()
    assert [x["supply_id"] for x in moved["supplies"]] == [s["supply_id"]]
    assert client.delete(f"/api/places/{drawer['id']}").status_code == 204
    qr = client.get(f"/api/places/{box['id']}/qr?url=https://pc.local:8443/supplies/place/{box['id']}")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg") and b'xmlns="http://www.w3.org/2000/svg"' in qr.content
    assert client.get(f"/api/places/{box['id']}/qr?url=javascript:alert(1)").status_code == 422


# ---------------------------------------------------------------- shelf life, forecast, set aside, warranty, swatch
def test_opening_starts_the_shelf_life_and_check_is_due_after_it(client, make_supply, ids):
    s = make_supply(condition="Sealed")
    opened = client.patch(f"/api/supplies/{s['supply_id']}", json={"condition": "Opened"}).json()
    assert opened["opened_on"] == TODAY.isoformat() and opened["shelf_life"] == 36 and not opened["check_due"]    # Paint: 3 years
    old = client.patch(f"/api/supplies/{s['supply_id']}", json={"opened_on": (TODAY - timedelta(days=800)).isoformat(),
                                                                  "shelf_months": 24}).json()
    assert old["check_due"] and old["check_by"] < TODAY.isoformat()
    assert client.patch(f"/api/supplies/{s['supply_id']}", json={"condition": "Half used"}).json()["opened_on"] != TODAY.isoformat()


def test_the_forecast_comes_from_how_fast_you_use_it(client, make_supply):
    s = make_supply(qty_on_hand=5)
    assert client.get(f"/api/supplies/{s['supply_id']}").json()["out_by"] is None          # no history yet
    for _ in range(3):
        client.post(f"/api/supplies/{s['supply_id']}/adjust", json={"delta": -1})
    with db() as conn:                                                                      # used 3 over 60 days
        conn.execute("UPDATE stock_movements SET created_at = now() - interval '60 days' WHERE supply_id = %s "
                     "AND movement_id = (SELECT min(movement_id) FROM stock_movements WHERE supply_id = %s AND reason = 'used')",
                     (s["supply_id"], s["supply_id"]))
    got = client.get(f"/api/supplies/{s['supply_id']}").json()
    assert got["used_year"] == 3 and abs(got["uses_per_month"] - 1.5) < 0.1
    assert date.fromisoformat(got["out_by"]) == TODAY + timedelta(days=40)                  # 2 left at one per 20 days


def test_set_aside_warranty_and_swatch(client, make_supply):
    sherman = client.post("/api/models", json={"name": "Sherman"}).json()
    s = make_supply()
    got = client.patch(f"/api/supplies/{s['supply_id']}", json={"reserved_model_id": sherman["model_id"], "swatch": "#5a6b3c",
                                                                  "warranty_until": (TODAY + timedelta(days=10)).isoformat()}).json()
    assert got["reserved_for"] == "Sherman" and got["swatch"] == "#5a6b3c" and got["warranty_soon"]
    assert client.patch(f"/api/supplies/{s['supply_id']}", json={"swatch": "green"}).status_code == 422
    assert client.patch(f"/api/supplies/{s['supply_id']}", json={"reserved_model_id": 999999}).status_code == 404
    client.delete(f"/api/models/{sherman['model_id']}")
    assert client.get(f"/api/supplies/{s['supply_id']}").json()["reserved_for"] is None


# ---------------------------------------------------------------- stocktake, shopping
def test_stocktake_counts_least_recently_counted_first(client, make_supply):
    a = make_supply(name="A paint", product_code="T1", qty_on_hand=3, reorder_at=1)
    b = make_supply(name="B paint", product_code="T2", qty_on_hand=2)
    counted = client.post(f"/api/supplies/{a['supply_id']}/count", json={"qty": 1}).json()
    assert counted["qty_on_hand"] == 1 and counted["counted_at"] and counted["auto_wish_id"]     # now Low: on the wishlist
    assert [x["supply_id"] for x in client.get("/api/supplies/stocktake").json()] == [b["supply_id"], a["supply_id"]]
    history = client.get(f"/api/supplies/{a['supply_id']}/history").json()
    assert history[0]["reason"] == "counted" and history[0]["change"] == -2


def test_the_shopping_list_has_the_wishlist_and_whats_low(client, make_supply):
    low = make_supply(name="Low paint", product_code="T3", qty_on_hand=0)            # Out, but not on the wishlist
    with db() as conn:
        conn.execute("DELETE FROM wishlist")
    wished = client.post(f"/api/supplies/{make_supply(name='Wanted', product_code='T4')['supply_id']}/wishlist").json()
    out = client.get("/api/supplies/shop").json()
    assert out["shop"] == "Hobbyrama" and [w["name"] for w in out["wishlist"]] == ["Wanted"]
    assert [s["supply_id"] for s in out["low"]] == [low["supply_id"]] and wished


# ---------------------------------------------------------------- attachments
def test_attachments_on_supplies_and_gear(client, make_supply):
    s = make_supply()
    up = client.post(f"/api/attachments?thing_kind=supply&thing_id={s['supply_id']}&name=Receipt.pdf&kind=Receipt",
                     content=b"%PDF-1.4 fake", headers={"content-type": "application/pdf"})
    assert up.status_code == 201, up.text
    a = up.json()
    assert [x["name"] for x in client.get(f"/api/attachments?thing_kind=supply&thing_id={s['supply_id']}").json()] == ["Receipt.pdf"]
    got = client.get(f"/api/attachments/{a['attachment_id']}")
    assert got.content == b"%PDF-1.4 fake" and got.headers["content-type"] == "application/pdf"
    assert client.post(f"/api/attachments?thing_kind=supply&thing_id={s['supply_id']}&name=x.exe", content=b"MZ",
                       headers={"content-type": "application/x-msdownload"}).status_code == 415
    assert client.post("/api/attachments?thing_kind=gear&thing_id=999&name=a.pdf", content=b"%PDF",
                       headers={"content-type": "application/pdf"}).status_code == 404
    client.delete(f"/api/supplies/{s['supply_id']}")                                    # it goes with its supply
    assert client.get(f"/api/attachments/{a['attachment_id']}").status_code == 404


# ---------------------------------------------------------------- bulk, value report, maintenance
def test_bulk_changes(client, make_supply, ids):
    a = make_supply(name="A", product_code="T5")
    b = make_supply(name="B", product_code="T6")
    box = place(client, "Test box")
    both = [a["supply_id"], b["supply_id"]]
    assert client.post("/api/supplies/bulk", json={"supply_ids": both, "action": "move", "value": box["id"]}).json() == {"changed": 2}
    assert {x["location_path"] for x in client.get("/api/supplies").json()} == {"Test box"}
    client.post("/api/supplies/bulk", json={"supply_ids": both, "action": "category", "value": ids["glue"]})
    assert {x["category"] for x in client.get("/api/supplies").json()} == {"Glue / Cement"}
    client.post("/api/supplies/bulk", json={"supply_ids": both, "action": "wishlist"})
    assert all(x["on_wishlist"] for x in client.get("/api/supplies").json())
    assert client.post("/api/supplies/bulk", json={"supply_ids": [*both, 99999], "action": "delete"}).status_code == 422
    assert client.post("/api/supplies/bulk", json={"supply_ids": both, "action": "category"}).status_code == 422
    client.post("/api/supplies/bulk", json={"supply_ids": both, "action": "delete"})
    assert client.get("/api/supplies").json() == []


def test_the_value_report_adds_up_each_hobby(client, make_supply):
    make_supply(qty_on_hand=2, unit_price="3.95")
    client.post("/api/gear", json={"name": "Shoes", "hobby": "volleyball", "price_paid": 180})
    client.post("/api/gear", json={"name": "Pads", "hobby": "volleyball"})                       # no price: listed, $0
    client.post("/api/shooting/ammo", json={"name": "Center-X", "rounds_bought": 500, "box_size": 50, "box_price": 20})
    out = client.get("/api/supplies/value-report").json()
    by = {s["title"]: s for s in out["sections"]}
    assert by["Hobby supplies"]["total"] == 7.9 and by["Volleyball gear"]["total"] == 180 and by["Volleyball gear"]["unpriced"] == 1
    assert by["Ammunition"]["total"] == 200 and out["total"] == 387.9


def test_maintenance_is_a_repeating_todo_on_the_tool(client, make_supply):
    s = make_supply(name="Airbrush", product_code="T7")
    t = client.post("/api/todos", json={"title": "Clean the airbrush", "supply_id": s["supply_id"], "repeats": "weekly",
                                        "due_on": TODAY.isoformat()}).json()
    assert [x["title"] for x in client.get(f"/api/todos?supply_id={s['supply_id']}").json()] == ["Clean the airbrush"]
    nxt = client.post(f"/api/todos/{t['todo_id']}/done").json()["next"]
    assert nxt["supply_id"] == s["supply_id"] and nxt["due_on"] == (TODAY + timedelta(days=7)).isoformat()
    assert client.post("/api/todos", json={"title": "x", "supply_id": 99999}).status_code == 422
