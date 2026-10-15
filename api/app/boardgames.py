"""Board games (a hobby module): your collection and every time you played.

    games   board_games: Owned / To sell / Wanted / Borrowed / Gone, players, play time, price, rating, photo
    lookup  find a game at Gameology (gameology.py: a shop whose products carry BGG's facts) and
            fill in players, time, age, weight, categories, mechanisms, its photo and price
    plays   board_game_plays: the day, who played, who won, how long, notes

Plays show on the calendar and in Recent activity (activity.py). Writing "played @Catan" in the
journal offers to log a play (journal_actions.py).
"""
import time
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import gameology
from .db import GAME_STATUSES, db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["board games"])

Status = Literal[tuple(GAME_STATUSES)]
Kind = Literal["game", "expansion", "other"]     # a game, an expansion for one, or something else (coins, sleeves...)
# A BoardGameGeek link is shown as a link, so only web addresses (no "javascript:...").
WEB_LINK = r"^https?://\S+$"


class GameIn(BaseModel):
    name: str = Field(min_length=1)
    publisher: str | None = None
    year: int | None = Field(None, ge=1800, le=2200)
    min_players: int | None = Field(None, ge=1)
    max_players: int | None = Field(None, ge=1)
    play_minutes: int | None = Field(None, gt=0)
    status: Status = "Owned"
    purchase_date: date | None = None
    price_paid: Decimal | None = Field(None, ge=0)
    rating: int | None = Field(None, ge=1, le=10)
    notes: str | None = None
    bgg_url: str | None = Field(None, pattern=WEB_LINK)
    designer: str | None = None
    min_age: int | None = Field(None, ge=1, le=99)
    kind: Kind = "game"
    base_game_id: int | None = None             # an expansion's base game
    shop_handle: str | None = Field(None, pattern=r"^[a-z0-9][a-z0-9-]{0,200}$")   # found at Gameology: its facts and
                                                                # photo are read from there (not taken from the browser)


class GamePatch(BaseModel):
    name: str | None = Field(None, min_length=1)
    publisher: str | None = None
    year: int | None = Field(None, ge=1800, le=2200)
    min_players: int | None = Field(None, ge=1)
    max_players: int | None = Field(None, ge=1)
    play_minutes: int | None = Field(None, gt=0)
    status: Status | None = None
    purchase_date: date | None = None
    price_paid: Decimal | None = Field(None, ge=0)
    rating: int | None = Field(None, ge=1, le=10)
    notes: str | None = None
    bgg_url: str | None = Field(None, pattern=WEB_LINK)
    designer: str | None = None
    min_age: int | None = Field(None, ge=1, le=99)
    kind: Kind | None = None
    base_game_id: int | None = None


class ShopIn(BaseModel):
    shop_handle: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,200}$")
    replace: bool = False          # true: the shop's facts replace yours; false: only fill in blanks


class PlayIn(BaseModel):
    played_on: date | None = None   # default today
    players: str | None = None
    winner: str | None = None
    minutes: int | None = Field(None, gt=0)
    notes: str | None = None


class PlayPatch(BaseModel):
    played_on: date | None = None
    players: str | None = None
    winner: str | None = None
    minutes: int | None = Field(None, gt=0)
    notes: str | None = None


GAME_SELECT = """
SELECT g.game_id, g.name, g.publisher, g.year, g.min_players, g.max_players, g.play_minutes, g.status,
       g.purchase_date, g.price_paid, g.rating, g.notes, g.bgg_url, g.created_at, g.updated_at,
       g.designer, g.min_age, g.bgg_id, g.weight, g.categories, g.mechanisms, g.shop_handle, g.shop_url,
       g.shop_price, g.kind, g.base_game_id, base.name AS base_name,
       (SELECT count(*) FROM board_games x WHERE x.base_game_id = g.game_id)::int AS add_ons,
       g.photo IS NOT NULL AS has_photo,
       CASE WHEN g.photo IS NOT NULL THEN '/api/board-games/' || g.game_id || '/photo?v='
            || (extract(epoch FROM g.photo_updated) * 1000)::bigint END AS photo_url,
       (SELECT count(*) FROM board_game_plays p WHERE p.game_id = g.game_id)::int AS plays,
       (SELECT max(played_on) FROM board_game_plays p WHERE p.game_id = g.game_id) AS last_played
FROM board_games g LEFT JOIN board_games base ON base.game_id = g.base_game_id"""

PLAY_SELECT = """
SELECT p.*, g.name AS game_name FROM board_game_plays p JOIN board_games g USING (game_id)"""


def fetch_game(conn, game_id: int) -> dict:
    game = found(conn.execute(GAME_SELECT + " WHERE g.game_id = %s", (game_id,)).fetchone(), "Board game")
    game["play_log"] = conn.execute(PLAY_SELECT + " WHERE p.game_id = %s ORDER BY p.played_on DESC, p.play_id DESC",
                                    (game_id,)).fetchall()
    return game


def add_play(conn, game_id: int, body: PlayIn) -> dict:
    data = tidy_text(body.model_dump())
    data["played_on"] = data["played_on"] or date.today()
    play_id = insert_row(conn, "board_game_plays", {"game_id": game_id, **data}, "play_id")
    return conn.execute(PLAY_SELECT + " WHERE p.play_id = %s", (play_id,)).fetchone()


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------
@router.get("/board-games")
def list_games():
    """Every game: owned first, then by name."""
    with db() as conn:
        return conn.execute(GAME_SELECT + " ORDER BY g.status = 'Gone', g.status NOT IN ('Owned', 'To sell'), lower(g.name)").fetchall()


@router.get("/board-games/summary")
def summary():
    """For Home and the Games page: games owned, plays this month and year, the most played."""
    with db() as conn:
        row = conn.execute("""
            SELECT (SELECT count(*) FROM board_games WHERE status IN ('Owned', 'To sell'))::int AS owned,     -- still yours
                   (SELECT count(*) FROM board_games WHERE status = 'To sell')::int AS to_sell,
                   (SELECT count(*) FROM board_games WHERE status = 'Wanted')::int AS wanted,
                   count(*) FILTER (WHERE played_on >= date_trunc('month', current_date))::int AS plays_this_month,
                   count(*) FILTER (WHERE played_on >= date_trunc('year', current_date))::int AS plays_this_year,
                   count(*)::int AS plays
            FROM board_game_plays""").fetchone()
        row["most_played"] = conn.execute("""
            SELECT g.game_id, g.name, count(*)::int AS plays FROM board_game_plays p JOIN board_games g USING (game_id)
            GROUP BY g.game_id, g.name ORDER BY count(*) DESC, max(p.played_on) DESC LIMIT 1""").fetchone()
        return row


# The shop's facts -> board_games columns (fill_in only sets the empty ones unless told to replace).
FACTS = ("name", "publisher", "min_players", "max_players", "play_minutes", "min_age", "weight")


def shop_game(handle: str) -> dict:
    try:
        found_ = gameology.product(handle)
    except gameology.ShopError as e:
        raise HTTPException(502, str(e))
    if not found_:
        raise HTTPException(404, "Gameology doesn't have that product any more.")
    return found_


def fill_in(conn, game_id: int, facts: dict, replace: bool = False, set_kind: bool = False):
    """The shop's facts onto a game: blanks only (or everything with replace); its categories and
    mechanisms, its page, price and handle always (they're the shop's, not yours). Its kind (game /
    expansion / other) when it's new, or with replace / set_kind."""
    game = fetch_game(conn, game_id)
    data = {k: facts[k] for k in FACTS if facts.get(k) is not None and (replace or game.get(k) in (None, ""))}
    low, high = data.get("min_players", game["min_players"]), data.get("max_players", game["max_players"])
    if low and high and high < low:                       # the shop's and yours don't fit together: keep yours
        data.pop("min_players", None)
        data.pop("max_players", None)
    data.update(categories=sorted(set(facts["categories"]) | set(facts["types"])), mechanisms=facts["mechanisms"],
                shop_handle=facts["handle"], shop_url=facts["shop_url"], shop_price=facts["price"],
                shop_expansions=facts.get("expansion_handles") or [])
    if facts.get("kind") and (replace or set_kind):
        data["kind"] = facts["kind"]
    update_row(conn, "board_games", "game_id", game_id, data)
    link_add_ons(conn)


def link_add_ons(conn):
    """Expansions / extras without a base game get one: the game whose shop product lists them as
    its expansion, else the game whose name starts theirs ("Scythe the Wind Gambit" -> Scythe)."""
    conn.execute("""
        UPDATE board_games e SET base_game_id = b.game_id FROM board_games b
        WHERE e.kind <> 'game' AND e.base_game_id IS NULL AND e.shop_handle IS NOT NULL
          AND b.game_id <> e.game_id AND e.shop_handle = ANY(b.shop_expansions)""")
    conn.execute("""
        UPDATE board_games e SET base_game_id = (
            SELECT b.game_id FROM board_games b
            WHERE b.kind = 'game' AND b.game_id <> e.game_id AND lower(e.name) LIKE lower(b.name) || ' %%'
            ORDER BY length(b.name) DESC LIMIT 1)
        WHERE e.kind <> 'game' AND e.base_game_id IS NULL""")


def fetch_photo(game_id: int, facts: dict):
    """In the background: the product's photo, if the game still has none."""
    image, image_type = gameology.photo(facts)
    if image:
        with db() as conn:
            conn.execute("UPDATE board_games SET photo = %s, photo_type = %s, photo_updated = now() "
                         "WHERE game_id = %s AND photo IS NULL", (image, image_type, game_id))


@router.get("/board-games/lookup")
def lookup(q: str = Query(min_length=2, max_length=120)):
    """Board games at Gameology matching a name, best first, each with `game_id` if it's already
    in your games."""
    try:
        results = gameology.search(q)
    except gameology.ShopError as e:
        raise HTTPException(502, str(e))
    with db() as conn:
        for r in results:
            mine = conn.execute("SELECT game_id FROM board_games WHERE shop_handle = %s LIMIT 1", (r["handle"],)).fetchone()
            r["game_id"] = mine and mine["game_id"]
    return results


@router.post("/board-games", status_code=201)
def add_game(body: GameIn, background: BackgroundTasks):
    """Add a game. With a shop_handle, the shop's facts fill in what you left blank and its photo
    is fetched in the background."""
    data = tidy_text(body.model_dump())
    handle = data.pop("shop_handle")
    facts = shop_game(handle) if handle else None
    with db() as conn:
        _check_base(conn, None, data)
        game_id = insert_row(conn, "board_games", data, "game_id")
        if facts:
            fill_in(conn, game_id, facts, set_kind=True)
        game = fetch_game(conn, game_id)
    if facts and facts["image"]:
        background.add_task(fetch_photo, game_id, facts)
    return game


@router.post("/board-games/{game_id}/shop")
def from_shop(game_id: int, body: ShopIn, background: BackgroundTasks):
    """Fill in a game you already have from a Gameology product (blanks only, unless replace), and
    fetch its photo in the background if it has none."""
    facts = shop_game(body.shop_handle)
    with db() as conn:
        fill_in(conn, game_id, facts, body.replace)
        game = fetch_game(conn, game_id)
    if facts["image"] and not game["has_photo"]:
        background.add_task(fetch_photo, game_id, facts)
    return game


@router.get("/board-games/plays")
def list_plays(limit: int = Query(100, ge=1, le=1000)):
    """Every play, newest first."""
    with db() as conn:
        return conn.execute(PLAY_SELECT + " ORDER BY p.played_on DESC, p.play_id DESC LIMIT %s", (limit,)).fetchall()


# ---------------------------------------------------------------------------
# Types from the shop: every game you found at Gameology, checked again (one at a time, a second
# apart, in the background) for what the shop says it is and which expansions a base game has.
# ---------------------------------------------------------------------------
KINDS_CHECK = {"running": False, "done": 0, "total": 0, "changed": 0, "error": None}


def check_kinds():
    if KINDS_CHECK["running"]:
        return
    with db() as conn:
        games = conn.execute("SELECT game_id, kind, shop_handle FROM board_games WHERE shop_handle IS NOT NULL "
                             "ORDER BY game_id").fetchall()
    KINDS_CHECK.update(running=True, done=0, total=len(games), changed=0, error=None)
    try:
        for i, g in enumerate(games):
            if i:
                time.sleep(gameology.PAUSE)
            facts = gameology.product(g["shop_handle"])
            if facts:
                with db() as conn:
                    conn.execute("UPDATE board_games SET kind = COALESCE(%s, kind), shop_expansions = %s WHERE game_id = %s",
                                 (facts["kind"], facts["expansion_handles"], g["game_id"]))
                    if facts["kind"] and facts["kind"] != g["kind"]:
                        KINDS_CHECK["changed"] += 1
                        if facts["kind"] == "game":
                            conn.execute("UPDATE board_games SET base_game_id = NULL WHERE game_id = %s", (g["game_id"],))
            KINDS_CHECK["done"] = i + 1
        with db() as conn:
            link_add_ons(conn)
    except gameology.ShopError as e:
        KINDS_CHECK["error"] = str(e)
    finally:
        KINDS_CHECK["running"] = False


@router.post("/board-games/check-types", status_code=202)
def start_check_kinds(background: BackgroundTasks):
    """Ask Gameology again what each of your games is (game / expansion / other) and link expansions
    to their base games. Runs in the background; GET shows how far it got."""
    background.add_task(check_kinds)
    return KINDS_CHECK


@router.get("/board-games/check-types")
def check_kinds_status():
    return KINDS_CHECK


@router.get("/board-games/{game_id}")
def get_game(game_id: int):
    with db() as conn:
        return fetch_game(conn, game_id)


@router.patch("/board-games/{game_id}")
def update_game(game_id: int, body: GamePatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if "name" in data and not data["name"]:
        raise HTTPException(422, "A game needs a name.")
    if data.get("status", "x") is None or data.get("kind", "x") is None:
        raise HTTPException(422, "Status and type can't be empty.")
    with db() as conn:
        current = fetch_game(conn, game_id)
        _check_base(conn, current, data)
        update_row(conn, "board_games", "game_id", game_id, data)
        if data.get("kind", "game") != "game":   # no longer a base game: its add-ons lose their base
            conn.execute("UPDATE board_games SET base_game_id = NULL WHERE base_game_id = %s", (game_id,))
        return fetch_game(conn, game_id)


def _check_base(conn, current: dict | None, data: dict):
    """An expansion / extra can name its base game (another game, which is a game itself); a game
    that is one has no base."""
    kind = data.get("kind", current["kind"] if current else "game")
    if kind == "game":
        data["base_game_id"] = None
        return
    base_id = data.get("base_game_id")
    if base_id is None:
        return
    if current and base_id == current["game_id"]:
        raise HTTPException(422, "A game can't be its own base game.")
    base = conn.execute("SELECT kind FROM board_games WHERE game_id = %s", (base_id,)).fetchone()
    if not base:
        raise HTTPException(422, "That base game isn't in your games.")
    if base["kind"] != "game":
        raise HTTPException(422, "The base game has to be a game, not an expansion or extra.")




@router.delete("/board-games/{game_id}", status_code=204)
def delete_game(game_id: int):
    """Delete a game and its plays. (To keep the plays, mark it Gone instead.)"""
    with db() as conn:
        found(conn.execute("DELETE FROM board_games WHERE game_id = %s RETURNING game_id", (game_id,)).fetchone(),
              "Board game")
        conn.execute("DELETE FROM journal_links WHERE target_kind = 'game' AND target_id = %s", (game_id,))
    return Response(status_code=204)


add_photo_routes(router, "/board-games", "board_games", "game_id", "Board game")


# ---------------------------------------------------------------------------
# Plays
# ---------------------------------------------------------------------------
@router.post("/board-games/{game_id}/plays", status_code=201)
def log_play(game_id: int, body: PlayIn):
    """You played it: logging a play of a game you only wanted doesn't change its status."""
    with db() as conn:
        fetch_game(conn, game_id)
        return add_play(conn, game_id, body)


@router.patch("/board-game-plays/{play_id}")
def update_play(play_id: int, body: PlayPatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if "played_on" in data and data["played_on"] is None:
        raise HTTPException(422, "A play needs a day.")
    with db() as conn:
        found(conn.execute("SELECT play_id FROM board_game_plays WHERE play_id = %s", (play_id,)).fetchone(), "Play")
        update_row(conn, "board_game_plays", "play_id", play_id, data)
        return conn.execute(PLAY_SELECT + " WHERE p.play_id = %s", (play_id,)).fetchone()


@router.delete("/board-game-plays/{play_id}", status_code=204)
def delete_play(play_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM board_game_plays WHERE play_id = %s RETURNING play_id", (play_id,)).fetchone(),
              "Play")
    return Response(status_code=204)
