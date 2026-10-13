"""Board games: the collection, plays, photos, and how they reach the journal and activity."""
from .test_journal import mention, paragraph, text


def add_game(client, **overrides):
    body = {"name": "Catan", "publisher": "Kosmos", "min_players": 3, "max_players": 4, "play_minutes": 90}
    body.update(overrides)
    r = client.post("/api/board-games", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_adding_editing_and_listing_games(client):
    catan = add_game(client)
    add_game(client, name="Wingspan", status="Wanted", publisher="  ")
    assert (catan["status"], catan["plays"], catan["has_photo"]) == ("Owned", 0, False)
    games = client.get("/api/board-games").json()
    assert [g["name"] for g in games] == ["Catan", "Wingspan"]                 # owned first
    assert games[1]["publisher"] is None                                       # blank = not set
    url = f"/api/board-games/{catan['game_id']}"
    assert client.patch(url, json={"min_players": 5}).status_code == 422       # more than max 4
    assert client.patch(url, json={"rating": 8}).json()["rating"] == 8
    assert client.post("/api/board-games", json={"name": "Bad", "status": "Lent out"}).status_code == 422


def test_plays_count_and_summary(client):
    catan = add_game(client)
    for day, winner in (("2026-10-01", "Sam"), ("2026-10-08", "Me")):
        r = client.post(f"/api/board-games/{catan['game_id']}/plays",
                        json={"played_on": day, "players": "Sam, Jo, Me", "winner": winner, "minutes": 80})
        assert r.status_code == 201, r.text
    game = client.get(f"/api/board-games/{catan['game_id']}").json()
    assert (game["plays"], game["last_played"]) == (2, "2026-10-08")
    assert [p["winner"] for p in game["play_log"]] == ["Me", "Sam"]
    play_id = game["play_log"][0]["play_id"]
    assert client.patch(f"/api/board-game-plays/{play_id}", json={"winner": "Jo"}).json()["winner"] == "Jo"
    summary = client.get("/api/board-games/summary").json()
    assert (summary["owned"], summary["plays"], summary["most_played"]["name"]) == (1, 2, "Catan")
    assert [p["game_name"] for p in client.get("/api/board-games/plays").json()] == ["Catan", "Catan"]
    assert client.delete(f"/api/board-game-plays/{play_id}").status_code == 204
    assert client.get(f"/api/board-games/{catan['game_id']}").json()["plays"] == 1


def test_a_game_photo(client):
    catan = add_game(client)
    url = f"/api/board-games/{catan['game_id']}/photo"
    assert client.get(url).status_code == 404
    assert client.put(url, content=b"\xff\xd8box", headers={"Content-Type": "image/jpeg"}).status_code == 204
    game = client.get(f"/api/board-games/{catan['game_id']}").json()
    assert game["has_photo"] and game["photo_url"].startswith(url)
    assert client.get(url).content == b"\xff\xd8box"
    assert client.delete(url).status_code == 204


def test_plays_are_activity_and_the_journal_offers_to_log_one(client):
    catan = add_game(client)
    page = client.post("/api/journal", json={"title": "Games night", "entry_date": "2026-10-10", "content": [paragraph(
        text("Played "), mention("game", catan["game_id"], "Catan"), text(" with Sam and Jo"))]}).json()
    [s] = page["suggestions"]
    assert (s["kind"], s["name"], s["label"]) == ("game", "Catan", "Log a play")
    page = client.post(f"/api/journal/{page['page_id']}/suggestions/apply", json={"key": s["key"]}).json()
    assert page["suggestions"] == []                                     # that day's play is logged
    [play] = client.get(f"/api/board-games/{catan['game_id']}").json()["play_log"]
    assert (play["played_on"], play["notes"]) == ("2026-10-10", "From the journal: Games night")
    assert {"kind": "game", "id": catan["game_id"], "name": "Catan"} in page["links"]
    played = [f for f in client.get("/api/activity").json() if f["verb"] == "Played"]
    assert [(f["kind"], f["title"], f["day"]) for f in played] == [("game", "Catan", "2026-10-10")]
    found = client.get("/api/journal/mentionable?q=cat").json()
    assert {"kind": "game", "id": catan["game_id"], "label": "Catan", "what": "Board game"} in found


def test_deleting_a_game_removes_its_plays(client):
    catan = add_game(client)
    client.post(f"/api/board-games/{catan['game_id']}/plays", json={})
    assert client.delete(f"/api/board-games/{catan['game_id']}").status_code == 204
    assert client.get("/api/board-games/plays").json() == []
    assert client.get(f"/api/board-games/{catan['game_id']}").status_code == 404


def test_pages_about_a_game(client):
    catan = add_game(client)
    client.post("/api/journal", json={"title": "Night in", "content": [paragraph(
        text("Taught "), mention("game", catan["game_id"], "Catan"))]})
    pages = client.get(f"/api/journal?mention=game:{catan['game_id']}").json()
    assert [p["title"] for p in pages] == ["Night in"]
