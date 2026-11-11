"""Vinyl: records by hand and from Discogs (faked with the walk-through's made-up catalogue, stand_ins.py - tests never
call Discogs or Last.fm), the Discogs sync, values, plays and scrobbling, and the parts other pages show: the wishlist,
the journal, activity, goals, the value report, the export."""
from datetime import datetime, timedelta, timezone

import pytest

from app import discogs, frankfurter, lastfm, stand_ins, vinyl_sync


@pytest.fixture
def dg(monkeypatch):
    """A fake Discogs (the stand-in catalogue) and AUD rates; `asked` records calls that write to Discogs."""
    asked = []
    monkeypatch.setenv("DISCOGS_TOKEN", "test-token")
    monkeypatch.setattr(discogs, "identity", lambda: "collector")
    monkeypatch.setattr(discogs, "collection", stand_ins.discogs_collection)
    monkeypatch.setattr(discogs, "wants", lambda user: iter([{"id": rid, "basic_information": stand_ins._basic(rid), "notes": "",
                                                               "date_added": "2026-03-01T10:00:00-07:00"} for rid in stand_ins.DISCOGS_WANTS]))
    monkeypatch.setattr(discogs, "release", lambda rid: stand_ins.DISCOGS_RELEASES.get(int(rid)))
    monkeypatch.setattr(discogs, "master_year", lambda mid: stand_ins.DISCOGS_MASTERS.get(int(mid)))
    monkeypatch.setattr(discogs, "search", stand_ins.discogs_search)
    monkeypatch.setattr(discogs, "price_suggestion",
                        lambda rid: {"NM": (40.0, "USD"), "VG+": (30.0, "USD"), "VG": (20.0, "USD")} if int(rid) != 9002 else {})
    monkeypatch.setattr(discogs, "cover", lambda url: (stand_ins.PNG, "image/png"))

    def add_to_collection(user, rid):
        asked.append(("add", user, rid))
        return 80000 + rid
    monkeypatch.setattr(discogs, "add_to_collection", add_to_collection)
    monkeypatch.setattr(frankfurter, "_get", lambda url, params: {"date": "2026-11-11", "rates": {"USD": 0.5}})   # 1 USD = 2 AUD
    return asked


def add(client, **record):
    r = client.post("/api/vinyl/records", json={**({} if "discogs_release_id" in record else {"title": "A Record"}), **record})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- Discogs' shapes
def test_discogs_shapes():
    assert discogs.artist_name([{"name": "Nirvana (2)", "join": "&"}, {"name": "Someone", "anv": "Some One"}]) == "Nirvana & Some One"
    assert discogs.artist_name([{"name": "A", "join": ","}, {"name": "B", "join": "Feat."}, {"name": "C"}]) == "A, B Feat. C"
    f = discogs.format_facts([{"name": "Vinyl", "qty": "2", "descriptions": ["LP", "Album", "180 Gram", "Limited Edition"], "text": "Blue"}])
    assert f == {"medium": "Vinyl", "format": "LP", "size": '12"', "discs": 2, "variant": "Blue, 180 Gram, Limited Edition"}
    assert discogs.format_facts([{"name": "Vinyl", "descriptions": ['7"', "45 RPM", "Single"]}])["format"] == "Single"
    assert discogs.format_facts([{"name": "Vinyl", "descriptions": ['7"', "45 RPM", "Single"]}])["size"] == '7"'
    assert discogs.format_facts([{"name": "CD", "descriptions": ["Album"]}]) | {} == {"medium": "CD", "format": "Other", "size": None,
                                                                                    "discs": 1, "variant": None}
    full = discogs.record_from(full=stand_ins.DISCOGS_RELEASES[9005])
    assert full["barcode"] == "5012345678900" and full["variant"] == "Clear, Limited Edition"
    assert [t["position"] for t in full["tracklist"]] == ["A1", "B1"] and full["lowest_price"] == 18.5


# ---------------------------------------------------------------- records
def test_add_by_hand_filter_update_delete(client):
    a = add(client, title="Blue Lines", artist="Massive Attack", year=1991, genres=["Electronic", " Trip Hop ", "Electronic"],
            media_condition="VG+", price_paid="35.00")
    assert a["status"] == "Owned" and a["format"] == "LP" and a["genres"] == ["Electronic", "Trip Hop"]
    add(client, title="Kind of Blue", artist="Miles Davis", year=1959, genres=["Jazz"])
    add(client, title="Wanted One", status="Wanted")
    r = client.get("/api/vinyl/records").json()
    assert [x["title"] for x in r["records"]] == ["Blue Lines", "Kind of Blue"]          # owned, by artist
    assert r["counts"] == {"Owned": 2, "Wanted": 1, "Gone": 0}
    assert r["facets"]["decades"] == [1950, 1990] and r["facets"]["genres"] == ["Electronic", "Jazz", "Trip Hop"]
    assert [x["title"] for x in client.get("/api/vinyl/records?decade=1955").json()["records"]] == ["Kind of Blue"]
    assert [x["title"] for x in client.get("/api/vinyl/records?genre=Trip Hop").json()["records"]] == ["Blue Lines"]
    assert [x["title"] for x in client.get("/api/vinyl/records?q=miles").json()["records"]] == ["Kind of Blue"]
    assert [x["title"] for x in client.get("/api/vinyl/records?status=Wanted").json()["records"]] == ["Wanted One"]
    assert len(client.get("/api/vinyl/records?status=all").json()["records"]) == 3

    r = client.patch(f"/api/vinyl/records/{a['record_id']}", json={"sleeve_condition": "Generic", "rating": 5,
                                                                   "tracklist": [{"position": "A1", "title": "Safe from Harm", "duration": "5:18"}]})
    assert r.status_code == 200 and r.json()["rating"] == 5 and r.json()["tracklist"][0]["title"] == "Safe from Harm"
    assert client.patch(f"/api/vinyl/records/{a['record_id']}", json={"media_condition": "Generic"}).status_code == 422   # not a record grade
    assert client.patch(f"/api/vinyl/records/{a['record_id']}", json={"title": " "}).status_code == 422
    assert client.patch(f"/api/vinyl/records/{a['record_id']}", json={"location_id": 99999}).status_code == 404
    assert client.post("/api/vinyl/records", json={"title": " "}).status_code == 422
    assert client.delete(f"/api/vinyl/records/{a['record_id']}").status_code == 204
    assert client.get(f"/api/vinyl/records/{a['record_id']}").status_code == 404


def test_your_own_value_is_kept(client):
    a = add(client, title="Mine")
    r = client.patch(f"/api/vinyl/records/{a['record_id']}", json={"value": "120.00"}).json()
    assert r["value"] == 120 and r["value_note"] == "Your value" and r["values"][-1]["value"] == 120


def test_lookup_and_add_from_discogs(client, dg):
    r = client.get("/api/vinyl/lookup?barcode=5012-3456-78900").json()
    assert r["barcode"] == "5012345678900" and [x["title"] for x in r["results"]] == ["Scanned In"]
    assert r["results"][0]["record_id"] is None and r["results"][0]["artist"] == "Barcode Band"
    rec = add(client, title="", discogs_release_id=9005, media_condition="NM", price_paid="45")
    assert rec["title"] == "Scanned In" and rec["artist"] == "Barcode Band" and rec["catno"] == "SIR-9005"
    assert rec["variant"] == "Clear, Limited Edition" and rec["barcode"] == "5012345678900" and rec["country"] == "Australia"
    assert rec["media_condition"] == "NM" and rec["have_count"] == 1205 and rec["discogs_url"].endswith("/release/9005")
    assert client.get(f"/api/vinyl/records/{rec['record_id']}").json()["has_photo"]       # the cover, fetched after
    again = client.get("/api/vinyl/lookup?q=scanned").json()["results"][0]
    assert again["record_id"] == rec["record_id"] and again["my_status"] == "Owned"
    assert dg == []                                                                         # Discogs not written to by default
    assert client.get("/api/vinyl/lookup").status_code == 422


def test_add_keeps_discogs_in_step_when_asked(client, dg):
    client.post("/api/vinyl/discogs/sync")                      # (learns the username)
    client.put("/api/vinyl/settings", json={"discogs_mirror": True})
    rec = add(client, discogs_release_id=9005)
    assert dg == [("add", "collector", 9005)] and rec["discogs_instance_id"] == 89005
    add(client, discogs_release_id=9004, status="Wanted")       # only owned ones go into the collection
    assert len(dg) == 1


def test_refresh_puts_discogs_facts_back(client, dg):
    rec = add(client, discogs_release_id=9001)
    assert rec["original_year"] == 1978 and rec["year"] == 1979
    client.patch(f"/api/vinyl/records/{rec['record_id']}", json={"label": "My label", "notes": "mine"})
    r = client.post(f"/api/vinyl/records/{rec['record_id']}/refresh").json()
    assert r["label"] == "Stand-in Records" and r["notes"] == "mine"
    hand = add(client, title="No link")
    assert client.post(f"/api/vinyl/records/{hand['record_id']}/refresh").status_code == 409


def test_no_token_says_so(client, monkeypatch):
    monkeypatch.delenv("DISCOGS_TOKEN", raising=False)
    r = client.post("/api/vinyl/discogs/sync")
    assert r.status_code == 409 and "DISCOGS_TOKEN" in r.json()["detail"]
    assert client.get("/api/vinyl/settings").json()["discogs"]["token"] is False


# ---------------------------------------------------------------- sync and values
def test_sync_brings_the_collection_and_wantlist(client, dg):
    hand = add(client, title="Only here")
    wanted = add(client, title="Spin Cycle", status="Wanted", discogs_release_id=9003)   # on your wantlist here; in the collection there
    assert client.post("/api/vinyl/discogs/sync").status_code == 202                     # (runs before the test client answers)
    s = client.get("/api/vinyl/settings").json()
    assert s["discogs"]["username"] == "collector" and s["discogs"]["synced_at"] and not s["sync"]["error"]
    assert (s["sync"]["added"], s["sync"]["linked"], s["sync"]["wanted"], s["sync"]["only_here"]) == (2, 1, 1, 1)
    owned = {r["title"]: r for r in client.get("/api/vinyl/records").json()["records"]}
    assert set(owned) == {"Needle Drop", "Test Pressing Suite", "Spin Cycle", "Only here"}
    needle = client.get(f"/api/vinyl/records/{owned['Needle Drop']['record_id']}").json()
    assert (needle["media_condition"], needle["sleeve_condition"], needle["notes"]) == ("NM", "VG+", "First pressing")
    assert needle["added_on"] == "2024-06-01" and needle["original_year"] == 1978 and len(needle["tracklist"]) == 4
    assert needle["has_photo"] and needle["details_at"]
    assert needle["value"] == 80 and needle["value_note"] == "Discogs' suggested price for NM"     # 40 USD at 2 AUD
    ep = client.get(f"/api/vinyl/records/{owned['Test Pressing Suite']['record_id']}").json()
    assert ep["format"] == "EP" and ep["size"] == '12"' and ep["variant"] == "Red Translucent"
    assert ep["value"] == 18.5 and ep["value_note"] == "The cheapest copy for sale on Discogs"    # no suggestion for it
    spin = client.get(f"/api/vinyl/records/{wanted['record_id']}").json()
    assert spin["status"] == "Owned" and spin["discogs_instance_id"] == 70003 and spin["media_condition"] == "VG"
    assert spin["value"] == 40                                                                     # VG: 20 USD
    assert client.get(f"/api/vinyl/records/{hand['record_id']}").json()["discogs_instance_id"] is None
    w = client.get("/api/vinyl/records?status=Wanted").json()["records"]
    assert [x["title"] for x in w] == ["Second Side"]
    prices = client.get(f"/api/wanted/record/{w[0]['record_id']}/prices").json()
    assert [(p["price"], p["source"]) for p in prices] == [(25.0, "Discogs")]                    # the wishlist's price history

    client.post("/api/vinyl/discogs/sync")                       # again: nothing doubled
    assert client.get("/api/vinyl/records?status=all").json()["counts"] == {"Owned": 4, "Wanted": 1, "Gone": 0}


def test_values_weekly_and_now(client, dg, monkeypatch):
    rec = add(client, discogs_release_id=9001, media_condition="VG+")
    vinyl_sync._values()
    assert client.get(f"/api/vinyl/records/{rec['record_id']}").json()["value"] == 60
    calls = []
    monkeypatch.setattr(discogs, "price_suggestion", lambda rid: calls.append(rid) or {"VG+": (35.0, "USD")})
    vinyl_sync._values()                                         # checked today: not again
    assert calls == []
    assert client.post("/api/vinyl/values/check").status_code == 202      # now: every one
    r = client.get(f"/api/vinyl/records/{rec['record_id']}").json()
    assert calls == [9001] and r["value"] == 70 and len(r["values"]) == 1  # one a day in the history
    st = client.get("/api/vinyl/stats").json()
    assert st["value_by_month"][-1]["value"] == 70 and st["most_valuable"][0]["record_id"] == rec["record_id"]


def test_sync_failure_is_shown(client, dg, monkeypatch):
    def down():
        raise discogs.DiscogsError("Couldn't reach Discogs (ConnectError).")
    monkeypatch.setattr(discogs, "identity", down)
    client.post("/api/vinyl/discogs/sync")
    s = client.get("/api/vinyl/settings").json()
    assert s["sync"]["error"] == s["discogs"]["error"] == "Couldn't reach Discogs (ConnectError)."


# ---------------------------------------------------------------- plays and Last.fm
def test_plays_summary_pick_and_stats(client):
    a = add(client, title="Played", artist="A", genres=["Rock"], year=1975, price_paid="20")
    b = add(client, title="Dusty", artist="B", genres=["Jazz"], year=1962)
    r = client.post(f"/api/vinyl/records/{a['record_id']}/plays", json={"sides": "A, B", "note": "great"})
    assert r.status_code == 201 and r.json()["title"] == "Played" and "scrobbling" not in r.json()
    client.post(f"/api/vinyl/records/{a['record_id']}/plays", json={})
    s = client.get("/api/vinyl/summary").json()
    assert (s["owned"], s["plays_this_month"], s["spun_this_year"], s["paid"]) == (2, 2, 1, 20)
    assert s["now_spinning"]["title"] == "Played" and [d["title"] for d in s["dusty"]] == ["Dusty"]
    assert client.get("/api/vinyl/pick").json()["record_id"] == b["record_id"]          # never played comes first
    assert client.get(f"/api/vinyl/pick?skip={b['record_id']}").json()["record_id"] == a["record_id"]
    st = client.get("/api/vinyl/stats").json()
    assert st["most_played"][0]["plays"] == 2 and [d["decade"] for d in st["decades"]] == [1960, 1970]
    assert st["plays_by_month"][-1]["plays"] == 2 and len(st["plays_by_month"]) == 24 and st["facts"]["records"] == 2
    feed = client.get("/api/activity").json()
    assert any(x["kind"] == "record" and x["verb"] == "Played" and x["detail"] == "A · 2 times · side A, B" for x in feed)
    play_id = client.get(f"/api/vinyl/records/{a['record_id']}").json()["plays"][0]["play_id"]
    assert client.delete(f"/api/vinyl/plays/{play_id}").status_code == 204
    assert len(client.get("/api/vinyl/plays").json()) == 1


def test_scrobbles_the_sides_played(client, dg, monkeypatch):
    sent = []
    monkeypatch.setattr(lastfm, "scrobble", lambda key, tracks: sent.append((key, tracks)) or len(tracks))
    rec = add(client, discogs_release_id=9001)
    with __import__("app.db", fromlist=["db"]).db() as conn:
        conn.execute("UPDATE vinyl_settings SET lastfm_session = 'sk', lastfm_user = 'listener' WHERE id = 1")
    r = client.post(f"/api/vinyl/records/{rec['record_id']}/plays", json={"sides": "b"}).json()
    assert r["scrobbling"]
    key, tracks = sent[0]
    assert key == "sk" and [t["track"] for t in tracks] == ["Run-out", "Locked Groove"]
    assert tracks[1]["timestamp"] - tracks[0]["timestamp"] == 310 and tracks[0]["album"] == "Needle Drop"
    play = client.get(f"/api/vinyl/records/{rec['record_id']}").json()["plays"][0]
    assert play["scrobbled"] == 2 and play["scrobble_error"] is None
    client.post(f"/api/vinyl/records/{rec['record_id']}/plays", json={"scrobble": False})
    assert len(sent) == 1                                                            # you said not to
    old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    p = client.post(f"/api/vinyl/records/{rec['record_id']}/plays", json={"played_at": old}).json()
    again = client.post(f"/api/vinyl/plays/{p['play_id']}/scrobble").json()
    assert again["scrobble_error"] == "Last.fm only takes plays from the last 14 days."
    assert vinyl_sync.side_of("A1") == "A" and vinyl_sync.side_of("12") == "" and vinyl_sync._seconds("1:02:03") == 3723


def test_lastfm_connect(client, monkeypatch):
    r = client.post("/api/vinyl/lastfm/start")
    assert r.status_code == 502 and "LASTFM_API_KEY" in r.json()["detail"]           # not set up
    monkeypatch.setenv("LASTFM_API_KEY", "k")
    monkeypatch.setenv("LASTFM_API_SECRET", "s")
    asked = []

    def post(params):
        asked.append(params)
        return {"token": "tok"} if params["method"] == "auth.getToken" else {"session": {"name": "listener", "key": "sk"}}
    monkeypatch.setattr(lastfm, "_post", post)
    assert client.post("/api/vinyl/lastfm/finish").status_code == 409
    assert client.post("/api/vinyl/lastfm/start").json()["url"] == "https://www.last.fm/api/auth/?api_key=k&token=tok"
    s = client.post("/api/vinyl/lastfm/finish").json()["lastfm"]
    assert s == {"configured": True, "user": "listener", "connected": True, "waiting": False, "auto": True}
    assert "sk" not in str(client.get("/api/vinyl/settings").json())                 # the key stays on the server
    assert client.delete("/api/vinyl/lastfm").status_code == 204
    assert client.get("/api/vinyl/settings").json()["lastfm"]["connected"] is False


def test_lastfm_signature(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setenv("LASTFM_API_SECRET", "secret")
    s = lastfm._signed({"method": "auth.getSession", "token": "t"})
    import hashlib
    assert s["api_sig"] == hashlib.md5(b"api_keykeymethodauth.getSessiontokentsecret").hexdigest() and s["format"] == "json"


# ---------------------------------------------------------------- the rest of the app
def test_wishlist_journal_goals_value_report_export(client, dg):
    want = add(client, discogs_release_id=9004, status="Wanted")
    shops = {s["shop"]: s for s in client.get("/api/wanted").json()["shops"]}
    item = shops["Discogs"]["items"][0]
    assert (item["kind"], item["name"], item["price"]) == ("record", "Second Side", 25.0)
    got = client.post(f"/api/wanted/record/{want['record_id']}/got", json={"paid": "30", "shop": "Rocking Horse"}).json()
    assert got["name"] == "Second Side"
    r = client.get(f"/api/vinyl/records/{want['record_id']}").json()
    assert (r["status"], r["price_paid"], r["bought_from"]) == ("Owned", 30, "Rocking Horse")

    trip = client.post("/api/travel/trips", json={"name": "Patagonia"}).json()
    content = [{"type": "paragraph", "content": [
        {"type": "mention", "props": {"kind": "record", "ref": str(want["record_id"]), "label": "Second Side"}},
        {"type": "mention", "props": {"kind": "trip", "ref": str(trip["trip_id"]), "label": "Patagonia"}}]}]
    page = client.post("/api/journal", json={"title": "Listening", "content": content})
    assert page.status_code == 201, page.text                      # a trip mention used to break saving
    assert {(x["kind"], x["name"]) for x in page.json()["links"]} == {("record", "Second Side (The Stand-ins)"), ("trip", "Patagonia")}
    assert client.get(f"/api/journal?mention=record:{want['record_id']}").json()

    goal = client.post("/api/goals", json={"title": "Spin 2 records", "timeframe": "year", "source": "records_played", "target_value": 2})
    assert goal.status_code == 201, goal.text
    client.post(f"/api/vinyl/records/{want['record_id']}/plays", json={})
    assert client.get(f"/api/goals/{goal.json()['goal_id']}").json()["current_value"] == 1

    report = {s["title"]: s for s in client.get("/api/supplies/value-report").json()["sections"]}
    assert report["Records"]["total"] == 30 and report["Records"]["items"][0]["name"] == "The Stand-ins - Second Side"
    csv = client.get("/api/vinyl/export.csv")
    assert csv.status_code == 200 and "Second Side" in csv.text and "https://www.discogs.com/release/9004" in csv.text
    assert client.post("/api/calendar/parse", json={"text": "Record Store Day Sat 10am"}).json()["hobby"] == "vinyl"
