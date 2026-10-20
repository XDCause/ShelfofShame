"""Travel: trips and their phases, bookings and the day plan, money in other currencies, packing, places and
countries, the journal and photos, the calendar and the activity feed."""
from datetime import date, timedelta

import pytest

from app import frankfurter, openmeteo
from app.db import db

TODAY = date.today()
D = lambda n: (TODAY + timedelta(days=n)).isoformat()  # noqa: E731
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")


@pytest.fixture
def rates(monkeypatch):
    """The ECB's rates, per AUD: 100 yen, 0.65 US dollars."""
    asked = []
    monkeypatch.setattr(frankfurter, "_get", lambda url, params: asked.append(params) or {
        "date": "2026-10-19", "rates": {"JPY": 100.0, "USD": 0.65}})
    return asked


def trip(client, **fields):
    r = client.post("/api/travel/trips", json={"name": "Japan", "kind": "Overseas", **fields})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_trips_phase_comes_from_its_dates(client):
    trip(client, name="Japan", start_date=D(30), end_date=D(43), countries=["jp"])
    trip(client, name="Bali", start_date=D(-60), end_date=D(-50))
    trip(client, name="Hobart", kind="Domestic", start_date=D(-1), end_date=D(2))
    trip(client, name="Iceland", status="Idea")
    trip(client, name="Fiji", start_date=D(5), status="Cancelled")
    trips = client.get("/api/travel/trips").json()
    assert [(t["name"], t["phase"]) for t in trips] == [
        ("Hobart", "now"), ("Japan", "upcoming"), ("Iceland", "idea"), ("Bali", "past"), ("Fiji", "cancelled")]
    hobart, japan = trips[0], trips[1]
    assert (hobart["days"], hobart["day_number"]) == (4, 2)
    assert (japan["starts_in"], japan["countries"]) == (30, ["JP"])
    assert [t["name"] for t in client.get("/api/travel/trips?phase=past").json()] == ["Bali"]
    assert client.post("/api/travel/trips", json={"name": "Back", "start_date": D(3), "end_date": D(1)}).status_code == 422
    assert client.patch(f"/api/travel/trips/{japan['trip_id']}", json={"end_date": D(1)}).status_code == 422
    assert client.post("/api/travel/trips", json={"name": "X", "countries": ["Japan"]}).status_code == 422


def test_bookings_and_money_in_other_currencies(client, rates):
    t = trip(client, start_date=D(10), end_date=D(20), budget=5000)
    url = f"/api/travel/trips/{t['trip_id']}"
    t = client.post(f"{url}/bookings", json={"kind": "Flight", "title": "QF61", "starts_at": f"{D(10)}T21:50",
                                             "from_place": "BNE", "to_place": "NRT", "cost": 1400, "paid": True}).json()
    assert t["bookings"][0]["rate"] == 1 and not rates                   # AUD: nothing asked
    t = client.post(f"{url}/bookings", json={"kind": "Stay", "title": "Hotel Gracery", "starts_at": f"{D(11)}T15:00",
                                             "ends_at": f"{D(14)}T10:00", "cost": 60000, "currency": "jpy",
                                             "reference": "ABC123"}).json()
    stay = next(b for b in t["bookings"] if b["kind"] == "Stay")
    assert (stay["currency"], stay["rate"], stay["cost_aud"], stay["category"]) == ("JPY", 0.01, 600.0, "Stay")
    t = client.post(f"{url}/expenses", json={"amount": 2500, "currency": "JPY", "category": "Food", "what": "Ramen",
                                             "spent_on": D(11)}).json()
    m = t["money"]
    assert (m["spent"], m["left"], m["unpaid"], m["currencies"]) == (2025.0, 2975.0, 600.0, ["JPY"])
    assert {c["category"]: c["aud"] for c in m["by_category"]} == {"Stay": 600.0, "Transport": 1400.0, "Food": 25.0}
    assert len(rates) == 1                                                # the rates are kept, not asked each time
    # Your own rate for yen on this trip - and re-price what's there
    t = client.put(f"{url}/rates/JPY?apply=true", json={"rate": 0.0095}).json()
    assert t["rates"] == {"JPY": 0.0095} and t["money"]["spent"] == pytest.approx(1400 + 570 + 23.75)
    # A booking keeps its rate unless its currency changes
    t = client.patch(f"/api/travel/bookings/{stay['booking_id']}", json={"cost": 50000, "paid": True}).json()
    stay = next(b for b in t["bookings"] if b["kind"] == "Stay")
    assert (stay["rate"], stay["cost_aud"], t["money"]["unpaid"]) == (0.0095, 475.0, 0)
    t = client.patch(f"/api/travel/bookings/{stay['booking_id']}", json={"currency": "USD"}).json()
    assert next(b for b in t["bookings"] if b["kind"] == "Stay")["rate"] == pytest.approx(1 / 0.65, rel=1e-6)
    # A currency with no published rate: set your own
    r = client.post(f"{url}/expenses", json={"amount": 100000, "currency": "VND"})
    assert r.status_code == 422 and "set your own" in r.json()["detail"]
    client.put(f"{url}/rates/VND", json={"rate": 0.00006})
    assert client.post(f"{url}/expenses", json={"amount": 100000, "currency": "VND"}).status_code == 201
    assert client.patch(f"/api/travel/bookings/{stay['booking_id']}", json={"ends_at": f"{D(1)}T10:00"}).status_code == 422


def test_rates_down_says_what_to_do(client, monkeypatch):
    def down(*_a):
        raise frankfurter.RatesError("Couldn't reach the exchange rates (Frankfurter: ConnectError).")
    monkeypatch.setattr(frankfurter, "_get", down)
    t = trip(client)
    r = client.post(f"/api/travel/trips/{t['trip_id']}/expenses", json={"amount": 10, "currency": "JPY"})
    assert r.status_code == 422 and "Set your own JPY rate" in r.json()["detail"]
    assert client.post(f"/api/travel/trips/{t['trip_id']}/expenses", json={"amount": 10}).status_code == 201   # AUD is fine
    assert "AUD" in client.get("/api/travel/lists").json()["currencies"]      # the usual ones, then


def test_the_day_plan_and_what_needs_doing(client):
    client.put("/api/travel/settings", json={"passport_expires": D(100)})
    t = trip(client, start_date=D(7), end_date=D(14))
    url = f"/api/travel/trips/{t['trip_id']}"
    t = client.post(f"{url}/plan", json={"title": "Apply for the visa"}).json()            # before you go
    t = client.post(f"{url}/plan", json={"title": "teamLab", "day": D(9), "at": "10:00"}).json()
    t = client.post(f"{url}/bookings", json={"kind": "Tour", "title": "Mt Fuji day trip", "cost": 150}).json()
    assert [i["title"] for i in t["plan"]] == ["Apply for the visa", "teamLab"]
    w = " ".join(t["warnings"])
    assert "passport expires" in w and "under 6 months" in w
    assert "1 booking not marked paid" in w and "1 thing to do before you go" in w
    visa = t["plan"][0]
    t = client.patch(f"/api/travel/plan/{visa['item_id']}", json={"done": True}).json()
    assert "before you go" not in " ".join(t["warnings"])
    client.put("/api/travel/settings", json={"passport_expires": D(3000)})
    assert "passport" not in " ".join(client.get(url).json()["warnings"])
    place = client.post("/api/travel/places", json={"name": "Elsewhere"}).json()
    assert client.post(f"{url}/plan", json={"title": "x", "place_id": place["place_id"]}).status_code == 422


def test_packing_from_lists_and_your_gear(client):
    t = trip(client)
    url = f"/api/travel/trips/{t['trip_id']}"
    lists = {p["name"]: p for p in client.get("/api/travel/packing-lists").json()}
    assert {"Essentials", "Overseas", "Camping", "Shooting trip", "Volleyball tournament"} <= set(lists)
    t = client.post(f"{url}/packing/from-list", json={"list_id": lists["Overseas"]["list_id"]}).json()
    n = len(t["packing"])
    assert n == lists["Overseas"]["count"] and t["packing"][0]["grp"] == "Documents"     # grouped: documents first
    t = client.post(f"{url}/packing/from-list", json={"list_id": lists["Overseas"]["list_id"]}).json()
    assert len(t["packing"]) == n                                          # nothing twice
    with db() as conn:
        conn.execute("INSERT INTO gear (hobby, name) VALUES ('hiking', 'Merrell boots'), ('hiking', 'Old pack')")
        conn.execute("UPDATE gear SET condition = 'Retired' WHERE name = 'Old pack'")
    t = client.post(f"{url}/packing/gear", json={"hobby": "hiking"}).json()
    boots = next(p for p in t["packing"] if p["name"] == "Merrell boots")
    assert boots["gear_hobby"] == "hiking" and not any(p["name"] == "Old pack" for p in t["packing"])
    assert client.post(f"{url}/packing/gear", json={"hobby": "chess"}).status_code == 422
    assert client.post(f"{url}/packing", json={"name": "Merrell boots"}).status_code == 409
    t = client.patch(f"/api/travel/packing/{boots['item_id']}", json={"packed": True}).json()
    assert t["packed_count"] == 1
    t = client.post(f"{url}/packing/unpack").json()
    assert t["packed_count"] == 0
    # Save it as a list of your own (your gear stays with the trip, not the list)
    saved = {p["name"]: p for p in client.post("/api/travel/packing-lists", json={"name": "Japan", "from_trip": t["trip_id"]}).json()}
    assert saved["Japan"]["count"] == n
    assert client.post("/api/travel/packing-lists", json={"name": "japan", "items": []}).status_code == 409
    after = client.delete(f"/api/travel/packing-lists/{saved['Japan']['list_id']}").json()
    assert "Japan" not in {p["name"] for p in after}


def test_places_the_map_and_countries(client, monkeypatch):
    past = trip(client, name="Bali", kind="Overseas", start_date=D(-60), end_date=D(-50), countries=["ID"])
    soon = trip(client, name="NZ", start_date=D(20), end_date=D(30), countries=["NZ"])
    r = client.post("/api/travel/places", json={"name": "Ubud", "trip_id": past["trip_id"], "country": "id", "lat": -8.5, "lon": 115.26})
    assert r.json()["places"][0]["status"] == "Been"                     # added to a trip that's over: been
    t = client.post("/api/travel/places", json={"name": "Queenstown", "trip_id": soon["trip_id"], "country": "NZ"}).json()
    t = client.post("/api/travel/places", json={"name": "Milford Sound", "trip_id": soon["trip_id"], "country": "NZ", "kind": "Nature"}).json()
    assert [(p["name"], p["stop_order"], p["status"]) for p in t["places"]] == [("Queenstown", 1, "Planned"), ("Milford Sound", 2, "Planned")]
    t = client.put(f"/api/travel/trips/{soon['trip_id']}/stops", json={"place_ids": [p["place_id"] for p in reversed(t["places"])]}).json()
    assert [p["name"] for p in t["places"]] == ["Milford Sound", "Queenstown"]
    wish = client.post("/api/travel/places", json={"name": "Machu Picchu", "country": "PE", "kind": "Sight"}).json()
    assert wish["status"] == "Want" and wish["trip_id"] is None
    assert [p["name"] for p in client.get("/api/travel/places?shown=Want").json()] == ["Machu Picchu"]
    client.put("/api/travel/countries/us", json={"status": "Been", "first_year": 2015})
    client.put("/api/travel/countries/IS", json={"status": "Want"})
    c = client.get("/api/travel/countries").json()
    assert [x["code"] for x in c["been"]] == ["US", "ID"]                 # by the year you first went
    assert [x["code"] for x in c["want"]] == ["IS", "PE"]                 # NZ isn't been yet (the trip hasn't started)
    s = client.get("/api/travel/summary").json()
    assert (s["countries_been"], s["places_been"], s["bucket_list"]) == (2, 1, 1)
    with db() as conn:                                                    # the NZ trip's over: its places were been
        conn.execute("UPDATE trips SET start_date = %s, end_date = %s WHERE trip_id = %s", (D(-10), D(-5), soon["trip_id"]))
    assert {p["name"]: p["shown"] for p in client.get("/api/travel/places").json()}["Queenstown"] == "Been"
    assert "NZ" in [x["code"] for x in client.get("/api/travel/countries").json()["been"]]
    # Finding a town: Open-Meteo's place search, with its country
    monkeypatch.setattr(openmeteo, "_get", lambda url, params: {"results": [
        {"name": "Kyoto", "admin1": "Kyoto", "country": "Japan", "country_code": "JP", "latitude": 35.02107, "longitude": 135.75386}]})
    assert client.get("/api/travel/find-place?q=Kyoto").json() == [
        {"name": "Kyoto", "region": "Kyoto, Japan", "country": "JP", "lat": 35.0211, "lon": 135.7539}]


def test_journal_photos_and_weather(client, monkeypatch):
    t = trip(client, start_date=D(-1), end_date=D(3))
    url = f"/api/travel/trips/{t['trip_id']}"
    t = client.put(f"{url}/entries/{D(-1)}", json={"text": "  Landed, found the hotel.  "}).json()
    assert [(e["day"], e["text"]) for e in t["entries"]] == [(D(-1), "Landed, found the hotel.")]
    t = client.put(f"{url}/entries/{D(-1)}", json={"text": ""}).json()
    assert t["entries"] == []
    r = client.post(f"{url}/photos?lat=35.0&lon=135.7&taken={D(0)}T09:30:00", content=PNG, headers={"Content-Type": "image/png"})
    assert r.status_code == 201
    photo = r.json()["photos"][0]
    assert (photo["day"], photo["lat"]) == (D(0), 35.0)
    assert client.get(photo["url"]).content == PNG
    assert client.get(url).json()["photo_url"] == photo["url"]           # no cover: the first photo
    assert [p["photo_id"] for p in client.get("/api/travel/photos").json()] == [photo["photo_id"]]
    t = client.patch(f"/api/travel/photos/{photo['photo_id']}", json={"caption": "Fushimi Inari"}).json()
    assert t["photos"][0]["caption"] == "Fushimi Inari"
    # The weather where you are (a stop with a place on the map), while the trip's on
    assert client.get(url).json()["weather"] is None                     # no stops yet
    client.post("/api/travel/places", json={"name": "Kyoto", "trip_id": t["trip_id"], "lat": 35.0, "lon": 135.7})
    monkeypatch.setattr(openmeteo, "_get", lambda url, params: {"daily": {"time": [D(0)], "temperature_2m_max": [24],
                                                                         "weather_code": [0]}})
    w = client.get(url).json()["weather"]
    assert w["place"] == "Kyoto" and w["days"][0]["sky"] == "Sunny"
    assert client.delete(f"/api/travel/photos/{photo['photo_id']}").json()["photos"] == []


def test_trips_on_the_calendar_and_in_the_activity_feed(client):
    t = trip(client, name="Japan", start_date=D(2), end_date=D(4), destination="Tokyo")
    url = f"/api/travel/trips/{t['trip_id']}"
    client.post(f"{url}/bookings", json={"kind": "Flight", "title": "QF61", "starts_at": f"{D(2)}T21:50", "ends_at": f"{D(3)}T06:00",
                                         "from_place": "BNE", "to_place": "NRT"})
    client.post(f"{url}/bookings", json={"kind": "Stay", "title": "Hotel", "starts_at": f"{D(3)}T15:00", "ends_at": f"{D(4)}T10:00"})
    trip(client, name="Maybe", status="Idea")
    cal = client.get(f"/api/calendar?start={D(0)}&end={D(10)}").json()["events"]
    titles = [(e["day"], e["title"], e["start_time"]) for e in cal if e.get("trip_id")]
    assert titles == [(D(2), "Japan · day 1 of 3", None), (D(2), "Flight: QF61", "21:50:00"),
                      (D(3), "Japan · day 2 of 3", None), (D(3), "Check in: Hotel", "15:00:00"),
                      (D(4), "Japan · day 3 of 3", None), (D(4), "Check out: Hotel", "10:00:00")]
    coming = client.get("/api/calendar/upcoming?limit=10").json()
    assert [e["title"] for e in coming] == ["Japan starts", "Flight: QF61", "Check in: Hotel", "Check out: Hotel"]
    with db() as conn:
        conn.execute("UPDATE trips SET start_date = start_date - 10, end_date = end_date - 10 WHERE trip_id = %s", (t["trip_id"],))
    feed = [a for a in client.get("/api/activity?limit=50").json() if a["kind"] == "trip"]
    assert [(a["verb"], a["title"], a["detail"]) for a in feed] == [("Travelled", "Japan", "Tokyo · 3 days")]
    found_ = client.get("/api/journal/mentionable?q=japan").json()
    assert [(m["kind"], m["what"]) for m in found_ if m["kind"] == "trip"] == [("trip", "Trip")]


def test_the_dashboard(client):
    client.put("/api/travel/settings", json={"passport_expires": D(200)})
    trip(client, name="Bali", start_date=date(TODAY.year, 1, 2).isoformat(), end_date=date(TODAY.year, 1, 8).isoformat(), budget=3000)
    trip(client, name="NZ", start_date=D(40), end_date=D(45))
    trip(client, name="Iceland", status="Idea")
    s = client.get("/api/travel/summary").json()
    assert [t["name"] for t in s["upcoming"]] == ["NZ"] and [t["name"] for t in s["ideas"]] == ["Iceland"]
    if TODAY > date(TODAY.year, 1, 8):
        assert (s["this_year"]["trips"], s["this_year"]["days"]) == (1, 7)
        assert [t["name"] for t in s["recent"]] == ["Bali"] and s["years"][-1]["trips"] == 1
    assert "renewing takes weeks" in s["passport_warning"]
    assert client.delete(f"/api/travel/trips/{s['upcoming'][0]['trip_id']}").status_code == 204
    assert [t["name"] for t in client.get("/api/travel/summary").json()["upcoming"]] == []
