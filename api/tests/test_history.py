"""Stock history: recorded by the database trigger, with a reason for each change."""
from app.db import db


def history(client, supply_id):
    return [(m["change"], m["qty_after"], m["reason"])
            for m in reversed(client.get(f"/api/supplies/{supply_id}/history").json())]


def test_every_kind_of_change_is_recorded_with_its_reason(client, make_supply):
    s = make_supply(qty_on_hand=2)
    sid = s["supply_id"]
    client.post(f"/api/supplies/{sid}/adjust", json={"delta": -1})
    client.post(f"/api/supplies/{sid}/adjust", json={"delta": 3})
    client.patch(f"/api/supplies/{sid}", json={"qty_on_hand": 10})
    client.patch(f"/api/supplies/{sid}", json={"notes": "no quantity change"})  # not logged
    with db() as conn:  # e.g. an edit in DBeaver: no reason set
        conn.execute("UPDATE supplies SET qty_on_hand = 7 WHERE supply_id = %s", (sid,))

    assert history(client, sid) == [
        (2, 2, "added"),
        (-1, 1, "used"),
        (3, 4, "bought"),
        (6, 10, "edited"),
        (-3, 7, "manual"),
    ]


def test_history_survives_deleting_the_item(client, make_supply):
    s = make_supply(qty_on_hand=2, name="Doomed paint")
    client.delete(f"/api/supplies/{s['supply_id']}")
    latest = client.get("/api/history", params={"limit": 1}).json()[0]
    assert latest["item_name"] == "Doomed paint"
    assert latest["supply_id"] is None
    assert (latest["change"], latest["qty_after"], latest["reason"]) == (-2, 0, "deleted")


def test_refused_change_leaves_no_history(client, make_supply):
    s = make_supply(qty_on_hand=0)
    client.post(f"/api/supplies/{s['supply_id']}/adjust", json={"delta": -1})  # 422
    assert history(client, s["supply_id"]) == [(0, 0, "added")]
