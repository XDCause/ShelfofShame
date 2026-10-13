"""Volleyball: games and training with results, gear, video links, and the activity feed."""


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
