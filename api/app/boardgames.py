"""Board games (a hobby module): your collection and every time you played.

    games   board_games: Owned / To sell / Wanted / Borrowed / Gone, players, play time, price, rating, photo
    lookup  find a game at Gameology (gameology.py: a shop whose products carry BGG's facts) and
            fill in players, time, age, weight, categories, mechanisms, its photo and price
    plays   board_game_plays: the day, who played (seats with scores: boardgames_people.py), how long (setup, teach,
            playing), where, expansions, who went first, how fun, notes, photos. Played live: boardgames_live.py.

Plays show on the calendar and in Recent activity (activity.py). Writing "played @Catan" in the
journal offers to log a play (journal_actions.py).
"""
import re
import time
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import boardgames_people as people, gameology, goodgames
from .boardgames_people import PHOTOS, SeatIn
from .db import GAME_STATUSES, db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["board games"])

Status = Literal[tuple(GAME_STATUSES)]
Kind = Literal["game", "expansion", "other"]     # a game, an expansion for one, or something else (coins, sleeves...)
Scoring = Literal["highest", "lowest", "coop", "none"]   # who wins: the highest / lowest score, the table together, no score
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
    scoring: Scoring = "highest"
    score_parts: list[str] = Field(default_factory=list, max_length=30)   # its score sheet: "Birds", "Eggs"...
    teach_notes: str | None = None
    gg_id: str | None = Field(None, pattern=r"^\d{1,20}$")                       # or found at Good Games (its product number)
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
    scoring: Scoring | None = None
    score_parts: list[str] | None = Field(None, max_length=30)
    teach_notes: str | None = None


class ShopIn(BaseModel):
    shop_handle: str | None = Field(None, pattern=r"^[a-z0-9][a-z0-9-]{0,200}$")   # a Gameology product
    gg_id: str | None = Field(None, pattern=r"^\d{1,20}$")                          # or a Good Games one
    replace: bool = False          # true: the shop's facts replace yours; false: only fill in blanks


class PlayIn(BaseModel):
    played_on: date | None = None   # default today
    seats: list[SeatIn] | None = Field(None, max_length=30)   # who played, their scores (else players / winner as text)
    players: str | None = None      # "Sam, Jo and me": each name becomes a player
    winner: str | None = None
    minutes: int | None = Field(None, gt=0)       # playing time
    setup_minutes: int | None = Field(None, ge=0)
    teach_minutes: int | None = Field(None, ge=0)
    location: str | None = Field(None, max_length=120)
    expansions: list[int] = Field(default_factory=list, max_length=30)
    first_player_id: int | None = None
    coop_won: bool | None = None    # a co-op game: did the table win?
    rounds: int | None = Field(None, ge=0, le=999)
    fun: int | None = Field(None, ge=1, le=5)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=12)     # "close game", "first time with the expansion"
    finished: bool = True           # false = abandoned before the end (no winner)


class ElsewhereIn(PlayIn):
    """A play of a game you don't own (a friend's): found by name among your games, else added as
    'Played elsewhere'."""
    game_name: str = Field(min_length=1, max_length=200)


class PlayPatch(BaseModel):
    played_on: date | None = None
    seats: list[SeatIn] | None = Field(None, max_length=30)
    players: str | None = None
    winner: str | None = None
    minutes: int | None = Field(None, gt=0)
    setup_minutes: int | None = Field(None, ge=0)
    teach_minutes: int | None = Field(None, ge=0)
    location: str | None = Field(None, max_length=120)
    expansions: list[int] | None = Field(None, max_length=30)
    first_player_id: int | None = None
    coop_won: bool | None = None
    rounds: int | None = Field(None, ge=0, le=999)
    fun: int | None = Field(None, ge=1, le=5)
    notes: str | None = None
    tags: list[str] | None = Field(None, max_length=12)
    finished: bool | None = None


GAME_SELECT = """
SELECT g.game_id, g.name, g.publisher, g.year, g.min_players, g.max_players, g.play_minutes, g.status,
       g.purchase_date, g.price_paid, g.rating, g.notes, g.bgg_url, g.created_at, g.updated_at,
       g.designer, g.min_age, g.bgg_id, g.weight, g.categories, g.mechanisms, g.shop_handle, g.shop_url,
       g.shop_price, g.shop_name, g.kind, g.base_game_id, base.name AS base_name, g.scoring, g.score_parts, g.teach_notes,
       (SELECT count(*) FROM board_games x WHERE x.base_game_id = g.game_id)::int AS add_ons,
       g.photo IS NOT NULL AS has_photo,
       CASE WHEN g.photo IS NOT NULL THEN '/api/board-games/' || g.game_id || '/photo?v='
            || (extract(epoch FROM g.photo_updated) * 1000)::bigint END AS photo_url,
       (SELECT count(*) FROM board_game_plays p WHERE p.game_id = g.game_id)::int AS plays,
       (SELECT max(played_on) FROM board_game_plays p WHERE p.game_id = g.game_id) AS last_played
FROM board_games g LEFT JOIN board_games base ON base.game_id = g.base_game_id"""

PLAY_SELECT = f"""
SELECT p.*, g.name AS game_name, g.status AS game_status, g.scoring,
       COALESCE((SELECT json_agg(json_build_object('player_id', s.player_id, 'name', pl.name, 'is_me', pl.is_me,
                    'score', s.score, 'parts', s.parts, 'place', s.place, 'won', s.won, 'team', s.team, 'colour', s.colour,
                    'first_time', s.first_time, 'turn_seconds', s.turn_seconds, 'turn_count', s.turn_count,
                    'turn_over', s.turn_over) ORDER BY s.seat)
                 FROM board_game_play_players s JOIN board_game_players pl USING (player_id) WHERE s.play_id = p.play_id),
                '[]'::json) AS seats,
       (SELECT name FROM board_game_players WHERE player_id = p.first_player_id) AS first_player,
       COALESCE((SELECT array_agg(e.name ORDER BY e.name) FROM board_games e WHERE e.game_id = ANY(p.expansions)),
                '{{}}') AS expansion_names,
       {PHOTOS.format(col="play_id", ref="p.play_id")} AS photos
FROM board_game_plays p JOIN board_games g USING (game_id)"""


def fetch_game(conn, game_id: int) -> dict:
    game = found(conn.execute(GAME_SELECT + " WHERE g.game_id = %s", (game_id,)).fetchone(), "Board game")
    game["play_log"] = conn.execute(PLAY_SELECT + " WHERE p.game_id = %s ORDER BY p.played_on DESC, p.play_id DESC",
                                    (game_id,)).fetchall()
    game["stats"] = people.game_stats(conn, game_id).get(game_id)
    game["score_stats"] = people.score_stats(conn, game_id)
    game["add_on_list"] = conn.execute("SELECT game_id, name FROM board_games WHERE base_game_id = %s "
                                       "AND status NOT IN ('Gone', 'Wanted') ORDER BY name", (game_id,)).fetchall()
    return game


def tidy_parts(data: dict) -> dict:
    """A score sheet's parts: trimmed, no blanks, each once (none given = an empty sheet)."""
    if "score_parts" in data:
        data["score_parts"] = list(dict.fromkeys(p.strip()[:40] for p in data["score_parts"] or [] if p.strip()))
    return data


def unfinished_has_no_winner(data: dict):
    if data.get("finished") is False:
        data["winner"] = None


def check_play(conn, game_id: int, data: dict):
    """A play's expansions are this game's; who went first is one of your players."""
    if data.get("expansions"):
        data["expansions"] = list(dict.fromkeys(data["expansions"]))
        ok = {r["game_id"] for r in conn.execute("SELECT game_id FROM board_games WHERE game_id = ANY(%s) AND base_game_id = %s",
                                                 (data["expansions"], game_id)).fetchall()}
        if set(data["expansions"]) - ok:
            raise HTTPException(422, "An expansion there isn't one of this game's.")
    if data.get("first_player_id") is not None and not conn.execute(
            "SELECT 1 FROM board_game_players WHERE player_id = %s", (data["first_player_id"],)).fetchone():
        raise HTTPException(422, "Who went first isn't one of your players.")


def add_play(conn, game_id: int, body: PlayIn) -> dict:
    """A play and who sat at it: the seats given, or the players / winner text made into seats."""
    data = tidy_text(body.model_dump(exclude={"game_name", "seats"}))
    data["played_on"] = data["played_on"] or date.today()
    data["tags"] = people.tidy_tags(data.get("tags"))
    unfinished_has_no_winner(data)
    if not data["finished"]:
        data["coop_won"] = None
    check_play(conn, game_id, data)
    seats = body.seats if body.seats is not None else people.seats_from_text(data["players"], data["winner"])
    play_id = insert_row(conn, "board_game_plays", {"game_id": game_id, **data}, "play_id")
    if seats:
        people.save_seats(conn, play_id, seats)
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
                   count(*)::int AS plays,
                   count(*) FILTER (WHERE NOT finished)::int AS abandoned,
                   (SELECT count(*) FROM board_games WHERE status = 'Played elsewhere')::int AS played_elsewhere,
                   (SELECT count(*) FROM board_game_players)::int AS players
            FROM board_game_plays""").fetchone()
        row["live"] = conn.execute("SELECT l.live_id, l.started_at, g.name AS game_name FROM board_game_live l "
                                   "JOIN board_games g USING (game_id) ORDER BY l.started_at").fetchall()
        row["most_played"] = conn.execute("""
            SELECT g.game_id, g.name, count(*)::int AS plays FROM board_game_plays p JOIN board_games g USING (game_id)
            GROUP BY g.game_id, g.name ORDER BY count(*) DESC, max(p.played_on) DESC LIMIT 1""").fetchone()
        return row


# The shop's facts -> board_games columns (fill_in only sets the empty ones unless told to replace).
FACTS = ("name", "publisher", "min_players", "max_players", "play_minutes", "min_age", "weight")


def shop_game(handle: str | None = None, gg_id: str | None = None) -> dict:
    """The shop's facts for a product: Gameology's by handle, or Good Games' by product number."""
    if gg_id:
        try:
            p = goodgames.get(gg_id)
        except goodgames.ShopError as e:
            raise HTTPException(502, str(e))
        if not p:
            raise HTTPException(404, "Good Games doesn't have that product any more.")
        return goodgames.board_game(p)
    held = _gl_found.get(handle)
    if held and time.time() - held[0] < GG_FOR:          # the search you just picked it from already has its facts
        return {**held[1], "shop_name": "Gameology"}
    try:
        found_ = gameology.product(handle)
    except gameology.ShopError as e:
        raise HTTPException(502, str(e))
    if not found_:
        raise HTTPException(404, "Gameology doesn't have that product any more.")
    return {**found_, "shop_name": "Gameology"}


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
                shop_name=facts.get("shop_name", "Gameology"),
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


GG_FOR = 600                           # seconds a Good Games answer is kept (the box searches as you type)
_gg_found: dict[str, tuple[float, list[dict]]] = {}
# Gameology's search results by handle, kept as long: adding the game you picked uses them instead of asking for the
# product again (2026-11-07: its /products/<handle>.js answered 429 "too many requests" from the first ask, for
# minutes, while its search still answered - "Hive Pocket Edition" couldn't be added).
_gl_found: dict[str, tuple[float, dict]] = {}


def _good_games(q: str) -> list[dict]:
    key, now = q.strip().lower(), time.time()
    held = _gg_found.get(key)
    if held and now - held[0] < GG_FOR:
        return held[1]
    found_ = goodgames.board_games(q)
    for old in [k for k, (t, _) in _gg_found.items() if now - t >= GG_FOR]:
        del _gg_found[old]
    _gg_found[key] = (now, found_)
    return found_


@router.get("/board-games/lookup")
def lookup(q: str = Query(min_length=2, max_length=120), more: bool = False):
    """Board games matching a name, best first, each with `game_id` if it's already in your games and
    `source` (gameology / goodgames). Gameology first (BoardGameGeek's facts); Good Games fills the
    holes - asked when Gameology has nothing with every word you typed, or with more=true. If only one
    shop answers, its results come back (`notes` says what went wrong with the other)."""
    notes, results = [], []
    try:
        results = [{**r, "source": "gameology", "shop_name": "Gameology"} for r in gameology.search(q)]
        now = time.time()
        for old in [k for k, (t, _) in _gl_found.items() if now - t >= GG_FOR]:
            del _gl_found[old]
        _gl_found.update({r["handle"]: (now, r) for r in results})
    except gameology.ShopError as e:
        notes.append(str(e))
    words = re.findall(r"[a-z0-9]+", q.lower())
    full_match = any(all(w in " ".join(re.findall(r"[a-z0-9]+", r["title"].lower())) for w in words) for r in results)
    if more or not full_match:
        try:
            have = {re.sub(r"[^a-z0-9]", "", r["name"].lower()) for r in results}
            results += [g for g in _good_games(q) if re.sub(r"[^a-z0-9]", "", g["name"].lower()) not in have]
        except goodgames.ShopError as e:
            notes.append(str(e))
    if not results and notes:
        raise HTTPException(502, " ".join(notes))
    with db() as conn:
        for r in results:
            mine = conn.execute("SELECT game_id FROM board_games WHERE shop_handle = %s AND shop_name = %s LIMIT 1",
                                (r["handle"], r["shop_name"])).fetchone()
            r["game_id"] = mine and mine["game_id"]
    return {"results": results, "asked_good_games": more or not full_match, "notes": notes}


@router.post("/board-games", status_code=201)
def add_game(body: GameIn, background: BackgroundTasks):
    """Add a game. With a shop_handle, the shop's facts fill in what you left blank and its photo
    is fetched in the background."""
    data = tidy_parts(tidy_text(body.model_dump()))
    handle, gg_id = data.pop("shop_handle"), data.pop("gg_id")
    facts = shop_game(handle, gg_id) if handle or gg_id else None
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
    if not body.shop_handle and not body.gg_id:
        raise HTTPException(422, "Which product? (a Gameology handle or a Good Games product number)")
    facts = shop_game(body.shop_handle, body.gg_id)
    with db() as conn:
        fill_in(conn, game_id, facts, body.replace)
        game = fetch_game(conn, game_id)
    if facts["image"] and not game["has_photo"]:
        background.add_task(fetch_photo, game_id, facts)
    return game


@router.get("/board-games/plays")
def list_plays(limit: int = Query(100, ge=1, le=1000), tag: str | None = Query(None, max_length=40)):
    """Every play, newest first; ?tag= only the plays with that tag (any case)."""
    with db() as conn:
        return conn.execute(
            PLAY_SELECT + " WHERE %(tag)s::text IS NULL OR EXISTS (SELECT 1 FROM unnest(p.tags) t WHERE lower(t) = lower(%(tag)s)) "
            "ORDER BY p.played_on DESC, p.play_id DESC LIMIT %(limit)s", {"tag": tag, "limit": limit}).fetchall()


@router.get("/board-games/tags")
def play_tags():
    """Every tag used on a play, most used first (the suggestions the play forms offer)."""
    with db() as conn:
        return conn.execute("SELECT min(t) AS tag, count(*)::int AS plays FROM board_game_plays p, unnest(p.tags) t "
                            "GROUP BY lower(t) ORDER BY 2 DESC, lower(min(t)) LIMIT 100").fetchall()


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
                             "AND shop_name = 'Gameology' ORDER BY game_id").fetchall()     # Good Games has no type tag
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
    data = tidy_parts(tidy_text(body.model_dump(exclude_unset=True)))
    if "name" in data and not data["name"]:
        raise HTTPException(422, "A game needs a name.")
    if data.get("status", "x") is None or data.get("kind", "x") is None or data.get("scoring", "x") is None:
        raise HTTPException(422, "Status, type and scoring can't be empty.")
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
    """You played it: logging a play of a game you only wanted doesn't change its status. Answers with the play and
    anything it beat (a personal best, the record)."""
    with db() as conn:
        fetch_game(conn, game_id)
        play = add_play(conn, game_id, body)
        return {**play, "highlights": people.highlights(conn, play["play_id"])}


@router.post("/board-games/plays", status_code=201)
def log_play_elsewhere(body: ElsewhereIn):
    """A play of a game that isn't in your library (at a friend's): the game is found by name (any
    case) among your games, or added with the status 'Played elsewhere' (not counted as yours)."""
    name = body.game_name.strip()
    with db() as conn:
        game = conn.execute("SELECT game_id FROM board_games WHERE lower(name) = lower(%s) "
                            "ORDER BY status = 'Gone' LIMIT 1", (name,)).fetchone()
        game_id = game["game_id"] if game else insert_row(
            conn, "board_games", {"name": name, "status": "Played elsewhere", "kind": "game"}, "game_id")
        play = add_play(conn, game_id, body)
        return {**play, "highlights": people.highlights(conn, play["play_id"])}


@router.patch("/board-game-plays/{play_id}")
def update_play(play_id: int, body: PlayPatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if "played_on" in data and data["played_on"] is None:
        raise HTTPException(422, "A play needs a day.")
    if data.get("finished", "x") is None:
        raise HTTPException(422, "Finished must be true or false.")
    if "expansions" in data and data["expansions"] is None:
        raise HTTPException(422, "Expansions must be a list.")
    unfinished_has_no_winner(data)
    if "tags" in data:
        data["tags"] = people.tidy_tags(data["tags"])
    data.pop("seats", None)
    with db() as conn:
        play = found(conn.execute("SELECT game_id, players, winner FROM board_game_plays WHERE play_id = %s",
                                  (play_id,)).fetchone(), "Play")
        check_play(conn, play["game_id"], data)
        update_row(conn, "board_game_plays", "play_id", play_id, data)
        if body.seats is not None:
            people.save_seats(conn, play_id, body.seats)
        elif "players" in data or "winner" in data:            # text, as before: made into seats
            text = {**play, **{k: data[k] for k in ("players", "winner") if k in data}}
            people.save_seats(conn, play_id, people.seats_from_text(text["players"], text["winner"]))
        elif {"finished", "coop_won", "played_on"} & data.keys():   # who won follows how it ended
            kept = conn.execute("SELECT player_id, score, parts, adds, team, colour, CASE WHEN won AND place IS NULL "
                                "THEN true END AS won FROM board_game_play_players WHERE play_id = %s ORDER BY seat",
                                (play_id,)).fetchall()
            if kept:
                people.save_seats(conn, play_id, [{**s, "adds": list(s["adds"])} for s in kept], resolved=True)
        return conn.execute(PLAY_SELECT + " WHERE p.play_id = %s", (play_id,)).fetchone()


@router.delete("/board-game-plays/{play_id}", status_code=204)
def delete_play(play_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM board_game_plays WHERE play_id = %s RETURNING play_id", (play_id,)).fetchone(),
              "Play")
    return Response(status_code=204)
