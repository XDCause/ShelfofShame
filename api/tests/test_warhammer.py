"""Warhammer kits from Good Games' official UCP interface (faked: made-up products in its layout)."""
import pytest

from app import gameology, goodgames, ucp, warhammer

REAL_CALL = goodgames._call          # kept when this file loads, before the tests' guard replaces it

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def product(n, title, sku, cents, available=True, tags=("Warhammer 40K",), text="", image=True):
    return {"id": f"gid://shopify/Product/{n}", "title": title, "url": f"https://www.goodgames.com.au/products/p{n}",
            "description": {"html": text}, "tags": list(tags),
            "media": [{"type": "image", "url": f"https://cdn.shopify.com/s/files/p{n}.jpg?v=1"}] if image else [],
            "variants": [{"id": f"gid://shopify/ProductVariant/{n}", "sku": sku, "price": {"amount": str(cents), "currency": "AUD"},
                          "availability": {"available": available}}]}


ADMECH = "Faction_Adeptus Mechanicus"
SHOP = [
    product(1, "Combat Patrol - Adeptus Mechanicus (59-05)", "5011921203208", 19277, tags=(ADMECH, "Warhammer 40K"),
            text="<p>This set includes:- 1x Tech-Priest Manipulus- 3x Serberys Sulphurhounds (which can alternatively be built "
                 "as 3x Serberys Raiders)- 10x Skitarii Vanguard (which can alternatively be built as 10x Skitarii Rangers)</p>"),
    product(2, "Combat Patrol � Adeptus Mechanicus (59-25)", "5011921139224", 24300, available=False, tags=(ADMECH,),
            text="Contains 1x Techpriest Enginseer, 1x Onager Dunecrawler, 10x Skitarii Rangers/Vanguard and 3 Kataphron Servitors"),
    product(3, "Adeptus Mechanicus - Onager Dunecrawler (59-13)", "5011921155897", 12141, tags=(ADMECH,)),
    product(4, "Codex - Adeptus Mechanicus (59-01)", "9781804572788", 8175, tags=(ADMECH,)),           # a book
    product(5, "Adeptus Mechanicus: Thulia Ghuld (59-33)", "5011921250000", 6000, text="1 plastic miniature"),  # not tagged
    product(6, "Horus Heresy - Mechanicum Battle Group (31-87)", "5011921000000", 30000, tags=("Faction_Mechanicum",)),
    product(7, "Warhammer Collectibles: 1/18 Scale Adeptus Mechanicus Skitarii Marshal", "JT7752", 14500, tags=(ADMECH,)),
    product(8, "Citadel Contrast Paint: Mechanicus Standard Grey (29-18)", "5011921000001", 1139, tags=(ADMECH,)),   # a paint
]


@pytest.fixture
def shop(monkeypatch):
    asked = []

    def call(tool, catalog):
        asked.append((tool, catalog))
        if tool == "get_product":
            n = catalog["id"].rsplit("/", 1)[-1]
            p = next((p for p in SHOP if p["id"].endswith("/" + n)), None)
            if not p:
                raise goodgames.ShopError("Good Games said no: Product not found.")
            return {"product": {k: v for k, v in p.items() if k != "tags"}}     # like the real one: no tags
        words = catalog["query"].lower().split()
        found = [p for p in SHOP if p["variants"][0]["availability"]["available"] == catalog["filters"]["available"]
                 and (all(w in p["title"].lower() for w in words) or catalog["query"] == p["variants"][0]["sku"])]
        return {"products": found, "pagination": {"has_next_page": False}}
    monkeypatch.setattr(goodgames, "_call", call)
    monkeypatch.setattr(gameology, "photo", lambda game: (PNG, "image/png"))
    warhammer._ranges.clear()
    return asked


def test_a_product_becomes_a_kit():
    k = goodgames.kit(SHOP[0])
    assert (k["name"], k["code"], k["army"], k["figures"], k["barcode"], k["price"], k["available"], k["is_kit"]) == \
        ("Combat Patrol: Adeptus Mechanicus", "59-05", "Adeptus Mechanicus", 14, "5011921203208", 192.77, True, True)   # alternatives not counted
    old = goodgames.kit(SHOP[1])
    assert old["title"] == "Combat Patrol – Adeptus Mechanicus (59-25)" and not old["available"]
    assert old["figures"] == 15                         # "... and 3 Kataphron Servitors" counts too (no "x")
    assert old["units"] == [{"unit": "Techpriest Enginseer", "count": 1}, {"unit": "Onager Dunecrawler", "count": 1},
                            {"unit": "Skitarii Rangers/Vanguard", "count": 10}, {"unit": "Kataphron Servitors", "count": 3}]
    assert goodgames.kit(SHOP[2])["name"] == "Onager Dunecrawler"
    assert not goodgames.kit(SHOP[3])["is_kit"] and not goodgames.kit(SHOP[6])["is_kit"] and not goodgames.kit(SHOP[7])["is_kit"]
    assert goodgames.kit(SHOP[4])["figures"] == 1 and goodgames.kit(SHOP[6])["barcode"] is None


def test_the_profile_names_the_app(monkeypatch):
    monkeypatch.delenv("UCP_PROFILE", raising=False)
    assert goodgames.profile() == "https://cdn.jsdelivr.net/gh/XDCause/ShelfofShame@ucp-agent-1/ucp-agent.json"
    monkeypatch.setenv("UCP_PROFILE", "https://example.com/p.json")
    assert goodgames.profile() == "https://example.com/p.json"


def test_an_armys_whole_range(client, shop):
    r = client.get("/api/warhammer/army?name=Adeptus Mechanicus").json()
    # Kits only (no codex, no collectible statue), the untagged Thulia Ghuld in, Mechanicum out; by GW code.
    assert [k["code"] for k in r["kits"]] == ["59-05", "59-13", "59-25", "59-33"]
    assert (r["total"], r["in_stock"], r["yours"]) == (4, 3, 0)
    # Asked twice within the hour: from memory.
    calls = len(shop)
    client.get("/api/warhammer/army?name=adeptus mechanicus")
    assert len(shop) == calls


def test_look_up_and_want(client, shop):
    r = client.get("/api/lookup/warhammer/combat patrol adeptus mechanicus").json()
    assert [c["code"] for c in r["choices"]] == ["59-05", "59-25"]           # in stock first
    found = client.get(f"/api/lookup/warhammer/id:{r['choices'][0]['id']}").json()
    assert (found["name"], found["product_code"], found["faction"], found["figures"], found["barcode"], found["has_image"]) == \
        ("Combat Patrol: Adeptus Mechanicus", "59-05", "Adeptus Mechanicus", 14, "5011921203208", True)
    # Looked up again by its code or barcode: from the cache (no shop call).
    calls = len(shop)
    again = client.get("/api/lookup/warhammer/5011921203208").json()
    assert again["from_cache"] and again["figures"] == 14 and len(shop) == calls
    # Scanning the box finds it too.
    assert client.get("/api/scan/5011921203208").json()["match"] == "known"
    # + Wanted: a Warhammer model, Wanted, with the army, minis and photo; then the range says it's yours.
    model = client.post("/api/warhammer/want", json={"id": "3"}).json()
    assert (model["name"], model["hobby"], model["status"], model["faction"], model["figures"], model["product_code"], model["has_image"]) == \
        ("Onager Dunecrawler", "Warhammer", "Wanted", "Adeptus Mechanicus", 1, "59-13", True)
    assert client.post("/api/warhammer/want", json={"id": "3"}).status_code == 409
    r = client.get("/api/warhammer/army?name=Adeptus Mechanicus").json()
    assert r["yours"] == 1 and next(k for k in r["kits"] if k["code"] == "59-13")["my_model"]["status"] == "Wanted"
    assert client.get("/api/warhammer/armies").json()["yours"] == ["Adeptus Mechanicus"]


def test_codes_that_dont_exist_and_shop_errors(client, shop, monkeypatch):
    assert client.get("/api/lookup/warhammer/99-99").status_code == 404
    assert client.post("/api/warhammer/want", json={"id": "999"}).status_code == 404

    def busy(tool, catalog):
        raise goodgames.ShopError("Good Games asked us to slow down - try again in a minute.")
    monkeypatch.setattr(goodgames, "_call", busy)
    r = client.get("/api/warhammer/search?q=onager")
    assert r.status_code == 502 and "slow down" in r.json()["detail"]


def test_slow_down_is_waited_out_once(monkeypatch):
    """A 429 is retried once (after Retry-After); a second one becomes the friendly message."""
    import httpx
    ok = httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": '{"products": []}'}]}})
    busy = httpx.Response(429, headers={"Retry-After": "0"})
    answers = [busy, ok]
    monkeypatch.setattr(ucp.httpx, "post", lambda *a, **k: answers.pop(0))
    assert REAL_CALL("search_catalog", {"query": "x"}) == {"products": []} and answers == []
    answers[:] = [busy, busy]
    with pytest.raises(goodgames.ShopError, match="slow down"):
        REAL_CALL("search_catalog", {"query": "x"})


def test_odd_ids_and_foreign_links(client, shop):
    assert client.get("/api/lookup/warhammer/id:abc").status_code == 404           # not a number: not a crash
    assert goodgames.get("12abc") is None
    p = {**SHOP[2], "url": "javascript:alert(1)"}
    assert goodgames.kit(p)["url"] is None and goodgames.kit(SHOP[2])["url"].startswith("https://www.goodgames.com.au/")


def test_what_is_in_the_box():
    assert goodgames.units_of("Christmas Box 2021Builds1x Tech-priest Manipulus5x Pteraxii10x Skitarii") == [
        {"unit": "Tech-priest Manipulus", "count": 1}, {"unit": "Pteraxii", "count": 5}, {"unit": "Skitarii", "count": 10}]
    assert goodgames.units_of("This set builds 5x Sicarian Infiltrators, which could alternatively be assembled as "
                              "5x Sicarian Ruststalkers") == [{"unit": "Sicarian Infiltrators", "count": 5}]
    assert goodgames.units_of("1x Tech-Priest Dominus- 3x Kataphron Destroyers, which can alternatively be built as "
                              "Kataphron Breachers- 5x Sicarian Infiltrators") == [
        {"unit": "Tech-Priest Dominus", "count": 1}, {"unit": "Kataphron Destroyers", "count": 3},
        {"unit": "Sicarian Infiltrators", "count": 5}]
    assert goodgames.units_of("10x Skitarii Vanguard (or Rangers) All models come unpainted") == [{"unit": "Skitarii Vanguard", "count": 10}]
    assert goodgames.units_of("Contents: 73 plastic components 5 Citadel 32mm Round Bases, 1 Transfer Sheet") == []


def test_each_mini_has_its_own_step(client, shop):
    model = client.post("/api/warhammer/want", json={"id": "1"}).json()       # 1 Manipulus, 3 Sulphurhounds, 10 Skitarii
    mid = model["model_id"]
    assert model["box_units"][1] == {"unit": "Serberys Sulphurhounds", "count": 3} and model["minis"] == []
    model = client.post(f"/api/models/{mid}/minis/from-box").json()
    assert [m["unit"] for m in model["minis"]][:5] == ["Tech-Priest Manipulus"] + ["Serberys Sulphurhounds"] * 3 + ["Skitarii Vanguard"]
    assert (len(model["minis"]), model["figures"], model["figures_done"], model["stage"], model["status"]) == (14, 14, 0, None, "Wanted")
    assert client.post(f"/api/models/{mid}/minis/from-box").status_code == 409
    client.patch(f"/api/models/{mid}", json={"status": "In stash"})
    # One mini primed: the box is started, but not every mini is built, so the box has no step yet.
    first = model["minis"][0]["mini_id"]
    model = client.patch(f"/api/model-minis/{first}", json={"stage": "Primed", "name": "Leader"}).json()
    assert (model["status"], model["stage"]) == ("In progress", None) and model["minis"][0]["name"] == "Leader"
    # The whole box built: the box is at Built (every mini has got that far).
    ids = [m["mini_id"] for m in model["minis"]]
    model = client.put(f"/api/models/{mid}/minis/stage", json={"mini_ids": ids[1:], "stage": "Built"}).json()
    assert model["stage"] == "Built" and model["skipped_steps"] == [] and model["minis"][0]["stage"] == "Primed"
    assert client.put(f"/api/models/{mid}/minis/stage", json={"mini_ids": ids, "stage": "Decals"}).status_code == 422
    assert client.put(f"/api/models/{mid}/minis/stage", json={"mini_ids": [999999], "stage": "Built"}).status_code == 404
    # Every mini Complete: the box is Finished, 14 of 14 painted.
    model = client.put(f"/api/models/{mid}/minis/stage", json={"mini_ids": ids, "stage": "Complete"}).json()
    assert (model["status"], model["stage"], model["figures_done"]) == ("Finished", "Complete", 14)
    # Un-finished from the box: the minis go back to the last step, not straight to Finished again.
    model = client.patch(f"/api/models/{mid}", json={"status": "In progress"}).json()
    assert model["status"] == "In progress" and model["stage"] != "Complete" and model["figures_done"] == 0
    # A step ticked for the whole box brings the minis behind it up to it.
    client.put(f"/api/models/{mid}/minis/stage", json={"mini_ids": ids[:4], "stage": None})
    model = client.patch(f"/api/models/{mid}", json={"stage": "Primed"}).json()
    assert {m["stage"] for m in model["minis"][:4]} == {"Primed"} and model["stage"] == "Primed"
    # Added by hand, renamed, removed.
    model = client.post(f"/api/models/{mid}/minis", json={"unit": "Skitarii Marshal"}).json()
    assert (model["figures"], model["stage"]) == (15, None)
    model = client.put(f"/api/models/{mid}/minis/unit", json={"unit": "Skitarii Marshal", "to": "Marshal"}).json()
    assert model["minis"][-1]["unit"] == "Marshal"
    assert client.delete(f"/api/models/{mid}/minis?unit=Marshal").status_code == 204
    assert client.delete(f"/api/model-minis/{ids[0]}").status_code == 204
    model = client.get(f"/api/models/{mid}").json()
    assert (model["figures"], model["stage"]) == (13, "Primed")
    assert client.post(f"/api/models/{mid}/minis", json={"unit": "Too many", "count": 100}).status_code == 201
    assert client.post(f"/api/models/{mid}/minis", json={"unit": "Way too many", "count": 100}).status_code == 422


def test_minis_from_a_box_read_before_contents_were_kept(client, shop):
    """A kit added before box contents were stored: the shop is asked again by its GW code."""
    from app.db import db
    model = client.post("/api/warhammer/want", json={"id": "1"}).json()
    with db() as conn:
        conn.execute("UPDATE product_info SET kit_units = NULL WHERE product_code = '59-05'")
    model = client.post(f"/api/models/{model['model_id']}/minis/from-box").json()
    assert len(model["minis"]) == 14
    other = client.post("/api/models", json={"name": "Kitbash", "hobby": "Warhammer"}).json()
    assert client.post(f"/api/models/{other['model_id']}/minis/from-box").status_code == 404
