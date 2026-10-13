"""The activity feed: stock, kits, build log, time and journal, newest first."""
from datetime import date, timedelta


def test_everything_you_did_newest_first(client, make_supply):
    paint = make_supply(product_code="T81710", name="Acrylic XF10 Flat Brown", qty_on_hand=1)
    client.post(f"/api/supplies/{paint['supply_id']}/adjust", json={"delta": -1})
    kit = client.post("/api/models", json={"name": "Zero", "status": "In progress",
                                           "purchase_date": "2026-10-01", "price_paid": "40"}).json()
    client.post(f"/api/models/{kit['model_id']}/log", json={"text": "Cockpit painted"})
    client.post(f"/api/models/{kit['model_id']}/sessions", json={"minutes": 45, "note": "wings"})
    client.post("/api/journal", json={"title": "Bench notes"})

    feed = client.get("/api/activity").json()
    seen = {(f["verb"], f["title"]) for f in feed}
    assert {("Added", "Acrylic XF10 Flat Brown"), ("Used", "Acrylic XF10 Flat Brown"), ("Bought", "Zero"),
            ("Started", "Zero"), ("Logged", "Zero"), ("Worked on", "Zero"), ("Wrote", "Bench notes")} <= seen
    assert [f["at"] for f in feed] == sorted((f["at"] for f in feed), reverse=True)
    logged = next(f for f in feed if f["verb"] == "Logged")
    assert (logged["kind"], logged["ref"], logged["detail"]) == ("model", kit["model_id"], "Cockpit painted")
    worked = next(f for f in feed if f["verb"] == "Worked on")
    assert worked["detail"] == "45 min · wings"


def test_wanted_kits_and_edits_are_not_activity(client, make_supply):
    paint = make_supply(product_code="T81701", name="XF-1", qty_on_hand=1)
    client.patch(f"/api/supplies/{paint['supply_id']}", json={"notes": "nice"})
    client.post("/api/models", json={"name": "Dream kit", "status": "Wanted", "purchase_date": "2026-10-01"})
    assert [(f["verb"], f["title"]) for f in client.get("/api/activity").json()] == [("Added", "XF-1")]


def test_limit_and_since(client):
    old = (date.today() - timedelta(days=30)).isoformat()
    kit = client.post("/api/models", json={"name": "Old kit", "status": "Finished"}).json()
    client.patch(f"/api/models/{kit['model_id']}", json={"started_on": old, "finished_on": old})
    client.post("/api/journal", json={"title": "Today"})
    assert len(client.get("/api/activity?limit=1").json()) == 1
    recent = client.get(f"/api/activity?since={(date.today() - timedelta(days=7)).isoformat()}").json()
    assert [f["title"] for f in recent] == ["Today"]
