"""Editing and removing things the other tests only add: shooting ranges, rifles and ammo; a trip's spending and the
packing lists; garden notes and reminders. Each: a change sticks, a required field can't be emptied, a missing one is
a 404, and removing it leaves what should stay."""
from datetime import date, timedelta

from tests.test_garden import balcony


def D(days):
    return (date.today() + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- shooting
def test_a_range_edited_then_removed_its_sessions_stay(client):
    r = client.post("/api/shooting/ranges", json={"name": "Club range"}).json()
    url = f"/api/shooting/ranges/{r['range_id']}"
    changed = client.patch(url, json={"name": "  Club range (north) ", "distances": "50, 100 m"}).json()
    assert (changed["name"], changed["distances"]) == ("Club range (north)", "50, 100 m")
    for field in ("name", "kind", "counts_for_club"):
        assert client.patch(url, json={field: None}).status_code == 422, field
    s = client.post("/api/shooting/sessions", json={"range_id": r["range_id"]}).json()
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404
    assert client.patch(url, json={"name": "x"}).status_code == 404
    assert client.get(f"/api/shooting/sessions/{s['session_id']}").json()["range_id"] is None   # the session stays


def test_a_rifle_edited_then_removed(client):
    rifle = client.post("/api/shooting/rifles", json={"name": "CZ 457", "scope_unit": "MIL"}).json()
    url = f"/api/shooting/rifles/{rifle['rifle_id']}"
    assert client.patch(url, json={"scope_unit": "MOA", "notes": " zeroed at 50 "}).json()["scope_unit"] == "MOA"
    for field in ("name", "kind", "scope_unit", "rounds_before", "status"):
        assert client.patch(url, json={field: None}).status_code == 422, field
    assert client.patch(url, json={"scope_unit": "Furlongs"}).status_code == 422
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404 and client.delete(url).status_code == 404


def test_ammo_edited_then_removed(client):
    ammo = client.post("/api/shooting/ammo", json={"name": "Center-X", "rounds_bought": 500}).json()
    url = f"/api/shooting/ammo/{ammo['ammo_id']}"
    assert client.patch(url, json={"rounds_bought": 1000}).json()["rounds_bought"] == 1000
    for field in ("name", "rounds_bought", "status"):
        assert client.patch(url, json={field: None}).status_code == 422, field
    assert client.patch(url, json={"rounds_bought": -1}).status_code == 422
    assert client.delete(url).status_code == 204
    assert client.patch(url, json={"name": "x"}).status_code == 404


# ---------------------------------------------------------------- travel
def test_a_trips_spending_edited_and_removed_moves_the_totals(client):
    t = client.post("/api/travel/trips", json={"name": "Coast", "kind": "Domestic", "start_date": D(5), "end_date": D(8),
                                               "budget": 1000}).json()
    t = client.post(f"/api/travel/trips/{t['trip_id']}/expenses", json={"amount": 120, "category": "Food", "spent_on": D(6)}).json()
    expense = t["expenses"][0]
    url = f"/api/travel/expenses/{expense['expense_id']}"
    t = client.patch(url, json={"amount": 80, "what": " fish and chips "}).json()
    assert t["money"]["spent"] == 80 and t["money"]["left"] == 920 and t["expenses"][0]["what"] == "fish and chips"
    for field in ("amount", "spent_on", "category"):
        assert client.patch(url, json={field: None}).status_code == 422, field
    t = client.delete(url).json()
    assert t["expenses"] == [] and t["money"]["spent"] == 0
    assert client.delete(url).status_code == 404 and client.patch(url, json={"amount": 1}).status_code == 404


def test_a_packing_list_renamed_and_its_items_replaced(client):
    lists = client.get("/api/travel/packing-lists").json()
    first, second = lists[0], lists[1]
    url = f"/api/travel/packing-lists/{first['list_id']}"
    after = {p["list_id"]: p for p in client.patch(url, json={"name": "  Weekend away "}).json()}
    assert after[first["list_id"]]["name"] == "Weekend away"
    assert client.patch(url, json={"name": second["name"].upper()}).status_code == 409       # names are unique, any case
    after = {p["list_id"]: p for p in client.patch(url, json={"items": [{"name": "Hat"}, {"name": "hat"}, {"name": "Sunscreen"}]}).json()}
    assert [i["name"] for i in after[first["list_id"]]["items"]] == ["Hat", "Sunscreen"]       # a repeat is dropped
    assert client.patch(url, json={"name": ""}).status_code == 422
    assert client.patch("/api/travel/packing-lists/999999", json={"name": "Nope"}).status_code == 404


# ---------------------------------------------------------------- garden
def test_a_garden_note_edited_then_removed(client):
    s = balcony(client)
    log = client.post("/api/garden/logs", json={"space_id": s["space_id"], "kind": "Note", "text": "Windy"}).json()
    url = f"/api/garden/logs/{log['log_id']}"
    changed = client.patch(url, json={"text": " Very windy ", "tags": [" Wind ", "", "x" * 60]}).json()
    assert changed["text"] == "Very windy" and changed["tags"] == ["Wind", "x" * 40]           # trimmed, blanks gone, capped
    for field in ("kind", "happened_on"):
        assert client.patch(url, json={field: None}).status_code == 422, field
    assert client.delete(url).status_code == 204
    assert client.patch(url, json={"text": "x"}).status_code == 404 and client.delete(url).status_code == 404


def test_a_garden_reminder_edited(client):
    task = client.post("/api/garden/tasks", json={"title": "Buy saucers"}).json()
    url = f"/api/garden/tasks/{task['task_id']}"
    changed = client.patch(url, json={"title": " Buy big saucers ", "due_on": D(3)}).json()
    assert (changed["title"], changed["due_on"]) == ("Buy big saucers", D(3))
    assert client.patch(url, json={"due_on": None}).status_code == 422
    assert client.patch(url, json={"title": None}).status_code == 422
    assert client.patch("/api/garden/tasks/999999", json={"title": "x"}).status_code == 404
