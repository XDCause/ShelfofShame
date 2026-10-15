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


# What each product is, from the shop's "Board Game BEA" tag; a base game lists its expansions' handles.
TYPED = {
    "scythe": {"handle": "scythe", "title": "Scythe", "type": "Board Games", "vendor": "Stonemaier", "price": 11000,
               "tags": ["Board Game BEA: Base Game", "Expansion: scythe-invaders-from-afar", "BGG Min Players: 1"]},
    "scythe-invaders-from-afar": {"handle": "scythe-invaders-from-afar", "title": "Scythe Invaders from Afar",
                                  "type": "Board Games", "vendor": "Stonemaier", "price": 4500,
                                  "tags": ["Board Game BEA: Expansion"]},
    "scythe-metal-coins": {"handle": "scythe-metal-coins", "title": "Scythe Metal Coins", "type": "Board Games",
                           "vendor": "Stonemaier", "price": 3000, "tags": ["Board Game BEA: Board Game Accessorie"]},
    "flip-7": {"handle": "flip-7", "title": "Flip 7 With a Vengeance", "type": "Board Games", "vendor": "x", "price": 2000,
               "tags": ["Board Game BEA: Base Game"]},
}


@pytest.fixture
def typed_shop(monkeypatch):
    from app import gameology

    def get(path, params=None):
        handle = path.removeprefix("/products/").removesuffix(".js")
        return TYPED.get(handle)
    monkeypatch.setattr(gameology, "_get", get)
    monkeypatch.setattr(gameology, "photo", lambda facts: (None, None))


def test_kinds_from_the_shop_and_base_games(client, typed_shop):
    from app import gameology
    assert [gameology.kind_of(p["tags"]) for p in TYPED.values()] == ["game", "expansion", "other", "game"]
    assert gameology.kind_of(["BGG Category: Expansion for Base-game"]) == "expansion" and gameology.kind_of([]) is None
    # Added from the shop: the kind comes with it; the expansion finds its base game (the base lists it).
    scythe = client.post("/api/board-games", json={"name": "Scythe", "shop_handle": "scythe"}).json()
    afar = client.post("/api/board-games", json={"name": "Invaders from Afar", "shop_handle": "scythe-invaders-from-afar"}).json()
    assert (scythe["kind"], afar["kind"], afar["base_game_id"], afar["base_name"]) == ("game", "expansion", scythe["game_id"], "Scythe")
    # Added by name only: guessed from the name when the shop's check runs; the base by the name.
    coins = client.post("/api/board-games", json={"name": "Scythe Metal Coins"}).json()
    assert coins["kind"] == "game"
    client.patch(f"/api/board-games/{coins['game_id']}", json={"bgg_url": None})
    from app.db import db
    with db() as conn:
        conn.execute("UPDATE board_games SET shop_handle = 'scythe-metal-coins' WHERE game_id = %s", (coins["game_id"],))
    assert client.post("/api/board-games/check-types").status_code == 202        # background: done when it answers
    check = client.get("/api/board-games/check-types").json()
    assert (check["done"], check["total"], check["changed"], check["error"]) == (3, 3, 1, None)
    coins = client.get(f"/api/board-games/{coins['game_id']}").json()
    assert (coins["kind"], coins["base_name"]) == ("other", "Scythe")
    assert client.get(f"/api/board-games/{scythe['game_id']}").json()["add_ons"] == 2


def test_choosing_a_kind_and_base_by_hand(client):
    base = add_game(client, name="Catan")
    ext = add_game(client, name="Seafarers")
    r = client.patch(f"/api/board-games/{ext['game_id']}", json={"kind": "expansion", "base_game_id": base["game_id"]}).json()
    assert (r["kind"], r["base_name"]) == ("expansion", "Catan")
    assert client.patch(f"/api/board-games/{ext['game_id']}", json={"base_game_id": ext["game_id"]}).status_code == 422
    assert client.patch(f"/api/board-games/{base['game_id']}", json={"kind": "other", "base_game_id": ext["game_id"]}).status_code == 422
    assert client.patch(f"/api/board-games/{ext['game_id']}", json={"kind": "game"}).json()["base_game_id"] is None
    assert client.patch(f"/api/board-games/{ext['game_id']}", json={"kind": "board"}).status_code == 422
    assert client.patch(f"/api/board-games/{ext['game_id']}", json={"kind": None}).status_code == 422


def test_to_sell_is_still_yours(client):
    game = add_game(client, name="Old Favourite")
    r = client.patch(f"/api/board-games/{game['game_id']}", json={"status": "To sell"}).json()
    assert r["status"] == "To sell"
    s = client.get("/api/board-games/summary").json()
    assert (s["owned"], s["to_sell"]) == (1, 1)                                # still counts as owned until it's Gone
    assert "To sell" in client.get("/api/lookups").json()["game_statuses"]
    assert client.patch(f"/api/board-games/{game['game_id']}", json={"status": "Sold"}).status_code == 422


def test_a_base_game_turned_expansion_lets_go(client):
    base = add_game(client, name="Base")
    ext = add_game(client, name="Ext")
    client.patch(f"/api/board-games/{ext['game_id']}", json={"kind": "expansion", "base_game_id": base["game_id"]})
    client.patch(f"/api/board-games/{base['game_id']}", json={"kind": "expansion"})
    assert client.get(f"/api/board-games/{ext['game_id']}").json()["base_game_id"] is None
