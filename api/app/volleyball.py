"""Volleyball (a hobby module): games and training, your gear, and videos.

    games   volleyball_games: the day, kind (Game / Training / Social / Tournament), team,
            opponent, sets won and lost, venue, notes. A game logged from a calendar event keeps
            its event_id, so the calendar knows that day's result is in.
    teams   volleyball_teams: the teams you play in and where they play; one can be the default.
            /volleyball/teams also gives what a new game starts with (defaults) and the opponents
            and venues used before (for suggestions), so nothing is typed twice.
    gear    gear (shared with future hobbies): shoes, knee pads, balls... with condition and photo
    videos  links to game footage or drills (YouTube, Google Drive...): only the link is stored

Games show on the calendar and in Recent activity (activity.py).
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from .db import GEAR_CONDITIONS, VOLLEYBALL_KINDS, db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["volleyball"])

Kind = Literal[tuple(VOLLEYBALL_KINDS)]
Condition = Literal[tuple(GEAR_CONDITIONS)]


class GameIn(BaseModel):
    played_on: date | None = None   # default today
    kind: Kind = "Game"
    team_id: int | None = None
    team: str | None = None          # or a team's name: found (any case), or added as a new team
    opponent: str | None = None
    venue: str | None = None
    sets_won: int | None = Field(None, ge=0)
    sets_lost: int | None = Field(None, ge=0)
    notes: str | None = None
    event_id: int | None = None


class GamePatch(BaseModel):
    played_on: date | None = None
    kind: Kind | None = None
    team_id: int | None = None
    team: str | None = None
    opponent: str | None = None
    venue: str | None = None
    sets_won: int | None = Field(None, ge=0)
    sets_lost: int | None = Field(None, ge=0)
    notes: str | None = None


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str | None = Field(None, max_length=200)
    is_default: bool = False
    notes: str | None = None


class TeamPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    location: str | None = Field(None, max_length=200)
    is_default: bool | None = None
    retired: bool | None = None
    notes: str | None = None


class GearIn(BaseModel):
    name: str = Field(min_length=1)
    kind: str | None = None
    brand: str | None = None
    size: str | None = None
    condition: Condition = "Good"
    purchase_date: date | None = None
    price_paid: Decimal | None = Field(None, ge=0)
    notes: str | None = None


class GearPatch(BaseModel):
    name: str | None = Field(None, min_length=1)
    kind: str | None = None
    brand: str | None = None
    size: str | None = None
    condition: Condition | None = None
    purchase_date: date | None = None
    price_paid: Decimal | None = Field(None, ge=0)
    notes: str | None = None


class VideoIn(BaseModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    topic: str | None = None
    game_id: int | None = None
    notes: str | None = None
    watched: bool = False


class VideoPatch(BaseModel):
    title: str | None = Field(None, min_length=1)
    url: str | None = Field(None, min_length=1)
    topic: str | None = None
    game_id: int | None = None
    notes: str | None = None
    watched: bool | None = None


# Won / Lost / Drew from the sets, when both are known.
RESULT = """CASE WHEN v.sets_won IS NULL OR v.sets_lost IS NULL THEN NULL
                 WHEN v.sets_won > v.sets_lost THEN 'Won' WHEN v.sets_won < v.sets_lost THEN 'Lost' ELSE 'Drew' END"""
GAME_SELECT = f"""
SELECT v.*, {RESULT} AS result, e.title AS event_title, t.name AS team, t.location AS team_location,
       (SELECT count(*) FROM volleyball_videos x WHERE x.game_id = v.game_id)::int AS videos
FROM volleyball_games v LEFT JOIN calendar_events e USING (event_id)
LEFT JOIN volleyball_teams t ON t.team_id = v.team_id"""

TEAM_SELECT = """
SELECT t.*, count(v.game_id)::int AS games, max(v.played_on) AS last_played
FROM volleyball_teams t LEFT JOIN volleyball_games v ON v.team_id = t.team_id
GROUP BY t.team_id"""

GEAR_SELECT = """
SELECT g.gear_id, g.hobby, g.name, g.kind, g.brand, g.size, g.condition, g.purchase_date, g.price_paid,
       g.notes, g.created_at, g.updated_at, g.photo IS NOT NULL AS has_photo,
       CASE WHEN g.photo IS NOT NULL THEN '/api/gear/' || g.gear_id || '/photo?v='
            || (extract(epoch FROM g.photo_updated) * 1000)::bigint END AS photo_url
FROM gear g"""

VIDEO_SELECT = """
SELECT x.*, v.played_on AS game_day, v.opponent AS game_opponent
FROM volleyball_videos x LEFT JOIN volleyball_games v USING (game_id)"""


def fetch_game(conn, game_id: int) -> dict:
    game = found(conn.execute(GAME_SELECT + " WHERE v.game_id = %s", (game_id,)).fetchone(), "Volleyball game")
    game["video_list"] = conn.execute(VIDEO_SELECT + " WHERE x.game_id = %s ORDER BY x.video_id", (game_id,)).fetchall()
    return game


def fetch_gear(conn, gear_id: int) -> dict:
    return found(conn.execute(GEAR_SELECT + " WHERE g.gear_id = %s", (gear_id,)).fetchone(), "Gear")


def fetch_video(conn, video_id: int) -> dict:
    return found(conn.execute(VIDEO_SELECT + " WHERE x.video_id = %s", (video_id,)).fetchone(), "Video")


def game_team(conn, data: dict):
    """A game's team: team_id (must exist) or a team name (found ignoring case, else added)."""
    name = data.pop("team", None)
    if data.get("team_id") is not None:
        found(conn.execute("SELECT 1 FROM volleyball_teams WHERE team_id = %s", (data["team_id"],)).fetchone(), "Team")
    elif name:
        row = conn.execute("SELECT team_id FROM volleyball_teams WHERE lower(name) = lower(%s)", (name,)).fetchone()
        data["team_id"] = row["team_id"] if row else insert_row(conn, "volleyball_teams", {"name": name}, "team_id")


def check_url(url: str | None):
    if url is not None and not url.lower().startswith(("http://", "https://")):
        raise HTTPException(422, "A video link must start with http:// or https://.")


# ---------------------------------------------------------------------------
# Games and training
# ---------------------------------------------------------------------------
@router.get("/volleyball/games")
def list_games():
    """Every game and training, newest first."""
    with db() as conn:
        return conn.execute(GAME_SELECT + " ORDER BY v.played_on DESC, v.game_id DESC").fetchall()


@router.get("/volleyball/summary")
def summary():
    """This year: games and training, wins and losses (games with both set counts), the last game."""
    with db() as conn:
        row = conn.execute(f"""
            SELECT count(*) FILTER (WHERE v.kind <> 'Training')::int AS games,
                   count(*) FILTER (WHERE v.kind = 'Training')::int AS trainings,
                   count(*) FILTER (WHERE {RESULT} = 'Won')::int AS won,
                   count(*) FILTER (WHERE {RESULT} = 'Lost')::int AS lost
            FROM volleyball_games v WHERE v.played_on >= date_trunc('year', current_date)""").fetchone()
        row["last"] = conn.execute(GAME_SELECT + " WHERE v.kind <> 'Training' ORDER BY v.played_on DESC, v.game_id DESC "
                                   "LIMIT 1").fetchone()
        row["gear_to_replace"] = conn.execute("SELECT count(*)::int AS n FROM gear WHERE condition = 'Needs replacing'"
                                              ).fetchone()["n"]
        return row


@router.post("/volleyball/games", status_code=201)
def add_game(body: GameIn):
    """Log a game or training (event_id = the calendar event it was on, if any)."""
    data = tidy_text(body.model_dump())
    data["played_on"] = data["played_on"] or date.today()
    with db() as conn:
        game_team(conn, data)
        return fetch_game(conn, insert_row(conn, "volleyball_games", data, "game_id"))


@router.get("/volleyball/games/{game_id}")
def get_game(game_id: int):
    with db() as conn:
        return fetch_game(conn, game_id)


@router.patch("/volleyball/games/{game_id}")
def update_game(game_id: int, body: GamePatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    for required in ("played_on", "kind"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"A game needs a {'day' if required == 'played_on' else 'kind'}.")
    with db() as conn:
        fetch_game(conn, game_id)
        game_team(conn, data)
        update_row(conn, "volleyball_games", "game_id", game_id, data)
        return fetch_game(conn, game_id)


@router.delete("/volleyball/games/{game_id}", status_code=204)
def delete_game(game_id: int):
    """Delete a game. Its videos stay (unlinked)."""
    with db() as conn:
        found(conn.execute("DELETE FROM volleyball_games WHERE game_id = %s RETURNING game_id",
                           (game_id,)).fetchone(), "Volleyball game")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Teams, and what a new game starts with
# ---------------------------------------------------------------------------
def fetch_team(conn, team_id: int) -> dict:
    return found(conn.execute(f"SELECT * FROM ({TEAM_SELECT}) t WHERE t.team_id = %s", (team_id,)).fetchone(), "Team")


def _only_default(conn, team_id: int):
    conn.execute("UPDATE volleyball_teams SET is_default = false WHERE is_default AND team_id <> %s", (team_id,))


@router.get("/volleyball/teams")
def list_teams():
    """Your teams (current ones first, the default at the top), plus:
        defaults   what a new game starts with: the default team - else the team of your latest
                   game - with its location as the venue (else the latest venue), and the kind
                   you logged last
        opponents  teams you've played, most recent first (suggestions while typing)
        venues     places you've played and your teams' locations"""
    with db() as conn:
        teams = conn.execute(f"SELECT * FROM ({TEAM_SELECT}) t "
                             "ORDER BY t.retired, t.is_default DESC, t.last_played DESC NULLS LAST, lower(t.name)").fetchall()
        last = conn.execute("SELECT v.kind, v.venue, v.team_id FROM volleyball_games v "
                            "ORDER BY v.played_on DESC, v.game_id DESC LIMIT 1").fetchone()
        opponents = [r["opponent"] for r in conn.execute(
            "SELECT opponent FROM volleyball_games WHERE opponent IS NOT NULL "
            "GROUP BY opponent ORDER BY max(played_on) DESC LIMIT 50").fetchall()]
        venues = [r["venue"] for r in conn.execute(
            "SELECT venue FROM (SELECT venue, played_on FROM volleyball_games UNION ALL "
            "SELECT location, current_date FROM volleyball_teams WHERE NOT retired) x "
            "WHERE venue IS NOT NULL GROUP BY venue ORDER BY max(played_on) DESC LIMIT 50").fetchall()]
    current = [t for t in teams if not t["retired"]]
    team = next((t for t in current if t["is_default"]), None) or \
        next((t for t in current if last and t["team_id"] == last["team_id"]), None)
    defaults = {"team_id": team and team["team_id"], "venue": (team and team["location"]) or (last and last["venue"]),
                "kind": last["kind"] if last else "Game"}
    return {"teams": teams, "defaults": defaults, "opponents": opponents, "venues": venues}


@router.post("/volleyball/teams", status_code=201)
def add_team(body: TeamIn):
    data = tidy_text(body.model_dump())
    with db() as conn:
        if conn.execute("SELECT 1 FROM volleyball_teams WHERE lower(name) = lower(%s)", (data["name"],)).fetchone():
            raise HTTPException(409, f"You already have a team called {data['name']}.")
        if data["is_default"]:
            _only_default(conn, 0)                   # before the insert: one default at most
        return fetch_team(conn, insert_row(conn, "volleyball_teams", data, "team_id"))


@router.patch("/volleyball/teams/{team_id}")
def update_team(team_id: int, body: TeamPatch):
    """Change a team. Making it the default takes that from any other; retiring it stops it being
    the default (it stays on its old games)."""
    data = tidy_text(body.model_dump(exclude_unset=True))
    if "name" in data and not data["name"]:
        raise HTTPException(422, "A team needs a name.")
    with db() as conn:
        fetch_team(conn, team_id)
        if data.get("name") and conn.execute("SELECT 1 FROM volleyball_teams WHERE lower(name) = lower(%s) "
                                             "AND team_id <> %s", (data["name"], team_id)).fetchone():
            raise HTTPException(409, f"You already have a team called {data['name']}.")
        if data.get("retired"):
            data["is_default"] = False
        if data.get("is_default"):
            _only_default(conn, team_id)
        update_row(conn, "volleyball_teams", "team_id", team_id, data)
        return fetch_team(conn, team_id)


@router.delete("/volleyball/teams/{team_id}", status_code=204)
def delete_team(team_id: int):
    """Only a team with no games (retire one that has some, so they keep its name)."""
    with db() as conn:
        team = fetch_team(conn, team_id)
        if team["games"]:
            raise HTTPException(409, f"{team['name']} has {team['games']} game{'s' if team['games'] != 1 else ''} "
                                     "logged - retire it instead, so they keep its name.")
        conn.execute("DELETE FROM volleyball_teams WHERE team_id = %s", (team_id,))
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Gear
# ---------------------------------------------------------------------------
@router.get("/gear")
def list_gear():
    """Your gear: in use first (worst condition first), retired last."""
    with db() as conn:
        return conn.execute(GEAR_SELECT + " ORDER BY g.condition = 'Retired', "
                            "array_position(ARRAY['Needs replacing', 'Worn', 'Good', 'New'], g.condition), "
                            "lower(g.name)").fetchall()


@router.post("/gear", status_code=201)
def add_gear(body: GearIn):
    with db() as conn:
        return fetch_gear(conn, insert_row(conn, "gear", tidy_text(body.model_dump()), "gear_id"))


@router.get("/gear/{gear_id}")
def get_gear(gear_id: int):
    with db() as conn:
        return fetch_gear(conn, gear_id)


@router.patch("/gear/{gear_id}")
def update_gear(gear_id: int, body: GearPatch):
    data = tidy_text(body.model_dump(exclude_unset=True))
    if "condition" in data and data["condition"] is None:
        raise HTTPException(422, "Condition can't be empty.")
    with db() as conn:
        fetch_gear(conn, gear_id)
        update_row(conn, "gear", "gear_id", gear_id, data)
        return fetch_gear(conn, gear_id)


@router.delete("/gear/{gear_id}", status_code=204)
def delete_gear(gear_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM gear WHERE gear_id = %s RETURNING gear_id", (gear_id,)).fetchone(), "Gear")
        conn.execute("DELETE FROM journal_links WHERE target_kind = 'gear' AND target_id = %s", (gear_id,))
    return Response(status_code=204)


add_photo_routes(router, "/gear", "gear", "gear_id", "Gear")


# ---------------------------------------------------------------------------
# Videos (links only)
# ---------------------------------------------------------------------------
@router.get("/volleyball/videos")
def list_videos():
    """Not watched first, then newest."""
    with db() as conn:
        return conn.execute(VIDEO_SELECT + " ORDER BY x.watched, x.created_at DESC").fetchall()


@router.post("/volleyball/videos", status_code=201)
def add_video(body: VideoIn):
    data = tidy_text(body.model_dump(), required=("title", "url"))
    check_url(data["url"])
    with db() as conn:
        return fetch_video(conn, insert_row(conn, "volleyball_videos", data, "video_id"))


@router.patch("/volleyball/videos/{video_id}")
def update_video(video_id: int, body: VideoPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title", "url"))
    check_url(data.get("url"))
    if data.get("watched", False) is None:
        raise HTTPException(422, "Watched must be true or false.")
    with db() as conn:
        fetch_video(conn, video_id)
        update_row(conn, "volleyball_videos", "video_id", video_id, data)
        return fetch_video(conn, video_id)


@router.delete("/volleyball/videos/{video_id}", status_code=204)
def delete_video(video_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM volleyball_videos WHERE video_id = %s RETURNING video_id",
                           (video_id,)).fetchone(), "Video")
    return Response(status_code=204)
