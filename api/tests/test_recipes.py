"""Paint recipes, "can I paint this now?", time per build step, the low / out report, owned alternatives and a price drop
(A01_models_supplies_extras.sql, recipes.py, models.py, supplies_more.py, colours.py, wanted_more.py)."""


def model(client, **fields):
    return client.post("/api/models", json={"name": "Sherman", **fields}).json()


def recipe(client, **fields):
    r = client.post("/api/recipes", json={"name": "Red armour", **fields})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_recipe_links_its_steps_to_your_supplies_and_says_what_you_can_paint(client, make_supply):
    have = make_supply()                                                      # T81701, XF-1 Flat Black, qty 1
    low = make_supply(product_code="T81702", name="Acrylic XF2 Flat White", reorder_at=2)
    make_supply(product_code="T81703", name="Acrylic XF3 Flat Yellow", qty_on_hand=0)
    r = recipe(client, steps=[
        {"label": "base", "supply_id": have["supply_id"], "note": "two thin coats"},
        {"label": "layer", "paint_text": "XF-2"},                              # a code you typed
        {"label": "highlight", "paint_text": "XF-3"},                          # owned, but empty
        {"label": "wash", "paint_text": "XF-4"},                               # not owned at all
        {"label": "glaze", "paint_text": "Mephiston Red"},                     # free text
    ])
    assert [s["state"] for s in r["steps"]] == ["owned", "low", "out", "missing", "free"]
    assert r["steps"][0]["note"] == "two thin coats" and r["steps"][1]["supply_id"] == low["supply_id"]
    assert r["check"]["ready"] is False and r["check"]["to_buy"] == 3
    got = client.get(f"/api/recipes/{r['recipe_id']}/paint-check").json()
    assert (got["owned"], got["low"], got["out"], got["missing"], got["free"]) == (1, 1, 1, 1, 1)

    added = client.post(f"/api/recipes/{r['recipe_id']}/paint-check/wishlist").json()
    assert len(added["added"]) == 3 and added["skipped"] == ["Mephiston Red"]
    assert client.post(f"/api/recipes/{r['recipe_id']}/paint-check/wishlist").json()["added"] == []   # nothing twice


def test_a_recipe_without_a_paint_is_refused_and_steps_can_be_replaced(client):
    assert client.post("/api/recipes", json={"name": "X", "steps": [{"label": "base"}]}).status_code == 422
    assert client.post("/api/recipes", json={"name": ""}).status_code == 422
    r = recipe(client, steps=[{"paint_text": "Agrax Earthshade"}, {"paint_text": "Nuln Oil"}])
    r = client.patch(f"/api/recipes/{r['recipe_id']}", json={"name": "Washes", "steps": [{"paint_text": "Nuln Oil"}]}).json()
    assert r["name"] == "Washes" and [s["paint_text"] for s in r["steps"]] == ["Nuln Oil"]
    assert client.patch(f"/api/recipes/{r['recipe_id']}", json={"notes": "keep"}).json()["steps"]    # steps untouched


def test_recipes_sit_on_a_model_or_alone_and_are_reused_by_copying(client):
    m = model(client)
    other = model(client, name="Panther")
    r = recipe(client, model_id=m["model_id"], unit="Hull", steps=[{"label": "base", "paint_text": "Mephiston Red"}])
    alone = recipe(client, name="Alone")
    assert [x["recipe_id"] for x in client.get(f"/api/recipes?model_id={m['model_id']}").json()] == [r["recipe_id"]]
    assert len(client.get("/api/recipes").json()) == 2 and alone["model_id"] is None
    copy = client.post(f"/api/recipes/{r['recipe_id']}/copy", json={"model_id": other["model_id"]}).json()
    assert copy["model_id"] == other["model_id"] and copy["recipe_id"] != r["recipe_id"]
    assert [s["paint_text"] for s in copy["steps"]] == ["Mephiston Red"]
    assert client.post("/api/recipes/99999/copy").status_code == 404
    assert client.post(f"/api/recipes/{r['recipe_id']}/copy", json={"model_id": 99999}).status_code == 404
    client.delete(f"/api/models/{m['model_id']}")                             # the recipe outlives its model
    assert client.get(f"/api/recipes/{r['recipe_id']}").json()["model_id"] is None
    assert client.delete(f"/api/recipes/{r['recipe_id']}").status_code == 204
    assert client.get(f"/api/recipes/{r['recipe_id']}").status_code == 404


def test_can_i_paint_this_for_a_models_paint_list(client, make_supply):
    make_supply()
    m = model(client)
    client.post(f"/api/models/{m['model_id']}/paints", json={"text": "XF-1\nXF-5\nHand tinted"})
    got = client.get(f"/api/models/{m['model_id']}/paint-check").json()
    assert (got["owned"], got["missing"], got["free"], got["ready"]) == (1, 1, 1, False)
    assert len(client.post(f"/api/models/{m['model_id']}/paint-check/wishlist").json()["added"]) == 1
    assert client.get("/api/models/99999/paint-check").status_code == 404


def test_session_time_adds_up_per_build_step_and_finished_kits_per_year(client):
    m = model(client, status="In progress", stage="Built")
    client.post(f"/api/models/{m['model_id']}/sessions", json={"minutes": 90})
    client.patch(f"/api/models/{m['model_id']}", json={"stage": "Primed"})
    client.post(f"/api/models/{m['model_id']}/sessions", json={"minutes": 30})
    steps = {s["step"]: s["minutes"] for s in client.get(f"/api/models/{m['model_id']}").json()["stage_minutes"]}
    assert steps == {"Primed": 90, "Painted": 30}                             # working towards the step after the last done
    done = model(client, name="Done")
    client.patch(f"/api/models/{done['model_id']}", json={"status": "Finished", "finished_on": "2025-05-01"})
    summary = client.get("/api/models/summary").json()
    assert [y["year"] for y in summary["finished_by_year"]] == [2025]
    assert {s["step"] for s in summary["stage_minutes"]} == {"Primed", "Painted"}


def test_stock_report_lists_low_out_and_old_and_one_tap_adds_them(client, make_supply, ids):
    make_supply(product_code="T1", name="Out one", qty_on_hand=0)
    make_supply(product_code="T2", name="Low one", qty_on_hand=1, reorder_at=2)
    make_supply(product_code="T3", name="Fine", qty_on_hand=5)
    old = make_supply(product_code="T4", name="Old glue", qty_on_hand=1, category_id=ids["glue"],
                      opened_on="2020-01-01", shelf_months=12)
    rep = client.get("/api/supplies/stock-report").json()
    assert [s["name"] for s in rep["out"]] == ["Out one"] and [s["name"] for s in rep["low"]] == ["Low one"]
    assert [s["supply_id"] for s in rep["old"]] == [old["supply_id"]] and rep["to_add"] == 2
    assert sorted(client.post("/api/supplies/stock-report/wishlist").json()["added"]) == ["Low one", "Out one"]
    assert client.get("/api/supplies/stock-report").json()["to_add"] == 0


def test_owned_alternatives_for_a_paint_that_has_run_out(client, make_supply, ids):
    make_supply(qty_on_hand=0)
    url = f"/api/colours/owned-alternatives?brand_id={ids['tamiya']}&product_code=T81701"
    assert client.get(url).json() == []                                       # nothing else owned
    make_supply(product_code="T81501", name="Acrylic XF1 Flat Black (jar)")
    assert client.get(url).status_code == 200


def test_new_exports_download(client):
    m = model(client)
    client.post(f"/api/models/{m['model_id']}/sessions", json={"minutes": 20})
    recipe(client, steps=[{"paint_text": "Nuln Oil"}])
    builds = client.get("/api/export/builds.csv")
    assert builds.status_code == 200 and "text/csv" in builds.headers["content-type"] and "Sherman" in builds.text
    assert "Nuln Oil" in client.get("/api/export/paint-recipes.csv").text


def test_a_price_drop_is_flagged(client, ids):
    w = client.post("/api/wishlist", json={"name": "Airbrush", "category_id": ids["paint"]}).json()
    url = f"/api/wanted/wish/{w['wish_id']}/prices"
    client.post(url, json={"price": "90"})
    assert client.post(url, json={"price": "80"}).json()["price_dropped"] is True
    assert client.post(url, json={"price": "85"}).json()["price_dropped"] is False
