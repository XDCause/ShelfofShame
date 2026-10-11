"""Wishlist: adding, ticking off, moving into inventory, and out-of-stock -> wishlist."""


def add_wish(client, ids, **overrides):
    body = {"brand_id": ids["tamiya"], "product_code": "T81702", "name": "Acrylic XF2 Flat White",
            "category_id": ids["paint"], "paint_type": "Acrylic", "finish": "Flat / Matt",
            "size": "10ml", "qty_wanted": 1, "est_price": "4.50"}
    body.update(overrides)
    r = client.post("/api/wishlist", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_tick_then_move_ticked_into_inventory(client, ids):
    w = add_wish(client, ids, qty_wanted=2, notes="for the Zero")
    add_wish(client, ids, product_code="T81703", name="Not ticked")
    assert client.patch(f"/api/wishlist/{w['wish_id']}", json={"got_it": True}).json()["got_it"] is True

    moved = client.post("/api/wishlist/buy-ticked", json={"purchased_from": " Hobbyrama "}).json()
    assert len(moved) == 1 and moved[0]["merged"] is False

    s = client.get(f"/api/supplies/{moved[0]['supply_id']}").json()
    assert (s["qty_on_hand"], s["reorder_at"], s["condition"]) == (2, 0, "Sealed")
    assert s["location"] == "Other" and s["purchased_from"] == "Hobbyrama"
    assert float(s["unit_price"]) == 4.50 and s["notes"] == "for the Zero"
    assert "used_for" not in s  # removed in the app refresh
    assert [w["name"] for w in client.get("/api/wishlist").json()] == ["Not ticked"]
    reasons = [m["reason"] for m in client.get(f"/api/supplies/{s['supply_id']}/history").json()]
    assert reasons == ["bought (wishlist)"]


def test_buying_something_you_own_adds_to_its_quantity(client, ids, make_supply):
    owned = make_supply(product_code="T81702", name="Acrylic XF2 Flat White", qty_on_hand=1)
    w = add_wish(client, ids, qty_wanted=3)
    assert client.get("/api/wishlist").json()[0]["owned_qty"] == 1

    r = client.post(f"/api/wishlist/{w['wish_id']}/buy", json={}).json()
    assert r["merged"] is True and r["supply_id"] == owned["supply_id"] and r["qty_on_hand"] == 4
    assert len(client.get("/api/supplies").json()) == 1  # no duplicate created


def test_same_item_twice_on_the_wishlist_is_refused(client, ids):
    add_wish(client, ids)
    r = client.post("/api/wishlist", json={"brand_id": ids["tamiya"], "product_code": "T81702",
                                           "name": "Again", "category_id": ids["paint"]})
    assert r.status_code == 409
    assert r.json()["detail"] == "That item is already on your wishlist."


def test_items_needing_attention_go_onto_the_wishlist_once(client, make_supply):
    make_supply(product_code="T81701", name="Empty one", qty_on_hand=0, unit_price="3.95")
    make_supply(product_code="T81702", name="Last bottle nearly empty", qty_on_hand=1, condition="Nearly empty")
    make_supply(product_code="T81710", name="Still have it", qty_on_hand=1, condition="Opened")

    first = client.post("/api/wishlist/restock").json()
    assert first["added"] == 2
    assert sorted(first["names"]) == ["Empty one", "Last bottle nearly empty"]
    wish = next(w for w in client.get("/api/wishlist").json() if w["name"] == "Empty one")
    assert float(wish["est_price"]) == 3.95

    assert client.post("/api/wishlist/restock").json()["added"] == 0


def test_filters_by_ticked(client, ids):
    w = add_wish(client, ids)
    add_wish(client, ids, product_code="T81703", name="Other")
    client.patch(f"/api/wishlist/{w['wish_id']}", json={"got_it": True})
    assert [x["name"] for x in client.get("/api/wishlist?show=got").json()] == ["Acrylic XF2 Flat White"]
    assert [x["name"] for x in client.get("/api/wishlist?show=needed").json()] == ["Other"]
