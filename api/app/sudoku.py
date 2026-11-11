"""Sudoku (a hobby module, 2026-11-11): every puzzle you play, where you're up to, how you've done, what you've earned.

The puzzles themselves are made, graded and explained in the browser (web/src/modules/sudoku/engine.js - so a game
works in the offline copy too, and no puzzle site is ever asked). Here they're kept:

    games    sudoku_games: 9 x 9, or a 16 x 16 giant (digits 1-9 then A-G); a new puzzle, the daily one, a technique to
             practise, or one you typed in; your board as you go (digits and notes), time, mistakes, hints; solved
             (checked against the answer here) or given up. A puzzle is checked when it's saved: a full valid answer that
             agrees with its clues, and only one answer (solve_count - two answers can't be solved by logic).
    daily    one 9 x 9 puzzle a day (the browser makes it from the date, so the same day gives the same puzzle); any past
             day's can be played too
    weekly   one big, hard puzzle a week (a 16 x 16, made from the week's Monday)
    sets     puzzles in a numbered set: 'hardest' (the Hardest 100, web/src/modules/sudoku/hardest.js) or an event's path
             (modules/sudoku/events.js) - each stop once
    papers   a puzzle typed in from a newspaper or a book can say which (paper): the app doesn't fetch papers' puzzles
             (they're licensed, often paywalled, and their terms don't allow copying) - you type or paste today's in
    rating   an Elo-style rating (rating()): each finished game is a match against its puzzle - difficulty against your
             rating; your time against the par, mistakes and hints make the score - and the rank it puts you in
    summary  for Home and Today: the game in progress, today's daily, solved this week, your streaks
    stats    per difficulty (solved, best and average time; the 16 x 16s apart), every solve over time, days played,
             techniques met in hints and needed by the puzzles you solved, clean solves (no hints, no mistakes)
    awards   achievements (ACHIEVEMENTS), worked out from your games - so games from before an award existed count -
             each with when it was earned (the solve that did it) or how far you've got. Solving a game answers with
             the ones it just earned.

Solved games show on the calendar and in Recent activity (activity.py); goals can count them (goal_sources.py).
"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .db import db, found, insert_row, update_row
from .videogames import streaks

router = APIRouter(prefix="/api", tags=["sudoku"])

DIFFICULTIES = ("Easy", "Medium", "Hard", "Expert", "Extreme")
Difficulty = Literal[DIFFICULTIES]
Source = Literal["new", "daily", "weekly", "practice", "typed", "set"]
SET_KEY = r"^[a-z0-9][a-z0-9-]{1,40}$"
SYMBOLS = "0123456789ABCDEFG"                 # 10-16 are A-G
GRID = r"^[0-9A-G]{81}$|^[0-9A-G]{256}$"
TECHNIQUE = r"^[a-z_]{2,30}$"
MIN_CLUES = {9: 17, 16: 55}


# ---------------------------------------------------------------- checking a puzzle
def _geometry(n: int, x: bool = False):
    b = 3 if n == 9 else 4
    units = ([[r * n + c for c in range(n)] for r in range(n)] + [[r * n + c for r in range(n)] for c in range(n)]
             + [[(k // b * b + i // b) * n + k % b * b + i % b for i in range(n)] for k in range(n)])
    if x:                                   # Diagonal (X): both long diagonals hold every digit once too
        units += [[i * n + i for i in range(n)], [i * n + n - 1 - i for i in range(n)]]
    return b, units


GEOMETRY = {n: _geometry(n) for n in (9, 16)}
X_UNITS = _geometry(9, True)[1]


def solve_count(grid: list[int], limit: int = 2, x: bool = False) -> int:
    """How many answers (stops at `limit`): backtracking on the cell with the fewest choices, digits as bit masks.
    x = Diagonal (X): the two long diagonals count too."""
    cells = len(grid)
    n = 9 if cells == 81 else 16
    b, _ = GEOMETRY[n]
    full = (1 << n) - 1
    v = list(grid)
    rows, cols, boxes, diag = [0] * n, [0] * n, [0] * n, [0, 0]
    on = [((c // n == c % n) if x else False, (c // n + c % n == n - 1) if x else False) for c in range(cells)]
    for c, d in enumerate(v):
        if d:
            bit, r, co, bx = 1 << (d - 1), c // n, c % n, (c // n) // b * b + (c % n) // b
            if rows[r] & bit or cols[co] & bit or boxes[bx] & bit or any(on[c][k] and diag[k] & bit for k in (0, 1)):
                return 0
            rows[r] |= bit
            cols[co] |= bit
            boxes[bx] |= bit
            for k in (0, 1):
                if on[c][k]:
                    diag[k] |= bit
    where = [(c // n, c % n, (c // n) // b * b + (c % n) // b) for c in range(cells)]
    found_ = 0

    def go() -> bool:
        nonlocal found_
        best, best_mask, best_n = -1, 0, n + 1
        for c in range(cells):
            if v[c]:
                continue
            r, co, bx = where[c]
            m = full & ~(rows[r] | cols[co] | boxes[bx] | (diag[0] if on[c][0] else 0) | (diag[1] if on[c][1] else 0))
            k = bin(m).count("1")
            if k == 0:
                return False
            if k < best_n:
                best, best_mask, best_n = c, m, k
                if k == 1:
                    break
        if best < 0:
            found_ += 1
            return found_ >= limit
        r, co, bx = where[best]
        m = best_mask
        while m:
            bit = m & -m
            m ^= bit
            v[best] = bit.bit_length()
            rows[r] |= bit
            cols[co] |= bit
            boxes[bx] |= bit
            for k in (0, 1):
                if on[best][k]:
                    diag[k] |= bit
            if go():
                return True
            rows[r] &= ~bit
            cols[co] &= ~bit
            boxes[bx] &= ~bit
            for k in (0, 1):
                if on[best][k]:
                    diag[k] &= ~bit
        v[best] = 0
        return False

    go()
    return found_


def check_puzzle(puzzle: str, solution: str, size: int, variant: str = "classic") -> int:
    """A real puzzle: the answer is a full valid grid, agrees with every clue, and is the only one. Answers the clues."""
    if len(puzzle) != size * size or len(solution) != size * size:
        raise HTTPException(422, f"A {size} x {size} puzzle has {size * size} cells.")
    p, s = [SYMBOLS.index(x) for x in puzzle], [SYMBOLS.index(x) for x in solution]
    if max(p + s) > size:
        raise HTTPException(422, f"A {size} x {size} puzzle only uses the digits up to {SYMBOLS[size]}.")
    units = X_UNITS if variant == "x" else GEOMETRY[size][1]
    if any(sorted(s[c] for c in u) != list(range(1, size + 1)) for u in units):
        raise HTTPException(422, "That answer isn't a valid finished grid.")
    if any(p[c] and p[c] != s[c] for c in range(size * size)):
        raise HTTPException(422, "The answer doesn't match the puzzle's clues.")
    clues = sum(1 for x in p if x)
    if clues < MIN_CLUES[size]:
        raise HTTPException(422, f"A {size} x {size} sudoku needs at least {MIN_CLUES[size]} clues to have only one answer.")
    if solve_count(p, x=variant == "x") != 1:
        raise HTTPException(422, "That puzzle has more than one answer, so it can't be solved by logic.")
    return clues


# ---------------------------------------------------------------- games
class State(BaseModel):
    v: str = Field(pattern=GRID)                           # your digits (and the clues)
    n: list[int] = Field(min_length=81, max_length=256)    # each cell's notes (bit d-1 = d)
    m: list[list[int]] | None = Field(None, max_length=5000)   # every digit change: [second, cell, digit (0 = taken out)] - the replay


class GameIn(BaseModel):
    puzzle: str = Field(pattern=GRID)
    solution: str = Field(pattern=r"^[1-9A-G]{81}$|^[1-9A-G]{256}$")
    size: Literal[9, 16] = 9
    variant: Literal["classic", "x"] = "classic"
    source: Source = "new"
    daily_on: date | None = None
    difficulty: Difficulty
    techniques: dict[str, int] = Field(default_factory=dict, max_length=40)
    hardest: str | None = Field(None, pattern=TECHNIQUE)
    practice: str | None = Field(None, pattern=TECHNIQUE)
    week_of: date | None = None
    set_key: str | None = Field(None, pattern=SET_KEY)
    set_stop: int | None = Field(None, ge=1, le=10000)
    paper: str | None = Field(None, max_length=80)
    # A game played while the PC couldn't be reached (the offline copy) arrives with how far it got:
    state: State | None = None
    seconds: int = Field(0, ge=0, le=10 ** 7)
    mistakes: int = Field(0, ge=0, le=100000)
    hints: int = Field(0, ge=0, le=100000)


class GamePatch(BaseModel):
    state: State | None = None
    seconds: int | None = Field(None, ge=0, le=10 ** 7)
    mistakes: int | None = Field(None, ge=0, le=100000)
    hints: int | None = Field(None, ge=0, le=100000)
    hint_kinds: dict[str, int] | None = Field(None, max_length=40)
    status: Literal["playing", "solved", "gave_up"] | None = None


LIST = """SELECT game_id, size, variant, puzzle, source, daily_on, week_of, set_key, set_stop, paper, difficulty, hardest, practice, clues, status, seconds, mistakes, hints,
                 finished_at, created_at, updated_at,
                 CASE WHEN state IS NULL THEN 0 ELSE length(replace(state ->> 'v', '0', '')) END AS filled
          FROM sudoku_games"""


def fetch_game(conn, game_id: int) -> dict:
    return found(conn.execute("SELECT * FROM sudoku_games WHERE game_id = %s", (game_id,)).fetchone(), "Sudoku game")


def _clean_counts(d: dict[str, int] | None) -> dict:
    return {k: max(0, min(int(v), 10000)) for k, v in (d or {}).items() if isinstance(k, str) and len(k) <= 30}


def _check_state(state: dict, game: dict):
    if len(state["v"]) != len(game["puzzle"]) or len(state["n"]) != len(game["puzzle"]):
        raise HTTPException(422, "That board isn't this puzzle's size.")
    if any(state["v"][c] != ch for c, ch in enumerate(game["puzzle"]) if ch != "0"):
        raise HTTPException(422, "That board doesn't keep the puzzle's clues.")


@router.get("/sudoku/games")
def list_games(status: Literal["playing", "solved", "gave_up"] | None = None, limit: int = Query(100, ge=1, le=2000)):
    """Your games, the latest first (the solution isn't in the list)."""
    with db() as conn:
        where = " WHERE status = %s" if status else ""
        return conn.execute(LIST + where + " ORDER BY updated_at DESC, game_id DESC LIMIT %s",
                            (status, limit) if status else (limit,)).fetchall()


@router.post("/sudoku/games", status_code=201)
def add_game(body: GameIn):
    """A puzzle to play. Checked first (see check_puzzle). The daily one is kept once per day: asking again for a day
    that has one gives that one."""
    if (body.source == "daily") != (body.daily_on is not None):
        raise HTTPException(422, "Only the daily puzzle has a day (and it needs one).")
    if body.daily_on and body.size != 9:
        raise HTTPException(422, "The daily puzzle is a 9 x 9.")
    if (body.source == "weekly") != (body.week_of is not None) or (body.week_of and body.week_of.isoweekday() != 1):
        raise HTTPException(422, "Only the weekly puzzle has a week (its Monday).")
    if (body.source == "set") != (body.set_key is not None and body.set_stop is not None):
        raise HTTPException(422, "A puzzle from a set needs the set and its number in it.")
    if body.paper and body.source != "typed":
        raise HTTPException(422, "Only a puzzle you typed in comes from a paper.")
    if body.variant == "x" and body.size != 9:
        raise HTTPException(422, "Diagonal (X) sudoku is a 9 x 9.")
    if body.variant == "x" and (body.daily_on or body.week_of or body.set_key):
        raise HTTPException(422, "The daily, the weekly and the sets are classic sudoku.")
    clues = check_puzzle(body.puzzle, body.solution, body.size, body.variant)
    if body.state:
        _check_state(body.state.model_dump(), {"puzzle": body.puzzle})
    data = body.model_dump(exclude={"state"})
    data["paper"] = (body.paper or "").strip() or None
    data.update(clues=clues, techniques=Jsonb(_clean_counts(body.techniques)),
                state=Jsonb(body.state.model_dump()) if body.state else None)
    with db() as conn:
        had = (conn.execute("SELECT game_id FROM sudoku_games WHERE daily_on = %s", (body.daily_on,)).fetchone() if body.daily_on
               else conn.execute("SELECT game_id FROM sudoku_games WHERE week_of = %s", (body.week_of,)).fetchone() if body.week_of
               else conn.execute("SELECT game_id FROM sudoku_games WHERE set_key = %s AND set_stop = %s", (body.set_key, body.set_stop)).fetchone()
               if body.set_key else None)
        if had:                              # the daily / weekly / a set's stop: once each
            return fetch_game(conn, had["game_id"])
        game_id = insert_row(conn, "sudoku_games", data, "game_id")
        return fetch_game(conn, game_id)


@router.get("/sudoku/daily")
def daily(day: date | None = None):
    """The daily puzzle for a day (today by default) if you've opened it, else null."""
    with db() as conn:
        day = day or conn.execute("SELECT current_date AS d").fetchone()["d"]
        row = conn.execute("SELECT game_id FROM sudoku_games WHERE daily_on = %s", (day,)).fetchone()
        return fetch_game(conn, row["game_id"]) if row else None


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


@router.get("/sudoku/weekly")
def weekly(week: date | None = None):
    """The weekly puzzle for the week holding `week` (this week by default) if you've opened it, else null."""
    with db() as conn:
        week = monday(week or _today(conn))
        row = conn.execute("SELECT game_id FROM sudoku_games WHERE week_of = %s", (week,)).fetchone()
        return fetch_game(conn, row["game_id"]) if row else None


@router.get("/sudoku/dailies")
def dailies(days: int = Query(42, ge=1, le=400)):
    """The daily puzzles of the last `days` days you've opened (to play a missed one)."""
    with db() as conn:
        return conn.execute(LIST + " WHERE daily_on >= current_date - %s ORDER BY daily_on DESC", (days,)).fetchall()


@router.get("/sudoku/sets/{set_key}")
def set_games(set_key: str = Path(pattern=SET_KEY)):
    """Every stop of a set you've opened (the Hardest 100, an event's path): {stop: game}."""
    with db() as conn:
        rows = conn.execute(LIST + " WHERE set_key = %s ORDER BY set_stop", (set_key,)).fetchall()
    return {str(r["set_stop"]): r for r in rows}


LIBRARY_CREDIT = {"hardest": "The sudoku community's hardest puzzles (rated 11+): the enjoysudoku.com forum's collection, "
                              "as shared in the tdoku project's benchmark data."}


@router.get("/sudoku/library/{list_key}")
def library(list_key: str = Path(pattern=SET_KEY), first: int = Query(1, ge=1), last: int = Query(1000, ge=1, le=100000)):
    """A list from the library (load-sudoku-library.ps1), ranks first..last - puzzles: [] when it isn't loaded here."""
    with db() as conn:
        rows = conn.execute("SELECT rank, puzzle, measure FROM sudoku_library WHERE list_key = %s AND rank BETWEEN %s AND %s "
                            "ORDER BY rank", (list_key, first, last)).fetchall()
    return {"list": list_key, "credit": LIBRARY_CREDIT.get(list_key) if rows else None, "puzzles": rows}


@router.get("/sudoku/games/{game_id}")
def get_game(game_id: int):
    with db() as conn:
        return fetch_game(conn, game_id)


@router.patch("/sudoku/games/{game_id}")
def update_game(game_id: int, body: GamePatch):
    """Where you're up to (saved as you play), and the end: solved (your board must be the answer) or given up. A solve
    answers with the achievements it just earned (new_awards)."""
    data = body.model_dump(exclude_unset=True)
    for k in ("seconds", "mistakes", "hints", "status", "state", "hint_kinds"):
        if k in data and data[k] is None:
            raise HTTPException(422, f"{k.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        game = fetch_game(conn, game_id)
        if game["status"] != "playing" and set(data) - {"status"} and data.get("status", game["status"]) != "playing":
            raise HTTPException(409, "That game is finished.")
        if "state" in data:
            _check_state(data["state"], game)
            data["state"] = Jsonb(data["state"])
        if "hint_kinds" in data:
            data["hint_kinds"] = Jsonb(_clean_counts(data["hint_kinds"]))
        status = data.get("status")
        solving = status == "solved" and game["status"] != "solved"
        if solving:
            board = body.state.v if body.state else (game["state"] or {}).get("v")
            if board != game["solution"]:
                raise HTTPException(422, "That board isn't the answer yet.")
            data["finished_at"] = conn.execute("SELECT now() AS t").fetchone()["t"]
        elif status == "gave_up" and game["status"] == "playing":
            data["finished_at"] = conn.execute("SELECT now() AS t").fetchone()["t"]
        elif status == "playing":
            data["finished_at"] = None
        update_row(conn, "sudoku_games", "game_id", game_id, data)
        out = fetch_game(conn, game_id)
        if solving:
            out["new_awards"] = [a for a in awards(conn) if a["game_id"] == game_id]
        if solving or (status == "gave_up" and game["status"] == "playing"):
            r = rating(conn)
            out["rating"] = {**next((x for x in r["games"] if x["game_id"] == game_id), {}), "now": r["now"], "rank": r["rank"]}
        return out


@router.delete("/sudoku/games/{game_id}", status_code=204)
def delete_game(game_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM sudoku_games WHERE game_id = %s RETURNING game_id", (game_id,)).fetchone(), "Sudoku game")
    return Response(status_code=204)


# ---------------------------------------------------------------- numbers
def _today(conn) -> date:
    return conn.execute("SELECT current_date AS d").fetchone()["d"]       # Brisbane


def _days(conn, where: str = "") -> list[date]:
    return [r["d"] for r in conn.execute(
        f"SELECT DISTINCT finished_at::date AS d FROM sudoku_games WHERE status = 'solved' {where} ORDER BY 1").fetchall()]


@router.get("/sudoku/summary")
def summary():
    """For Home and Today: the game in progress, today's daily, solved this week / ever, your streaks (days in a row
    with a solve; daily puzzles in a row), achievements earned."""
    with db() as conn:
        today = _today(conn)
        s = conn.execute("""
            SELECT count(*) FILTER (WHERE status = 'solved')::int AS solved,
                   count(*) FILTER (WHERE status = 'solved' AND finished_at >= date_trunc('week', current_date))::int AS solved_this_week,
                   count(*) FILTER (WHERE status = 'solved' AND finished_at >= date_trunc('month', current_date))::int AS solved_this_month,
                   count(*) FILTER (WHERE status = 'playing')::int AS playing_count
            FROM sudoku_games""").fetchone()
        s["playing"] = conn.execute(LIST + " WHERE status = 'playing' ORDER BY updated_at DESC LIMIT 1").fetchone()
        s["today"] = today
        s["daily"] = conn.execute(LIST + " WHERE daily_on = %s", (today,)).fetchone()
        s["streak"] = streaks(_days(conn), today)
        daily_days = [r["daily_on"] for r in conn.execute(
            "SELECT daily_on FROM sudoku_games WHERE status = 'solved' AND daily_on IS NOT NULL ORDER BY 1").fetchall()]
        s["daily_streak"] = streaks(daily_days, today)
        s["recent"] = conn.execute(LIST + " WHERE status = 'solved' ORDER BY finished_at DESC LIMIT 5").fetchall()
        s["weekly"] = conn.execute(LIST + " WHERE week_of = %s", (monday(today),)).fetchone()
        s["week_of"] = monday(today)
        r = rating(conn)
        s["rating"] = {"now": r["now"], "peak": r["peak"], "rank": r["rank"], "games": len(r["games"]),
                       "last": r["games"][-1] if r["games"] else None}
        s["sets"] = {x["set_key"]: {"solved": x["solved"], "furthest": x["furthest"]} for x in conn.execute(
            """SELECT set_key, count(*) FILTER (WHERE status = 'solved')::int AS solved,
                      COALESCE(max(set_stop) FILTER (WHERE status = 'solved'), 0) AS furthest
               FROM sudoku_games WHERE set_key IS NOT NULL GROUP BY set_key""").fetchall()}
        got = [a for a in awards(conn) if a["unlocked_at"]]
        s["awards"] = {"earned": len(got), "of": len(ACHIEVEMENTS),
                       "latest": sorted(got, key=lambda a: a["unlocked_at"], reverse=True)[:3]}
    return s


def _per_difficulty(conn, size: int) -> list[dict]:
    per = {r["difficulty"]: r for r in conn.execute("""
        SELECT difficulty, count(*) FILTER (WHERE status = 'solved')::int AS solved,
               count(*) FILTER (WHERE status = 'gave_up')::int AS gave_up,
               min(seconds) FILTER (WHERE status = 'solved')::int AS best,
               round(avg(seconds) FILTER (WHERE status = 'solved'))::int AS average,
               count(*) FILTER (WHERE status = 'solved' AND hints = 0 AND mistakes = 0)::int AS clean
        FROM sudoku_games WHERE size = %s AND variant = 'classic' GROUP BY difficulty""", (size,)).fetchall()}
    levels = DIFFICULTIES if size == 9 else DIFFICULTIES[:3]
    for d in levels:                                     # the last ten solves' average: are you getting faster?
        recent = conn.execute("""SELECT round(avg(seconds))::int AS a FROM (SELECT seconds FROM sudoku_games
                                 WHERE status = 'solved' AND difficulty = %s AND size = %s AND variant = 'classic' ORDER BY finished_at DESC LIMIT 10) x""",
                              (d, size)).fetchone()["a"]
        per.setdefault(d, {"difficulty": d, "solved": 0, "gave_up": 0, "best": None, "average": None, "clean": 0})["recent"] = recent
    return [per[d] for d in levels]


@router.get("/sudoku/stats")
def stats(days: int = Query(365, ge=7, le=3660)):
    """How you've done: per difficulty (9 x 9; giant = the 16 x 16s), every solve (time over time), days played,
    techniques, clean solves."""
    with db() as conn:
        today = _today(conn)
        solves = conn.execute("""SELECT game_id, size, finished_at::date AS day, difficulty, seconds, hints, mistakes, source FROM sudoku_games
                                 WHERE status = 'solved' AND finished_at >= current_date - %s ORDER BY finished_at""", (days,)).fetchall()
        by_day = conn.execute("""SELECT finished_at::date AS day, count(*)::int AS count FROM sudoku_games
                                 WHERE status = 'solved' AND finished_at >= current_date - 371 GROUP BY 1 ORDER BY 1""").fetchall()
        # Where your wrong digits go (classic 9 x 9s, from each game's moves): by cell, by box, by digit.
        by_cell, by_digit = [0] * 81, {}
        for g in conn.execute("""SELECT solution, state FROM sudoku_games WHERE size = 9 AND variant = 'classic'
                                 AND status IN ('solved', 'gave_up') AND state ? 'm'""").fetchall():
            for move in (g["state"] or {}).get("m") or []:
                if len(move) >= 3 and 0 <= move[1] < 81 and move[2] and str(move[2]) != g["solution"][move[1]]:
                    by_cell[move[1]] += 1
                    by_digit[str(move[2])] = by_digit.get(str(move[2]), 0) + 1
        needed, hinted = {}, {}
        for r in conn.execute("SELECT techniques, hint_kinds, status FROM sudoku_games").fetchall():
            if r["status"] == "solved":
                for k in (r["techniques"] or {}):
                    needed[k] = needed.get(k, 0) + 1
            for k, n in (r["hint_kinds"] or {}).items():
                hinted[k] = hinted.get(k, 0) + n
        totals = conn.execute("""SELECT count(*) FILTER (WHERE status = 'solved')::int AS solved,
                                        count(*) FILTER (WHERE status = 'gave_up')::int AS gave_up,
                                        COALESCE(sum(seconds), 0)::int AS seconds, COALESCE(sum(hints), 0)::int AS hints,
                                        count(*) FILTER (WHERE status = 'solved' AND hints = 0 AND mistakes = 0)::int AS clean,
                                        count(*) FILTER (WHERE status = 'solved' AND daily_on IS NOT NULL)::int AS dailies,
                                        count(*) FILTER (WHERE status = 'solved' AND size = 16)::int AS giants
                                 FROM sudoku_games""").fetchone()
        r = rating(conn)
        return {"rating": [{"day": g["finished_at"].date(), "rating": g["after"]} for g in r["games"]],
                "today": today, "per_difficulty": _per_difficulty(conn, 9), "giant": _per_difficulty(conn, 16), "solves": solves,
                "by_day": by_day, "techniques_needed": needed, "hints_by_technique": hinted, "totals": totals,
                "streak": streaks(_days(conn), today), "since": today - timedelta(days=days),
                "mistakes_by_cell": by_cell, "mistakes_by_digit": by_digit}


# ---------------------------------------------------------------- achievements
# (key, group, name, what it takes, target). Worked out in awards() from the solved games, oldest first.
SPEED = {"Easy": 300, "Medium": 480, "Hard": 900, "Expert": 1500, "Extreme": 2700}
PRACTISABLE = ["pointing", "claiming", "naked_pair", "hidden_pair", "naked_triple", "hidden_triple", "naked_quad",
               "x_wing", "swordfish", "xy_wing", "xyz_wing"]
WINGS = ["x_wing", "swordfish", "xy_wing", "xyz_wing"]
# Events: their paths (modules/sudoku/events.js - the same keys and lengths).
EVENTS = {"grand-tour": 30, "patagonia-trail": 25}          # (events_all: these two)


def event_length(key: str | None) -> int | None:
    """How many stops an event's path has: the fixed ones, and each year's Advent calendar (advent-<year>, 24)."""
    if key in EVENTS:
        return EVENTS[key]
    return 24 if key and key.startswith("advent-") else None
ACHIEVEMENTS = [
    ("first", "Milestones", "First grid", "Solve your first sudoku.", 1),
    ("solved_10", "Milestones", "Ten down", "Solve 10 sudokus.", 10),
    ("solved_50", "Milestones", "Half a hundred", "Solve 50 sudokus.", 50),
    ("solved_100", "Milestones", "Centurion", "Solve 100 sudokus.", 100),
    ("solved_250", "Milestones", "Grid devotee", "Solve 250 sudokus.", 250),
    ("solved_500", "Milestones", "Five hundred", "Solve 500 sudokus.", 500),
    ("solved_1000", "Milestones", "The thousand", "Solve 1,000 sudokus.", 1000),
    ("medium", "Difficulty", "Stepping up", "Solve a Medium puzzle.", 1),
    ("hard", "Difficulty", "Hard won", "Solve a Hard puzzle.", 1),
    ("expert", "Difficulty", "Expert", "Solve an Expert puzzle.", 1),
    ("extreme", "Difficulty", "Beyond the techniques", "Solve an Extreme puzzle.", 1),
    ("all_levels", "Difficulty", "Full range", "Solve a puzzle at every difficulty.", 5),
    ("expert_10", "Difficulty", "Expert ten", "Solve 10 Expert or Extreme puzzles.", 10),
    ("extreme_10", "Difficulty", "Chain gang", "Solve 10 Extreme puzzles.", 10),
    ("clean", "Clean", "Clean sheet", "Solve one with no hints and no mistakes.", 1),
    ("clean_10", "Clean", "Ten clean", "Solve 10 with no hints and no mistakes.", 10),
    ("clean_hard", "Clean", "Hard and clean", "Solve a Hard (or harder) one with no hints and no mistakes.", 1),
    ("clean_expert", "Clean", "Flawless expert", "Solve an Expert (or Extreme) one with no hints and no mistakes.", 1),
    ("no_hints_extreme", "Clean", "On my own", "Solve an Extreme puzzle without a hint.", 1),
    ("fast_easy", "Speed", "Quick start", "Solve an Easy one in under 5 minutes.", 1),
    ("lightning", "Speed", "Lightning", "Solve an Easy one in under 3 minutes.", 1),
    ("fast_medium", "Speed", "Brisk", "Solve a Medium one in under 8 minutes.", 1),
    ("fast_hard", "Speed", "Sharp", "Solve a Hard one in under 15 minutes.", 1),
    ("fast_expert", "Speed", "Swift expert", "Solve an Expert one in under 25 minutes.", 1),
    ("fast_extreme", "Speed", "Extreme pace", "Solve an Extreme one in under 45 minutes.", 1),
    ("daily", "Daily", "Daily habit", "Solve a daily puzzle.", 1),
    ("daily_7", "Daily", "A week of dailies", "Solve the daily puzzle 7 days in a row.", 7),
    ("daily_30", "Daily", "A month of dailies", "Solve the daily puzzle 30 days in a row.", 30),
    ("daily_100", "Daily", "Hundred-day run", "Solve the daily puzzle 100 days in a row.", 100),
    ("dailies_50", "Daily", "Regular", "Solve 50 daily puzzles.", 50),
    ("streak_7", "Streaks", "Seven days", "Solve a puzzle 7 days in a row.", 7),
    ("streak_30", "Streaks", "Thirty days", "Solve a puzzle 30 days in a row.", 30),
    ("marathon", "Streaks", "Marathon", "Solve 5 puzzles in one day.", 5),
    ("practice", "Learning", "Student", "Solve a practice puzzle.", 1),
    ("practice_5", "Learning", "Toolkit", "Solve practice puzzles for 5 different techniques.", 5),
    ("practice_all", "Learning", "Every technique", "Solve a practice puzzle for every technique.", len(PRACTISABLE)),
    ("wings", "Learning", "Wing collector", "Solve puzzles that needed an X-Wing, a Swordfish, an XY-Wing and an XYZ-Wing.", 4),
    ("easy_25", "Difficulty", "Easy does it", "Solve 25 Easy puzzles.", 25),
    ("easy_100", "Difficulty", "Easy hundred", "Solve 100 Easy puzzles.", 100),
    ("medium_25", "Difficulty", "Middle ground", "Solve 25 Medium puzzles.", 25),
    ("medium_100", "Difficulty", "Medium hundred", "Solve 100 Medium puzzles.", 100),
    ("hard_10", "Difficulty", "Hard ten", "Solve 10 Hard puzzles.", 10),
    ("hard_50", "Difficulty", "Hard fifty", "Solve 50 Hard puzzles.", 50),
    ("hard_100", "Difficulty", "Hard hundred", "Solve 100 Hard puzzles.", 100),
    ("expert_25", "Difficulty", "Expert twenty-five", "Solve 25 Expert puzzles.", 25),
    ("expert_100", "Difficulty", "Expert hundred", "Solve 100 Expert puzzles.", 100),
    ("extreme_25", "Difficulty", "Extreme twenty-five", "Solve 25 Extreme puzzles.", 25),
    ("weekly", "Weekly", "The big one", "Solve a weekly puzzle.", 1),
    ("weekly_4", "Weekly", "Four in a row", "Solve the weekly puzzle 4 weeks in a row.", 4),
    ("weekly_12", "Weekly", "Twelve weeks", "Solve 12 weekly puzzles.", 12),
    ("weekly_52", "Weekly", "A year of weeklies", "Solve 52 weekly puzzles.", 52),
    ("hardest_1", "Hardest 100", "Into the deep end", "Solve one of the Hardest 100.", 1),
    ("hardest_10", "Hardest 100", "Ten of the toughest", "Solve 10 of the Hardest 100.", 10),
    ("hardest_25", "Hardest 100", "A quarter of the way", "Solve 25 of the Hardest 100.", 25),
    ("hardest_50", "Hardest 100", "Halfway down the list", "Solve 50 of the Hardest 100.", 50),
    ("hardest_100", "Hardest 100", "The whole list", "Solve all of the Hardest 100.", 100),
    ("hardest_top", "Hardest 100", "Number one", "Solve number 100 - the hardest of them all.", 1),
    ("event_10", "Events", "On the trail", "Reach stop 10 on an event's path.", 10),
    ("event_done", "Events", "Journey's end", "Finish an event's whole path.", 1),
    ("events_all", "Events", "Every road", "Finish The Grand Tour and the Patagonia Trail.", len(EVENTS)),
    ("advent", "Events", "Every door opened", "Finish an Advent calendar.", 1),
    ("rank_solver", "Rank", "Solver", "Reach the Solver rank (rating 1050).", 1050),
    ("rank_adept", "Rank", "Adept", "Reach the Adept rank (rating 1200).", 1200),
    ("rank_expert", "Rank", "Expert rank", "Reach the Expert rank (rating 1400).", 1400),
    ("rank_master", "Rank", "Master", "Reach the Master rank (rating 1600).", 1600),
    ("rank_grandmaster", "Rank", "Grandmaster", "Reach the Grandmaster rank (rating 1800).", 1800),
    ("rank_legend", "Rank", "Legend", "Reach the Legend rank (rating 2000).", 2000),
    ("paper", "Papers", "Morning paper", "Solve a puzzle typed in from a newspaper.", 1),
    ("paper_10", "Papers", "Paper round", "Solve 10 puzzles from newspapers.", 10),
    ("papers_3", "Papers", "Well read", "Solve puzzles from 3 different papers.", 3),
    ("x_1", "Diagonal", "Thinking diagonally", "Solve a Diagonal (X) sudoku.", 1),
    ("x_10", "Diagonal", "Cross-eyed", "Solve 10 Diagonal (X) sudokus.", 10),
    ("x_hard", "Diagonal", "Hard angles", "Solve a Hard Diagonal (X) sudoku.", 1),
    ("giant", "Giant", "Going big", "Solve a 16 x 16.", 1),
    ("giant_hard", "Giant", "Giant slayer", "Solve a Hard 16 x 16.", 1),
    ("giant_10", "Giant", "Big ten", "Solve 10 16 x 16s.", 10),
    ("typed", "Habits", "From the page", "Solve a puzzle you typed in from a book or a paper.", 1),
    ("night_owl", "Habits", "Night owl", "Solve one between midnight and 4 am.", 1),
    ("early_bird", "Habits", "Early bird", "Solve one between 5 and 7 am.", 1),
    ("long_haul", "Habits", "The long haul", "Spend over an hour on one puzzle - and solve it.", 1),
]


def _run_ending(days: set, day: date) -> int:
    n = 0
    while day - timedelta(days=n) in days:
        n += 1
    return n


def awards(conn) -> list[dict]:
    """Every achievement: earned (when, and by which game) or how far you've got."""
    after = {g["game_id"]: g["after"] for g in rating(conn)["games"]}
    rows = conn.execute("""SELECT game_id, size, variant, difficulty, source, daily_on, week_of, set_key, set_stop, paper, practice, techniques,
                                  seconds, hints, mistakes, finished_at, finished_at::date AS day
                           FROM sudoku_games WHERE status = 'solved' ORDER BY finished_at, game_id""").fetchall()
    meta = {k: (group, name, about, target) for k, group, name, about, target in ACHIEVEMENTS}
    progress = {k: 0 for k in meta}
    earned: dict[str, tuple] = {}
    n = {"solved": 0, "expert": 0, "extreme": 0, "clean": 0, "dailies": 0, "giants": 0}
    levels, practised, wings, solve_days, daily_days, per_day = set(), set(), set(), set(), set(), {}
    by_level, weeks, hardest, papers, event_stops, events_done = {}, set(), set(), set(), {}, set()
    paper_n = 0
    x_n = 0

    def hit(key, value, g):
        progress[key] = max(progress[key], value)
        if key not in earned and value >= meta[key][3]:
            earned[key] = (g["finished_at"], g["game_id"])

    for g in rows:
        diff, clean = g["difficulty"], g["hints"] == 0 and g["mistakes"] == 0
        rank = DIFFICULTIES.index(diff)
        n["solved"] += 1
        for key in ("first", "solved_10", "solved_50", "solved_100", "solved_250", "solved_500", "solved_1000"):
            hit(key, n["solved"], g)
        if g["size"] == 9 and g["variant"] == "classic":
            levels.add(diff)
            hit("all_levels", len(levels), g)
            for key, level in (("medium", "Medium"), ("hard", "Hard"), ("expert", "Expert"), ("extreme", "Extreme")):
                if rank >= DIFFICULTIES.index(level):
                    hit(key, 1, g)
            if rank >= 3:
                n["expert"] += 1
                hit("expert_10", n["expert"], g)
            if diff == "Extreme":
                n["extreme"] += 1
                hit("extreme_10", n["extreme"], g)
                if g["hints"] == 0:
                    hit("no_hints_extreme", 1, g)
            for key, level in (("fast_easy", "Easy"), ("fast_medium", "Medium"), ("fast_hard", "Hard"), ("fast_expert", "Expert"), ("fast_extreme", "Extreme")):
                if diff == level and g["seconds"] < SPEED[level]:
                    hit(key, 1, g)
            if diff == "Easy" and g["seconds"] < 180:
                hit("lightning", 1, g)
        if clean:
            n["clean"] += 1
            hit("clean", 1, g)
            hit("clean_10", n["clean"], g)
            if rank >= 2:
                hit("clean_hard", 1, g)
            if rank >= 3:
                hit("clean_expert", 1, g)
        if g["daily_on"]:
            n["dailies"] += 1
            daily_days.add(g["daily_on"])
            run = _run_ending(daily_days, g["daily_on"])
            hit("daily", 1, g)
            hit("dailies_50", n["dailies"], g)
            for key in ("daily_7", "daily_30", "daily_100"):
                hit(key, run, g)
        solve_days.add(g["day"])
        run = _run_ending(solve_days, g["day"])
        hit("streak_7", run, g)
        hit("streak_30", run, g)
        per_day[g["day"]] = per_day.get(g["day"], 0) + 1
        hit("marathon", per_day[g["day"]], g)
        if g["practice"]:
            hit("practice", 1, g)
            if g["practice"] in PRACTISABLE:
                practised.add(g["practice"])
            hit("practice_5", len(practised), g)
            hit("practice_all", len(practised), g)
        wings |= {w for w in WINGS if w in (g["techniques"] or {})}
        hit("wings", len(wings), g)
        if g["size"] == 9 and g["variant"] == "classic":
            by_level[diff] = by_level.get(diff, 0) + 1
            for key, level in (("easy_25", "Easy"), ("easy_100", "Easy"), ("medium_25", "Medium"), ("medium_100", "Medium"),
                               ("hard_10", "Hard"), ("hard_50", "Hard"), ("hard_100", "Hard"), ("expert_25", "Expert"),
                               ("expert_100", "Expert"), ("extreme_25", "Extreme")):
                if diff == level:
                    hit(key, by_level[diff], g)
        if g["week_of"]:
            weeks.add(g["week_of"])
            hit("weekly", 1, g)
            hit("weekly_12", len(weeks), g)
            hit("weekly_52", len(weeks), g)
            run = 0
            while g["week_of"] - timedelta(weeks=run) in weeks:
                run += 1
            hit("weekly_4", run, g)
        if g["set_key"] == "hardest":
            hardest.add(g["set_stop"])
            for key in ("hardest_1", "hardest_10", "hardest_25", "hardest_50", "hardest_100"):
                hit(key, len(hardest), g)
            if g["set_stop"] == 100:
                hit("hardest_top", 1, g)
        elif event_length(g["set_key"]):
            done = event_stops.setdefault(g["set_key"], set())
            done.add(g["set_stop"])
            hit("event_10", max(done), g)
            if len(done) >= event_length(g["set_key"]):
                hit("event_done", 1, g)
                if g["set_key"] in EVENTS:
                    events_done.add(g["set_key"])
                if g["set_key"].startswith("advent-"):
                    hit("advent", 1, g)
            hit("events_all", len(events_done), g)
        if g["variant"] == "x":
            x_n += 1
            hit("x_1", 1, g)
            hit("x_10", x_n, g)
            if rank >= 2:
                hit("x_hard", 1, g)
        if g["paper"]:
            paper_n += 1
            papers.add(g["paper"].lower())
            hit("paper", 1, g)
            hit("paper_10", paper_n, g)
            hit("papers_3", len(papers), g)
        if g["game_id"] in after:
            for key in ("rank_solver", "rank_adept", "rank_expert", "rank_master", "rank_grandmaster", "rank_legend"):
                hit(key, after[g["game_id"]], g)
        if g["size"] == 16:
            n["giants"] += 1
            hit("giant", 1, g)
            hit("giant_10", n["giants"], g)
            if rank >= 2:
                hit("giant_hard", 1, g)
        if g["source"] == "typed":
            hit("typed", 1, g)
        hour = g["finished_at"].hour
        if hour < 4:
            hit("night_owl", 1, g)
        if 5 <= hour < 7:
            hit("early_bird", 1, g)
        if g["seconds"] > 3600:
            hit("long_haul", 1, g)

    out = []
    for key, group, name, about, target in ACHIEVEMENTS:
        when, game_id = earned.get(key, (None, None))
        out.append({"key": key, "group": group, "name": name, "about": about, "target": target,
                    "progress": min(progress[key], target), "unlocked_at": when, "game_id": game_id})
    return out


@router.get("/sudoku/achievements")
def achievements():
    """Every achievement, earned or not, in its group."""
    with db() as conn:
        return awards(conn)


# ---------------------------------------------------------------- rating
# Each finished game (practice lessons aside) is a match: you against the puzzle. The puzzle's rating comes from its
# difficulty (a 16 x 16 or one of the Hardest 100 a bit more); your score is 1 for a solve in par time with no mistakes
# or hints - less the slower you were (down to 0.35 at 1.8 x par) and for each mistake (0.06) and hint (0.12) - and 0 for
# giving up. Elo: change = K * (score - expected), expected = 1 / (1 + 10 ^ ((puzzle - you) / 400)). K = 40 for your
# first 20 games (finding your level), then 24. Everyone starts at 1000.
PUZZLE_RATING = {"Easy": 800, "Medium": 1050, "Hard": 1300, "Expert": 1600, "Extreme": 1900}
PAR = {"Easy": 360, "Medium": 600, "Hard": 1080, "Expert": 1800, "Extreme": 3000}       # seconds, 9 x 9
RANKS = [(0, "Novice"), (900, "Apprentice"), (1050, "Solver"), (1200, "Adept"), (1400, "Expert"), (1600, "Master"),
         (1800, "Grandmaster"), (2000, "Legend")]
START = 1000


def rank_of(r: int) -> dict:
    i = max(k for k, (at, _) in enumerate(RANKS) if r >= at)
    nxt = RANKS[i + 1] if i + 1 < len(RANKS) else None
    return {"name": RANKS[i][1], "from": RANKS[i][0], "next": nxt and {"name": nxt[1], "at": nxt[0]}}


def puzzle_rating(g: dict) -> int:
    r = PUZZLE_RATING[g["difficulty"]] + (150 if g["size"] == 16 else 0) + (75 if g.get("variant") == "x" else 0)
    if g["set_key"] == "hardest":
        r += 100 + 2 * (g["set_stop"] or 0)        # the list gets harder as it goes: #100 is rated 2200
    return r


def score_of(g: dict) -> float:
    if g["status"] != "solved":
        return 0.0
    par = PAR[g["difficulty"]] * (3 if g["size"] == 16 else 1)
    pace = max(0.35, min(1.0, 1.25 - 0.5 * g["seconds"] / par))
    return max(0.0, min(1.0, pace - min(0.3, 0.06 * g["mistakes"]) - min(0.6, 0.12 * g["hints"])))


def rating(conn) -> dict:
    """Your rating now, at its peak, your rank, and every rated game with its change."""
    rows = conn.execute("""SELECT game_id, size, variant, difficulty, status, seconds, mistakes, hints, set_key, set_stop, finished_at
                           FROM sudoku_games WHERE status IN ('solved', 'gave_up') AND source <> 'practice'
                           ORDER BY finished_at, game_id""").fetchall()
    r, peak, games = START, START, []
    for i, g in enumerate(rows):
        opp = puzzle_rating(g)
        expected = 1 / (1 + 10 ** ((opp - r) / 400))
        score = score_of(g)
        change = round((40 if i < 20 else 24) * (score - expected))
        games.append({"game_id": g["game_id"], "before": r, "after": r + change, "change": change, "score": round(score, 2),
                      "expected": round(expected, 2), "puzzle": opp, "finished_at": g["finished_at"], "difficulty": g["difficulty"]})
        r += change
        peak = max(peak, r)
    return {"now": r, "peak": peak, "rank": rank_of(r), "games": games, "ranks": [{"at": at, "name": name} for at, name in RANKS]}


@router.get("/sudoku/rating")
def get_rating():
    """Your rating, rank, and how it got there (the latest 500 games)."""
    with db() as conn:
        r = rating(conn)
    return {**r, "games": r["games"][-500:]}
