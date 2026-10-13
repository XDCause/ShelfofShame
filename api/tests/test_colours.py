"""Colour matches (same code, same name, your own), mixes, kit paint lists and "used on"."""
from decimal import Decimal

import pytest

from app import paints, tamiya
from tests.conftest import FIXTURES


# ---------------------------------------------------------------- what colour is it?
@pytest.mark.parametrize("name, colour", [
    ("ACRYLIC PAINT MINI XF-62 OLIVE DRAB", ("XF-62", "OLIVE DRAB")),
    ("XF-62 OLIVE DRAB", ("XF-62", "OLIVE DRAB")),
    ("TAMIYA COLOR XF-62 OLIVE DRAB", ("XF-62", "OLIVE DRAB")),
    ("LP-28 OLIVE DRAB", ("LP-28", "OLIVE DRAB")),
    ("TS-5 OLIVE DRAB", ("TS-5", "OLIVE DRAB")),
    ("Acrylic XF76 Grey Green (IJN)", ("XF-76", "GRAY GREEN (IJN)")),   # your naming, grey = gray
    ("ACRYLIC PAINT MINI X-20A THINNER (10ml)", None),                   # not a colour
    ("PANEL LINE ACCENT COLOR (BLACK)", None),                            # no code
    ("Milliput Silver Grey", None),
    (None, None),
])
def test_colour_of(name, colour):
    assert tamiya.colour_of(name) == colour


@pytest.mark.parametrize("text, parts", [
    ("XF-62 + XF-2 (3:1)", [("XF-62", 3), ("XF-2", 1)]),
    ("XF-62 + XF-2", [("XF-62", 1), ("XF-2", 1)]),
    ("XF-62 3 + XF-2 1", [("XF-62", 3), ("XF-2", 1)]),
    ("XF-1 + XF-2 + XF-3 2:1:0.5", [("XF-1", 2), ("XF-2", 1), ("XF-3", Decimal("0.5"))]),
    ("XF 62 + XF 2", [("XF 62", 1), ("XF 2", 1)]),                        # "XF 62" isn't 62 parts
])
def test_parse_mix(text, parts):
    assert paints.parse_mix(text) == [(n, Decimal(a)) for n, a in parts]


# ---------------------------------------------------------------- matches
def test_matches_same_code_and_same_name(client, ids, tamiya_catalogue):
    r = client.get("/api/colours/matches", params={"brand_id": ids["tamiya"], "product_code": "T81762"}).json()
    assert r["colour"] == {"code": "XF-62", "name": "Olive Drab"}
    assert {e["product_code"] for e in r["same_code"]} == {"T80362", "T81362"}   # not the generic page
    assert {e["product_code"] for e in r["same_name"]} == {"T82128", "T85005"}
    assert r["groups"] == []


def test_matches_for_something_without_a_colour(client, ids, tamiya_catalogue):
    r = client.get("/api/colours/matches", params={"brand_id": ids["tamiya"], "product_code": "T87131"}).json()
    assert r == {"colour": None, "same_code": [], "same_name": [], "groups": []}


def test_your_own_colour_groups(client, ids, tamiya_catalogue):
    bad = client.post("/api/colour-groups", json={"name": "Lonely", "paints": "XF-62"})
    assert bad.status_code == 422
    g = client.post("/api/colour-groups", json={
        "name": "US Olive Drab", "note": "From the Sherman instructions",
        "paints": "XF-62\nMr. Color C38 Olive Drab"}).json()
    assert [(m["product_code"], m["paint_name"]) for m in g["members"]] == [
        ("T81762", "Acrylic XF62 Olive Drab"), (None, "Mr. Color C38 Olive Drab")]
    r = client.get("/api/colours/matches", params={"brand_id": ids["tamiya"], "product_code": "T81762"}).json()
    assert [x["name"] for x in r["groups"]] == ["US Olive Drab"]

    g = client.patch(f"/api/colour-groups/{g['group_id']}", json={"paints": "XF-62\nXF-1\nC38"}).json()
    assert len(g["members"]) == 3
    assert [x["name"] for x in client.get("/api/colour-groups").json()] == ["US Olive Drab"]
    assert client.delete(f"/api/colour-groups/{g['group_id']}").status_code == 204
    assert client.delete(f"/api/colour-groups/{g['group_id']}").status_code == 404


# ---------------------------------------------------------------- mixes
def test_mixes(client, make_supply, tamiya_catalogue):
    assert client.post("/api/mixes", json={"recipe": "XF-62"}).status_code == 422
    mix = client.post("/api/mixes", json={"recipe": "XF-62 + XF-2 (3:1)", "notes": "Faded OD"}).json()
    assert mix["name"] == "XF-62 + XF-2 (3:1)"
    assert [(p["product_code"], float(p["parts"])) for p in mix["parts"]] == [("T81762", 3), ("T81702", 1)]
    assert mix["recipe"] == "Acrylic XF62 Olive Drab + Acrylic XF2 Flat White (3:1)"
    assert mix["short"] == "XF-62 + XF-2 (3:1)"
    assert mix["have_all"] is False

    make_supply(product_code="T81762", name="Acrylic XF62 Olive Drab")
    make_supply(product_code="T81702", name="Acrylic XF2 Flat White")
    assert client.get("/api/mixes").json()[0]["have_all"] is True

    mix = client.patch(f"/api/mixes/{mix['mix_id']}", json={"name": "Faded OD", "recipe": "XF-62 + XF-1"}).json()
    assert (mix["name"], mix["recipe"]) == ("Faded OD", "Acrylic XF62 Olive Drab + Acrylic XF1 Flat Black")
    assert client.delete(f"/api/mixes/{mix['mix_id']}").status_code == 204
    assert client.get("/api/mixes").json() == []


def test_a_checklist_line_can_be_a_mix(client, make_supply, tamiya_catalogue):
    model = client.post("/api/models", json={"name": "Sherman"}).json()
    m = client.post(f"/api/models/{model['model_id']}/paints",
                    json={"text": "XF-62 + XF-2 (3:1) - Faded hull\nXF-1\tTracks"}).json()
    mix_line, plain = m["paints"]
    assert (mix_line["paint_name"], mix_line["purpose"], mix_line["have"]) == ("XF-62 + XF-2 (3:1)", "Faded hull", False)
    assert mix_line["mix"]["parts"][0]["product_code"] == "T81762"

    make_supply(product_code="T81762", name="Acrylic XF62 Olive Drab")
    m = client.get(f"/api/models/{model['model_id']}").json()
    assert m["paints"][0]["have"] is False and m["paints_have"] == 0     # still missing XF-2

    # missing paints -> wishlist: the mix's missing part, and the plain paint
    r = client.post(f"/api/models/{model['model_id']}/wishlist").json()
    assert sorted(r["added"]) == ["Acrylic XF1 Flat Black", "Acrylic XF2 Flat White"]
    wishes = {w["product_code"]: w for w in client.get("/api/wishlist").json()}
    assert wishes["T81702"]["notes"] == "For Sherman: Faded hull (XF-62 + XF-2 (3:1))"
    assert float(wishes["T81702"]["est_price"]) == 3.95

    make_supply(product_code="T81702", name="Acrylic XF2 Flat White")
    m = client.get(f"/api/models/{model['model_id']}").json()
    assert m["paints"][0]["have"] is True and m["paints_have"] == 1

    # deleting the mix keeps the line, as a plain name
    client.delete(f"/api/mixes/{mix_line['mix_id']}")
    line = client.get(f"/api/models/{model['model_id']}").json()["paints"][0]
    assert (line["paint_name"], line["mix_id"]) == ("XF-62 + XF-2 (3:1)", None)


def test_checklist_suggests_a_matching_paint_you_own(client, make_supply, tamiya_catalogue, ids):
    model = client.post("/api/models", json={"name": "Sherman"}).json()
    client.post(f"/api/models/{model['model_id']}/paints", json={"text": "XF-62\nXF-1\nX-7"})
    make_supply(product_code="T80362", name="Enamel XF-62 Olive Drab")     # same code, enamel
    make_supply(product_code="T82103", name="LP-3 Flat Black")             # same name, lacquer
    paints_ = {p["product_code"]: p for p in client.get(f"/api/models/{model['model_id']}").json()["paints"]}
    assert paints_["T81762"]["alternative"]["how"] == "same colour (XF-62)"
    assert paints_["T81701"]["alternative"] == {"supply_id": 2, "name": "LP-3 Flat Black",
                                                "how": "same name (Flat Black)"}
    assert paints_["T81507"]["alternative"] is None


def test_used_on_shows_the_models_using_a_supply(client, make_supply, tamiya_catalogue):
    xf1 = make_supply()                                                     # T81701
    xf2 = make_supply(product_code="T81702", name="Acrylic XF2 Flat White")
    zero = client.post("/api/models", json={"name": "Zero"}).json()
    sherman = client.post("/api/models", json={"name": "Sherman"}).json()
    client.post(f"/api/models/{zero['model_id']}/paints", json={"text": "XF-1"})
    client.post(f"/api/models/{sherman['model_id']}/paints", json={"text": "XF-62 + XF-2"})
    assert [m["name"] for m in client.get(f"/api/supplies/{xf1['supply_id']}").json()["used_on"]] == ["Zero"]
    assert [m["name"] for m in client.get(f"/api/supplies/{xf2['supply_id']}").json()["used_on"]] == ["Sherman"]
    assert client.get("/api/supplies").json()[0]["used_on"][0]["name"] == "Zero"


# ---------------------------------------------------------------- the kit's own paint list
def test_kit_page_paint_list_is_parsed():
    info = tamiya.parse((FIXTURES / "tamiya_kit_32595.html").read_text(encoding="utf-8"))
    assert info["title"] == '1/48 SCALE U.S. MEDIUM TANK M4A3E8 SHERMAN "EASY EIGHT"'
    kit = info["kit_paints"]
    assert len(kit) == 34
    assert kit[0] == {"section": 0, "group": "Tamiya Color spray paints", "item": "85005",
                      "title": "TS-5 OLIVE DRAB"}
    assert {"section": 2, "group": "Tamiya Colors for brush and airbrush painting", "item": "0XF62",
            "title": "TAMIYA COLOR XF-62 OLIVE DRAB"} in kit
    assert next(p for p in kit if p["item"] == "87140")["title"] == "PANEL LINE ACCENT COLOR (DARK BROWN)"  # tidied
    assert tamiya.parse((FIXTURES / "tamiya_81701.html").read_bytes().decode("cp932", errors="replace"))["kit_paints"] == []


def sherman(client, ids):
    return client.post("/api/models", json={"name": "M4A3E8 Sherman", "brand_id": ids["tamiya"],
                                            "product_code": "T32595", "scale": "1/48"}).json()


def test_pick_paints_from_the_kit_list(client, ids, make_supply, fake_tamiya, tamiya_catalogue):
    model = sherman(client, ids)
    make_supply(product_code="T81701", name="Acrylic XF1 Flat Black")
    kit = client.get(f"/api/models/{model['model_id']}/kit-paints").json()
    assert kit["kit"].startswith("1/48 SCALE U.S. MEDIUM TANK M4A3E8")
    assert [g["label"] for g in kit["groups"]] == [
        "Spray cans", "Lacquer paints (LP)", "Acrylic paints (X / XF) - as Acrylic Minis",
        "Useful finishing materials", "Recreating mud and dirt", "Useful tools",
        "Protecting your model from dust and dirt"]
    acrylics = {p["product_code"]: p for p in kit["groups"][2]["paints"]}
    assert len(acrylics) == 12 and all(p["suggested"] for p in acrylics.values())
    assert acrylics["T81762"]["paint_name"] == "Acrylic XF62 Olive Drab"      # name from the catalogue
    assert acrylics["T81701"]["owned_qty"] == 1
    lacquer = kit["groups"][1]["paints"][2]
    assert (lacquer["product_code"], lacquer["suggested"]) == ("T82128", False)

    picked = [{"product_code": p["product_code"], "paint_name": p["paint_name"]} for p in acrylics.values()]
    m = client.post(f"/api/models/{model['model_id']}/kit-paints", json={"paints": picked + picked[:2]}).json()
    assert m["paints_total"] == 12 and m["paints_have"] == 1                 # duplicates skipped
    again = client.get(f"/api/models/{model['model_id']}/kit-paints").json()
    assert all(p["on_model"] for p in again["groups"][2]["paints"])
    assert fake_tamiya == ["32595"]                                           # read once, then cached


def test_only_tamiya_kits_have_a_paint_list(client):
    model = client.post("/api/models", json={"name": "P-40E"}).json()
    assert client.get(f"/api/models/{model['model_id']}/kit-paints").status_code == 422
