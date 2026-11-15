"""Board games: the people you play with, who sat at each play and how they scored, and what that adds up to
(94_board_game_table.sql). Included before boardgames.py: /board-games/players would otherwise hit
/board-games/{game_id}.

    players   board_game_players: everyone you play with, once - one can be you (is_me). Listed most played lately
              first (the order the play forms offer them in), with plays, wins and win rate. A player in plays can't
              be deleted: merge them into another (a typo, a nickname) instead.
    groups    board_game_groups: a usual group ("Thursday crew") added to a play in one tap
    seats     board_game_play_players, written by save_seats for every play: score (typed, or the sum of its score
              sheet's parts, or of the +/- taps), place and who won - worked out from the scores and how the game is
              scored (highest / lowest wins, co-op: the table wins or loses together, no score), unless you said who
              won (a tie-break). Each seat knows whether it was that person's first play of the game.
    stats     wins and head-to-heads (you against each player), per game: plays, average teach and play time, your
              best and average score, the record and who holds it, how much fun it was
    extras    stats also has your H-index (games played at least that many times), win streaks (yours and each
              player's) and the first player's win rate - overall and per game (the helpers just above stats)
    photos    board_game_play_photos: the final board or the table, on a play or a live one (moved on finishing)
"""
import re
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .images import photo_response, read_photo

router = APIRouter(prefix="/api", tags=["board games"])

SPLIT = re.compile(r"\s*(?:,|&|\s+and\s+)\s*", re.I)
ME_WORDS = {"me", "myself"}
EVERYONE = {"everyone", "all", "all of us", "we", "us"}     # a winner that means the whole table won together


class SeatIn(BaseModel):
    """Someone at a play: a player you have (player_id) or a name (found in your players, any case, or added)."""
    player_id: int | None = None
    name: str | None = Field(None, max_length=80)
    score: Decimal | None = Field(None, ge=-100000, le=100000)
    parts: dict[str, Decimal] | None = None        # the game's score sheet: {"Birds": 34, "Eggs": 12}
    adds: list[Decimal] = Field(default_factory=list, max_length=500)   # the +/- taps, in order
    team: str | None = Field(None, max_length=40)
    colour: str | None = Field(None, max_length=40)
    won: bool | None = None                        # said by hand (a tie-break, a game without scores)


class PlayerIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    is_me: bool = False
    notes: str | None = None


class PlayerPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    is_me: bool | None = None
    notes: str | None = None


class MergeIn(BaseModel):
    into: int                                      # the player who stays


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    player_ids: list[int] = Field(default_factory=list, max_length=30)


class GroupPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    player_ids: list[int] | None = Field(None, max_length=30)


# ---------------------------------------------------------------------------
# Seats: who played, scores, places, winners
# ---------------------------------------------------------------------------
def player_for(conn, name: str) -> int:
    """A player by name (any case), added if new. "me" is you, once one of your players is."""
    name = " ".join(name.split())
    if not name:
        raise HTTPException(422, "A player needs a name.")
    if name.lower() in ME_WORDS:
        me = conn.execute("SELECT player_id FROM board_game_players WHERE is_me").fetchone()
        if me:
            return me["player_id"]
    row = conn.execute("SELECT player_id FROM board_game_players WHERE lower(name) = lower(%s)", (name,)).fetchone()
    if row:
        return row["player_id"]
    return insert_row(conn, "board_game_players", {"name": name}, "player_id")


def resolve(conn, seats: list[SeatIn]) -> list[dict]:
    """Seats with a player_id each (names found or added); the same person twice is refused."""
    out = []
    for s in seats:
        if s.player_id is not None:
            found(conn.execute("SELECT 1 FROM board_game_players WHERE player_id = %s", (s.player_id,)).fetchone(), "Player")
            pid = s.player_id
        elif s.name and s.name.strip():
            pid = player_for(conn, s.name)
        else:
            raise HTTPException(422, "Each player needs a name.")
        if any(o["player_id"] == pid for o in out):
            raise HTTPException(422, "The same person is in the play twice.")
        out.append({**s.model_dump(exclude={"name"}), "player_id": pid})
    return out


def seats_from_text(players: str | None, winner: str | None) -> list[SeatIn]:
    """Typed text ("Alex Morgan, Sam and me", winner "Alex") as seats. A winner is the listed player with that
    name, or whose name starts with it (Alex -> Alex Morgan); a winner who isn't listed played too. "Everyone"
    won together; a team ("Team blue") isn't a person."""
    names = [n.strip() for n in SPLIT.split(players or "") if n.strip()]
    if (winner or "").strip().lower() in EVERYONE:
        return [SeatIn(name=n, won=True) for n in names]
    won = set()
    for w in (w.strip() for w in SPLIT.split(winner or "") if w.strip()):
        low = w.lower()
        if low.startswith("team "):
            continue
        match = (next((n for n in names if n.lower() == low), None)
                 or next((n for n in names if n.lower().startswith(low + " ")), None))
        if match is None:
            names.append(w)
            match = w
        won.add(match.lower())
    return [SeatIn(name=n, won=n.lower() in won or None) for n in names]


def total(seat: dict) -> Decimal | None:
    """A seat's score: typed, else its score sheet's parts added up, else its +/- taps."""
    if seat.get("score") is not None:
        return num(seat["score"])
    if seat.get("parts"):
        return sum((num(v) for v in seat["parts"].values() if v is not None), Decimal(0))
    if seat.get("adds"):
        return sum((num(v) for v in seat["adds"]), Decimal(0))
    return None


def num(v) -> Decimal:
    """A score as a Decimal (from JSON's floats via text: 0.1 stays 0.1)."""
    return v if isinstance(v, Decimal) else Decimal(str(v))


def outcome(seats: list[dict], scoring: str, finished: bool, coop_won: bool | None) -> list[dict]:
    """Each seat's score, place and won. Unfinished: nobody won. Co-op: everyone or no one. Otherwise whoever you
    said won (a tie-break), else the best score - highest or lowest - (a tie shares it); places by score (1, 1, 3)."""
    for s in seats:
        s["score"] = total(s)
        s["place"] = None
    if not finished:
        for s in seats:
            s["won"] = False
        return seats
    if scoring == "coop":
        for s in seats:
            s["won"] = bool(coop_won)
        return seats
    scored = [s for s in seats if s["score"] is not None]
    if scoring in ("highest", "lowest") and scored:
        low = scoring == "lowest"
        for s in scored:
            s["place"] = 1 + sum(1 for o in scored if (o["score"] < s["score"] if low else o["score"] > s["score"]))
    said = [s for s in seats if s.get("won")]
    for s in seats:
        s["won"] = bool(s.get("won")) if said else s["place"] == 1
    if said and not scored:
        for s in seats:
            s["place"] = 1 if s["won"] else None
    return seats


def save_seats(conn, play_id: int, seats: list[SeatIn] | list[dict], *, resolved: bool = False) -> None:
    """Write who sat at a play (replacing what was there) and the play's players / winner text from them."""
    play = conn.execute("SELECT p.play_id, p.game_id, p.played_on, p.finished, p.coop_won, g.scoring "
                        "FROM board_game_plays p JOIN board_games g USING (game_id) WHERE p.play_id = %s",
                        (play_id,)).fetchone()
    rows = outcome(seats if resolved else resolve(conn, seats), play["scoring"], play["finished"], play["coop_won"])
    conn.execute("DELETE FROM board_game_play_players WHERE play_id = %s", (play_id,))
    for i, s in enumerate(rows):
        parts = {k: float(v) for k, v in (s.get("parts") or {}).items() if v is not None} or None
        conn.execute("""
            INSERT INTO board_game_play_players (play_id, player_id, seat, score, parts, adds, place, won, team, colour, first_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOT EXISTS (
                SELECT 1 FROM board_game_play_players o JOIN board_game_plays op USING (play_id)
                WHERE o.player_id = %s AND op.game_id = %s AND op.play_id <> %s
                  AND (op.played_on, op.play_id) < (%s, %s)))""",
            (play_id, s["player_id"], i + 1, s["score"], parts and Jsonb(parts), [num(a) for a in s.get("adds") or []],
             s["place"], s["won"], (s.get("team") or "").strip() or None, (s.get("colour") or "").strip() or None,
             s["player_id"], play["game_id"], play_id, play["played_on"], play_id))
    names = conn.execute("SELECT pl.name, s.won FROM board_game_play_players s JOIN board_game_players pl USING (player_id) "
                         "WHERE s.play_id = %s ORDER BY s.seat", (play_id,)).fetchall()
    if play["scoring"] == "coop":
        winner = "Everyone" if play["finished"] and play["coop_won"] else None
    else:
        winner = " & ".join(n["name"] for n in names if n["won"]) or None
    conn.execute("UPDATE board_game_plays SET players = %s, winner = %s WHERE play_id = %s",
                 (", ".join(n["name"] for n in names) or None, winner, play_id))


def highlights(conn, play_id: int) -> list[str]:
    """What a just-saved play beat: a player's own best on this game, or the best anyone has done."""
    rows = conn.execute("""
        SELECT pl.name, pl.is_me, s.score, g.scoring, g.name AS game,
               (SELECT CASE WHEN g.scoring = 'lowest' THEN min(o.score) ELSE max(o.score) END
                FROM board_game_play_players o JOIN board_game_plays op USING (play_id)
                WHERE op.game_id = p.game_id AND o.player_id = s.player_id AND op.play_id <> p.play_id AND op.finished) AS own_best,
               (SELECT CASE WHEN g.scoring = 'lowest' THEN min(o.score) ELSE max(o.score) END
                FROM board_game_play_players o JOIN board_game_plays op USING (play_id)
                WHERE op.game_id = p.game_id AND op.play_id <> p.play_id AND op.finished) AS record
        FROM board_game_play_players s JOIN board_game_players pl USING (player_id)
        JOIN board_game_plays p USING (play_id) JOIN board_games g USING (game_id)
        WHERE s.play_id = %s AND s.score IS NOT NULL AND p.finished AND g.scoring IN ('highest', 'lowest')
        ORDER BY s.seat""", (play_id,)).fetchall()
    out = []
    better = lambda a, b, low: a < b if low else a > b   # noqa: E731
    for r in rows:
        low, score = r["scoring"] == "lowest", r["score"].normalize()
        who = "Your" if r["is_me"] else f"{r['name']}'s"
        if r["record"] is not None and better(r["score"], r["record"], low):
            out.append(f"New record for {r['game']}: {r['name']} scored {score:f} (the best was {r['record'].normalize():f}).")
        elif r["own_best"] is not None and better(r["score"], r["own_best"], low):
            out.append(f"{who} best at {r['game']}: {score:f} (was {r['own_best'].normalize():f}).")
    return out


# ---------------------------------------------------------------------------
# Players and groups
# ---------------------------------------------------------------------------
PLAYERS = """
SELECT pl.player_id, pl.name, pl.is_me, pl.notes,
       count(p.play_id)::int AS plays,
       count(p.play_id) FILTER (WHERE p.played_on >= current_date - 90)::int AS recent,
       count(DISTINCT p.game_id)::int AS games,
       max(p.played_on) AS last_played,
       count(p.play_id) FILTER (WHERE s.won AND g.scoring <> 'coop')::int AS wins,
       count(p.play_id) FILTER (WHERE p.finished AND g.scoring <> 'coop' AND EXISTS (
           SELECT 1 FROM board_game_play_players w WHERE w.play_id = p.play_id AND w.won))::int AS contests,
       count(p.play_id) FILTER (WHERE s.first_time)::int AS games_learned
FROM board_game_players pl
LEFT JOIN board_game_play_players s USING (player_id)
LEFT JOIN board_game_plays p USING (play_id)
LEFT JOIN board_games g ON g.game_id = p.game_id"""


def fetch_player(conn, player_id: int) -> dict:
    return found(conn.execute(PLAYERS + " WHERE pl.player_id = %s GROUP BY pl.player_id", (player_id,)).fetchone(), "Player")


@router.get("/board-games/players")
def list_players():
    """Everyone you play with, the ones you've played with most lately first (you, if you're one of them, at the
    top); your groups; and the places you've played (for the play forms' suggestions)."""
    with db() as conn:
        players = conn.execute(PLAYERS + " GROUP BY pl.player_id ORDER BY pl.is_me DESC, 6 DESC, 5 DESC, lower(pl.name)").fetchall()
        groups = conn.execute("SELECT * FROM board_game_groups ORDER BY lower(name)").fetchall()
        places = [r["location"] for r in conn.execute(
            "SELECT location FROM board_game_plays WHERE location IS NOT NULL GROUP BY location "
            "ORDER BY max(played_on) DESC, count(*) DESC LIMIT 30").fetchall()]
    have = {p["player_id"] for p in players}
    for g in groups:
        g["player_ids"] = [i for i in g["player_ids"] if i in have]
    return {"players": players, "groups": groups, "places": places}


def _one_me(conn, player_id: int, data: dict):
    if data.get("is_me"):
        conn.execute("UPDATE board_game_players SET is_me = false WHERE is_me AND player_id <> %s", (player_id,))


@router.post("/board-games/players", status_code=201)
def add_player(body: PlayerIn):
    data = tidy_text(body.model_dump())
    with db() as conn:
        if conn.execute("SELECT 1 FROM board_game_players WHERE lower(name) = lower(%s)", (data["name"],)).fetchone():
            raise HTTPException(409, f"You already have a player called {data['name']}.")
        if data["is_me"]:
            conn.execute("UPDATE board_game_players SET is_me = false WHERE is_me")
        return fetch_player(conn, insert_row(conn, "board_game_players", data, "player_id"))


@router.patch("/board-games/players/{player_id}")
def update_player(player_id: int, body: PlayerPatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if data.get("name", "x") in ("", None) or data.get("is_me", False) is None:
        raise HTTPException(422, "A player needs a name.")
    with db() as conn:
        fetch_player(conn, player_id)
        if "name" in data and conn.execute("SELECT 1 FROM board_game_players WHERE lower(name) = lower(%s) AND player_id <> %s",
                                           (data["name"], player_id)).fetchone():
            raise HTTPException(409, f"You already have a player called {data['name']} - merge them instead.")
        _one_me(conn, player_id, data)
        update_row(conn, "board_game_players", "player_id", player_id, data)
        _rename_in_plays(conn, player_id)
        return fetch_player(conn, player_id)


def _rename_in_plays(conn, player_id: int):
    """The players / winner text of their plays, written again (a rename, a merge)."""
    for r in conn.execute("SELECT DISTINCT play_id FROM board_game_play_players WHERE player_id = %s", (player_id,)).fetchall():
        seats = conn.execute("SELECT player_id, score, parts, adds, team, colour, won FROM board_game_play_players "
                             "WHERE play_id = %s ORDER BY seat", (r["play_id"],)).fetchall()
        save_seats(conn, r["play_id"], [{**s, "parts": s["parts"], "adds": list(s["adds"])} for s in seats], resolved=True)


@router.post("/board-games/players/{player_id}/merge")
def merge_player(player_id: int, body: MergeIn):
    """Two players who are one person: this one's plays go to `into`, then this one goes."""
    if body.into == player_id:
        raise HTTPException(422, "Pick someone else to merge into.")
    with db() as conn:
        fetch_player(conn, player_id)
        fetch_player(conn, body.into)
        both = conn.execute("SELECT count(*)::int AS n FROM board_game_play_players a JOIN board_game_play_players b USING (play_id) "
                            "WHERE a.player_id = %s AND b.player_id = %s", (player_id, body.into)).fetchone()["n"]
        if both:
            raise HTTPException(409, f"They played together in {both} play{'s' if both > 1 else ''}, so they're two people.")
        conn.execute("UPDATE board_game_play_players SET player_id = %s WHERE player_id = %s", (body.into, player_id))
        conn.execute("UPDATE board_game_plays SET first_player_id = %s WHERE first_player_id = %s", (body.into, player_id))
        conn.execute("UPDATE board_game_groups SET player_ids = array_remove(player_ids, %s) || "
                     "CASE WHEN %s = ANY(player_ids) THEN '{}'::int[] ELSE ARRAY[%s] END WHERE %s = ANY(player_ids)",
                     (player_id, body.into, body.into, player_id))
        me = conn.execute("SELECT is_me FROM board_game_players WHERE player_id = %s", (player_id,)).fetchone()["is_me"]
        conn.execute("DELETE FROM board_game_players WHERE player_id = %s", (player_id,))
        if me:
            conn.execute("UPDATE board_game_players SET is_me = true WHERE player_id = %s", (body.into,))
        _rename_in_plays(conn, body.into)
        return fetch_player(conn, body.into)


@router.delete("/board-games/players/{player_id}", status_code=204)
def delete_player(player_id: int):
    """Only someone in no plays (merge the others)."""
    with db() as conn:
        p = fetch_player(conn, player_id)
        if p["plays"]:
            raise HTTPException(409, f"{p['name']} is in {p['plays']} play{'s' if p['plays'] > 1 else ''}: "
                                     "rename them, or merge them into someone else.")
        conn.execute("UPDATE board_game_groups SET player_ids = array_remove(player_ids, %s)", (player_id,))
        conn.execute("DELETE FROM board_game_players WHERE player_id = %s", (player_id,))
    return Response(status_code=204)


def _group_players(conn, ids: list[int]) -> list[int]:
    ids = list(dict.fromkeys(ids))
    have = {r["player_id"] for r in conn.execute("SELECT player_id FROM board_game_players WHERE player_id = ANY(%s)", (ids,)).fetchall()}
    if set(ids) - have:
        raise HTTPException(422, "A player in that group isn't one of your players.")
    return ids


@router.post("/board-games/groups", status_code=201)
def add_group(body: GroupIn):
    data = tidy_text(body.model_dump())
    with db() as conn:
        data["player_ids"] = _group_players(conn, data["player_ids"])
        group_id = insert_row(conn, "board_game_groups", data, "group_id")
        return conn.execute("SELECT * FROM board_game_groups WHERE group_id = %s", (group_id,)).fetchone()


@router.patch("/board-games/groups/{group_id}")
def update_group(group_id: int, body: GroupPatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if data.get("name", "x") in ("", None) or ("player_ids" in data and data["player_ids"] is None):
        raise HTTPException(422, "A group needs a name.")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM board_game_groups WHERE group_id = %s", (group_id,)).fetchone(), "Group")
        if "player_ids" in data:
            data["player_ids"] = _group_players(conn, data["player_ids"])
        update_row(conn, "board_game_groups", "group_id", group_id, data)
        return conn.execute("SELECT * FROM board_game_groups WHERE group_id = %s", (group_id,)).fetchone()


@router.delete("/board-games/groups/{group_id}", status_code=204)
def delete_group(group_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM board_game_groups WHERE group_id = %s RETURNING 1", (group_id,)).fetchone(), "Group")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
def game_stats(conn, game_id: int | None = None) -> dict[int, dict]:
    """Per game (one, or all with plays): plays, average setup / teach / play minutes, how fun, your best and average
    score and wins, the record and who holds it."""
    plays = conn.execute("""
        SELECT p.game_id, count(*)::int AS plays, round(avg(p.setup_minutes))::int AS avg_setup,
               round(avg(p.teach_minutes))::int AS avg_teach, round(avg(p.minutes))::int AS avg_minutes,
               round(avg(p.fun), 1) AS avg_fun, count(*) FILTER (WHERE p.teach_minutes > 0)::int AS teaches
        FROM board_game_plays p WHERE %(g)s::int IS NULL OR p.game_id = %(g)s GROUP BY p.game_id""", {"g": game_id}).fetchall()
    out = {r["game_id"]: {**r, "my_plays": 0, "my_wins": 0, "my_best": None, "my_avg": None, "record": None} for r in plays}
    seats = conn.execute("""
        SELECT p.game_id, g.scoring, pl.name, pl.is_me, s.score, s.won, p.played_on
        FROM board_game_play_players s JOIN board_game_plays p USING (play_id) JOIN board_games g USING (game_id)
        JOIN board_game_players pl USING (player_id)
        WHERE p.finished AND (%(g)s::int IS NULL OR p.game_id = %(g)s) ORDER BY p.played_on""", {"g": game_id}).fetchall()
    mine: dict[int, list] = {}
    lowest = {s["game_id"] for s in seats if s["scoring"] == "lowest"}
    for s in seats:
        o = out.get(s["game_id"])
        if o is None:
            continue
        low = s["scoring"] == "lowest"
        if s["is_me"]:
            o["my_plays"] += 1
            o["my_wins"] += s["won"]
            if s["score"] is not None:
                mine.setdefault(s["game_id"], []).append(s["score"])
        if s["score"] is not None and s["scoring"] in ("highest", "lowest"):
            r = o["record"]
            if r is None or (s["score"] < r["score"] if low else s["score"] > r["score"]):
                o["record"] = {"score": s["score"], "name": s["name"], "is_me": s["is_me"], "on": s["played_on"]}
    for gid, scores in mine.items():
        out[gid]["my_best"] = min(scores) if gid in lowest else max(scores)
        out[gid]["my_avg"] = round(sum(scores) / len(scores), 1)
    return out


def h_index(plays: list[int]) -> int:
    """The biggest n such that n games have each been played at least n times."""
    ranked = sorted(plays, reverse=True)
    return sum(1 for i, p in enumerate(ranked, 1) if p >= i)


def plays_to_next(plays: list[int]) -> int:
    """Plays still needed for the H-index to go up by one: the top n+1 games each need n+1 plays."""
    n = h_index(plays)
    top = sorted(plays, reverse=True)[:n + 1]
    top += [0] * (n + 1 - len(top))
    return sum(max(0, n + 1 - p) for p in top)


def win_streaks(results: list[bool]) -> dict:
    """Wins in a row, from results in date order: the run going now (a loss ends it) and the longest ever."""
    current = longest = 0
    for won in results:
        current = current + 1 if won else 0
        longest = max(longest, current)
    return {"current": current, "longest": longest}


def first_player_stats(rows: list[dict]) -> dict:
    """Does going first help? From finished competitive plays with a winner and a known first player
    (rows: game_id, name, won, seats): the first player's win rate overall, what chance alone would give
    (1 over the seats, averaged) and, for games with at least 3 such plays, the same per game."""
    def sums(group):
        n = len(group)
        wins = sum(1 for r in group if r["won"])
        return {"plays": n, "wins": wins, "rate": round(100 * wins / n) if n else None,
                "chance": round(100 * sum(1 / r["seats"] for r in group) / n) if n else None}
    per_game = {}
    for r in rows:
        per_game.setdefault(r["game_id"], []).append(r)
    games = [{"game_id": g, "name": rs[0]["name"], **sums(rs)} for g, rs in per_game.items() if len(rs) >= 3]
    games.sort(key=lambda g: (-g["plays"], g["name"].lower()))
    return {**sums(rows), "games": games}


@router.get("/board-games/stats")
def stats():
    """The Players page: each player's plays and wins, you against each of them (who beat whom, co-op plays won
    together), and per game your record, times and fun."""
    with db() as conn:
        players = conn.execute(PLAYERS + " GROUP BY pl.player_id ORDER BY 5 DESC, lower(pl.name)").fetchall()
        rivals = conn.execute("""
            WITH me AS (SELECT player_id FROM board_game_players WHERE is_me),
            together AS (
                SELECT o.player_id, m.won AS i_won, o.won AS they_won, m.place AS mp, o.place AS op, g.scoring
                FROM board_game_play_players m JOIN me USING (player_id)
                JOIN board_game_play_players o ON o.play_id = m.play_id AND o.player_id <> m.player_id
                JOIN board_game_plays p ON p.play_id = m.play_id JOIN board_games g ON g.game_id = p.game_id
                WHERE p.finished)
            SELECT player_id, count(*)::int AS together,
                   count(*) FILTER (WHERE scoring <> 'coop' AND ((i_won AND NOT they_won) OR mp < op))::int AS i_beat,
                   count(*) FILTER (WHERE scoring <> 'coop' AND ((they_won AND NOT i_won) OR op < mp))::int AS they_beat,
                   count(*) FILTER (WHERE scoring = 'coop')::int AS coop_plays,
                   count(*) FILTER (WHERE scoring = 'coop' AND i_won)::int AS coop_wins
            FROM together GROUP BY player_id""").fetchall()
        games = game_stats(conn)
        names = {r["game_id"]: r for r in conn.execute(
            "SELECT game_id, name, scoring FROM board_games WHERE game_id = ANY(%s)", (list(games),)).fetchall()}
        places = conn.execute("SELECT location, count(*)::int AS plays, max(played_on) AS last_played FROM board_game_plays "
                              "WHERE location IS NOT NULL GROUP BY location ORDER BY 2 DESC, 3 DESC LIMIT 12").fetchall()
        results = conn.execute("""
            SELECT s.player_id, s.won FROM board_game_play_players s JOIN board_game_plays p USING (play_id)
            JOIN board_games g USING (game_id)
            WHERE p.finished AND g.scoring <> 'coop'
              AND EXISTS (SELECT 1 FROM board_game_play_players w WHERE w.play_id = p.play_id AND w.won)
            ORDER BY p.played_on, p.play_id""").fetchall()
        first = conn.execute("""
            SELECT p.game_id, g.name, s.won, (SELECT count(*)::int FROM board_game_play_players o WHERE o.play_id = p.play_id) AS seats
            FROM board_game_plays p JOIN board_games g USING (game_id)
            JOIN board_game_play_players s ON s.play_id = p.play_id AND s.player_id = p.first_player_id
            WHERE p.finished AND g.scoring <> 'coop'
              AND EXISTS (SELECT 1 FROM board_game_play_players w WHERE w.play_id = p.play_id AND w.won)""").fetchall()
        times = conn.execute("""
            SELECT count(*) FILTER (WHERE teach_minutes IS NOT NULL)::int AS timed, coalesce(sum(teach_minutes), 0)::int AS teach,
                   coalesce(sum(setup_minutes), 0)::int AS setup, coalesce(sum(minutes), 0)::int AS playing
            FROM board_game_plays""").fetchone()
    by_id = {r["player_id"]: r for r in rivals}
    by_player: dict[int, list[bool]] = {}
    for r in results:
        by_player.setdefault(r["player_id"], []).append(r["won"])
    for p in players:
        p["vs_me"] = by_id.get(p["player_id"])
        p["streak"] = win_streaks(by_player.get(p["player_id"], []))
    counts = sorted((s["plays"] for s in games.values()), reverse=True)
    n = h_index(counts)
    by_name = {r["game_id"]: r["name"] for r in names.values()}
    h = {"n": n, "next_n": n + 1, "plays_to_next": plays_to_next(counts),
         "games": [{"game_id": g, "name": by_name[g], "plays": s["plays"]}
                   for g, s in sorted(games.items(), key=lambda kv: -kv[1]["plays"])[:n] if g in by_name]}
    game_rows = sorted(({**names[g], **s} for g, s in games.items() if g in names), key=lambda r: (-r["plays"], r["name"].lower()))
    return {"players": players, "games": game_rows, "places": places, "times": times,
            "has_me": any(p["is_me"] for p in players), "h_index": h, "first_player": first_player_stats(first)}


# ---------------------------------------------------------------------------
# Photos of a play
# ---------------------------------------------------------------------------
PHOTOS = """COALESCE((SELECT json_agg(json_build_object('photo_id', ph.photo_id, 'caption', ph.caption,
    'url', '/api/board-games/play-photos/' || ph.photo_id) ORDER BY ph.photo_id)
    FROM board_game_play_photos ph WHERE ph.{col} = {ref}), '[]'::json)"""


def add_photo(conn, column: str, owner_id: int, image: bytes, image_type: str, caption: str | None) -> dict:
    return conn.execute(f"INSERT INTO board_game_play_photos ({column}, photo, photo_type, caption) VALUES (%s, %s, %s, %s) "
                        "RETURNING photo_id, caption, '/api/board-games/play-photos/' || photo_id AS url",
                        (owner_id, image, image_type, (caption or "").strip()[:200] or None)).fetchone()


@router.post("/board-game-plays/{play_id}/photos", status_code=201)
async def add_play_photo(play_id: int, request: Request, caption: str | None = None):
    """A photo of a play (the body: an image, shrunk by the browser)."""
    image, image_type = await read_photo(request)
    with db() as conn:
        found(conn.execute("SELECT 1 FROM board_game_plays WHERE play_id = %s", (play_id,)).fetchone(), "Play")
        return add_photo(conn, "play_id", play_id, image, image_type, caption)


@router.get("/board-games/play-photos/{photo_id}")
def get_play_photo(photo_id: int):
    """A play's photo (a new photo is a new id, so it can be kept for a year)."""
    with db() as conn:
        row = found(conn.execute("SELECT photo, photo_type FROM board_game_play_photos WHERE photo_id = %s",
                                 (photo_id,)).fetchone(), "Photo")
    return photo_response(row["photo"], row["photo_type"])


@router.delete("/board-games/play-photos/{photo_id}", status_code=204)
def delete_play_photo(photo_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM board_game_play_photos WHERE photo_id = %s RETURNING 1", (photo_id,)).fetchone(), "Photo")
    return Response(status_code=204)

