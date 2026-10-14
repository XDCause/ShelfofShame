"""Video games on other platforms: Epic and Ubisoft, kept apart from Steam (videogames.py).

    account   the Exophase profile (a name or profile address) -> the player id for each linked
              platform, read from the profile page. Setting it reads the games straight away.
    sync      Exophase's public API lists each platform's games (exophase.player_games). Runs with
              every Steam sync (videogames.run_sync), after the DLC lists, on the same polite
              one-at-a-time Exophase queue.
    games     Epic: achievements as Exophase has them. Ubisoft: Exophase only sees Ubisoft's
              *challenges*, never the achievements, so it brings names, pictures and playtime and
              you type the achievements in (my_done / my_total; my_minutes overrides the playtime).
              Ubisoft games Exophase doesn't list can be added by hand.

Profile completion, the goal, streaks and the 7-day changes stay Steam-only (they match SteamHunters).
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import exophase
from .db import db, found

router = APIRouter(prefix="/api", tags=["video games"])
log = logging.getLogger("othergames")

# Ubisoft's numbers are the ones you typed in; Epic's are Exophase's (unless you typed your own).
# Playtime: yours if you gave it, else Exophase's.
SELECT = """
SELECT o.game_id, o.platform, o.source_id, o.name, o.picture_url, o.page_url, o.hidden, o.last_played,
       o.my_done, o.my_total, o.my_minutes, o.exo_minutes,
       CASE WHEN o.platform = 'ubisoft' THEN o.exo_done END AS challenges_done,
       CASE WHEN o.platform = 'ubisoft' THEN o.exo_total END AS challenges_total,
       d.done, d.total, COALESCE(o.my_minutes, o.exo_minutes) AS playtime_minutes,
       CASE WHEN d.total > 0 THEN round(100.0 * d.done / d.total, 1) END AS percent,
       CASE WHEN d.total > 0 AND d.done >= d.total THEN COALESCE(o.exo_completed_at, o.updated_at) END AS completed_at
FROM vg_other_games o
CROSS JOIN LATERAL (SELECT CASE WHEN o.platform = 'ubisoft' THEN o.my_done ELSE COALESCE(o.my_done, o.exo_done) END AS done,
                           CASE WHEN o.platform = 'ubisoft' THEN o.my_total ELSE COALESCE(o.my_total, o.exo_total) END AS total) d"""
NAMES = {"epic": "Epic", "ubisoft": "Ubisoft"}


class AccountIn(BaseModel):
    profile: str = Field(min_length=2, max_length=200)   # an Exophase name or profile address


class GameIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    done: int | None = Field(None, ge=0)
    total: int | None = Field(None, ge=0)
    hours: float | None = Field(None, ge=0, le=100000)


class GamePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    done: int | None = Field(None, ge=0)
    total: int | None = Field(None, ge=0)
    hours: float | None = Field(None, ge=0, le=100000)
    hidden: bool | None = None


def _ts(unix) -> datetime | None:
    return datetime.fromtimestamp(int(unix), timezone.utc) if unix else None


def sync_other() -> str:
    """Read every linked platform's games from Exophase and save them. Typed-in numbers are never
    touched. Returns a note for the sync's message ('' if no profile is set)."""
    with db() as conn:
        account = conn.execute("SELECT exo_players FROM vg_sync WHERE id = 1").fetchone()
    players = (account or {}).get("exo_players") or {}
    if not players:
        return ""
    counts = {}
    try:
        for environment, player in players.items():
            platform = exophase.PLATFORMS.get(environment)
            if not platform:
                continue
            games = exophase.player_games(player, environment)
            exophase.pause()
            with db() as conn:
                for g in games:
                    conn.execute("""
                        INSERT INTO vg_other_games (platform, source_id, name, picture_url, page_url, exo_done, exo_total,
                                                    exo_minutes, last_played, exo_completed_at)
                        VALUES (%(platform)s, %(source_id)s, %(name)s, %(picture_url)s, %(page_url)s, %(exo_done)s,
                                %(exo_total)s, %(exo_minutes)s, %(last_played)s, %(exo_completed_at)s)
                        ON CONFLICT (platform, source_id) WHERE source_id IS NOT NULL DO UPDATE SET
                            name = EXCLUDED.name, picture_url = EXCLUDED.picture_url, page_url = EXCLUDED.page_url,
                            exo_done = EXCLUDED.exo_done, exo_total = EXCLUDED.exo_total,
                            exo_minutes = EXCLUDED.exo_minutes, last_played = EXCLUDED.last_played,
                            exo_completed_at = EXCLUDED.exo_completed_at""",
                        {**g, "platform": platform, "last_played": _ts(g["last_played"]),
                         "exo_completed_at": _ts(g["exo_completed_at"])})
            counts[NAMES[platform]] = len(games)
    except exophase.Unavailable as e:
        log.warning("Other platforms: %s", e)
        with db() as conn:
            conn.execute("UPDATE vg_sync SET exo_error = %s WHERE id = 1", (str(e),))
        return " (Exophase didn't answer, so the Epic / Ubisoft games wait for the next sync)"
    with db() as conn:
        conn.execute("UPDATE vg_sync SET exo_synced_at = now(), exo_error = NULL WHERE id = 1")
    return ", " + ", ".join(f"{n} {name}" for name, n in counts.items()) + " games from Exophase"


def summarise(games: list[dict]) -> list[dict]:
    """Per platform: games, achievements you have / of, games at 100%, playtime; Ubisoft also how
    many games still need their achievements typed in."""
    out = []
    for platform, name in NAMES.items():
        mine = [g for g in games if g["platform"] == platform and not g["hidden"]]
        if not mine:
            continue
        counted = [g for g in mine if g["total"]]
        out.append({
            "platform": platform, "name": name, "games": len(mine),
            "done": sum(g["done"] or 0 for g in counted), "total": sum(g["total"] for g in counted),
            "perfect": sum(1 for g in counted if g["done"] >= g["total"]),
            "playtime_minutes": sum(g["playtime_minutes"] or 0 for g in mine),
            "to_fill_in": sum(1 for g in mine if platform == "ubisoft" and g["total"] is None),
        })
    return out


@router.get("/videogames/other/account")
def account():
    with db() as conn:
        a = conn.execute("SELECT exo_profile, exo_players, exo_synced_at, exo_error FROM vg_sync WHERE id = 1").fetchone()
    a = a or {}
    return {"profile": a.get("exo_profile"), "linked": [exophase.PLATFORMS[e] for e in (a.get("exo_players") or {})],
            "synced_at": a.get("exo_synced_at"), "error": a.get("exo_error")}


@router.put("/videogames/other/account")
def set_account(body: AccountIn):
    """Follow an Exophase profile for Epic and Ubisoft games, and read them now (a few requests)."""
    name = exophase.profile_name(body.profile)
    if not name:
        raise HTTPException(422, "Enter your Exophase name or profile address (exophase.com/user/...).")
    try:
        players = exophase.profile_players(name)
    except exophase.Unavailable as e:
        raise HTTPException(502, str(e))
    if not players:
        raise HTTPException(422, f"Exophase has no profile called '{name}' with Epic or Ubisoft linked.")
    with db() as conn:
        conn.execute("UPDATE vg_sync SET exo_profile = %s, exo_players = %s, exo_error = NULL WHERE id = 1",
                     (name, Jsonb(players)))
    exophase.pause()
    sync_other()
    return {**account(), **games()}


@router.get("/videogames/other")
def games():
    """Every Epic and Ubisoft game (hidden ones too, marked) and a summary per platform."""
    with db() as conn:
        rows = conn.execute(SELECT + " ORDER BY o.last_played DESC NULLS LAST, lower(o.name)").fetchall()
    return {"games": rows, "platforms": summarise(rows)}


def _one(conn, game_id: int) -> dict:
    return found(conn.execute(SELECT + " WHERE o.game_id = %s", (game_id,)).fetchone(), "Game")


def _check(done, total):
    if done is not None and total is not None and done > total:
        raise HTTPException(422, "You can't have more achievements than the game has.")


@router.post("/videogames/other", status_code=201)
def add_game(body: GameIn):
    """A Ubisoft game Exophase doesn't list, with its achievements (and hours) typed in."""
    _check(body.done, body.total)
    with db() as conn:
        game_id = conn.execute(
            "INSERT INTO vg_other_games (platform, name, my_done, my_total, my_minutes) VALUES ('ubisoft', %s, %s, %s, %s) "
            "RETURNING game_id", (body.name.strip(), body.done, body.total,
                                  round(body.hours * 60) if body.hours is not None else None)).fetchone()["game_id"]
        return _one(conn, game_id)


@router.patch("/videogames/other/{game_id}")
def update_game(game_id: int, body: GamePatch):
    """Type in a Ubisoft game's achievements and hours (null clears them), rename one you added,
    or hide one."""
    sent = body.model_dump(exclude_unset=True)
    with db() as conn:
        game = _one(conn, game_id)
        if "name" in sent and game["source_id"]:
            raise HTTPException(409, "This game's name comes from Exophase.")
        done = sent.get("done", game["my_done"])
        total = sent.get("total", game["my_total"])
        _check(done, total)
        changes = {"name": sent.get("name"), "my_done": done, "my_total": total, "hidden": sent.get("hidden")}
        if "hours" in sent:
            changes["my_minutes"] = round(sent["hours"] * 60) if sent["hours"] is not None else None
        sets = {k: v for k, v in changes.items() if k in ("my_done", "my_total", "my_minutes") or v is not None}
        conn.execute("UPDATE vg_other_games SET " + ", ".join(f"{k} = %({k})s" for k in sets) +
                     ", updated_at = now() WHERE game_id = %(id)s", {**sets, "id": game_id})
        return _one(conn, game_id)


@router.delete("/videogames/other/{game_id}", status_code=204)
def delete_game(game_id: int):
    """Remove a game you added by hand (Exophase's games can only be hidden - they'd come back)."""
    with db() as conn:
        game = _one(conn, game_id)
        if game["source_id"]:
            raise HTTPException(409, "This game comes from Exophase: hide it instead.")
        conn.execute("DELETE FROM vg_other_games WHERE game_id = %s", (game_id,))
