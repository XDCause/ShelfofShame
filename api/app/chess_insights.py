"""What your reviewed games say about you (A02_chess_sudoku_extras.sql). Everything here is read from the reviews that
chess_review.py keeps - no new engine work, no other players' numbers (only your own history).

    GET  /chess/insights            skill scores, "lost a won position" games, endgames by type, clock stats
    GET  /chess/puzzles             your puzzles: counts + the ones to do now (due first, then new)
    POST /chess/puzzles/sync        look through your reviews for new puzzles (they're also added when a review finishes)
    POST /chess/puzzles/{id}/answer right or wrong: the next time it comes back (the opening trainer's scheduler)

Puzzles: every move of yours the review called a mistake, miss or blunder, with the position BEFORE it and the engine's
move. Scheduling is chess_trainer.schedule (SM-2, the way Anki does it).
"""
import chess
from fastapi import APIRouter
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from . import chess_review, chess_trainer
from .db import db, found

router = APIRouter(prefix="/api", tags=["chess"])

BAD = ("mistake", "miss", "blunder")
SLIPS = ("inaccuracy", "mistake", "miss", "blunder")
PHASES = ("opening", "middlegame", "endgame")
RECENT = 10                                    # "lately" = your last ten reviewed games
AHEAD, WON, BEHIND = 70, 80, 30                # win chances (%) that count as ahead / a won position / behind


# ---------------------------------------------------------------------------
# Reading a review from your side
# ---------------------------------------------------------------------------
def _rows(conn) -> list[dict]:
    return conn.execute("""
        SELECT g.game_id, g.played_at, g.colour, g.result, g.how, g.opp_name, g.time_class, g.pgn, r.summary, r.moves
        FROM chess_reviews r JOIN chess_games g USING (game_id) WHERE r.status = 'done' ORDER BY g.played_at""").fetchall()


def my_chances(row: dict) -> list[float]:
    """Your win chance (0-100) at the start and after every move."""
    flip = row["colour"] == "black"
    return [(100 - w if flip else w) for w in [row["summary"]["start_win_white"]] + [m["win_white"] for m in row["moves"]]]


def endgame_type(fen: str) -> str:
    """The kind of endgame by the pieces left (not counting pawns and kings)."""
    kinds = {p.piece_type for p in chess.Board(fen).piece_map().values()} - {chess.PAWN, chess.KING}
    if not kinds:
        return "pawn"
    if kinds == {chess.ROOK}:
        return "rook"
    if kinds <= {chess.KNIGHT, chess.BISHOP}:
        return "minor piece"
    if kinds == {chess.QUEEN}:
        return "queen"
    return "mixed"


def endgame_of(row: dict) -> str | None:
    """The type when the endgame phase began (None if the game never got there)."""
    start = next((m for m in row["moves"] if m["phase"] == "endgame"), None)
    return endgame_type(start["fen_before"]) if start else None


def score_of(result: str) -> float:
    return 100.0 if result == "win" else 50.0 if result == "draw" else 0.0


def game_skills(row: dict) -> dict:
    """{skill: (value 0-100, weight)} for the skills this game says something about."""
    me = row["colour"]
    mine = row["summary"]["sides"][me]["phases"]
    moves, out = row["moves"], {}
    if mine.get("opening") is not None:
        out["openings"] = (mine["opening"], 1)
    if mine.get("endgame") is not None:
        out["endgames"] = (mine["endgame"], 1)
    chances = my_chances(row)
    given = punished = 0
    for i, m in enumerate(moves[:-1]):
        if m["colour"] != me and m["kind"] in BAD:             # they went wrong: did you take advantage?
            given += 1
            nxt = moves[i + 1]
            punished += nxt["kind"] not in SLIPS and nxt["loss"] <= 0.05
    if given:
        out["tactics"] = (100.0 * punished / given, given)
    if max(chances) >= AHEAD:
        out["converting"] = (score_of(row["result"]), 1)
    if min(chances) <= BEHIND:
        out["resourcefulness"] = (score_of(row["result"]), 1)
    return out


SKILLS = [("openings", "Openings", "Accuracy in the opening phase."),
          ("tactics", "Tactics", "How often you punished an opponent's mistake with a good move."),
          ("endgames", "Endgames", "Accuracy once the endgame began."),
          ("converting", "Converting", "Points won from games where you were clearly ahead."),
          ("resourcefulness", "Resourcefulness", "Points saved from games where you were clearly behind.")]


def skill_scores(rows: list[dict]) -> list[dict]:
    """Each skill over all your reviewed games and over the last ten, so you see it against your own history."""
    per_game = [game_skills(r) for r in rows]

    def mean(games, key):
        pts = [g[key] for g in games if key in g]
        w = sum(x[1] for x in pts)
        return {"score": round(sum(x[0] * x[1] for x in pts) / w, 1), "games": len(pts)} if w else None
    out = []
    for key, label, how in SKILLS:
        recent, before = mean(per_game[-RECENT:], key), mean(per_game[:-RECENT], key)
        allg = mean(per_game, key)
        out.append({"id": key, "label": label, "how": how, "score": allg and allg["score"], "games": allg["games"] if allg else 0,
                    "recent": recent and recent["score"], "before": before and before["score"]})
    return out


def lost_won(rows: list[dict]) -> list[dict]:
    """Games where you reached a won position (80%+) and didn't win - newest first - with the move where it slipped."""
    out = []
    for r in rows:
        chances = my_chances(r)
        first = next((i for i, c in enumerate(chances) if c >= WON), None)
        if first is None or r["result"] == "win":
            continue
        mine = [m for m in r["moves"] if m["colour"] == r["colour"] and m["ply"] > first]
        slip = max(mine, key=lambda m: m["loss"], default=None)
        out.append({"game_id": r["game_id"], "played_at": r["played_at"], "opp_name": r["opp_name"], "result": r["result"],
                    "how": r["how"], "peak": round(max(chances)), "ply": slip["ply"] if slip else max(first, 1),
                    "san": slip and slip["san"], "best": slip and slip["best"], "loss": slip and slip["loss"]})
    return sorted(out, key=lambda g: g["played_at"], reverse=True)


def endgames(rows: list[dict]) -> list[dict]:
    by = {}
    for r in rows:
        kind = endgame_of(r)
        if not kind:
            continue
        e = by.setdefault(kind, {"type": kind, "games": 0, "win": 0, "draw": 0, "loss": 0, "acc": []})
        e["games"] += 1
        e[r["result"]] += 1
        acc = r["summary"]["sides"][r["colour"]]["phases"].get("endgame")
        if acc is not None:
            e["acc"].append(acc)
    return sorted(({**{k: v for k, v in e.items() if k != "acc"}, "accuracy": round(sum(e["acc"]) / len(e["acc"]), 1) if e["acc"] else None}
                   for e in by.values()), key=lambda e: -e["games"])


def time_stats(rows: list[dict]) -> dict | None:
    """Clock numbers from the games that have a clock (chess.com's do). None if no reviewed game has one."""
    games = trouble_bad = bad = flagged = 0
    spent = {ph: [] for ph in PHASES}
    for r in rows:
        moves = chess_review.with_clocks(r["moves"], r["pgn"])
        mine = [m for m in moves if m["colour"] == r["colour"] and "clock" in m]
        if not mine:
            continue
        games += 1
        flagged += r["result"] == "loss" and r.get("how") == "timeout"
        for m in mine:
            if m.get("spent") is not None:
                spent[m["phase"]].append(m["spent"])
            if m["kind"] in BAD:
                bad += 1
                trouble_bad += bool(m.get("low"))
    if not games:
        return None
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None    # noqa: E731
    return {"games": games, "bad_moves": bad, "bad_in_trouble": trouble_bad, "flagged": flagged,
            "avg_spent": {ph: avg(v) for ph, v in spent.items()}}


@router.get("/chess/insights")
def insights():
    with db() as conn:
        rows = _rows(conn)
    return {"reviewed": len(rows), "skills": skill_scores(rows) if rows else [], "lost_won": lost_won(rows),
            "endgames": endgames(rows), "time": time_stats(rows)}


# ---------------------------------------------------------------------------
# Your mistakes as puzzles
# ---------------------------------------------------------------------------
def add_puzzles(conn) -> int:
    """Make a puzzle of each of your mistakes in the finished reviews that doesn't have one yet. Returns how many are new."""
    added = 0
    for r in _rows(conn):
        for m in r["moves"]:
            if m["colour"] != r["colour"] or m["kind"] not in BAD or not m.get("best_uci") or m["best_uci"] == m["uci"]:
                continue
            added += conn.execute("""
                INSERT INTO chess_puzzles (game_id, ply, fen, colour, played_san, best_san, best_uci, best_line, loss, kind)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (game_id, ply) DO NOTHING""",
                (r["game_id"], m["ply"], m["fen_before"], r["colour"], m["san"], m["best"], m["best_uci"],
                 Jsonb(m["best_line"]), m["loss"], m["kind"])).rowcount
    return added


@router.get("/chess/puzzles")
def puzzles(limit: int = 20):
    """Counts, and the next puzzles: the ones that are due (oldest first), then new ones (worst blunders first)."""
    limit = max(1, min(limit, 100))
    with db() as conn:
        counts = conn.execute("""
            SELECT count(*) AS total, count(*) FILTER (WHERE last_at IS NULL) AS new,
                   count(*) FILTER (WHERE last_at IS NOT NULL AND due_at <= now()) AS due,
                   count(*) FILTER (WHERE reps >= 3) AS learned FROM chess_puzzles""").fetchone()
        cards = conn.execute("""
            SELECT p.puzzle_id, p.game_id, p.ply, p.fen, p.colour, p.played_san, p.best_san, p.best_uci, p.best_line, p.loss, p.kind,
                   p.reps, p.lapses, p.last_at, g.opp_name, g.played_at
            FROM chess_puzzles p JOIN chess_games g USING (game_id)
            WHERE p.last_at IS NULL OR p.due_at <= now()
            ORDER BY (p.last_at IS NULL), p.due_at, p.loss DESC, p.puzzle_id LIMIT %s""", (limit,)).fetchall()
    return {**counts, "cards": cards}


@router.post("/chess/puzzles/sync")
def sync_puzzles():
    with db() as conn:
        return {"added": add_puzzles(conn)}


class PuzzleAnswer(BaseModel):
    correct: bool


@router.post("/chess/puzzles/{puzzle_id}/answer")
def answer_puzzle(puzzle_id: int, body: PuzzleAnswer):
    with db() as conn:
        card = found(conn.execute("SELECT * FROM chess_puzzles WHERE puzzle_id = %s", (puzzle_id,)).fetchone(), "Puzzle")
        new = chess_trainer.schedule(card, body.correct)
        conn.execute("""UPDATE chess_puzzles SET interval_days = %(interval_days)s, ease = %(ease)s, reps = %(reps)s,
                        lapses = %(lapses)s, due_at = %(due_at)s, last_result = %(last_result)s, last_at = now()
                        WHERE puzzle_id = %(id)s""", {**new, "id": puzzle_id})
    return {"puzzle_id": puzzle_id, "reps": new["reps"], "lapses": new["lapses"], "interval_days": float(new["interval_days"]),
            "last_result": new["last_result"]}
