"""Everything wanted, grouped by the shop it would come from (the Wishlist page)."""


def test_wanted_by_shop(client, ids):
    assert client.post("/api/wishlist", json={"name": "Acrylic XF2 Flat White", "category_id": ids["paint"]}).status_code == 201
    client.post("/api/models", json={"name": "RX-78-2", "hobby": "Gundam", "status": "Wanted", "brand_name": "Bandai", "grade": "HG"})
    client.post("/api/models", json={"name": "Onager", "hobby": "Warhammer", "status": "Wanted", "purchased_from": "Good Games"})
    client.post("/api/models", json={"name": "Zero", "status": "In stash"})                      # not wanted
    client.post("/api/board-games", json={"name": "Arcs", "status": "Wanted"})
    client.post("/api/gear", json={"name": "Knee pads", "condition": "Wanted"})
    client.post("/api/gear", json={"name": "Ball", "condition": "Good"})                          # not wanted
    r = client.get("/api/wanted").json()
    assert (r["default_shop"], r["supplies"]) == ("Hobbyrama", 1)
    shops = {s["shop"]: [(i["kind"], i["name"]) for i in s["items"]] for s in r["shops"]}
    assert [s["shop"] for s in r["shops"]] == ["Hobbyrama", "Good Games", "No shop yet"]          # default first, no shop last
    assert shops["Hobbyrama"] == [("model", "RX-78-2")]
    assert shops["Good Games"] == [("model", "Onager"), ("game", "Arcs")]                         # the kit's own shop
    assert shops["No shop yet"] == [("gear", "Knee pads")]
    # A different default shop (Settings) moves the kits without a shop of their own.
    client.patch("/api/settings", json={"default_shop": "Frontline Hobbies"})
    first = client.get("/api/wanted").json()["shops"][0]
    assert first["shop"] == "Frontline Hobbies" and [i["name"] for i in first["items"]] == ["RX-78-2"]
