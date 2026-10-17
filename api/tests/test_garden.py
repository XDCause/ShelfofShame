"""Gardening: spaces and their layout, containers, plants, care, notes and photos, reminders, today, harvests,
the plant guide, supplies and seeds, Bunnings links (a made-up page here) and weather tips (a made-up forecast)."""
import json
from datetime import date, timedelta

from app import bunnings, garden, openmeteo
from app.db import db

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200


def db_today():
    with db() as conn:
        return conn.execute("SELECT current_date AS d").fetchone()["d"]


def guide(client, name):
    return next(g for g in client.get(f"/api/garden/guides?q={name}").json()["guides"] if g["name"] == name)


def balcony(client, **kw):
    return client.post("/api/garden/spaces", json={"name": "Balcony", "kind": "Balcony", "width_cm": 300, "depth_cm": 120,
                                                   "facing": "N", "sun_hours": 3, "covered": False, "max_load_kg": 200, **kw}).json()


def test_spaces_layout_and_plants(client):
    s = balcony(client)
    assert (s["width_cm"], s["open_side"], s["wind"], s["containers"]) == (300, "top", "Some wind", [])
    trough = client.post("/api/garden/containers", json={"name": "Long trough", "space_id": s["space_id"], "kind": "Trough",
                                                         "shape": "rect", "x_cm": 280, "y_cm": 5, "width_cm": 80, "depth_cm": 25,
                                                         "volume_l": 40}).json()
    assert trough["x_cm"] == 220                                         # kept inside the 300 cm plan
    basil = guide(client, "Basil")
    p = client.post("/api/garden/plantings", json={"guide_id": basil["guide_id"], "container_id": trough["container_id"],
                                                   "source": "Seedling", "quantity": 3}).json()
    assert (p["name"], p["stage"], p["water_every_days"], p["space_name"]) == ("Basil", "Growing", 2, "Balcony")
    start = date.fromisoformat(p["started_on"])
    assert date.fromisoformat(p["harvest_from"]) == start + timedelta(days=50 - 21)        # seedlings: ~3 weeks on
    assert any("wants about 5 h of sun" in w for w in p["warnings"])                        # the balcony gets 3
    assert date.fromisoformat(p["water_due_on"]) == db_today()                              # never watered: due today
    assert client.post("/api/garden/plantings", json={"container_id": trough["container_id"]}).status_code == 422
    layout = client.get(f"/api/garden/spaces/{s['space_id']}").json()
    assert [c["name"] for c in layout["containers"]] == ["Long trough"]
    assert [x["name"] for x in layout["containers"][0]["plantings"]] == ["Basil"]
    assert layout["load_kg"] == 40 and layout["plants"] == 1
    moved = client.patch(f"/api/garden/containers/{trough['container_id']}", json={"x_cm": 10, "y_cm": 90}).json()
    assert (moved["x_cm"], moved["y_cm"]) == (10, 90)
    assert client.delete(f"/api/garden/spaces/{s['space_id']}").status_code == 409            # it still has a container

    window = client.post("/api/garden/spaces", json={"name": "Kitchen window", "kind": "Windowsill", "width_cm": 90,
                                                     "depth_cm": 25, "sun_hours": 6}).json()
    client.patch(f"/api/garden/containers/{trough['container_id']}", json={"space_id": window["space_id"]})
    p = client.get(f"/api/garden/plantings/{p['planting_id']}").json()
    assert p["space_name"] == "Kitchen window" and not any("sun" in w for w in p["warnings"])
    assert p["logs"][0]["kind"] == "Moved" and "Kitchen window" in p["logs"][0]["text"]
    c = client.get(f"/api/garden/containers/{trough['container_id']}").json()
    assert c["width_cm"] <= 90 and c["x_cm"] + c["width_cm"] <= 90                             # fitted to the windowsill


def test_care_today_and_self_watering(client):
    s = balcony(client)
    pot = client.post("/api/garden/containers", json={"name": "Blue pot", "space_id": s["space_id"], "volume_l": 10}).json()
    wick = client.post("/api/garden/containers", json={"name": "Wicking pot", "space_id": s["space_id"], "kind": "Self-watering pot"}).json()
    assert wick["self_watering"] is True
    mint = client.post("/api/garden/plantings", json={"name": "Mint", "container_id": pot["container_id"], "water_every_days": 2,
                                                      "feed_every_days": 14}).json()
    herb = client.post("/api/garden/plantings", json={"name": "Parsley", "container_id": wick["container_id"], "water_every_days": 2}).json()
    t = client.get("/api/garden/today").json()
    assert {p["name"] for p in t["water"]} == {"Mint", "Parsley"} and t["growing"] == 2
    assert client.get("/api/garden/summary").json()["need_water"] == 2
    done = client.post("/api/garden/care", json={"action": "watered", "all_due": True}).json()
    assert done["done"] == 2
    p = client.get(f"/api/garden/plantings/{mint['planting_id']}").json()
    assert date.fromisoformat(p["water_due_on"]) == db_today() + timedelta(days=2) and p["logs"][0]["kind"] == "Watered"
    h = client.get(f"/api/garden/plantings/{herb['planting_id']}").json()
    assert date.fromisoformat(h["water_due_on"]) == db_today() + timedelta(days=4)            # self-watering: half as often
    assert client.get("/api/garden/summary").json()["need_water"] == 0
    assert client.post("/api/garden/care", json={"action": "fed", "space_id": s["space_id"], "text": "seaweed"}).json()["done"] == 2
    assert client.post("/api/garden/care", json={"action": "fed"}).status_code == 422


def test_logs_photos_harvests_and_activity(client):
    s = balcony(client)
    pot = client.post("/api/garden/containers", json={"name": "Big pot", "space_id": s["space_id"]}).json()
    tom = client.post("/api/garden/plantings", json={"name": "Cherry tomato", "variety": "Tumbling Tom",
                                                     "container_id": pot["container_id"]}).json()
    log = client.post("/api/garden/logs", json={"planting_id": tom["planting_id"], "kind": "Harvested", "amount": 120, "unit": "g",
                                                "text": "First pick"}).json()
    client.post("/api/garden/logs", json={"planting_id": tom["planting_id"], "kind": "Harvested", "amount": 80, "unit": "g"})
    photo = client.post(f"/api/garden/logs/{log['log_id']}/photos", content=JPEG, headers={"Content-Type": "image/jpeg"}).json()
    assert client.get(photo["url"]).content == JPEG
    p = client.get(f"/api/garden/plantings/{tom['planting_id']}").json()
    assert p["stage"] == "Harvesting" and p["harvested"] == [{"unit": "g", "amount": 200.0, "times": 2}]
    assert p["photo_url"] == photo["url"] and p["logs"][1]["photos"][0]["url"] == photo["url"]
    pest = client.post("/api/garden/logs", json={"planting_id": tom["planting_id"], "kind": "Pest", "tags": ["Whitefly", " "],
                                                 "text": "Under the leaves"}).json()
    assert pest["tags"] == ["Whitefly"]
    h = client.get("/api/garden/harvests").json()
    assert h["by_plant"] == [{"name": "Cherry tomato", "unit": "g", "amount": 200.0}] and len(h["harvests"]) == 2
    feed = client.get("/api/activity?limit=50").json()
    mine = [(a["kind"], a["verb"], a["title"]) for a in feed if a["kind"] == "planting"]
    assert ("planting", "Planted", "Cherry tomato (Tumbling Tom)") in mine and ("planting", "Harvested", "Cherry tomato") in mine
    assert ("planting", "Spotted", "Cherry tomato") in mine
    assert any(a["photo_url"] == photo["url"] for a in feed)
    assert client.get(f"/api/garden/photos?planting_id={tom['planting_id']}").json()[0]["url"] == photo["url"]
    assert client.post("/api/garden/logs", json={"kind": "Note", "text": "about nothing"}).status_code == 422
    # done: an end date and reason; brought back: cleared
    done = client.patch(f"/api/garden/plantings/{tom['planting_id']}", json={"stage": "Done"}).json()
    assert done["ended_on"] and done["end_reason"] == "Harvested out"
    back = client.patch(f"/api/garden/plantings/{tom['planting_id']}", json={"stage": "Fruiting"}).json()
    assert back["ended_on"] is None
    # repotting a container dates it
    client.post("/api/garden/logs", json={"container_id": pot["container_id"], "kind": "Repotted"})
    assert client.get(f"/api/garden/containers/{pot['container_id']}").json()["potted_on"] == str(db_today())


def test_tasks_and_propagation(client):
    s = balcony(client)
    worm = client.post("/api/garden/containers", json={"name": "Worm farm", "space_id": s["space_id"], "kind": "Worm farm"}).json()
    t = client.post("/api/garden/tasks", json={"title": "Feed the worms", "container_id": worm["container_id"], "repeat_days": 7}).json()
    assert t["due"] and t["container_name"] == "Worm farm"
    t = client.post(f"/api/garden/tasks/{t['task_id']}/done").json()
    assert date.fromisoformat(t["due_on"]) == db_today() + timedelta(days=7) and t["done_on"] is None
    one = client.post("/api/garden/tasks", json={"title": "Buy saucers"}).json()
    assert client.post(f"/api/garden/tasks/{one['task_id']}/done").json()["done_on"] == str(db_today())
    assert [x["title"] for x in client.get("/api/garden/tasks").json()] == ["Feed the worms"]
    mint = client.post("/api/garden/plantings", json={"name": "Mint", "source": "Bought plant"}).json()
    kid = client.post(f"/api/garden/plantings/{mint['planting_id']}/propagate", json={"quantity": 3}).json()
    assert (kid["parent"]["name"], kid["source"], kid["quantity"], kid["stage"]) == ("Mint", "Cutting", 3, "Seedling")
    assert client.get(f"/api/garden/plantings/{mint['planting_id']}").json()["children"][0]["planting_id"] == kid["planting_id"]


def test_guides_sow_now_and_custom(client):
    data = client.get("/api/garden/guides").json()
    assert data["climate"] == "Subtropical" and len(data["guides"]) >= 50
    basil = guide(client, "Basil")
    month = db_today().month
    assert basil["sow_now"] == (month in basil["sow_subtropical"])
    now = client.get("/api/garden/sow-now").json()
    assert all(g["sow_now"] for g in now["now"]) and all(not g["sow_now"] and g["sow_next"] for g in now["next"])
    balcony(client, sun_hours=7)
    assert "Balcony" in guide(client, "Cherry tomato")["fits_spaces"]
    assert client.patch(f"/api/garden/guides/{basil['guide_id']}", json={"tips": "x"}).status_code == 409
    mine = client.post(f"/api/garden/guides/{basil['guide_id']}/copy").json()
    assert mine["name"] == "Basil (mine)" and mine["custom"]
    mine = client.patch(f"/api/garden/guides/{mine['guide_id']}", json={"sow_subtropical": [9, 10, 9], "tips": "Mine"}).json()
    assert mine["sow_subtropical"] == [9, 10]
    assert client.patch(f"/api/garden/guides/{mine['guide_id']}", json={"sow_cool": [13]}).status_code == 422
    assert client.patch(f"/api/garden/guides/{mine['guide_id']}", json={"days_min": 99, "days_max": 10}).status_code == 422
    own = client.post("/api/garden/guides", json={"name": "Pandan", "kind": "Herb", "sun": "Part sun", "water": "High"}).json()
    assert own["slug"] == "my-pandan"
    assert client.delete(f"/api/garden/guides/{own['guide_id']}").status_code == 204
    assert client.delete(f"/api/garden/guides/{basil['guide_id']}").status_code == 409
    client.put("/api/garden/settings", json={"climate": "Cool"})
    assert client.get("/api/garden/guides?q=Basil").json()["climate"] == "Cool"


def bunnings_page(item="1234567", price=9.49, name="Test Premium Potting Mix 10L"):
    data = {"props": {"pageProps": {"dehydratedState": {"queries": [
        {"queryKey": ["product-retail-price", item, "6400"], "state": {"data": {"priceAvailable": True, "value": price}}},
        {"queryKey": ["retail-product", item, "6400"], "state": {"data": {
            "name": name, "itemNumber": item, "manufacturer": "Test Brand", "averageRating": 4.5, "numberOfReviews": 12,
            "weight": "5.10", "feature": {"description": "Good <b>mix</b> &amp; more."},
            "allCategories": [{"displayName": "Garden"}, {"displayName": "Garden Supplies"}, {"displayName": "Soil & Potting Mix"}],
            "installationInformation": "HOW TO USE<br><br>Fill the pot.",
            "images": [{"imageType": "PRIMARY", "url": "https://media.bunnings.com.au/api/public/content/abc?v=1"}]}}}]}}}}
    return f'<html><head><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></head></html>'


def test_bunnings_parse_and_links():
    p = bunnings.parse(bunnings_page())
    assert (p["name"], p["bunnings_item"], p["price"], p["brand"], p["rating"], p["reviews"], p["weight_kg"]) == \
        ("Test Premium Potting Mix 10L", "1234567", 9.49, "Test Brand", 4.5, 12, 5.1)
    assert p["category"] == "Garden Supplies › Soil & Potting Mix" and p["description"] == "Good mix & more."
    assert p["how_to"] == "HOW TO USE\n\nFill the pot."
    assert bunnings.product_url("Check this out https://www.bunnings.com.au/Test-Mix-10l_p1234567?utm_source=x") == \
        "https://www.bunnings.com.au/test-mix-10l_p1234567"
    assert bunnings.product_url("https://www.bunnings.com.au/search/products?q=mix") is None
    assert bunnings.photo_url("https://media.bunnings.com.au/x?v=1") == "https://media.bunnings.com.au/x?v=1&t=w1200"
    assert bunnings.photo_url("https://evil.example/x") is None
    for page in ("<html>Checking your browser</html>", '<script id="__NEXT_DATA__" type="application/json">{}</script>'):
        try:
            bunnings.parse(page)
            raise AssertionError("parsed")
        except bunnings.BunningsError:
            pass


def test_items_from_bunnings_wanted_and_sowing(client, monkeypatch):
    pages = {"1234567": bunnings_page(), "7654321": bunnings_page("7654321", 4.98, "Test Basil Seeds")}
    asked = []
    monkeypatch.setattr(bunnings, "_get", lambda url: asked.append(url) or pages[url.rsplit("_p", 1)[1]])
    r = client.post("/api/garden/items/bunnings", json={"url": "https://www.bunnings.com.au/test-mix_p1234567", "status": "Wanted"})
    assert r.status_code == 201
    mix = r.json()
    assert (mix["kind"], mix["price"], mix["status"], mix["existing"]) == ("Potting mix", 9.49, "Wanted", False)
    again = client.post("/api/garden/items/bunnings", json={"url": "https://www.bunnings.com.au/whatever_p1234567"})
    assert again.status_code == 200 and again.json()["existing"] and len(asked) == 1          # not read again
    assert client.post("/api/garden/items/bunnings", json={"url": "https://example.com/x_p1234567"}).status_code == 422
    shops = {s["shop"]: s for s in client.get("/api/wanted").json()["shops"]}
    assert [i["name"] for i in shops["Bunnings"]["items"]] == ["Test Premium Potting Mix 10L"] and shops["Bunnings"]["total"] == 9.49
    pages["1234567"] = bunnings_page(price=8.0)
    fresh = client.post(f"/api/garden/items/{mix['item_id']}/bunnings").json()
    assert (fresh["price"], fresh["price_before"]) == (8.0, 9.49)
    hand = client.post("/api/garden/items", json={"name": "Saucers", "kind": "Pot"}).json()
    assert client.post(f"/api/garden/items/{hand['item_id']}/bunnings").status_code == 422          # no link yet
    assert client.post(f"/api/garden/items/{hand['item_id']}/bunnings",
                       json={"url": "https://www.bunnings.com.au/test-mix_p1234567"}).status_code == 409   # that's the mix
    basil = guide(client, "Basil")
    seeds = client.post("/api/garden/items", json={"name": "Basil seeds", "kind": "Seeds", "qty": 2, "guide_id": basil["guide_id"],
                                                   "sow_by": "2020-01-01"}).json()
    assert seeds["expired"] and seeds["guide_name"] == "Basil"
    p = client.post(f"/api/garden/items/{seeds['item_id']}/sow", json={}).json()
    assert (p["name"], p["source"], p["stage"], p["item_id"]) == ("Basil", "Seed", "Sown", seeds["item_id"])
    assert client.get(f"/api/garden/items/{seeds['item_id']}").json()["qty"] == 1
    assert client.post(f"/api/garden/items/{mix['item_id']}/sow", json={}).status_code == 422


def test_weather_tips(client, monkeypatch):
    days = [{"day": "2026-01-10", "max": 36, "min": 24, "rain_mm": 8, "rain_chance": 90, "gusts": 65, "uv": 12},
            {"day": "2026-01-11", "max": 22, "min": 4, "rain_mm": 0, "rain_chance": 0, "gusts": 20, "uv": 3}]
    tips = garden.weather_tips(days, [{"name": "Balcony", "kind": "Balcony", "covered": False}])
    kinds = [(t["day"], t["kind"]) for t in tips]
    assert kinds == [("Today", "heat"), ("Today", "wind"), ("Today", "rain"), ("Today", "uv"), ("Tomorrow", "cold")]
    assert "Balcony" in tips[2]["text"]
    assert [t["kind"] for t in garden.weather_tips(days[:1], [{"name": "Shelf", "kind": "Indoor", "covered": True}])] == ["heat"]
    assert client.get("/api/garden/today").json()["weather"] is None                  # no place set
    monkeypatch.setattr(openmeteo, "_get", lambda url, params: {
        "results": [{"name": "Brisbane", "admin1": "Queensland", "country": "Australia", "latitude": -27.46794, "longitude": 153.02809}]}
        if "geocoding" in url else {"daily": {"time": ["2026-01-10"], "temperature_2m_max": [31], "temperature_2m_min": [20],
                                              "precipitation_sum": [0], "precipitation_probability_max": [10],
                                              "wind_gusts_10m_max": [20], "uv_index_max": [8]}})
    place = client.get("/api/garden/places?q=Brisbane").json()[0]
    assert place == {"name": "Brisbane", "region": "Queensland, Australia", "lat": -27.4679, "lon": 153.0281}
    client.put("/api/garden/settings", json={"place_name": "Brisbane", "lat": place["lat"], "lon": place["lon"]})
    w = client.get("/api/garden/today").json()["weather"]
    assert w["place"] == "Brisbane" and w["days"][0]["max"] == 31 and w["tips"][0]["kind"] == "heat"
    assert client.put("/api/garden/settings", json={"climate": "Polar"}).status_code == 422


def test_lists(client):
    lists = client.get("/api/garden/lists").json()
    assert "Self-watering pot" in lists["container_kinds"] and "Balcony" in lists["space_kinds"] and "Seeds" in lists["item_kinds"]


def test_regional_plant_links_still_add(client, monkeypatch):
    """A plant only some stores sell is a 404 for Bunnings' default store: kept from what its link says."""
    def not_here(url):
        raise bunnings.NotAtDefaultStore("Bunnings only shows that product to some stores")
    monkeypatch.setattr(bunnings, "_get", not_here)
    r = client.post("/api/garden/items/bunnings", json={"url": "https://www.bunnings.com.au/100mm-leek-alllium-ampeloprasum-var-porrum_p0194944",
                                                        "status": "Wanted"}).json()
    assert (r["name"], r["kind"], r["bunnings_item"], r["partial"], r["price"]) == \
        ("100mm Leek Alllium Ampeloprasum Var Porrum", "Seedling", "0194944", True, None)
    assert r["url"].endswith("_p0194944") and "plants are regional" in r["notes"]
    again = client.post(f"/api/garden/items/{r['item_id']}/bunnings")
    assert again.status_code == 422 and "stores that sell it" in again.json()["detail"]
    assert bunnings.name_from_url("https://www.bunnings.com.au/scotts-osmocote-10l-premium-mix_p2962117") == "Scotts Osmocote 10l Premium Mix"
