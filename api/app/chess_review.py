"""Chess game review (95_chess_review.sql): Stockfish looks at every position of one game, when you ask, and the review
is kept (chess_reviews) - one game at a time, never all of them in the background (user, 2026-11-15).

    POST   /chess/games/{id}/review      start one (?again=true redoes a finished one); answers with how far it is
    GET    /chess/games/{id}/review      how far it got, or the review: summary + every move
    DELETE /chess/games/{id}/review      forget it
    GET    /chess/reviews                what your reviewed games add up to (accuracy over time, kinds of moves, openings)

How a move is judged (the method of the two big sites, in the open):
  - Each position's engine eval (centipawns, White's view) becomes White's win chance with Lichess's published curve:
    win% = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)   (mates count as won / lost).
  - A move's cost is the win chance the mover lost (chess.com calls it "expected points": 1.00 = sure win).
    best = the engine's move; excellent <= 0.02; good <= 0.05; inaccuracy <= 0.10; mistake <= 0.20; blunder > 0.20.
    book = still on a known opening line (chess_openings.py); forced = the only legal move.
    miss = a mistake or blunder right after the opponent's own mistake (they gave you something; you gave it back).
    great = the best move (or as good) when the second-best would have cost 0.15+ (the only move that holds).
    brilliant = as good as the best, and it leaves a piece where it can be taken for less (a sound sacrifice), while
                not already completely winning.
  - Move accuracy (Lichess): 103.1668 * exp(-0.04354 * win% lost) - 3.1669. A side's accuracy: Lichess's mix of a
    volatility-weighted mean and the harmonic mean of its moves.
  - Game rating: a rough estimate from accuracy (2900 * accuracy^2.5) - chess.com's own formula isn't public.
"""
import logging
import math
import os
import queue
import threading
from io import StringIO

import chess
import chess.engine
import chess.pgn
from fastapi import APIRouter, HTTPException, Response
from psycopg.types.json import Jsonb

from . import chess_openings
from .db import db, found

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chess"])

ENGINE = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
DEPTH = int(os.environ.get("CHESS_REVIEW_DEPTH", "16"))     # ~0.5 s a position: a 40-move game in about a minute
THREADS = 2
RUN_INLINE = False                                          # tests: review at once instead of on the worker thread

VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
CLASSES = ["brilliant", "great", "best", "excellent", "good", "book", "forced", "inaccuracy", "mistake", "miss", "blunder"]
_jobs: "queue.Queue[int]" = queue.Queue()
_active: set[int] = set()                                  # queued or being reviewed (in this process)
_worker: list[threading.Thread] = []
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# The maths
# ---------------------------------------------------------------------------
def win_pct(cp: int | None, mate: int | None) -> float:
    """White's win chance (0-100) from White's eval."""
    if mate is not None:
        return 100.0 if mate > 0 else 0.0
    cp = max(-1000, min(1000, cp or 0))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def move_accuracy(before: float, after: float) -> float:
    """A move's accuracy from the mover's win chance before and after (Lichess)."""
    lost = max(0.0, before - after)
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * lost) - 3.1669))


def side_accuracy(accs: list[float], weights: list[float]) -> float | None:
    """Lichess: the mean of a volatility-weighted mean and the harmonic mean."""
    if not accs:
        return None
    weighted = sum(a * w for a, w in zip(accs, weights)) / sum(weights)
    harmonic = len(accs) / sum(1 / max(a, 1) for a in accs)
    return round((weighted + harmonic) / 2, 1)


def volatility(white_wins: list[float]) -> list[float]:
    """A weight per move: how much the game was swinging around it (the standard deviation of win% in a window)."""
    n = len(white_wins) - 1
    size = max(2, min(8, n // 10))
    out = []
    for i in range(n):
        window = white_wins[max(0, i - size + 1): i + 2]
        mean = sum(window) / len(window)
        sd = math.sqrt(sum((x - mean) ** 2 for x in window) / len(window))
        out.append(max(0.5, min(12.0, sd)))
    return out


def game_rating(accuracy: float | None) -> int | None:
    return None if accuracy is None else int(round(2900 * (accuracy / 100) ** 2.5, -1))


def hangs(board: chess.Board, square: int, mover: bool) -> bool:
    """Can the piece on `square` (the mover's, just moved) be taken for less than it's worth?"""
    piece = board.piece_at(square)
    if not piece or piece.piece_type in (chess.PAWN, chess.KING):
        return False
    takers = board.attackers(not mover, square)
    if not takers:
        return False
    cheapest = min(VALUE[board.piece_at(s).piece_type] for s in takers)
    return cheapest < VALUE[piece.piece_type] or not board.attackers(mover, square)


def phase_of(board: chess.Board, ply: int, book: bool) -> str:
    if book or ply < 16:
        return "opening"
    pieces = sum(VALUE[p.piece_type] for p in board.piece_map().values() if p.piece_type not in (chess.PAWN, chess.KING))
    return "endgame" if pieces <= 20 else "middlegame"


# ---------------------------------------------------------------------------
# Reviewing a game
# ---------------------------------------------------------------------------
def _eval(info) -> dict:
    s = info["score"].white()
    return {"mate": s.mate()} if s.is_mate() else {"cp": s.score()}


def _final_eval(board: chess.Board) -> dict | None:
    """A finished position: mate (the side to move is mated) or a draw."""
    if board.is_checkmate():
        return {"mate": -1 if board.turn == chess.WHITE else 1}       # (White's view: White mated = -1)
    if board.is_stalemate() or board.is_insufficient_material():
        return {"cp": 0}
    return None


def _line(board: chess.Board, pv: list[chess.Move], n: int = 8) -> list[str]:
    probe, out = board.copy(), []
    for m in pv[:n]:
        if m not in probe.legal_moves:
            break
        out.append(probe.san(m))
        probe.push(m)
    return out


def analyse(pgn: str, progress=lambda done, total: None, depth: int | None = None) -> dict:
    """Review a game: {summary, moves}. progress(done, total) is told after each position."""
    game = chess.pgn.read_game(StringIO(pgn))
    if game is None:
        raise ValueError("These moves couldn't be read.")
    if game.headers.get("Variant", "Standard").lower() not in ("standard", "chess"):
        raise ValueError("Only standard chess can be reviewed.")
    board = game.board()
    played = list(game.mainline_moves())
    if not played:
        raise ValueError("This game has no moves to review.")
    boards = [board.copy()]
    for m in played:
        board.push(m)
        boards.append(board.copy())

    evals, bests, seconds = [], [], []
    engine = chess.engine.SimpleEngine.popen_uci(ENGINE)
    try:
        engine.configure({"Threads": THREADS, "Hash": 64})
        for i, b in enumerate(boards):
            final = _final_eval(b)
            if final:
                evals.append(final)
                bests.append(None)
                seconds.append(None)
            else:
                infos = engine.analyse(b, chess.engine.Limit(depth=depth or DEPTH), multipv=2)
                evals.append(_eval(infos[0]))
                pv = infos[0].get("pv") or []
                bests.append({"move": pv[0], "line": _line(b, pv)} if pv else None)
                seconds.append(_eval(infos[1]) if len(infos) > 1 else None)
            progress(i + 1, len(boards))
        name = engine.id.get("name", "Stockfish")
    finally:
        engine.quit()

    white_wins = [win_pct(e.get("cp"), e.get("mate")) for e in evals]
    weights = volatility(white_wins)
    moves, book_so_far, left_book = [], True, None
    for i, m in enumerate(played):
        before_b, after_b = boards[i], boards[i + 1]
        white = before_b.turn == chess.WHITE
        mine = (lambda w: w) if white else (lambda w: 100 - w)
        wb, wa = mine(white_wins[i]), mine(white_wins[i + 1])
        loss = max(0.0, (wb - wa) / 100)
        best = bests[i]
        san = before_b.san(m)
        in_book = book_so_far and chess_openings.in_book(after_b)
        if book_so_far and not in_book:
            left_book = i
        book_so_far = in_book
        second = seconds[i]
        second_w = mine(win_pct(second.get("cp"), second.get("mate"))) if second else None
        if before_b.legal_moves.count() == 1:
            kind = "forced"
        elif in_book:
            kind = "book"
        elif best and m == best["move"]:
            kind = "best"
        elif loss <= 0.02:
            kind = "excellent"
        elif loss <= 0.05:
            kind = "good"
        elif loss <= 0.10:
            kind = "inaccuracy"
        elif loss <= 0.20:
            kind = "mistake"
        else:
            kind = "blunder"
        if kind in ("best", "excellent"):
            taken = before_b.piece_at(m.to_square)
            moved = before_b.piece_at(m.from_square)
            sacrifice = hangs(after_b, m.to_square, white) and (VALUE[taken.piece_type] if taken else 0) < VALUE[moved.piece_type]
            if sacrifice and wa >= 50 and wb < 95:
                kind = "brilliant"
            elif second_w is not None and wb - second_w >= 15 and wb < 95 and not (i and played[i - 1].to_square == m.to_square):
                kind = "great"                              # (taking back what was just taken isn't "great": it's obvious)
        if kind in ("mistake", "blunder") and moves and moves[-1]["loss"] >= 0.10:
            kind = "miss"
        moves.append({
            "ply": i + 1, "san": san, "uci": m.uci(), "colour": "white" if white else "black",
            "fen_before": before_b.fen(), "eval": evals[i + 1], "win_white": round(white_wins[i + 1], 1),
            "loss": round(loss, 3), "accuracy": round(move_accuracy(wb, wa), 1), "kind": kind,
            "best": best and before_b.san(best["move"]), "best_uci": best and best["move"].uci(),
            "best_line": best["line"] if best else [], "phase": phase_of(before_b, i, in_book),
        })

    opening = chess_openings.name_of(boards)
    deviation = None
    if left_book is not None:
        at = boards[left_book]
        deviation = {"ply": left_book + 1, "played": moves[left_book]["san"], "colour": moves[left_book]["colour"],
                     "theory": chess_openings.theory(at)[:6], "best": moves[left_book]["best"]}
    sides = {}
    for colour in ("white", "black"):
        own = [(mv, w) for mv, w in zip(moves, weights) if mv["colour"] == colour]
        acc = side_accuracy([mv["accuracy"] for mv, _ in own], [w for _, w in own])
        sides[colour] = {
            "accuracy": acc, "game_rating": game_rating(acc),
            "counts": {k: sum(1 for mv, _ in own if mv["kind"] == k) for k in CLASSES},
            "phases": {ph: side_accuracy([mv["accuracy"] for mv, _ in own if mv["phase"] == ph],
                                         [w for mv, w in own if mv["phase"] == ph]) for ph in ("opening", "middlegame", "endgame")},
        }
    swings = sorted((mv for mv in moves if mv["kind"] in ("brilliant", "great", "miss", "mistake", "blunder")),
                    key=lambda mv: -abs(mv["win_white"] - (moves[mv["ply"] - 2]["win_white"] if mv["ply"] > 1 else white_wins[0])))
    return {
        "engine": name,
        "summary": {"sides": sides, "opening": opening, "deviation": deviation, "start_win_white": round(white_wins[0], 1),
                    "key_moments": sorted(mv["ply"] for mv in swings[:5])},
        "moves": moves,
    }


def _review(game_id: int):
    """Review one game, saving how far it is as it goes."""
    try:
        with db() as conn:
            pgn = conn.execute("SELECT pgn FROM chess_games WHERE game_id = %s", (game_id,)).fetchone()["pgn"]

        def progress(done, total):
            if done % 4 == 0 or done == total:
                with db() as conn:
                    conn.execute("UPDATE chess_reviews SET done_plies = %s, total_plies = %s WHERE game_id = %s",
                                 (done, total, game_id))
        out = analyse(pgn, progress)
        with db() as conn:
            conn.execute("UPDATE chess_reviews SET status = 'done', engine = %s, depth = %s, summary = %s, moves = %s, "
                         "error = NULL, finished_at = now() WHERE game_id = %s",
                         (out["engine"], DEPTH, Jsonb(out["summary"]), Jsonb(out["moves"]), game_id))
    except Exception as e:  # noqa: BLE001 - whatever went wrong is the review's result
        log.exception("Chess review failed for game %s", game_id)
        with db() as conn:
            conn.execute("UPDATE chess_reviews SET status = 'failed', error = %s, finished_at = now() WHERE game_id = %s",
                         (str(e)[:300] or e.__class__.__name__, game_id))
    finally:
        _active.discard(game_id)


def _work():
    while True:
        _review(_jobs.get())


def _queue(game_id: int):
    _active.add(game_id)
    if RUN_INLINE:
        _review(game_id)
        return
    with _lock:
        if not _worker:
            _worker.append(threading.Thread(target=_work, daemon=True, name="chess-review"))
            _worker[0].start()
    _jobs.put(game_id)


def _status(conn, game_id: int) -> dict:
    found(conn.execute("SELECT 1 FROM chess_games WHERE game_id = %s", (game_id,)).fetchone(), "Game")
    row = conn.execute("SELECT * FROM chess_reviews WHERE game_id = %s", (game_id,)).fetchone()
    if not row:
        return {"status": "none"}
    if row["status"] == "running" and game_id not in _active:          # the app restarted part-way: start it again
        return {"status": "failed", "error": "It stopped part-way (the app restarted). Start it again."}
    return {k: row[k] for k in ("status", "done_plies", "total_plies", "engine", "depth", "summary", "moves", "error",
                                "started_at", "finished_at")}


@router.get("/chess/games/{game_id}/review")
def get_review(game_id: int):
    with db() as conn:
        return _status(conn, game_id)


@router.post("/chess/games/{game_id}/review", status_code=202)
def start_review(game_id: int, again: bool = False):
    with db() as conn:
        game = found(conn.execute("SELECT pgn, rules FROM chess_games WHERE game_id = %s", (game_id,)).fetchone(), "Game")
        if not game["pgn"]:
            raise HTTPException(422, "This game has no moves saved to review.")
        if game["rules"] != "chess":
            raise HTTPException(422, "Only standard chess can be reviewed.")
        now = _status(conn, game_id)
        if now["status"] == "running" or (now["status"] == "done" and not again):
            return now
        conn.execute("""
            INSERT INTO chess_reviews (game_id, status, done_plies, total_plies, started_at, finished_at, error)
            VALUES (%s, 'running', 0, 0, now(), NULL, NULL)
            ON CONFLICT (game_id) DO UPDATE SET status = 'running', done_plies = 0, total_plies = 0, started_at = now(),
                finished_at = NULL, error = NULL""", (game_id,))
    _queue(game_id)
    with db() as conn:
        return _status(conn, game_id)


@router.delete("/chess/games/{game_id}/review", status_code=204)
def delete_review(game_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM chess_reviews WHERE game_id = %s AND status <> 'running' RETURNING 1",
                           (game_id,)).fetchone(), "Review")
    return Response(status_code=204)


@router.get("/chess/reviews")
def reviews_overall():
    """Your reviewed games together: accuracy over time, how many of each kind of move per game, by opening, and the
    mistakes that keep coming back (the phase they happen in)."""
    with db() as conn:
        rows = conn.execute("""
            SELECT g.game_id, g.played_at, g.colour, g.result, g.time_class, g.opp_name, g.my_rating, g.opp_rating,
                   g.opening_family, r.summary
            FROM chess_reviews r JOIN chess_games g USING (game_id) WHERE r.status = 'done' ORDER BY g.played_at""").fetchall()
    games, totals, by_opening, by_phase = [], {k: 0 for k in CLASSES}, {}, {"opening": [], "middlegame": [], "endgame": []}
    for r in rows:
        me = r["summary"]["sides"][r["colour"]]
        them = r["summary"]["sides"]["black" if r["colour"] == "white" else "white"]
        games.append({"game_id": r["game_id"], "played_at": r["played_at"], "result": r["result"], "time_class": r["time_class"],
                      "opp_name": r["opp_name"], "accuracy": me["accuracy"], "opp_accuracy": them["accuracy"],
                      "game_rating": me["game_rating"], "my_rating": r["my_rating"], "opp_rating": r["opp_rating"],
                      "blunders": me["counts"]["blunder"], "mistakes": me["counts"]["mistake"] + me["counts"]["miss"]})
        for k in CLASSES:
            totals[k] += me["counts"].get(k, 0)
        name = (r["summary"].get("opening") or {}).get("name", "").split(":")[0] or r["opening_family"] or "Unknown"
        o = by_opening.setdefault(name, {"opening": name, "games": 0, "accuracy": [], "blunders": 0})
        o["games"] += 1
        o["blunders"] += me["counts"]["blunder"]
        if me["accuracy"] is not None:
            o["accuracy"].append(me["accuracy"])
        for ph, acc in me["phases"].items():
            if acc is not None:
                by_phase[ph].append(acc)
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None    # noqa: E731
    openings = sorted(({**o, "accuracy": avg(o["accuracy"])} for o in by_opening.values()), key=lambda o: -o["games"])
    return {"reviewed": len(games), "games": games, "kinds": totals, "openings": openings,
            "phases": {ph: avg(v) for ph, v in by_phase.items()},
            "accuracy": avg([g["accuracy"] for g in games if g["accuracy"] is not None])}
