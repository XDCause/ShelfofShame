"""Chess: chess.com games through the public API (faked here), the summary, ratings, filters,
openings, over-the-board games, and the activity feed / journal hooks."""
from datetime import datetime, timedelta, timezone

import pytest

from app import chesscom

# "Now" for the fake games: they're 2 h, 1 h and 30 min before it and must all fall on the same day in
# Brisbane (the database's time zone - activity groups a day's games). Before 3 am there, use 11 pm
# the night before instead (this test failed once at 1 am).
_BRISBANE = timezone(timedelta(hours=10))
_local = datetime.now(_BRISBANE)
NOW = (_local if _local.hour >= 3 else (_local - timedelta(days=1)).replace(hour=23, minute=0)).astimezone(timezone.utc)
THIS_MONTH = NOW.strftime("%Y-%m")
PGN = """[Event "Live Chess"]
[ECO "B90"]
[ECOUrl "https://www.chess.com/openings/Sicilian-Defense-Najdorf-Variation-6.Be3"]

1. e4 {[%clk 0:03:00]} 1... c5 {[%clk 0:03:00]} 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 1-0"""


def game(uuid, when, white, black, white_result, black_result, time_class="blitz", eco="Sicilian-Defense-Najdorf-Variation-6.Be3",
         accuracies=None, rules="chess"):
    return {"uuid": uuid, "url": f"https://www.chess.com/game/live/{uuid}", "end_time": int(when.timestamp()),
            "time_class": time_class, "time_control": "180+2", "rated": True, "rules": rules,
            "white": {"username": white[0], "rating": white[1], "result": white_result},
            "black": {"username": black[0], "rating": black[1], "result": black_result},
            "eco": f"https://www.chess.com/openings/{eco}", "pgn": PGN, **({"accuracies": accuracies} if accuracies else {})}


OLD = datetime(2020, 1, 15, tzinfo=timezone.utc)
MONTHS = {
    "2020-01": [game("a1", OLD, ("Me_Player", 1200), ("Bob", 1180), "win", "resigned"),
                game("a2", OLD + timedelta(hours=1), ("Ann", 1250), ("me_player", 1190), "win", "checkmated")],
    THIS_MONTH: [game("b1", NOW - timedelta(hours=2), ("me_player", 1210), ("Cat", 1230), "agreed", "agreed",
                      accuracies={"white": 81.2, "black": 79.5}),
                 game("b2", NOW - timedelta(hours=1), ("Dan", 1300), ("me_player", 1222), "resigned", "win",
                      eco="Caro-Kann-Defense-Advance-Variation-3...Bf5"),
                 game("b3", NOW - timedelta(minutes=30), ("me_player", 1500), ("Eve", 1500), "win", "timeout", time_class="rapid"),
                 game("x9", NOW, ("Someone", 1000), ("Else", 1000), "win", "resigned")],   # not my game
}
STATS = {"chess_blitz": {"last": {"rating": 1222}, "best": {"rating": 1300, "game": "https://x/best"},
                         "record": {"win": 2, "loss": 1, "draw": 1}},
         "chess_rapid": {"last": {"rating": 1500}, "record": {"win": 1, "loss": 0, "draw": 0}},
         "tactics": {"highest": {"rating": 1800}}, "puzzle_rush": {"best": {"score": 25}}}


@pytest.fixture
def fake(monkeypatch):
    asked = []
    monkeypatch.setattr(chesscom, "profile", lambda user: asked.append(("profile", user)) or (
        {"username": user, "name": "Me Myself", "avatar": "https://x/a.png", "url": "https://www.chess.com/member/me_player"}
        if user == "me_player" else (_ for _ in ()).throw(chesscom.NotFound("chess.com has no player by that name."))))
    monkeypatch.setattr(chesscom, "stats", lambda user: STATS)
    monkeypatch.setattr(chesscom, "archives", lambda user: list(MONTHS))
    monkeypatch.setattr(chesscom, "month", lambda user, ym: asked.append(("month", ym)) or MONTHS[ym])
    return asked


def connect(client):
    r = client.put("/api/chess/account", json={"username": "https://www.chess.com/member/Me_Player"})
    assert r.status_code == 200, r.text
    return r.json()


def test_reading_chess_com_helpers():
    assert chesscom.username_from("https://www.chess.com/member/Some_Player") == "some_player"
    assert chesscom.username_from("no spaces allowed") is None
    assert chesscom.opening_names("https://www.chess.com/openings/Sicilian-Defense-Najdorf-Variation-6.Be3") == \
        ("Sicilian Defense Najdorf Variation", "Sicilian Defense")
    assert chesscom.opening_names("https://www.chess.com/openings/Caro-Kann-Defense-Advance-Variation-3...Bf5") == \
        ("Caro Kann Defense Advance Variation", "Caro Kann Defense")
    assert chesscom.family_of("Italian Game Two Knights Defense") == "Italian Game"
    row = chesscom.game_row(MONTHS[THIS_MONTH][0], "me_player")
    assert (row["colour"], row["result"], row["how"], float(row["accuracy"]), row["moves"]) == ("white", "draw", "agreed", 81.2, 6)
    lost = chesscom.game_row(MONTHS["2020-01"][1], "me_player")
    assert (lost["colour"], lost["result"], lost["how"], lost["opp_name"]) == ("black", "loss", "checkmated", "Ann")
    assert chesscom.game_row(MONTHS[THIS_MONTH][3], "me_player") is None


def test_following_an_account_reads_every_month_once(client, fake):
    account = connect(client)
    assert (account["username"], account["name"]) == ("me_player", "Me Myself")
    assert [a[1] for a in fake if a[0] == "month"] == ["2020-01", THIS_MONTH]
    assert client.get("/api/chess/games").json()["total"] == 5                  # not the game I'm not in
    fake.clear()
    client.post("/api/chess/sync")
    assert [a[1] for a in fake if a[0] == "month"] == [THIS_MONTH]              # the past month is done
    client.post("/api/chess/sync?full=true")
    assert len([a for a in fake if a[0] == "month"]) == 3
    assert client.get("/api/chess/games").json()["total"] == 5                  # no doubles
    assert client.put("/api/chess/account", json={"username": "nobody"}).status_code == 422
    assert client.put("/api/chess/account", json={"username": "x y"}).status_code == 422


def test_the_summary_ratings_and_filters(client, fake):
    connect(client)
    s = client.get("/api/chess/summary").json()
    blitz = next(c for c in s["classes"] if c["time_class"] == "blitz")
    assert (s["main"], blitz["rating"], blitz["best"], blitz["games"]) == ("blitz", 1222, 1300, 4)
    assert blitz["week_change"] == 1222 - 1190                                   # last blitz rating before this week
    assert (s["week"]["games"], s["week"]["win"], s["week"]["draw"], s["week"]["loss"]) == (3, 2, 1, 0)
    assert s["puzzles"] == {"highest": 1800, "lowest": None, "rush_best": 25}
    ratings = client.get("/api/chess/ratings?days=5000").json()
    assert [r["rating"] for r in ratings["blitz"]][-1] == 1222 and len(ratings["rapid"]) == 1
    games = client.get("/api/chess/games?time_class=blitz").json()["games"]
    assert [g["rating_change"] for g in games] == [12, 20, -10, None]           # newest first, vs the game before
    assert client.get("/api/chess/games?result=loss").json()["total"] == 1
    assert client.get("/api/chess/games?q=caro").json()["total"] == 1
    one = client.get(f"/api/chess/games/{games[0]['game_id']}").json()
    assert one["pgn"].startswith("[Event") and one["opening_family"] == "Caro Kann Defense"


def test_openings_as_white_and_black(client, fake):
    connect(client)
    white = client.get("/api/chess/openings?colour=white").json()["openings"]
    sicilian = next(o for o in white if o["name"] == "Sicilian Defense")
    assert (sicilian["games"], sicilian["wins"], sicilian["draws"], float(sicilian["score"])) == (3, 2, 1, 83.3)
    assert sicilian["variations"][0]["name"] == "Sicilian Defense Najdorf Variation"
    black = client.get("/api/chess/openings?colour=black&time_class=blitz").json()["openings"]
    assert {o["name"]: (o["wins"], o["losses"]) for o in black} == {"Sicilian Defense": (0, 1), "Caro Kann Defense": (1, 0)}


def test_over_the_board_games(client, fake):
    r = client.post("/api/chess/games", json={"played_on": NOW.astimezone(_BRISBANE).date().isoformat(), "colour": "black", "opp_name": "  Club Champ ",
                                              "result": "draw", "event": "Club night", "opening": "French Defense Winawer"})
    assert r.status_code == 201, r.text
    g = r.json()
    assert (g["source"], g["opp_name"], g["time_class"], g["opening_family"]) == ("otb", "Club Champ", "classical", "French Defense")
    assert client.patch(f"/api/chess/games/{g['game_id']}", json={"result": "win"}).json()["result"] == "win"
    assert client.post("/api/chess/games", json={"played_on": "2026-01-01", "colour": "red", "opp_name": "X",
                                                 "result": "win"}).status_code == 422
    connect(client)
    online = client.get("/api/chess/games?source=chesscom").json()["games"][0]
    assert client.patch(f"/api/chess/games/{online['game_id']}", json={"result": "win"}).status_code == 409
    assert client.patch(f"/api/chess/games/{online['game_id']}", json={"notes": "Good game"}).json()["notes"] == "Good game"
    assert client.delete(f"/api/chess/games/{online['game_id']}").status_code == 409
    feed = [(f["title"], f["detail"]) for f in client.get("/api/activity?limit=50").json() if f["kind"] == "chess"]
    assert ("Chess vs Club Champ", "Won · Club night") in feed
    assert ("Blitz chess", "2 games · 1–0–1") in feed                              # one row a day per time control
    found = client.get("/api/journal/mentionable?q=champ").json()
    assert any(m["kind"] == "chess" and m["label"].startswith("Chess vs Club Champ") for m in found)
    assert client.delete(f"/api/chess/games/{g['game_id']}").status_code == 204
