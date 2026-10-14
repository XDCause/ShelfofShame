"""Video games (a hobby module): your Steam games and achievements, for a 100% dashboard.

    sync      reads Steam (steam.py) into vg_games / vg_achievements. The first sync reads every
              game; after that only games played since the last sync (or never read), unless
              full=true. Runs in the background; GET /videogames/sync shows how it's going.
              A sync also runs by itself once a day while the app is up (start_daily_sync).
    dashboard summary tiles, closest to 100%, recent unlocks, rarest achievements you have, and
              profile completion: the average completion of the games you've started (at least one
              achievement; untouched games don't count) against your goal (settings key
              vg_goal_percent, 50 unless changed), the total alongside, the quickest route and your pace
    stats     for the charts: unlocks per month, how rare your achievements are, your started games
              by completion, most played games
    games     every game with its completion; one game with its achievements

Steam's pictures are linked from Steam's own servers (header and icon addresses below).
"""
import logging
import math
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import steam
from .db import db, found
from .settings import get_setting

router = APIRouter(prefix="/api", tags=["video games"])
log = logging.getLogger("videogames")

HEADER = "https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"
ICON = "https://media.steampowered.com/steamcommunity/public/images/apps/{app_id}/{hash}.jpg"
RARITY_EVERY = timedelta(days=7)     # rarity changes slowly: re-read it weekly at most
DAILY = timedelta(hours=20)          # the automatic sync's spacing

# How the background sync is going (one at a time).
SYNC = {"running": False, "done": 0, "total": 0, "message": None, "error": None, "finished_at": None}
_lock = threading.Lock()


class ProfileIn(BaseModel):
    profile: str = Field(min_length=2, max_length=200)   # a name, id or profile address


class GamePatch(BaseModel):
    hidden: bool


class ExtraIn(BaseModel):
    game: str = Field(min_length=1, max_length=300)   # its store link, or its app id


class GoalIn(BaseModel):
    percent: int = Field(ge=1, le=100)   # % of every achievement in your games


GOAL_KEY, GOAL_DEFAULT = "vg_goal_percent", 50


GAME_SELECT = """
SELECT g.*, CASE WHEN g.achievements_total > 0
                 THEN round(100.0 * g.achievements_done / g.achievements_total, 1) END AS percent,
       g.achievements_total - g.achievements_done AS left_to_get
FROM vg_games g"""


def with_pictures(game: dict) -> dict:
    """The game's pictures: its header from the store API (header_url), else the old fixed address
    (older games still have one; the page shows a placeholder if that fails too)."""
    game["header_url"] = game.get("header_url") or HEADER.format(app_id=game["app_id"])
    game["icon_url"] = ICON.format(app_id=game["app_id"], hash=game["icon_hash"]) if game.get("icon_hash") else None
    return game


def _ts(unix) -> datetime | None:
    return datetime.fromtimestamp(int(unix), timezone.utc) if unix else None


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------
def sync_game(conn, steam_id: str, app_id: int, rarity_due: bool):
    """Read one game's achievements (and their names and rarity when needed) into the database."""
    try:
        mine = steam.player_achievements(steam_id, app_id)
    except steam.NoStats:
        conn.execute("UPDATE vg_games SET has_achievements = false, achievements_total = 0, achievements_done = 0, "
                     "completed_at = NULL, synced_at = now() WHERE app_id = %s", (app_id,))
        return
    steam.pause()
    known = conn.execute("SELECT count(*) AS n FROM vg_achievements WHERE app_id = %s", (app_id,)).fetchone()["n"]
    if known != len(mine):            # new game, or achievements added since (DLC): read the names again
        for a in steam.schema(app_id):
            conn.execute("""
                INSERT INTO vg_achievements (app_id, api_name, name, description, icon, icon_gray, hidden)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (app_id, api_name) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description,
                    icon = EXCLUDED.icon, icon_gray = EXCLUDED.icon_gray, hidden = EXCLUDED.hidden""",
                (app_id, a["name"], a.get("displayName") or a["name"], a.get("description") or None,
                 a.get("icon"), a.get("icongray"), bool(a.get("hidden"))))
        steam.pause()
        rarity_due = True
    for a in mine:
        conn.execute("""
            INSERT INTO vg_achievements (app_id, api_name, name, achieved, unlocked_at) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (app_id, api_name) DO UPDATE SET achieved = EXCLUDED.achieved, unlocked_at = EXCLUDED.unlocked_at""",
            (app_id, a["apiname"], a["apiname"], bool(a.get("achieved")), _ts(a.get("unlocktime")) if a.get("achieved") else None))
    if rarity_due:
        for api_name, percent in steam.global_percentages(app_id).items():
            conn.execute("UPDATE vg_achievements SET global_percent = %s WHERE app_id = %s AND api_name = %s",
                         (round(percent, 3), app_id, api_name))
        conn.execute("UPDATE vg_games SET rarity_synced_at = now() WHERE app_id = %s", (app_id,))
        steam.pause()
    conn.execute("""
        UPDATE vg_games g SET has_achievements = s.total > 0, achievements_total = s.total, achievements_done = s.done,
               completed_at = CASE WHEN s.total > 0 AND s.done = s.total THEN s.last END, synced_at = now()
        FROM (SELECT count(*)::int AS total, count(*) FILTER (WHERE achieved)::int AS done,
                     max(unlocked_at) AS last FROM vg_achievements WHERE app_id = %s) s
        WHERE g.app_id = %s""", (app_id, app_id))


def run_sync(full: bool = False):
    """The whole sync. Each game is saved as it's read, so a sync that stops part-way keeps what
    it got, and the next one carries on (games never read are always read)."""
    try:
        with db() as conn:
            account = conn.execute("SELECT * FROM vg_sync WHERE id = 1").fetchone()
        if not account["steam_id"]:
            raise steam.SteamError("Set your Steam profile first.")
        steam_id = account["steam_id"]
        SYNC.update(message="Reading your games list...")
        owned = steam.owned_games(steam_id)
        with db() as conn:
            before = {r["app_id"]: r for r in conn.execute(
                "SELECT app_id, last_played, synced_at, rarity_synced_at FROM vg_games").fetchall()}
            for g in owned:
                conn.execute("""
                    INSERT INTO vg_games (app_id, name, icon_hash, playtime_minutes, playtime_2weeks, last_played)
                    VALUES (%(appid)s, %(name)s, %(icon)s, %(play)s, %(two)s, %(last)s)
                    ON CONFLICT (app_id) DO UPDATE SET name = EXCLUDED.name, icon_hash = EXCLUDED.icon_hash,
                        playtime_minutes = EXCLUDED.playtime_minutes, playtime_2weeks = EXCLUDED.playtime_2weeks,
                        last_played = EXCLUDED.last_played""",
                    {"appid": g["appid"], "name": g.get("name") or f"App {g['appid']}", "icon": g.get("img_icon_url") or None,
                     "play": g.get("playtime_forever", 0), "two": g.get("playtime_2weeks", 0),
                     "last": _ts(g.get("rtime_last_played"))})
        # Pictures: games never looked up (every game on a full sync, as the art changes).
        with db() as conn:
            missing = [r["app_id"] for r in conn.execute(
                "SELECT app_id FROM vg_games" + ("" if full else " WHERE header_url IS NULL")).fetchall()]
        if missing:
            SYNC.update(message=f"Finding pictures for {len(missing)} games...")
            pictures = steam.header_pictures(missing)
            with db() as conn:
                for app_id, url in pictures.items():
                    conn.execute("UPDATE vg_games SET header_url = %s WHERE app_id = %s", (url or "", app_id))
        now = datetime.now(timezone.utc)
        to_read = []
        for g in owned:
            old = before.get(g["appid"])
            played = _ts(g.get("rtime_last_played"))
            if full or not old or not old["synced_at"] or (played and (not old["last_played"] or played > old["last_played"])):
                rarity_due = full or not old or not old["rarity_synced_at"] or now - old["rarity_synced_at"] > RARITY_EVERY
                to_read.append((g["appid"], g.get("name"), rarity_due))
        # Games added by hand (not in the owned list): read every time - Steam doesn't say when they
        # were last played.
        with db() as conn:
            for r in conn.execute("SELECT app_id, name, rarity_synced_at FROM vg_games WHERE extra").fetchall():
                rarity_due = full or not r["rarity_synced_at"] or now - r["rarity_synced_at"] > RARITY_EVERY
                to_read.append((r["app_id"], r["name"], rarity_due))
        SYNC.update(total=len(to_read), done=0)
        for app_id, name, rarity_due in to_read:
            SYNC.update(message=f"Reading {name}...")
            with db() as conn:
                sync_game(conn, steam_id, app_id, rarity_due)
            SYNC["done"] += 1
            steam.pause()
        with db() as conn:
            conn.execute("UPDATE vg_sync SET last_sync_at = now(), last_error = NULL"
                         + (", last_full_at = now()" if full or not account["last_full_at"] else "") + " WHERE id = 1")
        SYNC.update(message=f"Done: {len(owned)} games, {len(to_read)} read from Steam")
    except steam.SteamError as e:
        SYNC.update(error=str(e), message=None)
        with db() as conn:
            conn.execute("UPDATE vg_sync SET last_error = %s WHERE id = 1", (str(e),))
    except Exception as e:  # keep the app up; say what happened
        log.exception("Steam sync failed")
        SYNC.update(error=f"The sync stopped: {e.__class__.__name__}.", message=None)
    finally:
        SYNC.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())


def start_sync(background: BackgroundTasks | None, full: bool) -> bool:
    """Start a sync unless one is running. False if one already was."""
    with _lock:
        if SYNC["running"]:
            return False
        SYNC.update(running=True, done=0, total=0, message="Starting...", error=None, finished_at=None)
    if background is not None:
        background.add_task(run_sync, full)
    else:
        threading.Thread(target=run_sync, args=(full,), daemon=True, name="steam-sync").start()
    return True


def start_daily_sync():
    """While the app runs: once a day (and soon after starting, if it's been a day), a sync."""
    def loop():
        while True:
            try:
                with db() as conn:
                    account = conn.execute("SELECT steam_id, last_sync_at FROM vg_sync WHERE id = 1").fetchone()
                due = account and account["steam_id"] and (
                    not account["last_sync_at"] or datetime.now(timezone.utc) - account["last_sync_at"] > DAILY)
                if due and steam.key():
                    start_sync(None, full=False)
            except Exception:  # no key, database restarting...: try again later
                pass
            threading.Event().wait(3600)
    threading.Thread(target=loop, daemon=True, name="steam-daily").start()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/videogames/account")
def account():
    """The Steam account being tracked, how the last sync went, and the sync running now (if any)."""
    with db() as conn:
        row = conn.execute("SELECT profile, steam_id, persona_name, last_sync_at, last_full_at, last_error "
                           "FROM vg_sync WHERE id = 1").fetchone()
    try:
        steam.key()
        has_key = True
    except steam.SteamError:
        has_key = False
    return {**row, "has_key": has_key, "sync": SYNC}


@router.put("/videogames/account")
def set_account(body: ProfileIn, background: BackgroundTasks):
    """Track this Steam profile (a name, id or profile address), then sync everything."""
    try:
        steam_id = steam.resolve(body.profile)
        name = steam.persona(steam_id)
    except steam.SteamError as e:
        raise HTTPException(422, str(e))
    with db() as conn:
        old = conn.execute("SELECT steam_id FROM vg_sync WHERE id = 1").fetchone()["steam_id"]
        if old and old != steam_id:                    # a different account: start afresh
            conn.execute("DELETE FROM vg_games")
            conn.execute("UPDATE vg_sync SET last_sync_at = NULL, last_full_at = NULL WHERE id = 1")
        conn.execute("UPDATE vg_sync SET profile = %s, steam_id = %s, persona_name = %s, last_error = NULL WHERE id = 1",
                     (body.profile.strip(), steam_id, name))
    start_sync(background, full=True)
    return account()


@router.post("/videogames/sync", status_code=202)
def sync(background: BackgroundTasks, full: bool = False):
    """Sync now: games played since last time (full=true: every game). 409 if one is running."""
    with db() as conn:
        if not conn.execute("SELECT steam_id FROM vg_sync WHERE id = 1").fetchone()["steam_id"]:
            raise HTTPException(409, "Set your Steam profile first.")
    if not start_sync(background, full):
        raise HTTPException(409, "A sync is already running.")
    return {"sync": SYNC}


@router.get("/videogames/summary")
def summary():
    """For the dashboard and Home: totals, the games closest to 100%, recent unlocks, the rarest you have."""
    with db() as conn:
        totals = conn.execute("""
            SELECT count(*)::int AS games,
                   count(*) FILTER (WHERE has_achievements)::int AS with_achievements,
                   count(*) FILTER (WHERE completed_at IS NOT NULL)::int AS perfect,
                   count(*) FILTER (WHERE achievements_done > 0 AND completed_at IS NULL)::int AS started,
                   COALESCE(sum(achievements_done), 0)::int AS achievements,
                   COALESCE(sum(achievements_total), 0)::int AS achievements_total,
                   COALESCE(sum(achievements_total) FILTER (WHERE achievements_done > 0), 0)::int
                       AS started_achievements_total,
                   round(avg(100.0 * achievements_done / achievements_total) FILTER (WHERE achievements_done > 0), 1)
                       AS average_percent,
                   COALESCE(sum(playtime_minutes), 0)::int AS playtime_minutes
            FROM vg_games WHERE NOT hidden""").fetchone()
        totals["unlocked_this_month"] = conn.execute(
            "SELECT count(*)::int AS n FROM vg_achievements a JOIN vg_games g USING (app_id) WHERE NOT g.hidden "
            "AND a.achieved AND a.unlocked_at >= date_trunc('month', now())").fetchone()["n"]
        totals["unlocked_last_30_days"] = conn.execute(
            "SELECT count(*)::int AS n FROM vg_achievements a JOIN vg_games g USING (app_id) WHERE NOT g.hidden "
            "AND a.achieved AND a.unlocked_at >= now() - interval '30 days'").fetchone()["n"]
        started = [(r["achievements_done"], r["achievements_total"]) for r in conn.execute(
            "SELECT achievements_done, achievements_total FROM vg_games WHERE NOT hidden AND achievements_done > 0").fetchall()]
        totals["goal"] = goal_progress(started, totals["unlocked_last_30_days"],
                                       int(get_setting(conn, GOAL_KEY) or GOAL_DEFAULT))
        closest = conn.execute(GAME_SELECT + """ WHERE NOT g.hidden AND g.achievements_done > 0 AND g.completed_at IS NULL
            ORDER BY 1.0 * g.achievements_done / g.achievements_total DESC, g.achievements_total - g.achievements_done
            LIMIT 6""").fetchall()
        recent = conn.execute("""
            SELECT a.app_id, g.name AS game, a.api_name, a.name, a.description, a.icon, a.global_percent, a.unlocked_at
            FROM vg_achievements a JOIN vg_games g USING (app_id)
            WHERE a.achieved AND NOT g.hidden ORDER BY a.unlocked_at DESC NULLS LAST LIMIT 8""").fetchall()
        rarest = conn.execute("""
            SELECT a.app_id, g.name AS game, a.api_name, a.name, a.description, a.icon, a.global_percent, a.unlocked_at
            FROM vg_achievements a JOIN vg_games g USING (app_id)
            WHERE a.achieved AND NOT g.hidden AND a.global_percent IS NOT NULL
            ORDER BY a.global_percent, a.unlocked_at LIMIT 8""").fetchall()
        perfect = conn.execute(GAME_SELECT + " WHERE NOT g.hidden AND g.completed_at IS NOT NULL "
                               "ORDER BY g.completed_at DESC LIMIT 6").fetchall()
    return {**totals, "closest": [with_pictures(g) for g in closest], "recent": recent, "rarest": rarest,
            "recent_perfect": [with_pictures(g) for g in perfect]}


# Rarity bands (the % of all players who have an achievement) and completion bands for the charts.
RARITY_BANDS = [(0, 1, "Under 1%"), (1, 5, "1–5%"), (5, 10, "5–10%"), (10, 20, "10–20%"), (20, 50, "20–50%"),
                (50, 101, "50% or more")]
COMPLETION_BANDS = [(0, 10, "Under 10%"), (10, 25, "10–24%"), (25, 50, "25–49%"), (50, 75, "50–74%"),
                    (75, 100, "75–99%"), (100, 101, "100%")]


@router.get("/videogames/stats")
def stats(months: int = Query(24, ge=1, le=120)):
    """The Stats page's charts, all from games you haven't hidden:
        by_month    achievements unlocked each month, oldest first (months with none included)
        rarity      your achievements by how many players have them
        completion  your started games by how much of each you've done
        most_played the ten games with the most playtime"""
    with db() as conn:
        by_month = conn.execute("""
            SELECT to_char(m, 'YYYY-MM') AS month, COALESCE(n.count, 0)::int AS count
            FROM generate_series(date_trunc('month', now()) - make_interval(months => %(months)s - 1),
                                 date_trunc('month', now()), interval '1 month') m
            LEFT JOIN (SELECT date_trunc('month', a.unlocked_at) AS m, count(*) AS count
                       FROM vg_achievements a JOIN vg_games g USING (app_id)
                       WHERE a.achieved AND NOT g.hidden GROUP BY 1) n USING (m)
            ORDER BY m""", {"months": months}).fetchall()
        percents = [float(r["global_percent"]) for r in conn.execute(
            "SELECT a.global_percent FROM vg_achievements a JOIN vg_games g USING (app_id) "
            "WHERE a.achieved AND NOT g.hidden AND a.global_percent IS NOT NULL").fetchall()]
        games = [float(r["p"]) for r in conn.execute(
            "SELECT 100.0 * achievements_done / achievements_total AS p FROM vg_games "
            "WHERE NOT hidden AND achievements_done > 0").fetchall()]
        most_played = [with_pictures(g) for g in conn.execute(
            GAME_SELECT + " WHERE NOT g.hidden AND g.playtime_minutes > 0 ORDER BY g.playtime_minutes DESC LIMIT 10"
        ).fetchall()]
    band = lambda bands, values: [{"label": label, "count": sum(lo <= v < hi for v in values)}  # noqa: E731
                                  for lo, hi, label in bands]
    return {"by_month": by_month, "rarity": band(RARITY_BANDS, percents),
            "completion": band(COMPLETION_BANDS, games), "most_played": most_played}


def goal_progress(games: list[tuple[int, int]], unlocked_last_30_days: int, goal_percent: int) -> dict:
    """Profile completion against the goal, from the started games' (done, total) achievements:
        percent        average completion: each game's %, averaged (SteamHunters' "avg completion";
                       a 2-achievement game counts as much as a 600-achievement one) - the goal's number
        total_percent  every achievement you have / every achievement in those games
        points_to_go   goal - average
        plan           the quickest way there: 100% your nearest-to-done games, fewest achievements
                       left first, until the average reaches the goal -> games and achievements needed
        days_at_pace   those achievements at your last-30-days pace
    Starting a new game adds a low % to the average, so it can dip when you do."""
    count = len(games)
    percents = [100 * d / t for d, t in games]
    average = sum(percents) / count if count else 0.0
    done, total = sum(d for d, _ in games), sum(t for _, t in games)
    reached = count > 0 and average >= goal_percent
    plan = None
    if count and not reached:
        gained, achievements = 0.0, 0
        for finished, (d, t) in enumerate(sorted((g for g in games if g[0] < g[1]), key=lambda g: g[1] - g[0]), 1):
            gained += (100 - 100 * d / t) / count
            achievements += t - d
            if average + gained >= goal_percent:
                plan = {"games": finished, "achievements": achievements}
                break
    per_day = unlocked_last_30_days / 30
    return {
        "percent": round(average, 1),
        "total_percent": round(100 * done / total, 1) if total else 0.0,
        "achievements": done,
        "achievements_total": total,
        "goal_percent": goal_percent,
        "points_to_go": round(max(0.0, goal_percent - average), 1),
        "reached": reached,
        "plan": plan,
        "days_at_pace": math.ceil(plan["achievements"] / per_day) if plan and per_day else None,
    }


@router.put("/videogames/goal")
def set_goal(body: GoalIn):
    """Change the profile completion goal (a % of every achievement in your games)."""
    with db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (%s, %s) "
                     "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (GOAL_KEY, str(body.percent)))
    return summary()


@router.get("/videogames")
def list_games(show: str = Query("all", pattern="^(all|perfect|started|untouched|no_achievements|hidden)$")):
    """Every game, most recently played first. show = perfect / started / untouched / no_achievements / hidden."""
    where = {
        "all": "NOT g.hidden",
        "perfect": "NOT g.hidden AND g.completed_at IS NOT NULL",
        "started": "NOT g.hidden AND g.achievements_done > 0 AND g.completed_at IS NULL",
        "untouched": "NOT g.hidden AND g.has_achievements AND g.achievements_done = 0",
        "no_achievements": "NOT g.hidden AND g.has_achievements = false",
        "hidden": "g.hidden",
    }[show]
    with db() as conn:
        rows = conn.execute(GAME_SELECT + f" WHERE {where} ORDER BY g.last_played DESC NULLS LAST, lower(g.name)").fetchall()
    return [with_pictures(g) for g in rows]


@router.post("/videogames/extra", status_code=201)
def add_extra(body: ExtraIn):
    """Track a game Steam's owned-games list leaves out (a free game like Counter-Strike 2, or one you
    no longer own) by its store link or app id. Its achievements are read straight away."""
    app_id = steam.app_id_from(body.game)
    if not app_id:
        raise HTTPException(422, "Paste the game's Steam store link (store.steampowered.com/app/...) or its app id.")
    with db() as conn:
        account = conn.execute("SELECT steam_id FROM vg_sync WHERE id = 1").fetchone()
        if not account["steam_id"]:
            raise HTTPException(409, "Set your Steam profile first.")
        existing = conn.execute("SELECT name, extra FROM vg_games WHERE app_id = %s", (app_id,)).fetchone()
    if existing:
        raise HTTPException(409, f"{existing['name']} is already in your games.")
    try:
        item = steam.store_items([app_id]).get(app_id) or {}
        mine = steam.player_achievements(account["steam_id"], app_id)
    except steam.NoStats:
        raise HTTPException(422, "That game has no achievements on Steam.")
    except steam.SteamError as e:
        raise HTTPException(422, str(e))
    if not any(a.get("achieved") for a in mine):
        raise HTTPException(422, "You haven't unlocked any of that game's achievements yet.")
    with db() as conn:
        conn.execute("INSERT INTO vg_games (app_id, name, header_url, extra) VALUES (%s, %s, %s, true)",
                     (app_id, item.get("name") or f"App {app_id}", item.get("header") or ""))
        sync_game(conn, account["steam_id"], app_id, rarity_due=True)
    return get_game(app_id)


@router.delete("/videogames/extra/{app_id}", status_code=204)
def remove_extra(app_id: int):
    """Stop tracking a game you added by hand (games from your library can only be hidden)."""
    with db() as conn:
        found(conn.execute("DELETE FROM vg_games WHERE app_id = %s AND extra RETURNING app_id",
                           (app_id,)).fetchone(), "A game you added")
    return Response(status_code=204)


@router.get("/videogames/{app_id}")
def get_game(app_id: int):
    """One game with its achievements: unlocked ones first (newest first), then the rest, rarest last."""
    with db() as conn:
        game = with_pictures(found(conn.execute(GAME_SELECT + " WHERE g.app_id = %s", (app_id,)).fetchone(), "Game"))
        game["achievements"] = conn.execute("""
            SELECT api_name, name, description, icon, icon_gray, hidden, global_percent, achieved, unlocked_at
            FROM vg_achievements WHERE app_id = %s
            ORDER BY achieved DESC, unlocked_at DESC NULLS LAST, global_percent DESC NULLS LAST, name""",
            (app_id,)).fetchall()
    return game


@router.patch("/videogames/{app_id}")
def update_game(app_id: int, body: GamePatch):
    """Hide a game from the dashboard (a demo, a game you'll never 100%), or show it again."""
    with db() as conn:
        found(conn.execute("UPDATE vg_games SET hidden = %s WHERE app_id = %s RETURNING app_id",
                           (body.hidden, app_id)).fetchone(), "Game")
    return get_game(app_id)
