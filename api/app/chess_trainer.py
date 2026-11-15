"""Chess opening trainer (96_chess_openings_trainer.sql): learn the lines of an opening, what people are likely to play
against it, and how to meet it - then drill them with spaced repetition.

    GET    /chess/trainer/explore            a position: its name, the moves played from it (Lichess players near your
                                             rating, and masters), theory, your own games through it, the engine on request
    GET    /chess/trainer/recommend          "how to meet it": the move to play here, and why (masters / engine)
    GET    /chess/trainer/search             named openings by name ("pick an opening to learn")
    POST   /chess/trainer/repertoires        start learning an opening (a colour + its moves); built in the background
    GET    /chess/trainer/repertoires        your openings with progress (new / due / learned / total) and how a build is going
    GET    /chess/trainer/repertoires/{id}   one, with its cards
    DELETE /chess/trainer/repertoires/{id}
    GET    /chess/trainer/drill              cards to learn (never seen) or review (due), plus what the opponent plays
    POST   /chess/trainer/cards/{id}/answer  right / wrong -> the next due date (Anki's SM-2 way)

How a repertoire is built (build()): from the start position along the opening's own moves (your moves there become
cards); then best-first, most likely lines first. At the OPPONENT's turn: their 2-3 likeliest replies from the Lichess
explorer for your rating (5% of games or more; the bundled theory when the explorer isn't there). At YOUR turn: one
move - the masters' most played that Stockfish doesn't think is bad, else Stockfish's best. It stops at a depth, a card
limit, a probability floor (rare lines aren't worth learning) or ~60 live explorer requests (answers are cached anyway).

How a card is scheduled (schedule()): right -> 1 day, then 6 days, then the interval times its ease (2.5 to start);
wrong -> back to 1 day, the ease drops 0.2 (never under 1.3), a lapse is counted, and it's due again in 10 minutes.
A card counts as learned once it has been right twice in a row.
"""
import heapq
import itertools
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from io import StringIO

import chess
import chess.engine
import chess.pgn
from fastapi import APIRouter, HTTPException, Query
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import chess_openings, chess_review, lichess
from .db import db, found

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chess"])

RUN_INLINE = False              # tests: build at once instead of on a thread
CALL_CAP = 60                   # live explorer requests per build
MAX_CARDS = 80
MAX_PLY = 20                    # ten moves each
MIN_PROB = 0.02                 # lines rarer than this (of the opponent's choices) aren't worth learning
MIN_SHARE = 5.0                 # % of games for an opponent reply to count
MIN_GAMES = 50                  # fewer games than this in the explorer: the line stops
REPLIES = 3
ENGINE_DEPTH = 12
BAD = 50                        # centipawns a move may be worse than the best and still not "bad"
PROGRESS: dict[int, dict] = {}  # repertoire_id -> how a build is going (polled through GET /chess/trainer/repertoires)
_build_lock = threading.Lock()
_mine_lock = threading.Lock()
_mine = {"stamp": None, "index": {}}


# ---------------------------------------------------------------------------------------------
# The engine (one process, opened for as long as a job needs it)
# ---------------------------------------------------------------------------------------------
class Engine:
    """Stockfish, if it's there. top(board, n) -> [{uci, san, cp, mate}] best first, from the side to move's view; [] when
    the engine isn't available (everything works without it, just with less to say)."""

    def __enter__(self):
        self.engine = None
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(chess_review.ENGINE)
            self.engine.configure({"Threads": 1, "Hash": 32})
        except (OSError, chess.engine.EngineError) as e:
            log.warning("No engine for the trainer: %s", e.__class__.__name__)
            self.engine = None
        return self

    def __exit__(self, *_):
        if self.engine:
            try:
                self.engine.quit()
            except (OSError, chess.engine.EngineError):
                pass

    def top(self, board: chess.Board, n: int = 3, depth: int = ENGINE_DEPTH) -> list[dict]:
        if not self.engine or board.is_game_over():
            return []
        try:
            infos = self.engine.analyse(board, chess.engine.Limit(depth=depth), multipv=n)
        except (chess.engine.EngineError, OSError):
            return []
        out = []
        for info in infos:
            pv = info.get("pv") or []
            score = info["score"].pov(board.turn)
            if pv:
                out.append({"uci": pv[0].uci(), "san": board.san(pv[0]), "cp": score.score(), "mate": score.mate()})
        return out


class NoEngine:
    """For tests: an engine that isn't there."""
    engine = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def top(self, board, n=3, depth=ENGINE_DEPTH):
        return []


def value(m: dict) -> int:
    """An engine score as one number (a mate is worth a lot)."""
    if m.get("mate") is not None:
        return (100000 - abs(m["mate"])) * (1 if m["mate"] > 0 else -1)
    return m.get("cp") or 0


def eval_text(m: dict) -> str:
    if m.get("mate") is not None:
        return f"mate in {abs(m['mate'])}" if m["mate"] > 0 else f"mated in {abs(m['mate'])}"
    return f"{(m.get('cp') or 0) / 100:+.1f}"


# ---------------------------------------------------------------------------------------------
# Asking the explorer (cached; counts the live requests of one job)
# ---------------------------------------------------------------------------------------------
class Asker:
    def __init__(self, ratings: str | None, cap: int | None = None):
        self.ratings, self.cap, self.live, self.error = ratings, cap, 0, None

    def ask(self, board: chess.Board, source: str) -> dict | None:
        """The explorer's answer, or None (with .error set) when it can't be had."""
        if self.cap is not None and self.live >= self.cap:
            return None
        try:
            a = lichess.explore(board.fen(), source, self.ratings if source == "lichess" else None)
        except lichess.LichessError as e:
            self.error = str(e)
            return None
        self.live += 1 if a.get("live") else 0
        return a


def my_rating() -> int | None:
    with db() as conn:
        row = conn.execute("SELECT my_rating FROM chess_games WHERE source = 'chesscom' AND my_rating IS NOT NULL "
                           "ORDER BY played_at DESC LIMIT 1").fetchone()
    return row and row["my_rating"]


def recommend(board: chess.Board, asker: Asker, eng) -> dict | None:
    """The move to play here: the masters' most played that the engine doesn't call bad, else the engine's best, else
    theory. {san, uci, why, note, cp, mate}"""
    masters = asker.ask(board, "masters")
    mm = (masters or {}).get("moves") or []
    top = eng.top(board, 5)
    if mm:
        for m in mm[:4]:
            if top:
                hit = next((t for t in top if t["uci"] == m["uci"]), None)
                if not hit or value(hit) < value(top[0]) - BAD:
                    continue
            else:
                hit = None
            note = f"Masters play it in {m['share']:.0f}% of {masters['total']:,} games"
            if hit:
                note += f"; the engine agrees ({eval_text(hit)})"
            return {"san": m["san"], "uci": m["uci"], "why": "masters", "note": note,
                    "cp": hit and hit["cp"], "mate": hit and hit["mate"]}
    if top:
        t = top[0]
        why = "The engine's best" + (" (no master game has been here)" if not mm else " (the masters' usual moves are weaker)")
        return {"san": t["san"], "uci": t["uci"], "why": "engine", "note": f"{why}: {eval_text(t)}", "cp": t["cp"], "mate": t["mate"]}
    th = chess_openings.theory(board)
    if th:
        return {"san": th[0]["san"], "uci": board.parse_san(th[0]["san"]).uci(), "why": "theory",
                "note": "A known theory move" + (f" ({th[0]['name']})" if th[0]["name"] else ""), "cp": None, "mate": None}
    return None


def opponent_replies(board: chess.Board, asker: Asker) -> tuple[list[dict], bool]:
    """What the opponent is likely to play here: [{san, uci, share}] (shares add to 100) and whether the explorer said it."""
    a = asker.ask(board, "lichess")
    if a is not None:
        if a["total"] < MIN_GAMES:
            return [], True
        keep = [m for m in a["moves"] if m["share"] >= MIN_SHARE][:REPLIES]
        total = sum(m["games"] for m in keep)
        return [{"san": m["san"], "uci": m["uci"], "share": round(100 * m["games"] / total, 1)} for m in keep], True
    th = chess_openings.theory(board)[:REPLIES]
    return [{"san": t["san"], "uci": board.parse_san(t["san"]).uci(), "share": round(100 / len(th), 1)} for t in th], False


# ---------------------------------------------------------------------------------------------
# Building a repertoire
# ---------------------------------------------------------------------------------------------
def play_sans(text: str) -> tuple[chess.Board, list[str]]:
    """A board after moves written in SAN ("1. e4 e5 2. Nf3" or "e4 e5 Nf3"); ValueError if one isn't legal."""
    board, sans = chess.Board(), []
    for token in text.split():
        if re.fullmatch(r"\d+\.+", token):
            continue
        token = re.sub(r"^\d+\.+", "", token)
        if not token:
            continue
        try:
            sans.append(_push(board, token))
        except ValueError:
            raise ValueError(f"'{token}' isn't a legal move there.") from None
    return board, sans


def _push(board: chess.Board, token: str) -> str:
    move = board.parse_san(token)
    san = board.san(move)
    board.push(move)
    return san


def add_card(rid: int, board: chess.Board, sans: list[str], move: dict) -> bool:
    """Save one card at once (its own transaction, so the web can show the count growing)."""
    with db() as conn:
        cur = conn.execute("""INSERT INTO chess_drill_cards (repertoire_id, epd, fen, ply, line, move_san, move_uci, why, note)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (repertoire_id, epd) DO NOTHING""",
                           (rid, board.epd(), board.fen(), len(sans), " ".join(sans), move["san"], move["uci"], move["why"], move["note"]))
        return cur.rowcount > 0


def build(rid: int):
    """Build a repertoire's drill cards (see the top of this file). Saves each card as it's found."""
    with _build_lock:
        state = PROGRESS[rid] = {"running": True, "cards": 0, "calls": 0, "message": "Starting..."}
        try:
            with db() as conn:
                rep = conn.execute("SELECT * FROM chess_repertoire WHERE repertoire_id = %s", (rid,)).fetchone()
            if not rep:
                return
            _build(rid, rep, state)
        except Exception as e:  # keep the app up; say what happened
            log.exception("Repertoire build failed")
            with db() as conn:
                conn.execute("UPDATE chess_repertoire SET status = 'failed', error = %s WHERE repertoire_id = %s",
                             (f"The build stopped: {e.__class__.__name__}.", rid))
        finally:
            state["running"] = False


def _build(rid: int, rep: dict, state: dict):
    me = chess.WHITE if rep["colour"] == "white" else chess.BLACK
    asker = Asker(lichess.band_for(my_rating()), CALL_CAP)
    replies, seen, cards, line = {}, set(), 0, []
    tie = itertools.count()
    heap = []
    with Engine() as eng:
        # 1. The opening's own moves: yours become cards; the opponent's are the line (no branching inside it)
        _, sans = play_sans(rep["start_moves"])
        walk = chess.Board()
        for san in sans:
            seen.add(walk.epd())
            move = walk.parse_san(san)
            if walk.turn == me:
                cards += add_card(rid, walk, line, {"san": san, "uci": move.uci(), "why": "opening",
                                                          "note": "Your opening's own move"})
            else:
                after = walk.copy()
                after.push(move)
                replies[walk.epd()] = [{"san": san, "uci": move.uci(), "share": 100, "epd": after.epd()}]
            walk.push(move)
            line = line + [san]
        # 2. Then the likeliest lines first
        heapq.heappush(heap, (-1.0, next(tie), walk, line))
        while heap and not (cards >= MAX_CARDS):
            neg, _, board, line = heapq.heappop(heap)
            prob, epd = -neg, board.epd()
            if epd in seen or board.is_game_over() or len(line) >= MAX_PLY or prob < MIN_PROB:
                continue
            seen.add(epd)
            state.update(cards=cards, calls=asker.live, message=f"Looking at move {len(line) // 2 + 1} of a line... {cards} cards so far")
            if board.turn == me:
                rec = recommend(board, asker, eng)
                if not rec:
                    continue
                cards += add_card(rid, board, line, rec)
                child = board.copy()
                child.push_uci(rec["uci"])
                heapq.heappush(heap, (neg, next(tie), child, line + [rec["san"]]))
            else:
                options, _ = opponent_replies(board, asker)
                if not options:
                    continue
                out = []
                for o in options:
                    child = board.copy()
                    child.push_uci(o["uci"])
                    out.append({**o, "epd": child.epd()})
                    heapq.heappush(heap, (-(prob * o["share"] / 100), next(tie), child, line + [o["san"]]))
                replies[epd] = out
        state.update(cards=cards, calls=asker.live)
        note = "Built from the Lichess explorer" if asker.live or not asker.error else f"Built without the explorer ({asker.error})"
        if not eng.engine:
            note += "; no engine, so your moves are the masters' / theory"
    with db() as conn:
        if cards:
            conn.execute("""UPDATE chess_repertoire SET status = 'ready', error = NULL, replies = %s, notes = %s, built_at = now()
                            WHERE repertoire_id = %s""", (Jsonb(replies), note, rid))
        else:
            conn.execute("UPDATE chess_repertoire SET status = 'failed', error = %s WHERE repertoire_id = %s",
                         ("Nothing to learn here: no moves could be found (the explorer and the opening list had none).", rid))


def start_build(rid: int):
    if RUN_INLINE:
        build(rid)
    else:
        threading.Thread(target=build, args=(rid,), daemon=True, name=f"repertoire-{rid}").start()


# ---------------------------------------------------------------------------------------------
# Scheduling (SM-2, the way Anki does it)
# ---------------------------------------------------------------------------------------------
def schedule(card: dict, correct: bool, now: datetime | None = None) -> dict:
    """The card's new numbers after an answer: {interval_days, ease, reps, lapses, due_at, last_result}."""
    now = now or datetime.now(timezone.utc)
    interval, ease = float(card["interval_days"]), float(card["ease"])
    reps, lapses = card["reps"], card["lapses"]
    if correct:
        reps += 1
        interval = 1.0 if reps == 1 else 6.0 if reps == 2 else max(interval + 1, round(interval * ease, 1))
        due = now + timedelta(days=interval)
    else:
        lapses += 1
        reps, interval, ease = 0, 1.0, max(1.3, round(ease - 0.2, 2))
        due = now + timedelta(minutes=10)
    return {"interval_days": interval, "ease": ease, "reps": reps, "lapses": lapses, "due_at": due,
            "last_result": "right" if correct else "wrong"}


# ---------------------------------------------------------------------------------------------
# Your own games through a position
# ---------------------------------------------------------------------------------------------
GAME_PLIES = 30


def _my_index() -> dict:
    """{epd: {"reached": [w, d, l], "moves": {(san, mine): [w, d, l]}}} over your games' first moves. Rebuilt when your
    games change (counted by a stamp); reading a few thousand PGNs takes a few seconds, once."""
    with db() as conn:
        stamp = tuple(conn.execute("SELECT count(*) AS n, max(game_id) AS m, sum(length(pgn)) AS l, max(created_at) AS c FROM chess_games "
                                   "WHERE pgn IS NOT NULL AND rules = 'chess'").fetchone().values())
        with _mine_lock:
            if _mine["stamp"] == stamp:
                return _mine["index"]
        rows = conn.execute("SELECT pgn, colour, result FROM chess_games WHERE pgn IS NOT NULL AND rules = 'chess'").fetchall()
    index = {}
    for row in rows:
        try:
            game = chess.pgn.read_game(StringIO(row["pgn"]))
        except (ValueError, KeyError):
            continue
        if not game:
            continue
        slot = {"win": 0, "draw": 1, "loss": 2}[row["result"]]
        board = game.board()
        for ply, move in enumerate(game.mainline_moves()):
            if ply >= GAME_PLIES:
                break
            try:
                here, san = board.epd(), board.san(move)
            except ValueError:
                break
            mine = (board.turn == chess.WHITE) == (row["colour"] == "white")
            e = index.setdefault(here, {"reached": [0, 0, 0], "moves": {}})
            e["reached"][slot] += 1
            e["moves"].setdefault((san, mine), [0, 0, 0])[slot] += 1
            board.push(move)
    with _mine_lock:
        _mine.update(stamp=stamp, index=index)
    return index


def my_games_here(board: chess.Board) -> dict:
    e = _my_index().get(board.epd())
    if not e:
        return {"games": 0, "wins": 0, "draws": 0, "losses": 0, "moves": []}
    w, d, loss = e["reached"]
    moves = [{"san": san, "mine": mine, "games": sum(r), "wins": r[0], "draws": r[1], "losses": r[2]}
             for (san, mine), r in e["moves"].items()]
    moves.sort(key=lambda m: -m["games"])
    return {"games": w + d + loss, "wins": w, "draws": d, "losses": loss, "moves": moves}


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------
class RepertoireIn(BaseModel):
    colour: str = Field(pattern="^(white|black)$")
    moves: str = Field("", max_length=600)                 # the opening's moves in SAN
    name: str | None = Field(None, max_length=200)
    eco: str | None = Field(None, max_length=10)


class AnswerIn(BaseModel):
    correct: bool
    played: str | None = Field(None, max_length=20)


def _board(fen: str | None, moves: str | None) -> tuple[chess.Board, list[str]]:
    try:
        if moves:
            return play_sans(moves)
        return chess.Board(fen) if fen else chess.Board(), []
    except ValueError as e:
        raise HTTPException(400, str(e) if moves else "That isn't a position (FEN) I can read.") from None


def _boards_along(sans: list[str]) -> list[chess.Board]:
    b, out = chess.Board(), [chess.Board()]
    for s in sans:
        b.push_san(s)
        out.append(b.copy())
    return out


def _arrow(uci: str) -> dict:
    return {"from": uci[:2], "to": uci[2:4]}


@router.get("/chess/trainer/explore")
def explore(fen: str | None = Query(None, max_length=120), moves: str | None = Query(None, max_length=600),
            ratings: str | None = Query(None, pattern=r"^\d{1,4}(,\d{1,4}){0,8}$"), engine: bool = False):
    board, sans = _board(fen, moves)
    rating = my_rating()
    band = ratings or lichess.band_for(rating)
    asker = Asker(band)
    theory = chess_openings.theory(board)
    in_theory = {t["san"]: t for t in theory}

    def tidy(answer):
        if not answer:
            return None
        for m in answer["moves"]:
            t = in_theory.get(m["san"])
            m["theory"], m["name"] = bool(t), t and t["name"]
        return answer
    lich = tidy(asker.ask(board, "lichess"))
    mast = tidy(asker.ask(board, "masters")) if lich is not None or asker.error is None else None
    named = chess_openings.name_of(_boards_along(sans)) if sans else chess_openings.named(board)
    out = {"fen": board.fen(), "epd": board.epd(), "turn": "white" if board.turn else "black", "moves": sans,
           "name": named, "in_book": chess_openings.in_book(board), "theory": theory,
           "lichess": lich, "masters": mast, "explorer_error": asker.error, "ratings": band, "my_rating": rating,
           "mine": my_games_here(board), "engine": None, "game_over": board.is_game_over()}
    if engine:
        with Engine() as eng:
            out["engine"] = [{**t, "text": eval_text(t)} for t in eng.top(board, 3)]
    return out


@router.get("/chess/trainer/recommend")
def recommend_route(fen: str | None = Query(None, max_length=120), moves: str | None = Query(None, max_length=600)):
    """How to meet a position: the move to play, and why."""
    board, _ = _board(fen, moves)
    if board.is_game_over():
        return {"move": None, "error": "The game is over here."}
    asker = Asker(lichess.band_for(my_rating()))
    with Engine() as eng:
        rec = recommend(board, asker, eng)
    if rec:
        rec = {**rec, **_arrow(rec["uci"]), "text": eval_text(rec) if rec["cp"] is not None or rec["mate"] is not None else None}
    return {"move": rec, "explorer_error": asker.error}


@router.get("/chess/trainer/search")
def search(q: str = Query("", max_length=80), limit: int = Query(30, ge=1, le=100)):
    return {"openings": chess_openings.search(q, limit)}


def _progress(conn, rid: int | None = None) -> dict:
    rows = conn.execute("""SELECT repertoire_id, count(*) AS total, count(*) FILTER (WHERE last_at IS NULL) AS new,
                                  count(*) FILTER (WHERE last_at IS NOT NULL AND due_at <= now()) AS due,
                                  count(*) FILTER (WHERE reps >= 2) AS learned
                           FROM chess_drill_cards WHERE (%(r)s::int IS NULL OR repertoire_id = %(r)s) GROUP BY repertoire_id""",
                        {"r": rid}).fetchall()
    return {r["repertoire_id"]: {k: r[k] for k in ("total", "new", "due", "learned")} for r in rows}


def _rep_out(row: dict, progress: dict) -> dict:
    status, error = row["status"], row["error"]
    live = PROGRESS.get(row["repertoire_id"])
    if status == "building" and not (live and live["running"]):
        status, error = "failed", "The build was interrupted (the app restarted). Delete it and start again."
    return {"repertoire_id": row["repertoire_id"], "name": row["name"], "colour": row["colour"], "moves": row["start_moves"],
            "eco": row["eco"], "status": status, "error": error, "notes": row["notes"], "created_at": row["created_at"],
            "progress": progress.get(row["repertoire_id"], {"total": 0, "new": 0, "due": 0, "learned": 0}),
            "building": live if status == "building" else None}


@router.post("/chess/trainer/repertoires", status_code=201)
def add_repertoire(body: RepertoireIn):
    try:
        _, sans = play_sans(body.moves)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    name = (body.name or "").strip() or (chess_openings.name_of(_boards_along(sans)) or {}).get("name") or "Starting position"
    eco = body.eco or (chess_openings.name_of(_boards_along(sans)) or {}).get("eco")
    with db() as conn:
        dup = conn.execute("SELECT repertoire_id FROM chess_repertoire WHERE colour = %s AND start_moves = %s",
                           (body.colour, " ".join(sans))).fetchone()
        if dup:
            raise HTTPException(409, "You're already learning that opening as that colour.")
        row = conn.execute("""INSERT INTO chess_repertoire (name, colour, start_moves, eco) VALUES (%s, %s, %s, %s) RETURNING *""",
                           (name, body.colour, " ".join(sans), eco)).fetchone()
    PROGRESS[row["repertoire_id"]] = {"running": True, "cards": 0, "calls": 0, "message": "Starting..."}
    start_build(row["repertoire_id"])
    with db() as conn:
        row = conn.execute("SELECT * FROM chess_repertoire WHERE repertoire_id = %s", (row["repertoire_id"],)).fetchone()
        return _rep_out(row, _progress(conn, row["repertoire_id"]))


@router.get("/chess/trainer/repertoires")
def list_repertoires():
    with db() as conn:
        rows = conn.execute("SELECT * FROM chess_repertoire ORDER BY created_at DESC, repertoire_id DESC").fetchall()
        progress = _progress(conn)
    return {"repertoires": [_rep_out(r, progress) for r in rows]}


@router.get("/chess/trainer/repertoires/{rid}")
def get_repertoire(rid: int):
    with db() as conn:
        row = found(conn.execute("SELECT * FROM chess_repertoire WHERE repertoire_id = %s", (rid,)).fetchone(), "Opening")
        cards = conn.execute("""SELECT card_id, ply, line, move_san, why, note, due_at, interval_days, reps, lapses, last_result, last_at
                                FROM chess_drill_cards WHERE repertoire_id = %s ORDER BY ply, card_id""", (rid,)).fetchall()
        out = _rep_out(row, _progress(conn, rid))
    return {**out, "cards": [{**c, "line": c["line"].split(), "interval_days": float(c["interval_days"])} for c in cards]}


@router.delete("/chess/trainer/repertoires/{rid}", status_code=204)
def delete_repertoire(rid: int):
    with db() as conn:
        found(conn.execute("DELETE FROM chess_repertoire WHERE repertoire_id = %s RETURNING repertoire_id", (rid,)).fetchone(),
              "Opening")
    PROGRESS.pop(rid, None)


@router.get("/chess/trainer/drill")
def drill(repertoire_id: int | None = None, mode: str = Query("review", pattern="^(learn|review)$"),
          limit: int = Query(20, ge=1, le=100)):
    """Cards to work on: 'learn' = never seen, shallowest first; 'review' = due, oldest first. Only reads."""
    where = "last_at IS NULL" if mode == "learn" else "last_at IS NOT NULL AND due_at <= now()"
    order = "c.ply, c.card_id" if mode == "learn" else "c.due_at, c.card_id"
    with db() as conn:
        cards = conn.execute(f"""SELECT c.card_id, c.repertoire_id, c.epd, c.fen, c.ply, c.line, c.move_san, c.move_uci, c.why, c.note,
                                        c.reps, c.lapses, r.name AS repertoire, r.colour
                                 FROM chess_drill_cards c JOIN chess_repertoire r USING (repertoire_id)
                                 WHERE {where} AND (%(r)s::int IS NULL OR c.repertoire_id = %(r)s) ORDER BY {order} LIMIT %(n)s""",
                             {"r": repertoire_id, "n": limit}).fetchall()
        ids = sorted({c["repertoire_id"] for c in cards})
        replies = {}
        for r in (conn.execute("SELECT replies FROM chess_repertoire WHERE repertoire_id = ANY(%s::int[])", (ids,)).fetchall() if ids else []):
            replies.update(r["replies"])
        progress = _progress(conn, repertoire_id)
    return {"mode": mode, "cards": [{**c, "line": c["line"].split()} for c in cards], "replies": replies,
            "progress": progress.get(repertoire_id) if repertoire_id else None}


@router.post("/chess/trainer/cards/{card_id}/answer")
def answer(card_id: int, body: AnswerIn):
    with db() as conn:
        card = found(conn.execute("SELECT * FROM chess_drill_cards WHERE card_id = %s", (card_id,)).fetchone(), "Card")
        new = schedule(card, body.correct)
        conn.execute("""UPDATE chess_drill_cards SET interval_days = %(interval_days)s, ease = %(ease)s, reps = %(reps)s,
                        lapses = %(lapses)s, due_at = %(due_at)s, last_result = %(last_result)s, last_at = now()
                        WHERE card_id = %(id)s""", {**new, "id": card_id})
        progress = _progress(conn, card["repertoire_id"]).get(card["repertoire_id"])
    return {"card_id": card_id, **{k: (float(v) if k in ("interval_days", "ease") else v) for k, v in new.items()},
            "progress": progress}
