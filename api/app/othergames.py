"""Video games on other platforms: Epic and Ubisoft, kept apart from Steam (videogames.py) but
shown the same way - every achievement, a picture, SteamHunters' numbers.

    account   the Exophase profile (a name or profile address) -> the player id for each linked
              platform, read from the profile page. Setting it reads the games straight away.
    sync      with every Steam sync (vgsync.run_sync), on the Exophase side:
              1. the games on each linked platform (exophase.player_games)
              2. per game: its Steam version (steam.find_app, by name, once; or set by you) -> the
                 Steam picture and SteamHunters' numbers (weekly)
              3. its achievements: Epic - the game's Exophase page + your earned list (again when
                 your earned count changes); Ubisoft - the Steam version's list (Exophase only sees
                 Ubisoft's *challenges*), which you tick off
    games     shaped like Steam games (app_id = "epic-12"), so the Games table and the game panel
              show them the same way

The dashboard, stats and recap count all three platforms together by default (?platforms= picks
some; Steam alone matches SteamHunters' numbers) - videogames.ALL_GAMES / ALL_ACHIEVEMENTS.
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import exophase, steam, steamhunters
from .db import db, found

router = APIRouter(prefix="/api", tags=["video games"])
log = logging.getLogger("othergames")

NAMES = {"epic": "Epic", "ubisoft": "Ubisoft"}
WEEKLY = timedelta(days=7)

# One game, shaped like a Steam game. done / total: the achievement list when there is one (Epic:
# what you've earned; Ubisoft: what you've ticked), else Epic's Exophase counts / Ubisoft's typed-in
# numbers. Playtime: yours if you gave it, else Exophase's.
SELECT = """
SELECT o.game_id, o.platform, o.platform || '-' || o.game_id AS app_id, o.source_id, o.name, o.page_url, o.hidden,
       o.last_played, o.steam_app_id, o.my_done, o.my_total, o.my_minutes, o.exo_minutes,
       COALESCE(o.header_url, o.picture_url) AS header_url, o.picture_url,
       o.sh_median_minutes, o.sh_fastest_minutes, o.sh_players_perfected, o.sh_players_started,
       round(100.0 * o.sh_players_perfected / NULLIF(o.sh_players_started, 0), 1) AS perfect_rate,
       CASE WHEN o.platform = 'ubisoft' THEN o.exo_done END AS challenges_done,
       CASE WHEN o.platform = 'ubisoft' THEN o.exo_total END AS challenges_total,
       a.listed, a.rarest_percent, d.done AS achievements_done, d.total AS achievements_total,
       d.total - d.done AS left_to_get, d.total > 0 AS has_achievements,
       CASE WHEN d.total > 0 THEN round(100.0 * d.done / d.total, 1) END AS percent,
       CASE WHEN d.total > 0 AND d.done >= d.total THEN COALESCE(a.last_unlock, o.exo_completed_at, o.updated_at) END
           AS completed_at,
       COALESCE(o.my_minutes, o.exo_minutes, 0) AS playtime_minutes, 0 AS dlc_count, false AS extra
FROM vg_other_games o
LEFT JOIN LATERAL (SELECT count(*)::int AS listed, count(*) FILTER (WHERE achieved)::int AS have,
                          min(global_percent) AS rarest_percent, max(unlocked_at) AS last_unlock
                   FROM vg_other_achievements WHERE game_id = o.game_id) a ON true
CROSS JOIN LATERAL (SELECT
    CASE WHEN a.listed > 0 THEN a.have WHEN o.platform = 'ubisoft' THEN o.my_done ELSE COALESCE(o.my_done, o.exo_done) END AS done,
    CASE WHEN a.listed > 0 THEN a.listed WHEN o.platform = 'ubisoft' THEN o.my_total ELSE COALESCE(o.my_total, o.exo_total) END
        AS total) d"""


class AccountIn(BaseModel):
    profile: str = Field(min_length=2, max_length=200)   # an Exophase name or profile address


class GameIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    platform: Literal["epic", "ubisoft"] = "ubisoft"
    exo_id: int | None = None            # picked from Find a game: its picture and Exophase page
    done: int | None = Field(None, ge=0)
    total: int | None = Field(None, ge=0)
    hours: float | None = Field(None, ge=0, le=100000)


class GamePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    done: int | None = Field(None, ge=0)
    total: int | None = Field(None, ge=0)
    hours: float | None = Field(None, ge=0, le=100000)
    hidden: bool | None = None


class SteamLinkIn(BaseModel):
    link: str | None = Field(None, max_length=300)       # a store link or app id; None = no Steam version


class TickIn(BaseModel):
    achieved: bool


def _ts(unix) -> datetime | None:
    return datetime.fromtimestamp(int(unix), timezone.utc) if unix else None


# ---------------------------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------------------------
def sync_other() -> str:
    """Read every linked platform's games from Exophase and save them, then each game's details.
    Typed-in numbers and ticks are never touched. Returns a note for the sync's message ('' if no
    profile is set)."""
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
        detailed = sync_details(players)
    except exophase.Unavailable as e:
        log.warning("Other platforms: %s", e)
        with db() as conn:
            conn.execute("UPDATE vg_sync SET exo_error = %s WHERE id = 1", (str(e),))
        return " (Exophase didn't answer, so the Epic / Ubisoft games wait for the next sync)"
    with db() as conn:
        conn.execute("UPDATE vg_sync SET exo_synced_at = now(), exo_error = NULL WHERE id = 1")
    note = ", " + ", ".join(f"{n} {name}" for name, n in counts.items()) + " games from Exophase"
    return note + (f" ({detailed} with new achievement lists)" if detailed else "")


def sync_details(players: dict) -> int:
    """For each game (not hidden): find its Steam version once, refresh SteamHunters' numbers
    weekly, and read its achievement list when due (Epic: never read or your earned count changed;
    Ubisoft: never read, or weekly for the rarity). A game Steam can't help with is skipped, not
    fatal. Returns how many lists were read."""
    with db() as conn:
        games = conn.execute("SELECT * FROM vg_other_games WHERE NOT hidden ORDER BY last_played DESC NULLS LAST").fetchall()
    now, read = datetime.now(timezone.utc), 0
    for g in games:
        try:
            if g["steam_checked_at"] is None:
                match_steam(g["game_id"], g["name"])
                with db() as conn:
                    g = conn.execute("SELECT * FROM vg_other_games WHERE game_id = %s", (g["game_id"],)).fetchone()
            if g["steam_app_id"] and (not g["sh_synced_at"] or now - g["sh_synced_at"] > WEEKLY):
                community(g["game_id"], g["steam_app_id"])
            if g["platform"] == "epic" and g["page_url"] and g["source_id"] and players.get("epic") and (
                    not g["list_synced_at"] or g["list_done"] != g["exo_done"]):
                epic_list(g, players["epic"])
                read += 1
            elif g["platform"] == "ubisoft" and g["steam_app_id"] and (
                    not g["list_synced_at"] or now - g["list_synced_at"] > WEEKLY):
                steam_list(g["game_id"], g["steam_app_id"])
                read += 1
        except (steam.SteamError, steamhunters.Unavailable) as e:
            log.warning("Details for %s: %s", g["name"], e)
    return read


def match_steam(game_id: int, name: str):
    """Look for the game on Steam by name; remember what was found (or that nothing was)."""
    found_app = steam.find_app(name)
    app_id = found_app[0] if found_app else None
    header = steam.header_pictures([app_id]).get(app_id) if app_id else None
    with db() as conn:
        conn.execute("UPDATE vg_other_games SET steam_app_id = %s, header_url = %s, steam_checked_at = now() "
                     "WHERE game_id = %s", (app_id, header, game_id))
    steam.pause()


def community(game_id: int, app_id: int):
    numbers = steamhunters.game(app_id) or {}
    with db() as conn:
        conn.execute("UPDATE vg_other_games SET sh_median_minutes = %s, sh_fastest_minutes = %s, "
                     "sh_players_perfected = %s, sh_players_started = %s, sh_synced_at = now() WHERE game_id = %s",
                     (numbers.get("sh_median_minutes"), numbers.get("sh_fastest_minutes"),
                      numbers.get("sh_players_perfected"), numbers.get("sh_players_started"), game_id))
    steamhunters.pause()


def save_list(conn, game_id: int, rows: list[dict], keep_ticks: bool):
    """Replace a game's achievement list. keep_ticks: leave 'achieved' as you ticked it (Ubisoft)."""
    names = [r["api_name"] for r in rows]
    conn.execute("DELETE FROM vg_other_achievements WHERE game_id = %s AND NOT (api_name = ANY(%s))", (game_id, names))
    for i, r in enumerate(rows):
        conn.execute(f"""
            INSERT INTO vg_other_achievements (game_id, api_name, name, description, icon, icon_gray, hidden,
                                               global_percent, achieved, unlocked_at, sort_order)
            VALUES (%(game_id)s, %(api_name)s, %(name)s, %(description)s, %(icon)s, %(icon_gray)s, %(hidden)s,
                    %(global_percent)s, %(achieved)s, %(unlocked_at)s, %(sort)s)
            ON CONFLICT (game_id, api_name) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description,
                icon = EXCLUDED.icon, icon_gray = EXCLUDED.icon_gray, hidden = EXCLUDED.hidden,
                global_percent = EXCLUDED.global_percent, sort_order = EXCLUDED.sort_order
                {"" if keep_ticks else ", achieved = EXCLUDED.achieved, unlocked_at = EXCLUDED.unlocked_at"}""",
                     {"game_id": game_id, "sort": i, "achieved": False, "unlocked_at": None, "icon_gray": None,
                      "hidden": False, **r})


def epic_list(g: dict, player: int):
    """An Epic game's achievements from its Exophase page, with what you've earned and when."""
    awards = exophase.game_awards(g["page_url"])
    exophase.pause()
    got = exophase.earned(player, g["source_id"])
    exophase.pause()
    rows = [{"api_name": a["id"], "name": a["name"], "description": a["description"], "icon": a["icon"],
             "global_percent": a["average"], "achieved": a["id"] in got, "unlocked_at": _ts(got.get(a["id"]))}
            for a in awards]
    with db() as conn:
        save_list(conn, g["game_id"], rows, keep_ticks=False)
        conn.execute("UPDATE vg_other_games SET list_synced_at = now(), list_done = %s WHERE game_id = %s",
                     (g["exo_done"], g["game_id"]))


def steam_list(game_id: int, app_id: int):
    """A Ubisoft game's achievements from its Steam version (names, icons, rarity); your ticks stay."""
    schema = steam.schema(app_id)
    steam.pause()
    rarity = steam.global_percentages(app_id) if schema else {}
    steam.pause()
    rows = [{"api_name": a["name"], "name": a.get("displayName") or a["name"], "description": a.get("description") or None,
             "icon": a.get("icon"), "icon_gray": a.get("icongray"), "hidden": bool(a.get("hidden")),
             "global_percent": round(rarity[a["name"]], 3) if a["name"] in rarity else None} for a in schema]
    with db() as conn:
        save_list(conn, game_id, rows, keep_ticks=True)
        conn.execute("UPDATE vg_other_games SET list_synced_at = now() WHERE game_id = %s", (game_id,))


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------
def summarise(games: list[dict]) -> list[dict]:
    """Per platform: games, achievements you have / of, games at 100%, playtime; Ubisoft also how
    many games still have no numbers."""
    out = []
    for platform, name in NAMES.items():
        mine = [g for g in games if g["platform"] == platform and not g["hidden"]]
        if not mine:
            continue
        counted = [g for g in mine if g["achievements_total"]]
        out.append({
            "platform": platform, "name": name, "games": len(mine),
            "done": sum(g["achievements_done"] or 0 for g in counted),
            "total": sum(g["achievements_total"] for g in counted),
            "perfect": sum(1 for g in counted if g["achievements_done"] >= g["achievements_total"]),
            "playtime_minutes": sum(g["playtime_minutes"] or 0 for g in mine),
            "to_fill_in": sum(1 for g in mine if platform == "ubisoft" and g["achievements_total"] is None),
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
    """Follow an Exophase profile for Epic and Ubisoft games, and read them now - with each game's
    Steam version and achievement list (a few requests per game, spaced)."""
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


def _one(conn, game_id: int, with_list: bool = True) -> dict:
    game = found(conn.execute(SELECT + " WHERE o.game_id = %s", (game_id,)).fetchone(), "Game")
    if with_list:
        game["achievements"] = conn.execute("""
            SELECT api_name, name, description, icon, icon_gray, hidden, global_percent, achieved, unlocked_at,
                   NULL AS dlc, false AS unobtainable
            FROM vg_other_achievements WHERE game_id = %s
            ORDER BY achieved DESC, unlocked_at DESC NULLS LAST, global_percent DESC NULLS LAST, sort_order""",
            (game_id,)).fetchall()
    return game


ENVIRONMENTS = {v: k for k, v in exophase.PLATFORMS.items()}     # ours -> Exophase's ("ubisoft" -> "uplay")
KEEP = 3600
_found: dict[tuple, tuple[float, list]] = {}
_seen: dict[int, dict] = {}              # every game a search has shown, by Exophase id (for adding it)


@router.get("/videogames/other/find")
def find(platform: Literal["epic", "ubisoft"], q: str = Query(..., min_length=2, max_length=80)):
    """Epic or Ubisoft games on Exophase matching the words, marked when they're already in your games.
    (Declared before /videogames/other/{game_id}.)"""
    words = " ".join(q.casefold().split())
    hit = _found.get((platform, words))
    if hit and time.monotonic() - hit[0] < KEEP:
        results = hit[1]
    else:
        try:
            results = exophase.search(words, ENVIRONMENTS[platform])
        except exophase.Unavailable as e:
            raise HTTPException(502, str(e))
        _found[(platform, words)] = (time.monotonic(), results)
    for r in results:
        _seen[r["exo_id"]] = {**r, "platform": platform}
    with db() as conn:
        mine = conn.execute("SELECT game_id, name, source_id FROM vg_other_games WHERE platform = %s", (platform,)).fetchall()
    by_key = {exophase.key(g["name"]): g["game_id"] for g in mine}
    by_source = {g["source_id"]: g["game_id"] for g in mine if g["source_id"]}
    out = []
    for r in results:
        game_id = by_source.get(str(r["exo_id"])) or by_key.get(exophase.key(r["name"]))
        out.append({**r, "yours": {"id": f"{platform}-{game_id}"} if game_id else None})
    return out


@router.get("/videogames/other/{game_id}")
def get_game(game_id: int):
    with db() as conn:
        return _one(conn, game_id)


def _check(done, total):
    if done is not None and total is not None and done > total:
        raise HTTPException(422, "You can't have more achievements than the game has.")


@router.post("/videogames/other", status_code=201)
def add_game(body: GameIn):
    """An Epic or Ubisoft game added by hand: hours played (a game without achievements, like
    Fortnite, is tracked by its hours), and for Ubisoft the numbers if you like. Picked from Find a
    game (exo_id): its picture and Exophase page come with it. Its Steam version (picture, other
    players' numbers; for Ubisoft the achievement list) is looked for straight away."""
    _check(body.done, body.total)
    picked = _seen.get(body.exo_id) if body.exo_id else None
    if body.exo_id and (not picked or picked["platform"] != body.platform):
        raise HTTPException(422, "Search for the game again, then pick it.")
    name = (picked["name"] if picked else body.name).strip()
    with db() as conn:
        same = [g for g in conn.execute("SELECT name FROM vg_other_games WHERE platform = %s",
                                        (body.platform,)).fetchall() if exophase.key(g["name"]) == exophase.key(name)]
        if same:
            raise HTTPException(409, f"{same[0]['name']} is already in your {NAMES[body.platform]} games.")
        game_id = conn.execute(
            "INSERT INTO vg_other_games (platform, name, my_done, my_total, my_minutes, picture_url, page_url) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING game_id",
            (body.platform, name, body.done, body.total, round(body.hours * 60) if body.hours is not None else None,
             picked and picked["picture"], picked and picked["page_url"])).fetchone()["game_id"]
    _find_and_list(game_id)
    with db() as conn:
        return _one(conn, game_id)


def _find_and_list(game_id: int, link: str | None = None, forget: bool = False):
    """Find (or set, or forget) a game's Steam version now, then read its list (Ubisoft) and numbers."""
    with db() as conn:
        g = found(conn.execute("SELECT * FROM vg_other_games WHERE game_id = %s", (game_id,)).fetchone(), "Game")
    if forget:
        with db() as conn:
            conn.execute("UPDATE vg_other_games SET steam_app_id = NULL, header_url = NULL, steam_checked_at = now(), "
                         "sh_median_minutes = NULL, sh_fastest_minutes = NULL, sh_players_perfected = NULL, "
                         "sh_players_started = NULL, sh_synced_at = NULL WHERE game_id = %s", (game_id,))
            if g["platform"] == "ubisoft":
                conn.execute("DELETE FROM vg_other_achievements WHERE game_id = %s", (game_id,))
                conn.execute("UPDATE vg_other_games SET list_synced_at = NULL WHERE game_id = %s", (game_id,))
        return
    app_id = None
    if link is not None:
        app_id = steam.app_id_from(link)
        if not app_id:
            raise HTTPException(422, "Paste the game's Steam store link (store.steampowered.com/app/...) or its app id.")
    try:
        if app_id:
            header = steam.header_pictures([app_id]).get(app_id)
            with db() as conn:
                conn.execute("UPDATE vg_other_games SET steam_app_id = %s, header_url = %s, steam_checked_at = now() "
                             "WHERE game_id = %s", (app_id, header, game_id))
        else:
            match_steam(game_id, g["name"])
        with db() as conn:
            g = conn.execute("SELECT * FROM vg_other_games WHERE game_id = %s", (game_id,)).fetchone()
        if g["steam_app_id"]:
            if g["platform"] == "ubisoft":
                steam_list(game_id, g["steam_app_id"])
            community(game_id, g["steam_app_id"])
    except (steam.SteamError, steamhunters.Unavailable) as e:
        log.warning("Steam version of %s: %s", g["name"], e)


@router.put("/videogames/other/{game_id}/steam")
def set_steam(game_id: int, body: SteamLinkIn):
    """The game's Steam version, when the name search got it wrong (a store link or app id), or
    none (null). A Ubisoft game's achievement list comes from it."""
    _find_and_list(game_id, link=body.link, forget=body.link is None)
    with db() as conn:
        return _one(conn, game_id)


def _ubisoft(conn, game_id: int) -> dict:
    game = _one(conn, game_id, with_list=False)
    if game["platform"] != "ubisoft":
        raise HTTPException(409, "Epic achievements come from your Exophase profile.")
    return game


@router.put("/videogames/other/{game_id}/achievements/{api_name}")
def tick(game_id: int, api_name: str, body: TickIn):
    """Tick off (or untick) one of a Ubisoft game's achievements."""
    with db() as conn:
        _ubisoft(conn, game_id)
        found(conn.execute("UPDATE vg_other_achievements SET achieved = %s WHERE game_id = %s AND api_name = %s "
                           "RETURNING api_name", (body.achieved, game_id, api_name)).fetchone(), "Achievement")
        conn.execute("UPDATE vg_other_games SET updated_at = now() WHERE game_id = %s", (game_id,))
        return _one(conn, game_id)


@router.put("/videogames/other/{game_id}/achievements")
def tick_all(game_id: int, body: TickIn):
    """Tick (or untick) every one of a Ubisoft game's achievements at once."""
    with db() as conn:
        _ubisoft(conn, game_id)
        conn.execute("UPDATE vg_other_achievements SET achieved = %s WHERE game_id = %s", (body.achieved, game_id))
        conn.execute("UPDATE vg_other_games SET updated_at = now() WHERE game_id = %s", (game_id,))
        return _one(conn, game_id)


@router.patch("/videogames/other/{game_id}")
def update_game(game_id: int, body: GamePatch):
    """Hours played, typed-in numbers (for a game without an achievement list; null clears them),
    rename one you added, or hide one."""
    sent = body.model_dump(exclude_unset=True)
    with db() as conn:
        game = _one(conn, game_id, with_list=False)
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
        game = _one(conn, game_id, with_list=False)
        if game["source_id"]:
            raise HTTPException(409, "This game comes from Exophase: hide it instead.")
        conn.execute("DELETE FROM vg_other_games WHERE game_id = %s", (game_id,))
