"""What you own for the other hobbies (api/app/owned.py): gear, garden supplies, rifles and ammo, by hobby and kind."""


def test_owned_lists_each_hobbys_kit_by_kind(client):
    client.post("/api/gear", json={"name": "Court shoes", "hobby": "volleyball", "kind": "Shoes", "brand": "Li-Ning"})
    client.post("/api/gear", json={"name": "Old pads", "hobby": "volleyball", "kind": "Knee pads", "condition": "Needs replacing"})
    client.post("/api/gear", json={"name": "Dream pack", "hobby": "hiking", "condition": "Wanted"})        # not owned
    client.post("/api/gear", json={"name": "Old boots", "hobby": "hiking", "condition": "Retired"})       # not any more
    client.post("/api/garden/items", json={"name": "Basil seeds", "kind": "Seeds", "qty": 2})
    client.post("/api/garden/items", json={"name": "Seasol", "kind": "Fertiliser", "status": "Running low"})
    client.post("/api/shooting/rifles", json={"name": "CZ 457", "calibre": ".22 LR"})
    client.post("/api/shooting/ammo", json={"name": "Center-X", "rounds_bought": 500, "box_size": 50})
    out = client.get("/api/owned").json()
    got = {(o["hobby"], o["kind"], o["name"]): o for o in out}
    assert set(got) == {("volleyball", "Shoes", "Court shoes"), ("volleyball", "Knee pads", "Old pads"),
                        ("gardening", "Seeds", "Basil seeds"), ("gardening", "Fertiliser", "Seasol"),
                        ("shooting", "Rifles", "CZ 457"), ("shooting", "Ammunition", "Center-X")}
    assert got[("volleyball", "Knee pads", "Old pads")]["attention"] and got[("volleyball", "Shoes", "Court shoes")]["detail"] == "Li-Ning"
    assert got[("gardening", "Fertiliser", "Seasol")]["attention"] and got[("gardening", "Seeds", "Basil seeds")]["amount"] == 2
    assert got[("shooting", "Ammunition", "Center-X")]["amount"] == "500 rounds"
    assert {o["open"] for o in out} == {"gear", "garden", "rifle", "ammo"}
