"""Board games (a hobby module): your collection and every time you played.

    games   board_games: Owned / Wanted / Borrowed / Gone, players, play time, price, rating, photo
    plays   board_game_plays: the day, who played, who won, how long, notes

Plays show on the calendar and in Recent activity (activity.py). Writing "played @Catan" in the
journal offers to log a play (journal_actions.py).
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .db import GAME_STATUSES, db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["board games"])

Status = Literal[tuple(GAME_STATUSES)]
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
       g.photo IS NOT NULL AS has_photo,
       CASE WHEN g.photo IS NOT NULL THEN '/api/board-games/' || g.game_id || '/photo?v='
            || (extract(epoch FROM g.photo_updated) * 1000)::bigint END AS photo_url,
       (SELECT count(*) FROM board_game_plays p WHERE p.game_id = g.game_id)::int AS plays,
       (SELECT max(played_on) FROM board_game_plays p WHERE p.game_id = g.game_id) AS last_played
FROM board_games g"""

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
        return conn.execute(GAME_SELECT + " ORDER BY g.status = 'Gone', g.status <> 'Owned', lower(g.name)").fetchall()


@router.get("/board-games/summary")
def summary():
    """For Home and the Games page: games owned, plays this month and year, the most played."""
    with db() as conn:
        row = conn.execute("""
            SELECT (SELECT count(*) FROM board_games WHERE status = 'Owned')::int AS owned,
                   (SELECT count(*) FROM board_games WHERE status = 'Wanted')::int AS wanted,
                   count(*) FILTER (WHERE played_on >= date_trunc('month', current_date))::int AS plays_this_month,
                   count(*) FILTER (WHERE played_on >= date_trunc('year', current_date))::int AS plays_this_year,
                   count(*)::int AS plays
            FROM board_game_plays""").fetchone()
        row["most_played"] = conn.execute("""
            SELECT g.game_id, g.name, count(*)::int AS plays FROM board_game_plays p JOIN board_games g USING (game_id)
            GROUP BY g.game_id, g.name ORDER BY count(*) DESC, max(p.played_on) DESC LIMIT 1""").fetchone()
        return row


@router.post("/board-games", status_code=201)
def add_game(body: GameIn):
    with db() as conn:
        return fetch_game(conn, insert_row(conn, "board_games", tidy_text(body.model_dump()), "game_id"))


@router.get("/board-games/plays")
def list_plays(limit: int = Query(100, ge=1, le=1000)):
    """Every play, newest first."""
    with db() as conn:
        return conn.execute(PLAY_SELECT + " ORDER BY p.played_on DESC, p.play_id DESC LIMIT %s", (limit,)).fetchall()


@router.get("/board-games/{game_id}")
def get_game(game_id: int):
    with db() as conn:
        return fetch_game(conn, game_id)


@router.patch("/board-games/{game_id}")
def update_game(game_id: int, body: GamePatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if "name" in data and not data["name"]:
        raise HTTPException(422, "A game needs a name.")
    if data.get("status", "x") is None:
        raise HTTPException(422, "Status can't be empty.")
    with db() as conn:
        fetch_game(conn, game_id)
        update_row(conn, "board_games", "game_id", game_id, data)
        return fetch_game(conn, game_id)


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
