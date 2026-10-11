"""Supplies: create, calculated fields, validation, adjusting stock, search, lookup lists."""


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_create_returns_names_and_calculated_fields(make_supply):
    s = make_supply(qty_on_hand=2, unit_price="3.95")
    assert s["item_ref"] == "SUP-0001"
    assert s["brand"] == "Tamiya" and s["category"] == "Paint"
    assert s["stock_status"] == "OK"
    assert float(s["total_value"]) == 7.90


def test_stock_status_rules(make_supply):
    assert make_supply(product_code="A", qty_on_hand=0)["stock_status"] == "Out"
    assert make_supply(product_code="B", qty_on_hand=1, reorder_at=1)["stock_status"] == "Low"
    assert make_supply(product_code="C", qty_on_hand=2, reorder_at=1)["stock_status"] == "OK"
    assert make_supply(product_code="D", qty_on_hand=1, reorder_at=None)["stock_status"] == "OK"


def test_last_bottle_running_out_counts_as_low(make_supply):
    for i, condition in enumerate(["Nearly empty", "Empty", "Dried out"]):
        assert make_supply(product_code=f"L{i}", qty_on_hand=1, condition=condition)["stock_status"] == "Low"
    assert make_supply(product_code="H", qty_on_hand=1, condition="Half used")["stock_status"] == "OK"
    # A spare in the cupboard: one nearly empty bottle isn't Low while there's a second
    assert make_supply(product_code="S", qty_on_hand=2, condition="Nearly empty")["stock_status"] == "OK"


def test_same_brand_and_code_twice_is_refused(client, make_supply, ids):
    make_supply()
    r = client.post("/api/supplies", json={"brand_id": ids["tamiya"], "product_code": "T81701",
                                           "name": "Again", "category_id": ids["paint"]})
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


def test_values_outside_the_allowed_lists_are_refused(client, ids):
    r = client.post("/api/supplies", json={"name": "Bad", "category_id": ids["paint"], "finish": "Shiny"})
    assert r.status_code == 422
    r = client.post("/api/supplies", json={"name": "Bad", "category_id": ids["paint"], "qty_on_hand": -1})
    assert r.status_code == 422


def test_adjust_up_and_down_but_never_below_zero(client, make_supply):
    s = make_supply(qty_on_hand=1)
    assert client.post(f"/api/supplies/{s['supply_id']}/adjust", json={"delta": 2}).json()["qty_on_hand"] == 3
    assert client.post(f"/api/supplies/{s['supply_id']}/adjust", json={"delta": -3}).json()["qty_on_hand"] == 0
    r = client.post(f"/api/supplies/{s['supply_id']}/adjust", json={"delta": -1})
    assert r.status_code == 422
    assert r.json()["detail"] == "Quantity can't go below 0."
    assert client.get(f"/api/supplies/{s['supply_id']}").json()["qty_on_hand"] == 0


def test_adding_stock_sets_last_purchased_to_today(client, make_supply):
    from datetime import date
    s = make_supply(qty_on_hand=1, purchase_date="2026-01-05")
    used = client.post(f"/api/supplies/{s['supply_id']}/adjust", json={"delta": -1}).json()
    assert used["purchase_date"] == "2026-01-05"  # using one doesn't change it
    bought = client.post(f"/api/supplies/{s['supply_id']}/adjust", json={"delta": 1}).json()
    assert bought["purchase_date"] == date.today().isoformat()


def test_patch_changes_only_what_was_sent(client, make_supply):
    s = make_supply(notes=None)
    r = client.patch(f"/api/supplies/{s['supply_id']}", json={"notes": "half used"})
    after = r.json()
    assert after["notes"] == "half used"
    assert after["name"] == s["name"] and after["qty_on_hand"] == s["qty_on_hand"]


def test_search_and_filters(client, make_supply, ids):
    make_supply(product_code="T81701", name="Acrylic XF1 Flat Black")
    make_supply(product_code="T87038", name="Extra Thin Cement", category_id=ids["glue"], qty_on_hand=0)
    names = lambda r: [s["name"] for s in r.json()]  # noqa: E731
    assert names(client.get("/api/supplies", params={"q": "flat"})) == ["Acrylic XF1 Flat Black"]
    assert names(client.get("/api/supplies", params={"q": "87038"})) == ["Extra Thin Cement"]
    assert names(client.get("/api/supplies", params={"category": "Glue / Cement"})) == ["Extra Thin Cement"]
    assert names(client.get("/api/supplies", params={"status": "Out"})) == ["Extra Thin Cement"]
    assert names(client.get("/api/supplies/low-stock")) == ["Extra Thin Cement"]
    # LIKE wildcards are treated as plain characters
    assert client.get("/api/supplies", params={"q": "%"}).json() == []


def test_delete(client, make_supply):
    s = make_supply()
    assert client.delete(f"/api/supplies/{s['supply_id']}").status_code == 204
    assert client.get(f"/api/supplies/{s['supply_id']}").status_code == 404
    assert client.delete(f"/api/supplies/{s['supply_id']}").status_code == 404


def test_lookup_lists_add_remove_and_in_use_protection(client, make_supply, ids):
    added = client.post("/api/lookups/brands", json={"name": "Vallejo"}).json()
    assert client.post("/api/lookups/brands", json={"name": "Vallejo"}).status_code == 409
    assert client.delete(f"/api/lookups/brands/{added['id']}").status_code == 204

    make_supply()
    tamiya = next(b for b in client.get("/api/lookups").json()["brands"] if b["name"] == "Tamiya")
    assert tamiya["uses"] == 1
    r = client.delete(f"/api/lookups/brands/{ids['tamiya']}")
    assert r.status_code == 409
    assert "still in use" in r.json()["detail"]
