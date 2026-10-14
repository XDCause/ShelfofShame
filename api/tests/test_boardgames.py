"""Board games: the collection, plays, photos, and how they reach the journal and activity."""
import pytest

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


# Gameology's answers (made up, in the shape its store gives them): the search's products carry
# prices in dollars and the picture as an object; a product's .js has the price in cents.
CATAN = {"handle": "catan-6th-edition-base-game", "title": "CATAN 6th Edition Base Game", "type": "Board Games",
         "vendor": "Catan Studios", "price": "69.95", "available": True,
         "featured_image": {"url": "https://cdn.shopify.com/s/files/catan.jpg?v=1"},
         "tags": ["BGG Category: Economic", "BGG Category: Negotiation", "BGG Max Play Time: 120", "BGG Max Players: 4",
                  "BGG Mechanism: Dice Rolling", "BGG Mechanism: Trading", "BGG Min Age: 10", "BGG Min Play Time: 60",
                  "BGG Min Players: 3", "BGG Type: Family Games", "BGG Weight: 2.5", "BGG Weight: 2.50", "Kmart"]}
EXTENSION = {**CATAN, "handle": "catan-6th-edition-5-6-player-extension", "title": "CATAN 6th Edition 5-6 Player Extension",
             "tags": ["BGG Category: Expansion for Base-game", "BGG Min Players: 5", "BGG Max Players: 6", "BGG Weight: 0.25"]}
SLEEVES = {**CATAN, "handle": "card-sleeves", "title": "Catan Card Sleeves", "type": "Accessories", "tags": []}
RIVALS = {**CATAN, "handle": "rivals-for-catan", "title": "Rivals for Catan", "available": False}   # sold out


@pytest.fixture
def shop(monkeypatch):
    from app import gameology
    asked = []

    def get(path, params=None):
        asked.append((path, params))
        if path == "/search/suggest.json":
            return {"resources": {"results": {"products": [SLEEVES, EXTENSION, RIVALS, CATAN]}}}
        if path == f"/products/{CATAN['handle']}.js":
            return {**CATAN, "price": 6995, "featured_image": "//cdn.shopify.com/s/files/catan.jpg?v=1", "tags": CATAN["tags"]}
        return None
    monkeypatch.setattr(gameology, "_get", get)
    monkeypatch.setattr(gameology, "photo", lambda facts: (b"\xff\xd8catan", "image/jpeg"))
    return asked


def test_finding_a_game_at_gameology(client, shop):
    found = client.get("/api/board-games/lookup?q=catan").json()
    assert [g["handle"] for g in found] == [CATAN["handle"], EXTENSION["handle"], RIVALS["handle"]]   # no sleeves; sold out too
    assert found[2]["available"] is False
    catan = found[0]
    assert (catan["name"], catan["publisher"], catan["min_players"], catan["max_players"]) == ("Catan 6th Edition", "Catan Studios", 3, 4)
    assert (catan["play_minutes"], catan["min_play_minutes"], catan["min_age"], catan["weight"], catan["price"]) == (120, 60, 10, 2.5, 69.95)
    assert catan["categories"] == ["Economic", "Negotiation"] and catan["types"] == ["Family"]
    assert catan["image_url"] == "https://cdn.shopify.com/s/files/catan.jpg?v=1&width=200" and catan["game_id"] is None
    assert found[1]["weight"] is None and found[1]["expansion"]                  # 0.25 = not rated
    assert shop[0][1]["q"] == 'catan product_type:"Board Games"' and shop[0][1]["resources[options][fields]"] == "title,product_type"
    assert shop[0][1]["resources[options][unavailable_products]"] == "show"


def test_adding_a_game_from_gameology_fills_blanks_and_fetches_the_photo(client, shop):
    r = client.post("/api/board-games", json={"name": "Catan", "max_players": 4, "shop_handle": CATAN["handle"]})
    assert r.status_code == 201, r.text
    game = client.get(f"/api/board-games/{r.json()['game_id']}").json()
    assert (game["name"], game["min_players"], game["max_players"], game["min_age"]) == ("Catan", 3, 4, 10)   # yours kept
    assert (float(game["weight"]), float(game["shop_price"]), game["shop_url"]) == \
        (2.5, 69.95, "https://www.gameology.com.au/products/catan-6th-edition-base-game")
    assert game["categories"] == ["Economic", "Family", "Negotiation"] and game["mechanisms"] == ["Dice Rolling", "Trading"]
    assert game["has_photo"]                                                 # fetched after the reply
    assert client.get("/api/board-games/lookup?q=catan").json()[0]["game_id"] == game["game_id"]
    assert client.post("/api/board-games", json={"name": "X", "shop_handle": "gone-game"}).status_code == 404
    assert client.post("/api/board-games", json={"name": "X", "shop_handle": "../admin"}).status_code == 422


def test_filling_in_a_game_you_have(client, shop):
    game = client.post("/api/board-games", json={"name": "Settlers", "min_players": 5, "max_players": 5}).json()
    url = f"/api/board-games/{game['game_id']}/shop"
    filled = client.post(url, json={"shop_handle": CATAN["handle"]}).json()
    assert (filled["min_players"], filled["max_players"], filled["play_minutes"]) == (5, 5, 120)     # yours kept
    replaced = client.post(url, json={"shop_handle": CATAN["handle"], "replace": True}).json()
    assert (replaced["name"], replaced["min_players"], replaced["max_players"]) == ("Catan 6th Edition", 3, 4)
