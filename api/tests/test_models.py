"""Models and their paint checklists."""

# The user's real list for the Tamiya 1/48 A6M3 (tab between the paint and what it's for).
ZERO_PAINTS = (
    "XF-76 Grey Green (IJN)\tThe whole exterior, including the wheel wells and gear doors\n"
    "XF-71 Cockpit Green (IJN)\tCockpit interior: floor, walls and seat\n"
    "X-10 Gun Metal (still to buy)\tGun barrels and engine details\n"
    "\n"
    "Mr. Color C-33\tSomething not in the inventory\n"
)


def make_model(client, ids, **overrides):
    body = {"name": "Mitsubishi A6M3 Zero", "brand_id": ids["tamiya"], "product_code": "T61108", "scale": "1/48"}
    body.update(overrides)
    r = client.post("/api/models", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_pasting_a_paint_list_links_it_to_the_inventory(client, ids, make_supply):
    make_supply(product_code="T81776", name="Acrylic XF76 Grey Green", qty_on_hand=1)
    make_supply(product_code="T81510", name="Acrylic Gun Metal", qty_on_hand=1)
    model = make_model(client, ids)

    m = client.post(f"/api/models/{model['model_id']}/paints", json={"text": ZERO_PAINTS}).json()
    paints = {p["paint_name"]: p for p in m["paints"]}
    assert list(paints) == ["XF-76 Grey Green (IJN)", "XF-71 Cockpit Green (IJN)", "X-10 Gun Metal",
                            "Mr. Color C-33"]  # blank line skipped, "(still to buy)" dropped

    grey = paints["XF-76 Grey Green (IJN)"]
    assert (grey["product_code"], grey["in_inventory"], grey["have"]) == ("T81776", True, True)
    assert grey["purpose"] == "The whole exterior, including the wheel wells and gear doors"
    assert paints["XF-71 Cockpit Green (IJN)"]["purpose"] == "Cockpit interior: floor, walls and seat"
    assert paints["XF-71 Cockpit Green (IJN)"]["have"] is False      # not owned
    assert paints["X-10 Gun Metal"]["have"] is True                   # owned, despite the note
    assert paints["Mr. Color C-33"]["product_code"] is None           # not linked
    assert (m["paints_total"], m["paints_have"]) == (4, 2)


def test_other_separators_and_code_only_lines(client, ids, make_supply):
    make_supply(product_code="T81701", name="Acrylic XF1 Flat Black", qty_on_hand=1)
    model = make_model(client, ids)
    m = client.post(f"/api/models/{model['model_id']}/paints",
                    json={"text": "xf1 - Tyres\nXF-7 Flat Red: Warning stripes"}).json()
    rows = [(p["paint_name"], p["product_code"], p["purpose"]) for p in m["paints"]]
    assert rows == [("Acrylic XF1 Flat Black", "T81701", "Tyres"),   # just a code: your name for it
                    ("XF-7 Flat Red", "T81707", "Warning stripes")]


def test_single_paint_with_separate_purpose(client, ids):
    model = make_model(client, ids)
    m = client.post(f"/api/models/{model['model_id']}/paints",
                    json={"text": "XF-64 Red Brown", "purpose": "Back of the propeller blades"}).json()
    assert m["paints"][0]["purpose"] == "Back of the propeller blades"


def test_tick_by_hand_for_paints_you_dont_track(client, ids):
    model = make_model(client, ids)
    m = client.post(f"/api/models/{model['model_id']}/paints", json={"text": "Borrowed silver"}).json()
    paint = m["paints"][0]
    assert paint["have"] is False
    m = client.patch(f"/api/model-paints/{paint['model_paint_id']}", json={"have_it": True}).json()
    assert m["paints"][0]["have"] is True and m["paints"][0]["in_inventory"] is False
    assert m["paints_have"] == 1


def test_missing_paints_go_onto_the_wishlist_once(client, ids, make_supply):
    make_supply(product_code="T81776", name="Acrylic XF76 Grey Green", qty_on_hand=1)
    model = make_model(client, ids)
    client.post(f"/api/models/{model['model_id']}/paints", json={"text": ZERO_PAINTS})

    r = client.post(f"/api/models/{model['model_id']}/wishlist").json()
    assert sorted(r["added"]) == ["X-10 Gun Metal", "XF-71 Cockpit Green (IJN)"]
    assert r["skipped"] == ["Mr. Color C-33"]  # no brand + code to buy by
    wish = next(w for w in client.get("/api/wishlist").json() if w["product_code"] == "T81771")
    assert wish["category"] == "Paint" and wish["notes"].startswith("For Mitsubishi A6M3 Zero: Cockpit")
    assert all(p["on_wishlist"] for p in r["model"]["paints"] if p["product_code"] in ("T81771", "T81510"))

    again = client.post(f"/api/models/{model['model_id']}/wishlist").json()
    assert again["added"] == []


def test_models_list_status_and_delete(client, ids):
    a = make_model(client, ids, name="Finished one", status="Finished")
    b = make_model(client, ids, name="Being built", status="In progress")
    names = [m["name"] for m in client.get("/api/models").json()]
    assert names == ["Being built", "Finished one"]  # in progress first

    assert client.patch(f"/api/models/{a['model_id']}", json={"status": "Glued"}).status_code == 422
    assert client.patch(f"/api/models/{a['model_id']}", json={"status": "On hold"}).json()["status"] == "On hold"

    client.post(f"/api/models/{b['model_id']}/paints", json={"text": "XF-1"})
    assert client.delete(f"/api/models/{b['model_id']}").status_code == 204
    assert client.get(f"/api/models/{b['model_id']}").status_code == 404


def test_removing_a_paint(client, ids):
    model = make_model(client, ids)
    m = client.post(f"/api/models/{model['model_id']}/paints", json={"text": "XF-1\nXF-2"}).json()
    m = client.delete(f"/api/model-paints/{m['paints'][0]['model_paint_id']}").json()
    assert [p["product_code"] for p in m["paints"]] == ["T81702"]
