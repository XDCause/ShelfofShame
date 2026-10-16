"""Volleyball: games and training with results, gear, video links, and the activity feed."""
import pytest


def test_games_results_and_summary(client):
    r = client.post("/api/volleyball/games", json={"opponent": "Spikers", "team": "Net Gains", "sets_won": 3,
                                                   "sets_lost": 1, "venue": "Sports hall"})
    assert r.status_code == 201, r.text
    won = r.json()
    assert (won["result"], won["kind"]) == ("Won", "Game")
    client.post("/api/volleyball/games", json={"kind": "Training"})
    client.post("/api/volleyball/games", json={"opponent": "Blockheads", "sets_won": 0, "sets_lost": 3})
    summary = client.get("/api/volleyball/summary").json()
    assert (summary["games"], summary["trainings"], summary["won"], summary["lost"]) == (2, 1, 1, 1)
    assert client.post("/api/volleyball/games", json={"kind": "Scrimmage"}).status_code == 422
    assert client.patch(f"/api/volleyball/games/{won['game_id']}", json={"sets_lost": 3}).json()["result"] == "Drew"
    assert client.delete(f"/api/volleyball/games/{won['game_id']}").status_code == 204


def test_games_are_activity(client):
    client.post("/api/volleyball/games", json={"played_on": "2026-10-06", "opponent": "Spikers", "sets_won": 3,
                                               "sets_lost": 1, "venue": "Sports hall"})
    client.post("/api/volleyball/games", json={"played_on": "2026-10-08", "kind": "Training"})
    feed = [(f["verb"], f["title"], f["detail"]) for f in client.get("/api/activity").json()]
    assert feed == [("Trained", "Volleyball training", None),
                    ("Played", "Volleyball vs Spikers", "Won 3–1 · Sports hall")]


def test_gear_condition_order_and_photo(client):
    shoes = client.post("/api/gear", json={"name": "Court shoes", "kind": "Shoes", "condition": "Worn",
                                           "purchase_date": "2026-03-01", "price_paid": "180"}).json()
    client.post("/api/gear", json={"name": "Knee pads", "kind": "Knee pads", "condition": "Needs replacing"})
    client.post("/api/gear", json={"name": "Old ball", "condition": "Retired"})
    assert [g["name"] for g in client.get("/api/gear").json()] == ["Knee pads", "Court shoes", "Old ball"]
    assert client.patch(f"/api/gear/{shoes['gear_id']}", json={"condition": "Muddy"}).status_code == 422
    url = f"/api/gear/{shoes['gear_id']}/photo"
    assert client.put(url, content=b"GIF89a", headers={"Content-Type": "image/gif"}).status_code == 204
    assert client.get(f"/api/gear/{shoes['gear_id']}").json()["has_photo"]
    bought = [f for f in client.get("/api/activity").json() if f["kind"] == "gear"]
    assert [(f["verb"], f["title"], f["photo_url"].startswith(url)) for f in bought] == [("Bought", "Court shoes", True)]
    assert client.get("/api/volleyball/summary").json()["gear_to_replace"] == 1
    found = client.get("/api/journal/mentionable?q=shoe").json()
    assert {"kind": "gear", "id": shoes["gear_id"], "label": "Court shoes", "what": "Gear"} in found


def test_video_links(client):
    game = client.post("/api/volleyball/games", json={"opponent": "Spikers"}).json()
    r = client.post("/api/volleyball/videos", json={"title": "Final set", "url": "https://youtu.be/abc123",
                                                    "topic": "Highlights", "game_id": game["game_id"]})
    assert r.status_code == 201, r.text
    client.post("/api/volleyball/videos", json={"title": "Float serve drill", "url": "https://example.com/serve",
                                                "topic": "Serving"})
    assert client.post("/api/volleyball/videos", json={"title": "Bad", "url": "youtube"}).status_code == 422
    video_url = f"/api/volleyball/videos/{r.json()['video_id']}"
    assert client.patch(video_url, json={"url": "ftp://x"}).status_code == 422
    client.patch(video_url, json={"watched": True})
    assert [v["title"] for v in client.get("/api/volleyball/videos").json()] == ["Float serve drill", "Final set"]
    game = client.get(f"/api/volleyball/games/{game['game_id']}").json()
    assert [v["title"] for v in game["video_list"]] == ["Final set"]


def test_teams_and_what_a_new_game_starts_with(client):
    empty = client.get("/api/volleyball/teams").json()
    assert empty["teams"] == [] and empty["defaults"] == {"team_id": None, "venue": None, "kind": "Game"}
    nets = client.post("/api/volleyball/teams", json={"name": "Net Gains", "location": "Sports hall"}).json()
    sets = client.post("/api/volleyball/teams", json={"name": "Set Pieces", "location": "Beach courts",
                                                      "is_default": True}).json()
    assert client.post("/api/volleyball/teams", json={"name": "net gains"}).status_code == 409      # any case
    r = client.get("/api/volleyball/teams").json()
    assert [t["name"] for t in r["teams"]] == ["Set Pieces", "Net Gains"]                          # default first
    assert r["defaults"] == {"team_id": sets["team_id"], "venue": "Beach courts", "kind": "Game"}

    client.patch(f"/api/volleyball/teams/{nets['team_id']}", json={"is_default": True})            # takes it over
    teams = {t["name"]: t for t in client.get("/api/volleyball/teams").json()["teams"]}
    assert teams["Net Gains"]["is_default"] and not teams["Set Pieces"]["is_default"]

    game = client.post("/api/volleyball/games", json={"kind": "Social", "team_id": sets["team_id"],
                                                      "opponent": "Spikers", "venue": "Beach courts"}).json()
    assert (game["team"], game["team_location"]) == ("Set Pieces", "Beach courts")
    by_name = client.post("/api/volleyball/games", json={"team": "set pieces", "opponent": "Blockheads"}).json()
    assert by_name["team_id"] == sets["team_id"]                                                  # found, not added
    new = client.post("/api/volleyball/games", json={"team": "Mixed Bag"}).json()
    assert new["team"] == "Mixed Bag"                                                              # a new team
    assert client.post("/api/volleyball/games", json={"team_id": 9999}).status_code == 404

    r = client.get("/api/volleyball/teams").json()
    assert r["defaults"]["kind"] == "Game" and r["opponents"][:2] in (["Blockheads", "Spikers"], ["Spikers", "Blockheads"])
    assert "Beach courts" in r["venues"] and "Sports hall" in r["venues"]
    client.patch(f"/api/volleyball/teams/{nets['team_id']}", json={"retired": True})               # retired: not default
    r = client.get("/api/volleyball/teams").json()
    assert r["defaults"]["team_id"] == new["team_id"] and r["teams"][-1]["name"] == "Net Gains"   # latest game's team
    assert client.delete(f"/api/volleyball/teams/{sets['team_id']}").status_code == 409            # has games
    assert client.delete(f"/api/volleyball/teams/{nets['team_id']}").status_code == 204
    csv = client.get("/api/export/volleyball.csv").text
    assert "Set Pieces" in csv


def test_byes(client):
    win = client.post("/api/volleyball/games", json={"bye": "win", "opponent": "Nobody", "sets_won": 3}).json()
    assert (win["bye"], win["result"], win["opponent"], win["sets_won"]) == ("win", "Won", None, None)   # no sets on a bye
    none_ = client.post("/api/volleyball/games", json={"bye": "no result", "kind": "Tournament"}).json()
    assert (none_["bye"], none_["result"]) == ("no result", None)
    client.post("/api/volleyball/games", json={"opponent": "Spikers", "sets_won": 1, "sets_lost": 3})
    s = client.get("/api/volleyball/summary").json()
    assert (s["games"], s["won"], s["lost"], s["bye_wins"]) == (3, 1, 1, 1)
    assert client.post("/api/volleyball/games", json={"bye": "maybe"}).status_code == 422
    back = client.patch(f"/api/volleyball/games/{win['game_id']}", json={"bye": None, "opponent": "Spikers",
                                                                         "sets_won": 3, "sets_lost": 0}).json()
    assert (back["bye"], back["result"]) == (None, "Won")                   # played after all
    feed = {(f["verb"], f["title"], f["detail"]) for f in client.get("/api/activity").json() if f["kind"] == "volleyball"}
    assert ("Had", "Volleyball bye", "No result") in feed


MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64          # the start of an MP4 file


def test_uploading_a_video(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path))
    video = client.post("/api/volleyball/videos", json={"title": "Serving drill"}).json()
    assert (video["url"], video["file_url"]) == (None, None)                 # the file comes next
    url = f"/api/volleyball/videos/{video['video_id']}/file"
    r = client.put(url, content=MP4, headers={"content-type": "video/mp4", "x-file-name": "IMG%200042.MP4"})
    assert r.status_code == 200, r.text
    up = r.json()
    assert (up["file_type"], up["file_size"], up["original_name"]) == ("video/mp4", len(MP4), "IMG 0042.MP4")
    assert up["file_url"].startswith(url) and (tmp_path / "videos" / up["file_name"]).read_bytes() == MP4
    got = client.get(up["file_url"])
    assert got.content == MP4 and got.headers["content-type"] == "video/mp4"
    part = client.get(url, headers={"Range": "bytes=4-7"})                  # skipping around the video
    assert part.status_code == 206 and part.content == b"ftyp"

    first = up["file_name"]
    again = client.put(url, content=MP4 + b"more", headers={"content-type": "video/quicktime"}).json()
    assert again["file_name"].endswith(".mov") and not (tmp_path / "videos" / first).exists()   # the old one goes
    assert client.put(url, content=b"not a video", headers={"content-type": "video/mp4"}).status_code == 422
    assert client.put(url, content=MP4, headers={"content-type": "image/png"}).status_code == 415
    assert list((tmp_path / "videos").glob("*.part")) == []                 # nothing half-written left
    assert client.delete(f"/api/volleyball/videos/{video['video_id']}").status_code == 204
    assert list((tmp_path / "videos").iterdir()) == []                      # the file goes with it


def test_gear_you_want(client):
    client.post("/api/gear", json={"name": "Old shoes", "condition": "Retired"})
    client.post("/api/gear", json={"name": "Ball", "condition": "Good"})
    want = client.post("/api/gear", json={"name": "Mikasa V200W", "kind": "Ball", "condition": "Wanted"}).json()
    assert [g["name"] for g in client.get("/api/gear").json()] == ["Ball", "Mikasa V200W", "Old shoes"]   # in use, wanted, retired
    assert client.get("/api/volleyball/summary").json()["gear_wanted"] == 1
    # Bought: it's dated today (unless a date is given).
    from app.db import db
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"].isoformat()
    got = client.patch(f"/api/gear/{want['gear_id']}", json={"condition": "New", "purchase_date": None}).json()
    assert (got["condition"], got["purchase_date"]) == ("New", today)
    other = client.post("/api/gear", json={"name": "Sleeves", "condition": "Wanted"}).json()
    got = client.patch(f"/api/gear/{other['gear_id']}", json={"condition": "New", "purchase_date": "2026-01-02"}).json()
    assert got["purchase_date"] == "2026-01-02"
    assert client.post("/api/gear", json={"name": "X", "condition": "Desired"}).status_code == 422
    # Wanted = not bought yet: no date or price, even if sent (or left from before).
    w = client.post("/api/gear", json={"name": "Shoes", "condition": "Wanted", "purchase_date": "2026-01-01", "price_paid": "99"}).json()
    assert (w["purchase_date"], w["price_paid"]) == (None, None)
    back = client.patch(f"/api/gear/{got['gear_id']}", json={"condition": "Wanted"}).json()
    assert (back["purchase_date"], back["price_paid"]) == (None, None)


# Blue Sky Athletics' search (made-up products in its UCP layout): sizes are variants with a "Shoe size" option.
def bs_product(n, title, cents, sizes):
    return {"id": f"gid://shopify/Product/{n}", "title": title, "url": f"https://blueskyathletics.com.au/products/p{n}",
            "options": [{"name": "Shoe size", "values": [{"label": s} for s, _ in sizes]}],
            "media": [{"type": "image", "url": f"https://cdn.shopify.com/s/files/w{n}.jpg?v=1"}],
            "variants": [{"id": f"gid://shopify/ProductVariant/{n}{i}", "title": s, "price": {"amount": cents, "currency": "AUD"},
                          "availability": {"available": ok}, "options": [{"name": "Shoe size", "label": s}]}
                         for i, (s, ok) in enumerate(sizes)]}


BS = [bs_product(1, 'Way of Wade 12 "Avocado"', 28999, [("9", True), ("10", False), ("11", True)]),
      bs_product(2, 'Wade DLO 2 "Canvas"', 17999, [("10", False)])]


@pytest.fixture
def bluesky_shop(monkeypatch):
    from app import bluesky, gameology

    def call(tool, catalog):
        if tool == "get_product":
            n = catalog["id"].rsplit("/", 1)[-1]
            p = next((p for p in BS if p["id"].endswith("/" + n)), None)
            if not p:
                raise bluesky.ShopError("Blue Sky Athletics said no: Product not found.")
            return {"product": p}
        words = catalog["query"].lower().split()
        hits = [p for p in BS if all(w in p["title"].lower() for w in words)
                and any(v["availability"]["available"] for v in p["variants"]) == catalog["filters"]["available"]]
        return {"products": hits}
    monkeypatch.setattr(bluesky, "_call", call)
    monkeypatch.setattr(gameology, "photo", lambda game: (b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png"))


def test_way_of_wade_shoes_from_blue_sky(client, bluesky_shop):
    found = client.get("/api/gear/lookup?q=wade").json()
    assert [f["name"] for f in found] == ['Way of Wade 12 "Avocado"', 'Wade DLO 2 "Canvas"']      # in stock first
    avocado = found[0]
    assert (avocado["price"], avocado["sizes"], avocado["all_sizes"], avocado["kind"], avocado["brand"], avocado["gear_id"]) == \
        (289.99, ["9", "11"], ["9", "10", "11"], "Shoes", "Li-Ning Way of Wade", None)
    # Wanted from the shop: its facts, link, price and photo; nothing paid yet.
    want = client.post("/api/gear", json={"name": "", "condition": "Wanted", "shop_id": avocado["id"], "size": "10"}).json()
    assert (want["name"], want["kind"], want["brand"], want["shop_name"], float(want["shop_price"]), want["has_photo"], want["size"]) == \
        ('Way of Wade 12 "Avocado"', "Shoes", "Li-Ning Way of Wade", "Blue Sky Athletics", 289.99, True, "10")
    assert want["shop_url"] == "https://blueskyathletics.com.au/products/p1" and want["price_paid"] is None
    assert client.get("/api/gear/lookup?q=avocado").json()[0]["gear_id"] == want["gear_id"]
    # Gear you already had, linked to its product: your name stays, the link and price come.
    mine = client.post("/api/gear", json={"name": "My DLOs", "kind": "Shoes"}).json()
    linked = client.post(f"/api/gear/{mine['gear_id']}/shop", json={"shop_id": "2"}).json()
    assert (linked["name"], linked["shop_name"], float(linked["shop_price"])) == ("My DLOs", "Blue Sky Athletics", 179.99)
    assert client.post("/api/gear", json={"name": "X", "shop_id": "999"}).status_code == 404
    assert client.post("/api/gear", json={"name": "X", "shop_id": "abc"}).status_code == 422
