"""Travel extras: splitting a trip's costs (who paid, who shares, who owes who) and the day-by-day map."""
from app import frankfurter
from app.travel_extras import km_between, settle, split_cents


def trip(client, **fields):
    r = client.post("/api/travel/trips", json={"name": "Japan", "kind": "Overseas", "start_date": "2026-12-01",
                                                "end_date": "2026-12-05", **fields})
    assert r.status_code == 201, r.text
    return r.json()["trip_id"]


def person(client, tid, name):
    r = client.post(f"/api/travel/trips/{tid}/people", json={"name": name})
    assert r.status_code == 201, r.text
    return {p["name"]: p["person_id"] for p in r.json()["people"]}[name]


def spend(client, tid, amount, what="Dinner", currency="AUD", **kw):
    r = client.post(f"/api/travel/trips/{tid}/expenses", json={"amount": amount, "what": what, "currency": currency,
                                                                "spent_on": "2026-12-02", **kw})
    assert r.status_code == 201, r.text
    return max(e["expense_id"] for e in r.json()["expenses"])


# -- the sums ---------------------------------------------------------------------------------
def test_cents_split_exactly_and_settling_takes_the_fewest_payments():
    assert split_cents(1000, [3, 1, 2]) == {1: 334, 2: 333, 3: 333}
    assert sum(split_cents(1001, [1, 2, 3, 4]).values()) == 1001 and split_cents(5, []) == {}
    assert settle({1: 5000, 2: -2000, 3: -3000}) == [(3, 1, 3000), (2, 1, 2000)]
    assert settle({1: 100, 2: -100}) == [(2, 1, 100)] and settle({1: 0, 2: 0}) == []
    # Two debtors, two creditors, each pair matching exactly: two payments, not three.
    pays = settle({1: 70, 2: 30, 3: -70, 4: -30})
    assert sorted(pays) == [(3, 1, 70), (4, 2, 30)]
    net = {1: 70, 2: 30, 3: -60, 4: -40}
    left = dict(net)
    for d, c, a in settle(net):
        left[d] += a
        left[c] -= a
    assert set(left.values()) == {0}


def test_straight_line_distance():
    assert abs(km_between((-27.47, 153.03), (-26.65, 153.09)) - 91.4) < 0.5          # Brisbane to Mooloolaba
    assert km_between((1, 1), (1, 1)) == 0


# -- splitting costs --------------------------------------------------------------------------
def test_who_owes_who(client):
    tid = trip(client)
    a, b, c = person(client, tid, "Alex"), person(client, tid, "Sam"), person(client, tid, "Kim")
    assert client.post(f"/api/travel/trips/{tid}/people", json={"name": " alex "}).status_code == 409
    dinner = spend(client, tid, 90)                                    # Alex paid, all three share
    taxi = spend(client, tid, 30, "Taxi")                              # Sam paid, Sam and Kim share
    spend(client, tid, 10, "Snack")                                    # nobody said who paid: left out
    assert client.put(f"/api/travel/expenses/{dinner}/split", json={"paid_by": a, "shared_by": []}).status_code == 200
    r = client.put(f"/api/travel/expenses/{taxi}/split", json={"paid_by": b, "shared_by": [b, c]})
    assert r.status_code == 200, r.text
    s = r.json()
    net = {x["name"]: x["net"] for x in s["balances"]}
    assert net == {"Alex": 60.0, "Sam": -15.0, "Kim": -45.0}                # Alex paid 90 owes 30; Sam paid 30 owes 30+15
    assert (s["counted"], s["unassigned"], s["total"]) == (2, 1, 120.0)
    assert [(p["from"], p["to"], p["amount"]) for p in s["settle"]] == [("Kim", "Alex", 45.0), ("Sam", "Alex", 15.0)]
    assert client.put(f"/api/travel/expenses/{taxi}/split", json={"paid_by": 999, "shared_by": []}).status_code == 422
    assert client.put("/api/travel/expenses/999/split", json={"paid_by": a}).status_code == 404
    # Take someone off the trip: what they paid becomes unassigned.
    s = client.delete(f"/api/travel/people/{b}").json()
    assert (s["counted"], s["unassigned"]) == (1, 2) and len(s["people"]) == 2
    assert client.patch(f"/api/travel/people/{c}", json={"name": "Alex"}).status_code == 409
    assert [p["name"] for p in client.patch(f"/api/travel/people/{c}", json={"name": "Kimmy"}).json()["people"]] == ["Alex", "Kimmy"]
    assert client.get("/api/travel/trips/999/split").status_code == 404


def test_a_booking_can_be_split_and_money_shows_in_another_currency(client, monkeypatch):
    monkeypatch.setattr(frankfurter, "_get", lambda url, params: {"date": "2026-10-19", "rates": {"JPY": 100.0}})
    tid = trip(client)
    a, b = person(client, tid, "Alex"), person(client, tid, "Sam")
    r = client.post(f"/api/travel/trips/{tid}/bookings", json={"kind": "Stay", "title": "Hotel", "cost": 20000, "currency": "JPY"})
    bid = r.json()["bookings"][0]["booking_id"]                          # 20000 yen at 0.01 = 200 AUD
    s = client.put(f"/api/travel/bookings/{bid}/split", json={"paid_by": a, "shared_by": [a, b]}).json()
    assert {x["name"]: x["net"] for x in s["balances"]} == {"Alex": 100.0, "Sam": -100.0}
    assert s["settle"][0]["amount"] == 100.0 and s["currency"] == "AUD"
    yen = client.get(f"/api/travel/trips/{tid}/split?show=JPY").json()
    assert yen["currency"] == "JPY" and yen["settle"][0]["amount"] == 10000.0 and yen["settle"][0]["aud"] == 100.0
    assert client.get(f"/api/travel/trips/{tid}/split?show=toolong").status_code == 422
    assert client.put(f"/api/travel/bookings/{bid}/split", json={"paid_by": None, "shared_by": [a]}).json()["counted"] == 0


# -- the day map ------------------------------------------------------------------------------
def test_the_day_map_orders_stops_and_measures_between_them(client):
    tid = trip(client)
    def place(name, lat, lon, **kw):
        r = client.post("/api/travel/places", json={"name": name, "trip_id": tid, "lat": lat, "lon": lon, **kw})
        assert r.status_code == 201, r.text
        return next(p for p in client.get(f"/api/travel/trips/{tid}").json()["places"] if p["name"] == name)["place_id"]
    park = place("Park", -27.47, 153.03)
    museum = place("Museum", -27.48, 153.04)
    place("Beach", -26.65, 153.09, visit_on="2026-12-03")           # (a place for another day: not on this day's map)
    nowhere = place("No position", None, None)
    for title, at, pid in (("Lunch", "12:00", museum), ("Walk", "09:00", park), ("Mystery", "10:00", nowhere)):
        r = client.post(f"/api/travel/trips/{tid}/plan", json={"title": title, "day": "2026-12-02", "at": at, "place_id": pid})
        assert r.status_code == 201, r.text
    m = client.get(f"/api/travel/trips/{tid}/day-map").json()
    assert [d["day"] for d in m["days"]] == ["2026-12-02", "2026-12-03"]
    d1, d2 = m["days"]
    assert (d1["number"], [s["name"] for s in d1["stops"]]) == (2, ["Park", "Museum"])      # by time; the unplaced one is left out
    assert len(d1["legs"]) == 1 and 1 < d1["legs"][0]["km"] < 2 and d1["legs"][0]["road_km"] > d1["legs"][0]["km"]
    assert [s["name"] for s in d2["stops"]] == ["Beach"] and d2["legs"] == []
    assert m["without_position"] == 1
    assert client.get("/api/travel/trips/999/day-map").status_code == 404
