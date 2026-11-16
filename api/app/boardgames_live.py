"""Board games being played right now (board_game_live, 94_board_game_table.sql): start a play as you sit down and the
app times it - setup, the teach, playing - while you keep score. Finishing it makes it a play like any other.

    POST   /board-games/live                  start: the game (or a friend's game by name), who's playing, where,
                                              the expansions in; the clock starts on setup (or straight on the teach)
    GET    /board-games/live                  plays going on now (Home, the Games page, the live screen)
    PATCH  /board-games/live/{id}             who's playing and their scores, where, expansions, who goes first,
                                              the round, notes - the screen sends these as you tap
    POST   /board-games/live/{id}/stage       to setup / teach / play, or pause / resume
    POST   /board-games/live/{id}/turns       the turn timer (chess clock): start (optional limit per turn), next (pass the
                                              turn on), to (pass it to a player), stop. Time counts only while playing
    POST   /board-games/live/{id}/photos      a photo (moved to the play when it's finished)
    POST   /board-games/live/{id}/finish      save it as a play (minutes = playing time; setup and teach minutes kept
                                              apart) with how it ended; answers with the play and any new bests
    DELETE /board-games/live/{id}             throw it away

The server keeps the times (each stage's from / to), so a phone that locks, reloads or runs out of battery loses
nothing; the screen counts on from the server's clock (`now`). Included before boardgames.py (/board-games/live would
otherwise hit /board-games/{game_id}).
"""
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import boardgames_people as people
from .boardgames_people import PHOTOS, SeatIn
from .db import db, found, insert_row
from .images import read_photo

router = APIRouter(prefix="/api", tags=["board games"])

Stage = Literal["setup", "teach", "play"]


class LiveIn(BaseModel):
    game_id: int | None = None
    game_name: str | None = Field(None, max_length=200)     # a game you don't have (added as Played elsewhere)
    seats: list[SeatIn] = Field(default_factory=list, max_length=30)
    location: str | None = Field(None, max_length=120)
    expansions: list[int] = Field(default_factory=list, max_length=30)
    stage: Stage = "setup"


class LivePatch(BaseModel):
    seats: list[SeatIn] | None = Field(None, max_length=30)
    location: str | None = Field(None, max_length=120)
    expansions: list[int] | None = Field(None, max_length=30)
    first_player_id: int | None = None
    rounds: int | None = Field(None, ge=0, le=999)
    notes: str | None = None
    tags: list[str] | None = Field(None, max_length=12)
    round_scores: list[dict[str, float | None]] | None = Field(None, max_length=999)   # the grid: a dict per round


class TurnsIn(BaseModel):
    action: Literal["start", "next", "to", "stop"]
    limit: int | None = Field(None, ge=5, le=3600)      # start: seconds a turn may take before the warning
    player_id: int | None = None                        # to: whose turn it is now


class StageIn(BaseModel):
    to: Literal["setup", "teach", "play", "pause", "resume"]


class FinishIn(BaseModel):
    finished: bool = True                 # false: abandoned
    coop_won: bool | None = None          # a co-op game: did the table win?
    fun: int | None = Field(None, ge=1, le=5)
    notes: str | None = None
    seats: list[SeatIn] | None = Field(None, max_length=30)   # the final scores (else the live ones)
    tags: list[str] = Field(default_factory=list, max_length=12)


def now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat()


def timings(stages: list[dict], paused: bool, at: datetime) -> dict:
    """Seconds spent in each stage so far, and the stage running now (none while paused)."""
    totals = {"setup": 0, "teach": 0, "play": 0}
    for s in stages:
        end = datetime.fromisoformat(s["to"]) if s.get("to") else at
        totals[s["stage"]] += max(0, int((end - datetime.fromisoformat(s["from"])).total_seconds()))
    last = stages[-1] if stages else None
    running = last if last and not last.get("to") and not paused else None
    return {"seconds": totals, "stage": running and running["stage"], "since": running and running["from"],
            "last_stage": last and last["stage"]}


def close(stages: list[dict], at: datetime) -> list[dict]:
    return [{**s, "to": s.get("to") or _iso(at)} for s in stages]


# --- the turn timer ----------------------------------------------------------------------------------------------
# live.turns: {"on", "limit", "order", "current", "since", "cur_s", "totals", "counts", "over"} (player ids as text in the
# dicts). `since` is when the current turn's clock last started - None while it isn't running (not the play stage, or
# paused), so a locked phone loses nothing; `cur_s` is the current turn's time before that.
def clock_runs(stages: list[dict], paused: bool) -> bool:
    last = stages[-1] if stages else None
    return bool(last and last["stage"] == "play" and not last.get("to") and not paused)


def new_turns(order: list[int], limit: int | None) -> dict:
    return {"on": True, "limit": limit, "order": order, "current": order[0] if order else None, "since": None, "cur_s": 0,
            "totals": {}, "counts": {}, "over": {}}


def fold(turns: dict, at: datetime) -> None:
    """Stop the running turn's clock, adding what it ran to the player's total and to this turn."""
    if turns.get("since") and turns.get("current") is not None:
        secs = max(0, int((at - datetime.fromisoformat(turns["since"])).total_seconds()))
        key = str(turns["current"])
        turns["totals"][key] = turns["totals"].get(key, 0) + secs
        turns["cur_s"] = turns.get("cur_s", 0) + secs
    turns["since"] = None


def end_turn(turns: dict, at: datetime) -> None:
    """The current turn is over: count it (and whether it went past the limit)."""
    fold(turns, at)
    key = str(turns["current"])
    if turns.get("current") is not None and turns["cur_s"] > 0:
        turns["counts"][key] = turns["counts"].get(key, 0) + 1
        if turns.get("limit") and turns["cur_s"] > turns["limit"]:
            turns["over"][key] = turns["over"].get(key, 0) + 1
    turns["cur_s"] = 0


def order_of(turns: dict, seat_ids: list[int]) -> list[int]:
    """The turn order, kept in line with who's sitting there now (new players go last, leavers go)."""
    kept = [i for i in turns.get("order", []) if i in seat_ids]
    return kept + [i for i in seat_ids if i not in kept]


def set_clock(turns: dict | None, was_running: bool, now_running: bool, at: datetime) -> None:
    """The stage changed: stop the turn clock when playing stops, start it again when playing carries on."""
    if not turns or not turns.get("on") or was_running == now_running:
        return
    if now_running:
        turns["since"] = _iso(at) if turns.get("current") is not None else None
    else:
        fold(turns, at)


LIVE = f"""
SELECT l.*, g.name AS game_name, g.status AS game_status, g.scoring, g.score_parts, g.teach_notes, g.min_players,
       g.max_players, g.play_minutes,
       CASE WHEN g.photo IS NOT NULL THEN '/api/board-games/' || g.game_id || '/photo?v='
            || (extract(epoch FROM g.photo_updated) * 1000)::bigint END AS photo_url,
       COALESCE((SELECT json_agg(json_build_object('game_id', e.game_id, 'name', e.name) ORDER BY e.name)
                 FROM board_games e WHERE e.base_game_id = g.game_id AND e.status NOT IN ('Gone', 'Wanted')), '[]'::json) AS add_ons,
       {PHOTOS.format(col="live_id", ref="l.live_id")} AS photos
FROM board_game_live l JOIN board_games g USING (game_id)"""


def shape(conn, row: dict) -> dict:
    """A live play for the screen: seats with names (and whether it's their first time), the timings, server time."""
    at = now()
    ids = [s["player_id"] for s in row["seats"]]
    named = {r["player_id"]: r for r in conn.execute(
        "SELECT pl.player_id, pl.name, pl.is_me, NOT EXISTS (SELECT 1 FROM board_game_play_players s "
        "JOIN board_game_plays p USING (play_id) WHERE s.player_id = pl.player_id AND p.game_id = %s) AS first_time "
        "FROM board_game_players pl WHERE pl.player_id = ANY(%s)", (row["game_id"], ids)).fetchall()}
    seats = [{**s, **named[s["player_id"]], "total": people.total(s)} for s in row["seats"] if s["player_id"] in named]
    turns = row.get("turns")
    if turns:
        turns = {**turns, "order": order_of(turns, ids), "running": clock_runs(row["stages"], row["paused"])}
    return {**row, "seats": seats, "turns": turns, "now": _iso(at), **timings(row["stages"], row["paused"], at)}


def fetch_live(conn, live_id: int) -> dict:
    return shape(conn, found(conn.execute(LIVE + " WHERE l.live_id = %s", (live_id,)).fetchone(), "Live play"))


def stored_seats(conn, seats: list[SeatIn]) -> list[dict]:
    """Seats as kept while playing (JSON): player ids, numbers as numbers."""
    out = []
    for s in people.resolve(conn, seats):
        out.append({"player_id": s["player_id"], "score": None if s["score"] is None else float(s["score"]),
                    "parts": {k: float(v) for k, v in (s["parts"] or {}).items() if v is not None} or None,
                    "adds": [float(a) for a in s["adds"]], "team": s["team"], "colour": s["colour"], "won": s["won"]})
    return out


def _expansions(conn, game_id: int, ids: list[int]) -> list[int]:
    ids = list(dict.fromkeys(ids))
    ok = {r["game_id"] for r in conn.execute("SELECT game_id FROM board_games WHERE game_id = ANY(%s) AND base_game_id = %s",
                                             (ids, game_id)).fetchall()}
    if set(ids) - ok:
        raise HTTPException(422, "An expansion there isn't one of this game's.")
    return ids


@router.get("/board-games/live")
def list_live():
    with db() as conn:
        return [shape(conn, r) for r in conn.execute(LIVE + " ORDER BY l.started_at").fetchall()]


@router.post("/board-games/live", status_code=201)
def start(body: LiveIn):
    """Sit down and start: the clock runs from now, on setup (or the teach, if it's set up already)."""
    with db() as conn:
        if body.game_id is not None:
            game_id = found(conn.execute("SELECT game_id FROM board_games WHERE game_id = %s", (body.game_id,)).fetchone(),
                            "Board game")["game_id"]
        elif body.game_name and body.game_name.strip():
            name = body.game_name.strip()
            row = conn.execute("SELECT game_id FROM board_games WHERE lower(name) = lower(%s) ORDER BY status = 'Gone' LIMIT 1",
                               (name,)).fetchone()
            game_id = row["game_id"] if row else insert_row(
                conn, "board_games", {"name": name, "status": "Played elsewhere", "kind": "game"}, "game_id")
        else:
            raise HTTPException(422, "Which game?")
        at = now()
        live_id = insert_row(conn, "board_game_live", {
            "game_id": game_id, "started_at": at, "stages": Jsonb([{"stage": body.stage, "from": _iso(at)}]),
            "seats": Jsonb(stored_seats(conn, body.seats)), "location": (body.location or "").strip() or None,
            "expansions": _expansions(conn, game_id, body.expansions)}, "live_id")
        return fetch_live(conn, live_id)


@router.get("/board-games/live/{live_id}")
def get_live(live_id: int):
    with db() as conn:
        return fetch_live(conn, live_id)


@router.patch("/board-games/live/{live_id}")
def update_live(live_id: int, body: LivePatch):
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        row = found(conn.execute("SELECT game_id, seats FROM board_game_live WHERE live_id = %s FOR UPDATE", (live_id,)).fetchone(),
                    "Live play")
        changes = {}
        if data.get("seats") is not None:
            changes["seats"] = Jsonb(stored_seats(conn, body.seats))
        if "location" in data:
            changes["location"] = (data["location"] or "").strip() or None
        if data.get("expansions") is not None:
            changes["expansions"] = _expansions(conn, row["game_id"], data["expansions"])
        if "first_player_id" in data:
            changes["first_player_id"] = data["first_player_id"]
        if data.get("rounds") is not None:
            changes["rounds"] = data["rounds"]
        if "notes" in data:
            changes["notes"] = (data["notes"] or "").strip() or None
        if data.get("tags") is not None:
            changes["tags"] = people.tidy_tags(data["tags"])
        if data.get("round_scores") is not None:
            changes["round_scores"] = Jsonb(people.tidy_rounds(data["round_scores"]))
        if changes:
            sets = ", ".join(f"{k} = %({k})s" for k in changes)
            conn.execute(f"UPDATE board_game_live SET {sets}, updated_at = now() WHERE live_id = %(id)s", {**changes, "id": live_id})
        return fetch_live(conn, live_id)


@router.post("/board-games/live/{live_id}/stage")
def change_stage(live_id: int, body: StageIn):
    """Move the clock on: to another stage, pause it, or carry on with the stage it was paused in."""
    with db() as conn:
        row = found(conn.execute("SELECT stages, paused, turns FROM board_game_live WHERE live_id = %s FOR UPDATE", (live_id,)).fetchone(),
                    "Live play")
        at, stages, paused = now(), row["stages"], row["paused"]
        was_running = clock_runs(stages, paused)
        if body.to == "pause":
            stages, paused = close(stages, at), True
        elif body.to == "resume":
            if paused:
                last = stages[-1]["stage"] if stages else "play"
                stages, paused = [*close(stages, at), {"stage": last, "from": _iso(at)}], False
        else:
            running = stages and not stages[-1].get("to") and not paused
            if not (running and stages[-1]["stage"] == body.to):
                stages, paused = [*close(stages, at), {"stage": body.to, "from": _iso(at)}], False
        turns = row["turns"]
        set_clock(turns, was_running, clock_runs(stages, paused), at)
        conn.execute("UPDATE board_game_live SET stages = %s, paused = %s, turns = %s, updated_at = now() WHERE live_id = %s",
                     (Jsonb(stages), paused, turns and Jsonb(turns), live_id))
        return fetch_live(conn, live_id)


@router.post("/board-games/live/{live_id}/turns")
def change_turns(live_id: int, body: TurnsIn):
    """The turn timer: start it (the order is the seats, from who goes first), pass the turn on, hand it to a player,
    or stop it. A turn's clock runs only while the play stage runs; the totals are saved with the play."""
    with db() as conn:
        row = found(conn.execute("SELECT stages, paused, turns, seats, first_player_id FROM board_game_live "
                                 "WHERE live_id = %s FOR UPDATE", (live_id,)).fetchone(), "Live play")
        at, ids = now(), [s["player_id"] for s in row["seats"]]
        running, turns = clock_runs(row["stages"], row["paused"]), row["turns"]
        if body.action == "start":
            if not ids:
                raise HTTPException(422, "Add the players first.")
            first = ids.index(row["first_player_id"]) if row["first_player_id"] in ids else 0
            if turns is None:
                turns = new_turns(ids[first:] + ids[:first], body.limit)
            else:
                turns["on"], turns["limit"] = True, body.limit
                turns["order"] = order_of(turns, ids)
                if turns.get("current") not in ids:
                    turns["current"] = turns["order"][0]
            turns["since"] = _iso(at) if running else None
        elif turns is None or not turns.get("on"):
            raise HTTPException(409, "The turn timer isn't on.")
        elif body.action == "stop":
            fold(turns, at)
            turns["on"] = False
        else:
            order = order_of(turns, ids)
            if turns.get("current") not in order:
                raise HTTPException(409, "Nobody's turn yet.")
            if body.action == "next":
                nxt = order[(order.index(turns["current"]) + 1) % len(order)]
            elif body.player_id in order:
                nxt = body.player_id
            else:
                raise HTTPException(422, "That player isn't in this play.")
            end_turn(turns, at)
            turns["order"], turns["current"] = order, nxt
            turns["since"] = _iso(at) if running else None
        conn.execute("UPDATE board_game_live SET turns = %s, updated_at = now() WHERE live_id = %s", (Jsonb(turns), live_id))
        return fetch_live(conn, live_id)


@router.post("/board-games/live/{live_id}/photos", status_code=201)
async def add_live_photo(live_id: int, request: Request, caption: str | None = None):
    image, image_type = await read_photo(request)
    with db() as conn:
        found(conn.execute("SELECT 1 FROM board_game_live WHERE live_id = %s", (live_id,)).fetchone(), "Live play")
        return people.add_photo(conn, "live_id", live_id, image, image_type, caption)


def minutes(seconds: int, used: bool) -> int | None:
    """Seconds as whole minutes: None for a stage never used; a used one is at least 1 (playing) or 0 (setup, teach)."""
    return round(seconds / 60) if used else None


@router.post("/board-games/live/{live_id}/finish", status_code=201)
def finish(live_id: int, body: FinishIn):
    """Stop the clock and save it as a play on the day it started. Its photos move to the play."""
    from .boardgames import PLAY_SELECT          # (boardgames imports this module's neighbours: import here)
    with db() as conn:
        row = found(conn.execute("SELECT * FROM board_game_live WHERE live_id = %s FOR UPDATE", (live_id,)).fetchone(), "Live play")
        at = now()
        t = timings(close(row["stages"], at), True, at)["seconds"]
        used = {s["stage"] for s in row["stages"]}
        play_min = minutes(t["play"], "play" in used)
        turns = row["turns"]
        if turns and turns.get("current") is not None:
            end_turn(turns, at)                 # the turn in progress counts
        seats = (stored_seats(conn, body.seats) if body.seats is not None else row["seats"])
        started: date = row["started_at"].astimezone().date()
        play_id = insert_row(conn, "board_game_plays", {
            "game_id": row["game_id"], "played_on": started, "minutes": max(1, play_min) if play_min is not None else None,
            "setup_minutes": minutes(t["setup"], "setup" in used), "teach_minutes": minutes(t["teach"], "teach" in used),
            "started_at": row["started_at"], "ended_at": at, "location": row["location"], "expansions": row["expansions"],
            "first_player_id": row["first_player_id"], "rounds": row["rounds"] or None, "finished": body.finished,
            "coop_won": body.coop_won if body.finished else None, "fun": body.fun,
            "notes": "\n".join(x for x in ((row["notes"] or "").strip(), (body.notes or "").strip()) if x) or None,
            "tags": people.tidy_tags([*row["tags"], *body.tags]), "round_scores": Jsonb(row["round_scores"]),
            "turn_limit_s": turns["limit"] if turns and any(turns["totals"].values()) else None,
        }, "play_id")
        people.save_seats(conn, play_id, [{**s, "adds": s.get("adds") or []} for s in seats], resolved=True)
        if turns:
            for pid, secs in turns["totals"].items():
                conn.execute("UPDATE board_game_play_players SET turn_seconds = %s, turn_count = %s, turn_over = %s "
                             "WHERE play_id = %s AND player_id = %s",
                             (secs, turns["counts"].get(pid, 0), turns["over"].get(pid, 0), play_id, int(pid)))
        conn.execute("UPDATE board_game_play_photos SET play_id = %s, live_id = NULL WHERE live_id = %s", (play_id, live_id))
        conn.execute("DELETE FROM board_game_live WHERE live_id = %s", (live_id,))
        play = conn.execute(PLAY_SELECT + " WHERE p.play_id = %s", (play_id,)).fetchone()
        return {"play": play, "highlights": people.highlights(conn, play_id)}


@router.delete("/board-games/live/{live_id}", status_code=204)
def discard(live_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM board_game_live WHERE live_id = %s RETURNING 1", (live_id,)).fetchone(), "Live play")
    return Response(status_code=204)
