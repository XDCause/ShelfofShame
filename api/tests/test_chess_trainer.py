"""The chess opening trainer: exploring a position (the Lichess explorer is faked - stand_ins' made-up answers), the
fall-back to the bundled opening list, your own games, building a repertoire, the drill and its scheduling, search."""
from datetime import datetime, timedelta, timezone

import pytest

from app import chess_trainer, lichess, stand_ins
from app.db import db

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture
def explorer(monkeypatch):
    """The explorer, faked: the stand-in's made-up counts. Returns the list of live requests made."""
    asked = []

    def fake(source, params):
        asked.append((source, params["fen"]))
        return stand_ins.lichess_explorer(source, params)
    monkeypatch.setattr(lichess, "_get", fake)
    return asked


@pytest.fixture
def offline(monkeypatch):
    def down(*_a, **_k):
        raise lichess.LichessError(lichess.UNREACHABLE)
    monkeypatch.setattr(lichess, "_get", down)


@pytest.fixture
def inline(monkeypatch):
    monkeypatch.setattr(chess_trainer, "RUN_INLINE", True)


class FakeEngine:
    """Stockfish, made up: top() says what the test gives it."""
    answers = []

    def __enter__(self):
        self.engine = object()
        return self

    def __exit__(self, *_):
        pass

    def top(self, board, n=3, depth=12):
        return FakeEngine.answers[:n]


def top(uci, san, cp):
    return {"uci": uci, "san": san, "cp": cp, "mate": None}


def add_game(colour, result, pgn, rating=1450):
    with db() as conn:
        conn.execute("""INSERT INTO chess_games (source, uuid, played_at, time_class, colour, my_rating, opp_name, result, pgn)
                        VALUES ('chesscom', %s, now(), 'blitz', %s, %s, 'Opp', %s, %s)""",
                     (f"t{abs(hash(pgn + colour))}", colour, rating, result, pgn))


# ---------------------------------------------------------------------------------------------
# Explore
# ---------------------------------------------------------------------------------------------
def test_explore_the_start(client, explorer):
    r = client.get("/api/chess/trainer/explore")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] is None and d["turn"] == "white" and d["explorer_error"] is None
    assert [m["san"] for m in d["lichess"]["moves"]][:2] == ["e4", "d4"]
    assert d["lichess"]["moves"][0]["theory"] is True
    assert d["masters"]["moves"] and d["lichess"]["moves"][0]["share"] > d["lichess"]["moves"][1]["share"]
    assert {t["san"] for t in d["theory"]} >= {"e4", "d4", "Nf3"}
    assert d["ratings"] == "1400,1600,1800" and d["my_rating"] is None        # no games yet: a wide band


def test_the_band_follows_your_rating_and_can_be_changed(client, explorer):
    add_game("white", "win", "1. e4 e5 *", rating=1450)
    assert client.get("/api/chess/trainer/explore").json()["ratings"] == "1400,1600"
    assert client.get("/api/chess/trainer/explore?ratings=2000,2200").json()["ratings"] == "2000,2200"
    assert client.get("/api/chess/trainer/explore?ratings=junk").status_code == 422


def test_each_position_is_asked_once(client, explorer):
    client.get("/api/chess/trainer/explore")
    assert len(explorer) == 2                                          # lichess + masters
    again = client.get("/api/chess/trainer/explore").json()
    assert len(explorer) == 2 and again["lichess"]["live"] is False     # from the cache (30 days)


def test_explore_by_moves_names_the_opening(client, explorer):
    d = client.get("/api/chess/trainer/explore", params={"moves": "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6"}).json()
    assert d["name"]["name"].startswith("Sicilian Defense") and "Najdorf" in d["name"]["name"]
    assert d["turn"] == "white" and len(d["moves"]) == 10
    assert client.get("/api/chess/trainer/explore", params={"moves": "e4 e4"}).status_code == 400
    assert client.get("/api/chess/trainer/explore", params={"fen": "not a fen"}).status_code == 400


def test_without_the_explorer_the_opening_list_still_answers(client, offline):
    d = client.get("/api/chess/trainer/explore", params={"moves": "e4 c5"}).json()
    assert "can't be reached" in d["explorer_error"]
    assert d["lichess"] is None and d["masters"] is None
    assert d["name"]["name"] == "Sicilian Defense" and "Nf3" in {t["san"] for t in d["theory"]}


def test_your_own_games_through_a_position(client, explorer):
    add_game("white", "win", "1. e4 c5 2. Nf3 d6 *")
    add_game("white", "loss", "1. e4 c5 2. Nc3 Nc6 *")
    add_game("black", "draw", "1. d4 d5 2. c4 e6 *")
    start = client.get("/api/chess/trainer/explore").json()["mine"]
    assert start["games"] == 3 and (start["wins"], start["draws"], start["losses"]) == (1, 1, 1)
    assert [(m["san"], m["mine"]) for m in start["moves"]][:1] == [("e4", True)] and start["moves"][0]["games"] == 2
    after_e4 = client.get("/api/chess/trainer/explore", params={"moves": "e4"}).json()["mine"]
    assert after_e4["games"] == 2 and after_e4["moves"][0]["san"] == "c5" and after_e4["moves"][0]["mine"] is False
    assert after_e4["moves"][0]["games"] == 2


def test_the_engine_only_when_asked(client, explorer, monkeypatch):
    monkeypatch.setattr(chess_trainer, "Engine", FakeEngine)
    FakeEngine.answers = [top("e2e4", "e4", 40), top("d2d4", "d4", 30)]
    assert client.get("/api/chess/trainer/explore").json()["engine"] is None
    d = client.get("/api/chess/trainer/explore?engine=true").json()
    assert [(e["san"], e["text"]) for e in d["engine"]] == [("e4", "+0.4"), ("d4", "+0.3")]


# ---------------------------------------------------------------------------------------------
# How to meet it
# ---------------------------------------------------------------------------------------------
def test_recommend_prefers_the_masters_move_unless_the_engine_calls_it_bad(client, explorer, monkeypatch):
    monkeypatch.setattr(chess_trainer, "Engine", FakeEngine)
    FakeEngine.answers = [top("d2d4", "d4", 30), top("e2e4", "e4", 10)]               # e4 is within 0.5 of the best
    m = client.get("/api/chess/trainer/recommend").json()["move"]
    assert (m["san"], m["why"], m["from"], m["to"]) == ("e4", "masters", "e2", "e4") and "engine agrees" in m["note"]
    # ... and here none of the masters' moves is anywhere near the engine's choice
    FakeEngine.answers = [top("b1c3", "Nc3", 300), top("e2e4", "e4", 10), top("d2d4", "d4", 20)]
    m = client.get("/api/chess/trainer/recommend").json()["move"]
    assert (m["san"], m["why"]) == ("Nc3", "engine") and m["text"] == "+3.0"


def test_recommend_without_the_explorer_or_engine_uses_theory(client, offline):
    m = client.get("/api/chess/trainer/recommend", params={"moves": "e4"}).json()["move"]
    assert m["why"] == "theory" and m["san"]


# ---------------------------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------------------------
def test_search_the_named_openings(client):
    r = client.get("/api/chess/trainer/search", params={"q": "sicilian najdorf"}).json()["openings"]
    assert r and all("najdorf" in o["name"].lower() and "sicilian" in o["name"].lower() for o in r)
    assert r[0]["moves"].startswith("e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6")
    first = client.get("/api/chess/trainer/search", params={"q": "italian"}).json()["openings"]
    assert first[0]["name"].startswith("Italian Game")
    assert client.get("/api/chess/trainer/search", params={"q": ""}).json() == {"openings": []}
    assert client.get("/api/chess/trainer/search", params={"q": "zzzzzz"}).json() == {"openings": []}


# ---------------------------------------------------------------------------------------------
# A repertoire
# ---------------------------------------------------------------------------------------------
def test_build_a_small_repertoire(client, explorer, inline):
    r = client.post("/api/chess/trainer/repertoires", json={"colour": "white", "moves": "e4 e5 Nf3"})
    assert r.status_code == 201
    rep = r.json()
    assert rep["name"].startswith("King's Knight Opening") or rep["name"]          # named from the opening list
    got = client.get(f"/api/chess/trainer/repertoires/{rep['repertoire_id']}").json()
    assert got["status"] == "ready" and got["progress"]["total"] == len(got["cards"]) >= 3
    first = got["cards"][0]
    assert (first["ply"], first["move_san"], first["why"], first["line"]) == (0, "e4", "opening", [])
    assert got["cards"][1]["line"] == ["e4", "e5"] and got["cards"][1]["move_san"] == "Nf3"
    assert any(c["why"] == "masters" for c in got["cards"])                      # beyond the opening: the masters' move
    assert len(explorer) <= chess_trainer.CALL_CAP
    # what the opponent plays is kept with how often (shares of 100) - beyond the line, 2-3 replies each
    drill = client.get("/api/chess/trainer/drill", params={"repertoire_id": rep["repertoire_id"], "mode": "learn"}).json()
    some = [v for v in drill["replies"].values() if len(v) > 1]
    assert some and all(abs(sum(o["share"] for o in v) - 100) < 1 for v in some) and all(len(v) <= 3 for v in some)


def test_a_build_asks_the_explorer_no_more_than_its_cap(client, explorer, inline, monkeypatch):
    monkeypatch.setattr(chess_trainer, "CALL_CAP", 4)
    client.post("/api/chess/trainer/repertoires", json={"colour": "black", "moves": "e4 c5"})
    assert len(explorer) == 4
    rep = client.get("/api/chess/trainer/repertoires").json()["repertoires"][0]
    assert rep["status"] == "ready" and rep["progress"]["total"] > 2          # (the rest came from theory and the cache)


def test_a_build_without_the_explorer_uses_the_opening_list(client, offline, inline):
    rep = client.post("/api/chess/trainer/repertoires", json={"colour": "black", "moves": "e4 c5"}).json()
    got = client.get(f"/api/chess/trainer/repertoires/{rep['repertoire_id']}").json()
    assert got["status"] == "ready" and "without the explorer" in got["notes"]
    assert [c["why"] for c in got["cards"]][0] == "opening" and got["progress"]["total"] >= 2


def test_a_repertoire_must_be_legal_and_new(client, explorer, inline):
    assert client.post("/api/chess/trainer/repertoires", json={"colour": "white", "moves": "e4 e4"}).status_code == 400
    assert client.post("/api/chess/trainer/repertoires", json={"colour": "green", "moves": "e4"}).status_code == 422
    assert client.post("/api/chess/trainer/repertoires", json={"colour": "white", "moves": "d4"}).status_code == 201
    assert client.post("/api/chess/trainer/repertoires", json={"colour": "white", "moves": "1. d4"}).status_code == 409
    assert client.post("/api/chess/trainer/repertoires", json={"colour": "black", "moves": "d4"}).status_code == 201


def test_an_interrupted_build_is_reported_not_stuck(client):
    with db() as conn:
        conn.execute("INSERT INTO chess_repertoire (name, colour, start_moves) VALUES ('Old', 'white', 'e4')")
    rep = client.get("/api/chess/trainer/repertoires").json()["repertoires"][0]
    assert rep["status"] == "failed" and "interrupted" in rep["error"]


def test_delete_a_repertoire_and_its_cards(client, explorer, inline):
    rid = client.post("/api/chess/trainer/repertoires", json={"colour": "white", "moves": "e4"}).json()["repertoire_id"]
    assert client.delete(f"/api/chess/trainer/repertoires/{rid}").status_code == 204
    assert client.get(f"/api/chess/trainer/repertoires/{rid}").status_code == 404
    with db() as conn:
        assert conn.execute("SELECT count(*) AS n FROM chess_drill_cards").fetchone()["n"] == 0
    assert client.delete(f"/api/chess/trainer/repertoires/{rid}").status_code == 404


# ---------------------------------------------------------------------------------------------
# The drill
# ---------------------------------------------------------------------------------------------
def make_card(client, explorer, inline):
    rid = client.post("/api/chess/trainer/repertoires", json={"colour": "white", "moves": "e4"}).json()["repertoire_id"]
    cards = client.get("/api/chess/trainer/drill", params={"repertoire_id": rid, "mode": "learn"}).json()["cards"]
    return rid, cards


def card_row(card_id):
    with db() as conn:
        return conn.execute("SELECT * FROM chess_drill_cards WHERE card_id = %s", (card_id,)).fetchone()


def test_new_cards_are_learned_first_and_reading_them_changes_nothing(client, explorer, inline):
    rid, cards = make_card(client, explorer, inline)
    assert cards and cards[0]["ply"] == 0 and cards[0]["colour"] == "white"
    assert client.get("/api/chess/trainer/drill", params={"repertoire_id": rid, "mode": "review"}).json()["cards"] == []
    again = client.get("/api/chess/trainer/drill", params={"repertoire_id": rid, "mode": "learn"}).json()["cards"]
    assert [c["card_id"] for c in again] == [c["card_id"] for c in cards]               # (a GET doesn't use them up)
    assert client.get("/api/chess/trainer/drill", params={"mode": "nonsense"}).status_code == 422


def test_right_answers_space_the_card_out(client, explorer, inline):
    rid, cards = make_card(client, explorer, inline)
    cid = cards[0]["card_id"]
    a = client.post(f"/api/chess/trainer/cards/{cid}/answer", json={"correct": True}).json()
    assert (a["reps"], a["interval_days"], a["ease"]) == (1, 1.0, 2.5)
    due = datetime.fromisoformat(a["due_at"])
    assert timedelta(hours=23) < due - datetime.now(timezone.utc) < timedelta(hours=25)
    assert a["progress"]["new"] == a["progress"]["total"] - 1 and a["progress"]["learned"] == 0     # (the drill page holds 20 at most)
    assert all(c["card_id"] != cid for c in client.get("/api/chess/trainer/drill", params={"repertoire_id": rid, "mode": "learn"}).json()["cards"])
    b = client.post(f"/api/chess/trainer/cards/{cid}/answer", json={"correct": True}).json()
    assert (b["reps"], b["interval_days"]) == (2, 6.0) and b["progress"]["learned"] == 1
    c = client.post(f"/api/chess/trainer/cards/{cid}/answer", json={"correct": True}).json()
    assert (c["reps"], c["interval_days"]) == (3, 15.0)


def test_a_wrong_answer_brings_it_back_soon(client, explorer, inline):
    rid, cards = make_card(client, explorer, inline)
    cid = cards[0]["card_id"]
    for _ in range(2):
        client.post(f"/api/chess/trainer/cards/{cid}/answer", json={"correct": True})
    w = client.post(f"/api/chess/trainer/cards/{cid}/answer", json={"correct": False, "played": "d4"}).json()
    assert (w["reps"], w["interval_days"], w["lapses"], w["ease"], w["last_result"]) == (0, 1.0, 1, 2.3, "wrong")
    assert datetime.fromisoformat(w["due_at"]) - datetime.now(timezone.utc) < timedelta(minutes=11)
    assert w["progress"]["learned"] == 0
    with db() as conn:                                               # time passes: it's due, in the review
        conn.execute("UPDATE chess_drill_cards SET due_at = now() - interval '1 hour' WHERE card_id = %s", (cid,))
    due = client.get("/api/chess/trainer/drill", params={"repertoire_id": rid, "mode": "review"}).json()
    assert [c["card_id"] for c in due["cards"]] == [cid] and due["progress"]["due"] == 1
    assert client.post("/api/chess/trainer/cards/999999/answer", json={"correct": True}).status_code == 404


def test_schedule_never_lets_the_ease_drop_under_1_3():
    card = {"interval_days": 6, "ease": 1.4, "reps": 2, "lapses": 0}
    new = chess_trainer.schedule(card, False, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert new["ease"] == 1.3 and new["due_at"] == datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)
    assert chess_trainer.schedule({**card, "reps": 3, "interval_days": 15, "ease": 1.3}, True)["interval_days"] == 19.5
