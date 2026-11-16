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


# ---- clock stats, skills, lost-won games, endgame types, puzzles (chess_insights.py) ----
CLOCKED = ('[TimeControl "180+2"]\n\n1. e4 {[%clk 0:03:00]} e5 {[%clk 0:03:00]} 2. Bc4 {[%clk 0:02:58]} Nc6 {[%clk 0:00:09]} '
           '3. Qh5 {[%clk 0:02:50]} Nf6 {[%clk 0:00:08]} 4. Qxf7# {[%clk 0:02:49]} 1-0')


def test_clock_times_come_from_the_pgn():
    import chess.pgn
    from io import StringIO
    c = chess_review.clocks(chess.pgn.read_game(StringIO(CLOCKED)))
    assert c[0] == {"clock": 180.0, "spent": 2.0, "low": False}        # 180 - 180 + the 2 s bonus
    assert c[3]["spent"] == 173.0 and c[3]["low"] is True              # Black took 173 s, then had 9 s left (under 18 s)
    assert chess_review.clocks(chess.pgn.read_game(StringIO("1. e4 e5")))[0] is None
    assert chess_review.time_trouble_at(None) == 15 and chess_review.time_trouble_at(3600) == 120


def test_endgame_types():
    from app import chess_insights
    assert chess_insights.endgame_type("8/5pk1/8/8/8/8/5PK1/8 w - - 0 1") == "pawn"
    assert chess_insights.endgame_type("8/5pk1/8/8/8/8/5PK1/R3r3 w - - 0 1") == "rook"
    assert chess_insights.endgame_type("8/5pk1/8/8/8/8/5PK1/1B3n2 w - - 0 1") == "minor piece"
    assert chess_insights.endgame_type("8/5pk1/8/8/8/8/5PK1/Q3q3 w - - 0 1") == "queen"
    assert chess_insights.endgame_type("8/5pk1/8/8/8/8/5PK1/Q3r3 w - - 0 1") == "mixed"


def test_insights_clock_puzzles_and_lost_won(client, inline):
    assert client.get("/api/chess/insights").json()["skills"] == []
    gid = add(client, CLOCKED)
    client.post(f"/api/chess/games/{gid}/review")
    review = client.get(f"/api/chess/games/{gid}/review").json()
    assert review["moves"][3]["spent"] == 173.0 and review["moves"][3]["low"] is True
    ins = client.get("/api/chess/insights").json()
    assert ins["reviewed"] == 1 and {s["id"] for s in ins["skills"]} == {"openings", "tactics", "endgames", "converting", "resourcefulness"}
    assert ins["time"]["games"] == 1 and ins["time"]["bad_in_trouble"] == 1       # Black's 3...Nf6?? with 8 s left
    assert client.get("/api/chess/reviews").json()["time"]["bad_moves"] == 1
    # finishing the review made a puzzle of the blunder (you were Black)
    p = client.get("/api/chess/puzzles").json()
    assert p["total"] == 1 and p["new"] == 1 and p["cards"][0]["played_san"] == "Nf6" and p["cards"][0]["colour"] == "black"
    assert client.post("/api/chess/puzzles/sync").json() == {"added": 0}
    pid = p["cards"][0]["puzzle_id"]
    assert client.post(f"/api/chess/puzzles/{pid}/answer", json={"correct": True}).json()["reps"] == 1
    after = client.get("/api/chess/puzzles").json()
    assert after["new"] == 0 and after["due"] == 0 and after["cards"] == []        # right once: back tomorrow
    assert client.post(f"/api/chess/puzzles/{pid}/answer", json={"correct": False}).json()["lapses"] == 1
    assert client.post("/api/chess/puzzles/999999/answer", json={"correct": True}).status_code == 404


def test_lost_won_and_skills_from_made_up_reviews():
    from app import chess_insights
    moves = [{"ply": 1, "colour": "white", "win_white": 85, "loss": 0, "kind": "best", "san": "e4", "best": "e4", "phase": "opening"},
             {"ply": 2, "colour": "black", "win_white": 85, "loss": 0.3, "kind": "blunder", "san": "a6", "best": "d5", "phase": "opening"},
             {"ply": 3, "colour": "white", "win_white": 30, "loss": 0.55, "kind": "blunder", "san": "Qh5", "best": "d4", "phase": "middlegame"}]
    row = {"game_id": 1, "played_at": "2026-11-01", "colour": "white", "result": "loss", "how": "resigned", "opp_name": "X",
           "summary": {"start_win_white": 50, "sides": {"white": {"phases": {"opening": 90, "middlegame": 40, "endgame": None}},
                                                       "black": {"phases": {}}}},
           "moves": moves}
    lw = chess_insights.lost_won([row])
    assert lw[0]["ply"] == 3 and lw[0]["san"] == "Qh5" and lw[0]["peak"] == 85
    sk = {s["id"]: s for s in chess_insights.skill_scores([row])}
    assert sk["openings"]["score"] == 90 and sk["tactics"]["score"] == 0 and sk["converting"]["score"] == 0
    assert sk["endgames"]["score"] is None
