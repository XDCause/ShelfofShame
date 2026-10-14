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


# Wikidata's answer for Catan, one row per combination of values (as SPARQL gives it): two
# editions' player counts and years, a play time in hours, two designer properties.
E = "http://www.wikidata.org/entity/"
CATAN_ROWS = [
    {"g": E + "Q17271", "name": "The Settlers of Catan", "ordinal": "1", "bgg": "13", "min": "3", "max": "4",
     "time": "1.25", "unit": E + "Q25235", "date": "1995-01-01T00:00:00Z", "age": "10",
     "image": "http://commons.wikimedia.org/wiki/Special:FilePath/Catan%20box.jpg", "designer": "Klaus Teuber",
     "publisher": "Kosmos", "description": "board game"},
    {"g": E + "Q17271", "name": "The Settlers of Catan", "ordinal": "1", "bgg": "13", "min": "2", "max": "6",
     "date": "1996-05-01T00:00:00Z", "designer": "Klaus Teuber", "publisher": "Mayfair Games"},
    {"g": E + "Q28114052", "name": "Catan series", "ordinal": "0"},                      # nothing but a name
]


@pytest.fixture
def wd(monkeypatch):
    from app import wikidata
    asked = []
    monkeypatch.setattr(wikidata, "_query", lambda q: asked.append(q) or [r for r in CATAN_ROWS if "Q28114052" not in q or True])
    monkeypatch.setattr(wikidata, "photo", lambda facts: (b"\xff\xd8catan", "image/jpeg"))
    return asked


def test_finding_a_game_on_wikidata(client, wd):
    [catan] = client.get("/api/board-games/lookup?q=catan").json()          # the name-only series is left out
    assert (catan["wikidata_id"], catan["name"], catan["year"], catan["min_players"], catan["max_players"]) ==         ("Q17271", "The Settlers of Catan", 1995, 2, 6)                    # widest players, earliest year
    assert (catan["play_minutes"], catan["min_age"], catan["designer"], catan["bgg_id"]) == (75, 10, "Klaus Teuber", 13)
    assert catan["publisher"] == "Kosmos, Mayfair Games" and catan["image_url"].endswith("Catan%20box.jpg?width=300")
    assert catan["game_id"] is None
    assert 'mwapi:search "catan"' in wd[0]
    client.get('/api/board-games/lookup?q=say "hi"')                         # quotes can't break the query
    assert 'mwapi:search "say \\"hi\\""' in wd[-1]


def test_adding_a_game_from_wikidata_fills_blanks_and_fetches_the_photo(client, wd):
    r = client.post("/api/board-games", json={"name": "Catan", "max_players": 4, "wikidata_id": "Q17271"})
    assert r.status_code == 201, r.text
    game = client.get(f"/api/board-games/{r.json()['game_id']}").json()
    assert (game["name"], game["max_players"], game["min_players"]) == ("Catan", 4, 2)    # yours kept, blanks filled
    assert (game["bgg_url"], game["bgg_id"], game["designer"], game["wikidata_id"]) ==         ("https://boardgamegeek.com/boardgame/13", 13, "Klaus Teuber", "Q17271")
    assert game["has_photo"]                                                 # fetched after the reply
    assert client.get("/api/board-games/lookup?q=catan").json()[0]["game_id"] == game["game_id"]


def test_filling_in_a_game_you_have(client, wd):
    game = client.post("/api/board-games", json={"name": "Settlers", "min_players": 5, "max_players": 5}).json()
    url = f"/api/board-games/{game['game_id']}/wikidata"
    filled = client.post(url, json={"wikidata_id": "Q17271"}).json()
    assert (filled["min_players"], filled["max_players"], filled["year"]) == (5, 5, 1995)     # yours kept
    replaced = client.post(url, json={"wikidata_id": "Q17271", "replace": True}).json()
    assert (replaced["name"], replaced["min_players"], replaced["max_players"]) == ("The Settlers of Catan", 2, 6)
    assert client.post(url, json={"wikidata_id": "catan"}).status_code == 422
