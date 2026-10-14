"""Chess (a hobby module): your chess.com games (chesscom.py, the official public API - no login)
and games over the board, logged by hand.

    sync      profile + stats, then every month of games the first time; after that only months
              that weren't over when read (the current one, and the last one until it's done) -
              or every month on a full sync. One request at a time. Runs in the background
              (GET /chess/account shows how it's going) and by itself once a day.
    summary   ratings per time control (now, best, the last 7 days), record, puzzles, recent games
    ratings   your rating after each day's games, per time control, for the chart
    games     every game (filters), one game with its moves; over-the-board games added by hand
    openings  how you do with each opening family (and its variations), as White and as Black
"""
import logging
import threading
import time as clock
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import chesscom
from .db import db, found, tidy_text

router = APIRouter(prefix="/api", tags=["chess"])
log = logging.getLogger("chess")

CLASSES = ("bullet", "blitz", "rapid", "daily", "classical")
DAILY = timedelta(hours=20)
SYNC = {"running": False, "done": 0, "total": 0, "message": None, "error": None, "finished_at": None}
_lock = threading.Lock()

LIST = """
SELECT game_id, source, url, played_at, time_class, time_control, rated, rules, colour, my_rating, opp_name,
       opp_rating, result, how, eco, opening, opening_family, moves, accuracy, opp_accuracy, event, notes,
       my_rating - lag(my_rating) OVER (PARTITION BY time_class, source, rated ORDER BY played_at) AS rating_change
FROM chess_games"""


class AccountIn(BaseModel):
    username: str = Field(min_length=3, max_length=200)       # a username or profile link


class GameIn(BaseModel):
    """An over-the-board game."""
    played_on: date
    time_class: str = Field("classical", pattern="^(bullet|blitz|rapid|daily|classical)$")
    colour: str = Field(pattern="^(white|black)$")
    opp_name: str = Field(min_length=1, max_length=120)
    result: str = Field(pattern="^(win|loss|draw)$")
    opp_rating: int | None = Field(None, ge=0, le=4000)
    my_rating: int | None = Field(None, ge=0, le=4000)
    rated: bool = False
    event: str | None = Field(None, max_length=200)
    opening: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=5000)
    pgn: str | None = Field(None, max_length=100000)


class GamePatch(BaseModel):
    played_on: date | None = None
    time_class: str | None = Field(None, pattern="^(bullet|blitz|rapid|daily|classical)$")
    colour: str | None = Field(None, pattern="^(white|black)$")
    opp_name: str | None = Field(None, min_length=1, max_length=120)
    result: str | None = Field(None, pattern="^(win|loss|draw)$")
    opp_rating: int | None = Field(None, ge=0, le=4000)
    my_rating: int | None = Field(None, ge=0, le=4000)
    rated: bool | None = None
    event: str | None = Field(None, max_length=200)
    opening: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=5000)
    pgn: str | None = Field(None, max_length=100000)


# ---------------------------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------------------------
UPSERT = """
INSERT INTO chess_games (source, uuid, url, played_at, time_class, time_control, rated, rules, colour, my_rating,
                         opp_name, opp_rating, result, how, eco, opening, opening_family, pgn, moves, accuracy, opp_accuracy)
VALUES ('chesscom', %(uuid)s, %(url)s, %(played_at)s, %(time_class)s, %(time_control)s, %(rated)s, %(rules)s, %(colour)s,
        %(my_rating)s, %(opp_name)s, %(opp_rating)s, %(result)s, %(how)s, %(eco)s, %(opening)s, %(opening_family)s,
        %(pgn)s, %(moves)s, %(accuracy)s, %(opp_accuracy)s)
ON CONFLICT (uuid) DO UPDATE SET accuracy = EXCLUDED.accuracy, opp_accuracy = EXCLUDED.opp_accuracy,
    pgn = COALESCE(EXCLUDED.pgn, chess_games.pgn), opening = EXCLUDED.opening, opening_family = EXCLUDED.opening_family"""


def run_sync(full: bool = False):
    """The whole sync; each month is saved as it's read, so a sync that stops keeps what it got."""
    try:
        with db() as conn:
            user = conn.execute("SELECT username FROM chess_account WHERE id = 1").fetchone()["username"]
        if not user:
            raise chesscom.ChessError("Set your chess.com username first.")
        SYNC.update(message="Reading your profile and ratings...")
        prof = chesscom.profile(user)
        chesscom.pause()
        stats = chesscom.stats(user)
        chesscom.pause()
        months = chesscom.archives(user)
        with db() as conn:
            conn.execute("UPDATE chess_account SET profile = %s, stats = %s WHERE id = 1", (Jsonb(prof), Jsonb(stats)))
            done = {r["month"] for r in conn.execute("SELECT month FROM chess_archives WHERE complete").fetchall()}
        this_month = datetime.now(timezone.utc).strftime("%Y-%m")
        due = [m for m in months if full or m not in done]
        SYNC.update(total=len(due), done=0)
        added = 0
        for ym in due:
            SYNC.update(message=f"Reading your games from {ym}...")
            chesscom.pause()
            games = [r for r in (chesscom.game_row(g, user) for g in chesscom.month(user, ym)) if r]
            with db() as conn:
                before = conn.execute("SELECT count(*) AS n FROM chess_games WHERE source = 'chesscom'").fetchone()["n"]
                for row in games:
                    conn.execute(UPSERT, row)
                added += conn.execute("SELECT count(*) AS n FROM chess_games WHERE source = 'chesscom'").fetchone()["n"] - before
                conn.execute("""INSERT INTO chess_archives (month, games, read_at, complete) VALUES (%s, %s, now(), %s)
                                ON CONFLICT (month) DO UPDATE SET games = EXCLUDED.games, read_at = now(),
                                    complete = EXCLUDED.complete""", (ym, len(games), ym < this_month))
            SYNC["done"] += 1
        with db() as conn:
            conn.execute("UPDATE chess_account SET last_sync_at = now(), last_error = NULL WHERE id = 1")
        SYNC.update(message=f"Done: {len(due)} month{'s' if len(due) != 1 else ''} read, {added} new game{'s' if added != 1 else ''}")
    except chesscom.ChessError as e:
        SYNC.update(error=str(e), message=None)
        with db() as conn:
            conn.execute("UPDATE chess_account SET last_error = %s WHERE id = 1", (str(e),))
    except Exception as e:  # keep the app up; say what happened
        log.exception("Chess sync failed")
        SYNC.update(error=f"The sync stopped: {e.__class__.__name__}.", message=None)
    finally:
        SYNC.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())


def start_sync(background: BackgroundTasks | None, full: bool = False) -> bool:
    with _lock:
        if SYNC["running"]:
            return False
        SYNC.update(running=True, done=0, total=0, message="Starting...", error=None, finished_at=None)
    if background is not None:
        background.add_task(run_sync, full)
    else:
        threading.Thread(target=run_sync, args=(full,), daemon=True, name="chess-sync").start()
    return True


def start_daily_sync():
    """Check every hour; sync when a username is set and the last sync is 20+ hours old."""
    def loop():
        while True:
            try:
                with db() as conn:
                    a = conn.execute("SELECT username, last_sync_at FROM chess_account WHERE id = 1").fetchone()
                if a and a["username"] and (not a["last_sync_at"] or datetime.now(timezone.utc) - a["last_sync_at"] > DAILY):
                    start_sync(None)
            except Exception:
                log.exception("Daily chess sync check failed")
            clock.sleep(3600)
    threading.Thread(target=loop, daemon=True, name="chess-daily").start()


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------
@router.get("/chess/account")
def account():
    with db() as conn:
        a = conn.execute("SELECT username, profile, last_sync_at, last_error FROM chess_account WHERE id = 1").fetchone()
    prof = a["profile"] or {}
    return {"username": a["username"], "name": prof.get("name"), "avatar": prof.get("avatar"), "title": prof.get("title"),
            "url": prof.get("url"), "last_sync_at": a["last_sync_at"], "last_error": a["last_error"], "sync": SYNC}


@router.put("/chess/account")
def set_account(body: AccountIn, background: BackgroundTasks):
    """Follow a chess.com account and read its games (a new account replaces the old one's games;
    over-the-board games stay)."""
    user = chesscom.username_from(body.username)
    if not user:
        raise HTTPException(422, "Enter your chess.com username or profile link (chess.com/member/...).")
    try:
        prof = chesscom.profile(user)
    except chesscom.ChessError as e:
        raise HTTPException(422 if isinstance(e, chesscom.NotFound) else 502, str(e))
    with db() as conn:
        old = conn.execute("SELECT username FROM chess_account WHERE id = 1").fetchone()["username"]
        if old and old != user:
            conn.execute("DELETE FROM chess_games WHERE source = 'chesscom'")
            conn.execute("DELETE FROM chess_archives")
        conn.execute("UPDATE chess_account SET username = %s, profile = %s, last_error = NULL WHERE id = 1",
                     (user, Jsonb(prof)))
    start_sync(background)
    return account()


@router.post("/chess/sync", status_code=202)
def sync(background: BackgroundTasks, full: bool = False):
    with db() as conn:
        if not conn.execute("SELECT username FROM chess_account WHERE id = 1").fetchone()["username"]:
            raise HTTPException(409, "Set your chess.com username first.")
    start_sync(background, full)
    return {"sync": SYNC}


def _record(rows) -> dict:
    out = {"win": 0, "loss": 0, "draw": 0}
    for r in rows:
        out[r["result"]] += r["n"]
    return out


@router.get("/chess/summary")
def summary():
    """For the dashboard and Home: each time control's rating (now, best, change in the last 7 days),
    your record, puzzles, this week, and recent games."""
    with db() as conn:
        a = conn.execute("SELECT username, profile, stats FROM chess_account WHERE id = 1").fetchone()
        stats = a["stats"] or {}
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        classes = []
        for tc in ("rapid", "blitz", "bullet", "daily"):
            s = stats.get(f"chess_{tc}")
            games = conn.execute("SELECT result, count(*)::int AS n FROM chess_games WHERE source = 'chesscom' "
                                 "AND time_class = %s AND rules = 'chess' GROUP BY result", (tc,)).fetchall()
            if not s and not games:
                continue
            before = conn.execute("SELECT my_rating FROM chess_games WHERE source = 'chesscom' AND time_class = %s "
                                  "AND rated AND rules = 'chess' AND played_at < %s ORDER BY played_at DESC LIMIT 1",
                                  (tc, week_ago)).fetchone()
            rating = (s or {}).get("last", {}).get("rating")
            classes.append({
                "time_class": tc, "rating": rating, "best": (s or {}).get("best", {}).get("rating"),
                "best_url": (s or {}).get("best", {}).get("game"),
                "record": (s or {}).get("record") or _record(games),
                "games": sum(g["n"] for g in games),
                "week_change": rating - before["my_rating"] if rating and before and before["my_rating"] else None,
            })
        classes.sort(key=lambda c: -c["games"])
        week = conn.execute("SELECT result, count(*)::int AS n FROM chess_games WHERE played_at >= %s GROUP BY result",
                            (week_ago,)).fetchall()
        recent = conn.execute(f"SELECT * FROM ({LIST}) g ORDER BY played_at DESC LIMIT 8").fetchall()
        otb = conn.execute("SELECT count(*)::int AS n FROM chess_games WHERE source = 'otb'").fetchone()["n"]
    tactics = stats.get("tactics") or {}
    rush = (stats.get("puzzle_rush") or {}).get("best") or {}
    return {"username": a["username"], "classes": classes, "main": classes[0]["time_class"] if classes else None,
            "puzzles": {"highest": (tactics.get("highest") or {}).get("rating"),
                        "lowest": (tactics.get("lowest") or {}).get("rating"), "rush_best": rush.get("score")},
            "week": {**_record(week), "games": sum(w["n"] for w in week)}, "recent": recent, "otb_games": otb}


@router.get("/chess/ratings")
def ratings(days: int = Query(365, ge=7, le=5000)):
    """Your rating after each day's rated games, per time control (online, standard chess)."""
    with db() as conn:
        rows = conn.execute("""
            SELECT DISTINCT ON (time_class, played_at::date) time_class, played_at::date AS day, my_rating AS rating
            FROM chess_games WHERE source = 'chesscom' AND rated AND rules = 'chess' AND my_rating IS NOT NULL
              AND played_at >= now() - make_interval(days => %s)
            ORDER BY time_class, played_at::date, played_at DESC""", (days,)).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["time_class"], []).append({"day": r["day"], "rating": r["rating"]})
    return out


@router.get("/chess/games")
def list_games(time_class: str | None = Query(None, pattern="^(bullet|blitz|rapid|daily|classical)$"),
               result: str | None = Query(None, pattern="^(win|loss|draw)$"),
               colour: str | None = Query(None, pattern="^(white|black)$"),
               source: str | None = Query(None, pattern="^(chesscom|otb)$"),
               opening: str | None = Query(None, max_length=200), q: str | None = Query(None, max_length=100),
               limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """Games, newest first, with the rating change each one made (same time control)."""
    where, params = [], {}
    for name, value in (("time_class", time_class), ("result", result), ("colour", colour), ("source", source),
                        ("opening_family", opening)):
        if value:
            where.append(f"{name} = %({name})s")
            params[name] = value
    if q and q.strip():
        where.append("(opp_name ILIKE %(q)s OR opening ILIKE %(q)s OR event ILIKE %(q)s)")
        params["q"] = f"%{q.strip()}%"
    with db() as conn:
        rows = conn.execute(f"SELECT * FROM ({LIST}) g" + (" WHERE " + " AND ".join(where) if where else "")
                            + " ORDER BY played_at DESC LIMIT %(limit)s OFFSET %(offset)s",
                            {**params, "limit": limit, "offset": offset}).fetchall()
        total = conn.execute("SELECT count(*)::int AS n FROM chess_games" + (" WHERE " + " AND ".join(where) if where else ""),
                             params).fetchone()["n"]
    return {"games": rows, "total": total}


def _one(conn, game_id: int) -> dict:
    game = found(conn.execute(f"SELECT g.*, c.pgn FROM ({LIST}) g JOIN chess_games c USING (game_id) "
                              "WHERE g.game_id = %s", (game_id,)).fetchone(), "Game")
    return game


@router.get("/chess/games/{game_id}")
def get_game(game_id: int):
    """One game with its moves (PGN)."""
    with db() as conn:
        return _one(conn, game_id)


def _otb_fields(sent: dict) -> dict:
    """An over-the-board game's fields as columns: text trimmed (blank = not set), the day at
    midday, the opening's family worked out from its name."""
    out = tidy_text(sent, required=("opp_name",))
    if "played_on" in out:
        out["played_at"] = datetime.combine(out.pop("played_on"), datetime.min.time()).replace(hour=12)
    if "opening" in out:
        out["opening_family"] = chesscom.family_of(out["opening"]) if out["opening"] else None
    return out


@router.post("/chess/games", status_code=201)
def add_game(body: GameIn):
    """An over-the-board game (club night, tournament...)."""
    fields = {**_otb_fields(body.model_dump()), "source": "otb"}
    with db() as conn:
        cols = ", ".join(fields)
        game_id = conn.execute(f"INSERT INTO chess_games ({cols}) VALUES ({', '.join(f'%({k})s' for k in fields)}) "
                               "RETURNING game_id", fields).fetchone()["game_id"]
        return _one(conn, game_id)


@router.patch("/chess/games/{game_id}")
def update_game(game_id: int, body: GamePatch):
    """Change an over-the-board game; an online game's notes."""
    sent = body.model_dump(exclude_unset=True)
    with db() as conn:
        game = _one(conn, game_id)
        if game["source"] != "otb" and set(sent) - {"notes"}:
            raise HTTPException(409, "An online game comes from chess.com: only its notes can change.")
        fields = _otb_fields(sent)
        if fields:
            conn.execute("UPDATE chess_games SET " + ", ".join(f"{k} = %({k})s" for k in fields) +
                         " WHERE game_id = %(id)s", {**fields, "id": game_id})
        return _one(conn, game_id)


@router.delete("/chess/games/{game_id}", status_code=204)
def delete_game(game_id: int):
    with db() as conn:
        if _one(conn, game_id)["source"] != "otb":
            raise HTTPException(409, "Online games come from chess.com.")
        conn.execute("DELETE FROM chess_games WHERE game_id = %s", (game_id,))


@router.get("/chess/openings")
def openings(colour: str = Query("white", pattern="^(white|black)$"),
             time_class: str | None = Query(None, pattern="^(bullet|blitz|rapid|daily|classical)$")):
    """How you do with each opening family as White or Black: games, wins / draws / losses, your
    score (a draw is half), the average opponent - and the same for each variation."""
    where = "colour = %(colour)s AND opening_family IS NOT NULL AND rules = 'chess'" + \
        (" AND time_class = %(tc)s" if time_class else "")
    sums = """count(*)::int AS games, count(*) FILTER (WHERE result = 'win')::int AS wins,
              count(*) FILTER (WHERE result = 'draw')::int AS draws, count(*) FILTER (WHERE result = 'loss')::int AS losses,
              round(100.0 * (count(*) FILTER (WHERE result = 'win') + 0.5 * count(*) FILTER (WHERE result = 'draw'))
                    / count(*), 1) AS score, round(avg(opp_rating))::int AS avg_opponent, max(played_at) AS last_played"""
    params = {"colour": colour, "tc": time_class}
    with db() as conn:
        families = conn.execute(f"SELECT opening_family AS name, {sums} FROM chess_games WHERE {where} "
                                "GROUP BY opening_family ORDER BY count(*) DESC, opening_family", params).fetchall()
        variations = conn.execute(f"SELECT opening_family, opening AS name, {sums} FROM chess_games WHERE {where} "
                                  "GROUP BY opening_family, opening ORDER BY count(*) DESC, opening", params).fetchall()
    by_family = {}
    for v in variations:
        by_family.setdefault(v.pop("opening_family"), []).append(v)
    for f in families:
        f["variations"] = by_family.get(f["name"], [])
    return {"colour": colour, "openings": families}
