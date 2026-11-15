"""Chess game review: Stockfish judges every move of one game, when asked (chess_review.py), and the review is kept.
Runs the real engine (it's in the API's image) at a low depth so the tests stay quick."""
import pytest

from app import chess_openings, chess_review

# A miniature: Black's 3...Nf6?? lets 4.Qxf7 mate (the Scholar's Mate). Italian Game moves first, so it's named.
SCHOLAR = "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0"


@pytest.fixture
def inline(monkeypatch):
    monkeypatch.setattr(chess_review, "RUN_INLINE", True)
    monkeypatch.setattr(chess_review, "DEPTH", 8)


def add(client, pgn=SCHOLAR, colour="black", result="loss"):
    r = client.post("/api/chess/games", json={"played_on": "2026-11-01", "colour": colour, "opp_name": "Club Champ",
                                              "result": result, "my_rating": 900, "opp_rating": 1100, "pgn": pgn})
    assert r.status_code == 201, r.text
    return r.json()["game_id"]


def test_the_maths():
    assert chess_review.win_pct(0, None) == 50
    assert chess_review.win_pct(None, 3) == 100 and chess_review.win_pct(None, -2) == 0
    assert 74 < chess_review.win_pct(300, None) < 76                       # +3 is about 75% for White
    assert chess_review.win_pct(5000, None) == chess_review.win_pct(1000, None)   # (capped at +10)
    assert chess_review.move_accuracy(60, 60) == pytest.approx(100, abs=0.01)
    assert 63 < chess_review.move_accuracy(60, 50) < 65                     # losing 10% of your chances: ~64% accurate
    assert chess_review.side_accuracy([], []) is None
    assert chess_review.game_rating(90) == 2230


def test_reviewing_a_game_finds_the_blunder_and_the_mate(client, inline):
    gid = add(client)
    assert client.get(f"/api/chess/games/{gid}/review").json() == {"status": "none"}
    r = client.post(f"/api/chess/games/{gid}/review")
    assert r.status_code == 202, r.text
    review = client.get(f"/api/chess/games/{gid}/review").json()
    assert review["status"] == "done", review
    moves = {m["san"]: m for m in review["moves"]}
    assert moves["Nf6"]["kind"] == "blunder" and moves["Nf6"]["best"] in ("g6", "Qe7", "Qf6", "Nh6")
    assert moves["Qxf7#"]["kind"] == "best"
    assert moves["e4"]["kind"] == "book"
    assert moves["Qxf7#"]["eval"] == {"mate": 0} or moves["Qxf7#"]["win_white"] == 100
    s = review["summary"]
    assert s["sides"]["black"]["counts"]["blunder"] == 1
    assert s["sides"]["white"]["accuracy"] > s["sides"]["black"]["accuracy"]
    assert s["opening"]["name"].startswith(("Italian", "Bishop's Opening", "King's Pawn", "Scholar"))
    assert s["deviation"]["ply"] >= 3
    # kept: asking again doesn't redo it, unless again=true
    assert client.post(f"/api/chess/games/{gid}/review").json()["finished_at"] == review["finished_at"]
    overall = client.get("/api/chess/reviews").json()
    assert overall["reviewed"] == 1 and overall["kinds"]["blunder"] == 1 and overall["games"][0]["accuracy"] is not None
    assert client.delete(f"/api/chess/games/{gid}/review").status_code == 204
    assert client.get(f"/api/chess/games/{gid}/review").json()["status"] == "none"


def test_what_cant_be_reviewed(client, inline):
    nothing = client.post("/api/chess/games", json={"played_on": "2026-11-01", "colour": "white", "opp_name": "X", "result": "win"}).json()
    assert client.post(f"/api/chess/games/{nothing['game_id']}/review").status_code == 422      # no moves
    assert client.post("/api/chess/games/999999/review").status_code == 404
    bad = add(client, pgn="1. e4 e5 2. Ke3 Ke6 3. Qxx9")                                      # moves that can't be read
    client.post(f"/api/chess/games/{bad}/review")
    r = client.get(f"/api/chess/games/{bad}/review").json()
    assert r["status"] in ("done", "failed")                                               # (read up to the bad move, or refused)


def test_a_review_stopped_by_a_restart_can_be_started_again(client, inline):
    gid = add(client)
    from app.db import db
    with db() as conn:
        conn.execute("INSERT INTO chess_reviews (game_id, status) VALUES (%s, 'running')", (gid,))
    r = client.get(f"/api/chess/games/{gid}/review").json()
    assert r["status"] == "failed" and "again" in r["error"]
    assert client.post(f"/api/chess/games/{gid}/review").json()["status"] == "done"


def test_opening_theory():
    import chess
    b = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bc4"):
        b.push_san(san)
    assert chess_openings.named(b)["name"].startswith("Italian Game")
    assert chess_openings.in_book(b)
    assert {"Bc5", "Nf6"} <= {t["san"] for t in chess_openings.theory(b)}
    b.push_san("Ke7")                                     # (a king walk no opening is named after)
    assert not chess_openings.named(b) and not chess_openings.in_book(b)
