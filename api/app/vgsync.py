"""The Steam sync behind the Video games hobby (videogames.py has the routes and the dashboard maths).

A sync reads Steam (steam.py) into vg_games / vg_achievements, then how other players did (steamhunters.py)
and which achievements come with a DLC (exophase.py), with Epic / Ubisoft games from Exophase alongside
(othergames.sync_other). The first sync reads every game; after that only games played since the last sync
(or never read), unless full=True. It runs in the background (start_sync) with its progress in SYNC, and
once a day by itself while the app is up (start_daily_sync). sync_one reads just one game, straight away
(the game you're playing now): its playtime, achievements and rarity, then its SteamHunters numbers and
DLC list if they're due.

SYNC and the daily loop live in this process's memory: the API runs with one worker (api/Dockerfile).
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks

from . import exophase, othergames, steam, steamhunters, vgplaytime
from .db import db

log = logging.getLogger("videogames")

RARITY_EVERY = timedelta(days=7)     # rarity changes slowly: re-read it weekly at most
COMMUNITY_EVERY = timedelta(days=7)  # SteamHunters' numbers: the same
UNTOUCHED_EVERY = timedelta(days=30) # ...for games not started yet: monthly (nobody's playing them; they barely move)
FRESH = timedelta(days=1)            # a full sync skips SteamHunters numbers newer than this...
DLC_EVERY = timedelta(days=30)       # ...and DLC lists newer than this (they change with the achievements)
STEAM_AT_ONCE = 4                    # Steam games read side by side (official API, your own key)
DAILY = timedelta(hours=20)          # the automatic sync's spacing

# How the background sync is going (one at a time).
SYNC = {"running": False, "done": 0, "total": 0, "message": None, "error": None, "finished_at": None}
_lock = threading.Lock()
# SteamHunters and Exophase are read side by side, but both write to a game's rows: their (quick)
# database writes take turns, or the two transactions can deadlock on the same game.
_writes = threading.Lock()


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
        conn.execute("UPDATE vg_games SET exo_synced_at = NULL WHERE app_id = %s", (app_id,))  # new ones: which DLC?
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
    recount(conn, app_id)
    conn.execute("UPDATE vg_games SET synced_at = now() WHERE app_id = %s", (app_id,))


def recount(conn, app_id: int):
    """A game's totals from its achievements. Unobtainable ones you don't have aren't counted, so a
    game can be 100% without them (one you got before it became unobtainable still counts)."""
    conn.execute("""
        UPDATE vg_games g SET has_achievements = s.every > 0, achievements_total = s.total, achievements_done = s.done,
               completed_at = CASE WHEN s.total > 0 AND s.done >= s.total THEN s.last END
        FROM (SELECT count(*)::int AS every, count(*) FILTER (WHERE achieved OR NOT unobtainable)::int AS total,
                     count(*) FILTER (WHERE achieved)::int AS done, max(unlocked_at) AS last
              FROM vg_achievements WHERE app_id = %s) s
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
                vgplaytime.snapshot(conn, "steam", g["appid"], g.get("playtime_forever", 0))
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

        def read(game):
            app_id, name, rarity_due = game
            with db() as conn:
                sync_game(conn, steam_id, app_id, rarity_due)
            step(f"Reading {name}...")
            steam.pause()
        with ThreadPoolExecutor(STEAM_AT_ONCE) as pool:
            list(pool.map(read, to_read))     # list(): a Steam error in any of them stops the sync
        with db() as conn:
            conn.execute("UPDATE vg_sync SET last_sync_at = now(), last_error = NULL"
                         + (", last_full_at = now()" if full or not account["last_full_at"] else "") + " WHERE id = 1")
        notes = sync_others(full, {app_id for app_id, _, _ in to_read})
        SYNC.update(message=f"Done: {len(owned)} games, {len(to_read)} read from Steam{notes}")
    except steam.SteamError as e:
        SYNC.update(error=str(e), message=None)
        with db() as conn:
            conn.execute("UPDATE vg_sync SET last_error = %s WHERE id = 1", (str(e),))
    except Exception as e:  # keep the app up; say what happened
        log.exception("Steam sync failed")
        SYNC.update(error=f"The sync stopped: {e.__class__.__name__}.", message=None)
    finally:
        SYNC.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())


def step(message: str):
    """One more thing done (the sync's parts run side by side, so count under the lock)."""
    with _lock:
        SYNC["done"] += 1
        SYNC["message"] = message


def sync_others(full: bool, read_now: set[int]) -> str:
    """After Steam: SteamHunters' numbers and Exophase's DLC lists (then the Epic / Ubisoft games)
    side by side - different sites, each still asked one request at a time. Returns the notes."""
    community, dlc = community_due(full, read_now), dlc_due(full)
    SYNC.update(total=len(community) + len(dlc), done=0)
    sh_done = threading.Event()      # the DLC side waits for this before games SteamHunters hadn't judged

    def sh_side():
        try:
            return sync_community(community)
        finally:
            sh_done.set()
    with ThreadPoolExecutor(2) as pool:
        sh = pool.submit(sh_side)
        exo = pool.submit(lambda: sync_dlc(dlc, sh_done) + othergames.sync_other())
        return sh.result() + exo.result()


def community_due(full: bool, read_now: set[int]) -> list[tuple[int, str]]:
    """Games whose SteamHunters numbers are due. Started ones: just read from Steam, a week old or
    never read - or, on a full sync, all but those read in the last day. Ones not started yet (so
    their median and 100% rate help pick what to start): never read or a month old, full sync or
    not. Started games first: if SteamHunters stops answering, they're the ones that matter."""
    now = datetime.now(timezone.utc)
    with db() as conn:
        rows = conn.execute("SELECT app_id, name, sh_synced_at, achievements_done > 0 AS started FROM vg_games "
                            "WHERE achievements_total > 0 AND NOT hidden "
                            "ORDER BY achievements_done > 0 DESC, last_played DESC NULLS LAST").fetchall()

    def due(r):
        if not r["sh_synced_at"]:
            return True
        age = now - r["sh_synced_at"]
        if not r["started"]:
            return age > UNTOUCHED_EVERY
        if full:                # a full sync re-reads every game from Steam: freshness decides here
            return age > FRESH
        return r["app_id"] in read_now or age > COMMUNITY_EVERY
    return [(r["app_id"], r["name"]) for r in rows if due(r)]


def sync_community(due: list[tuple[int, str]], progress=step) -> str:
    """How other players did, from SteamHunters, for the games due. One a second. If SteamHunters
    can't be reached the Steam sync still counts; this part tries again next time. Returns a note
    for the sync's message."""
    if not due:
        return ""
    for left, (app_id, name) in zip(range(len(due), 0, -1), due):
        try:
            fields = steamhunters.game(app_id) or {}
            gone = set()
            if fields.get("sh_unobtainable"):             # which ones (only asked when there are some)
                steamhunters.pause()
                gone = steamhunters.unobtainable(app_id)
        except steamhunters.Unavailable as e:
            log.warning("SteamHunters: %s", e)
            return f" (SteamHunters didn't answer, so {left} games' community numbers wait for the next sync)"
        with _writes, db() as conn:
            conn.execute("UPDATE vg_games SET sh_median_minutes = %s, sh_fastest_minutes = %s, sh_players_perfected = %s, "
                         "sh_players_started = %s, sh_points = %s, sh_has_dlc = %s, sh_unobtainable = %s, "
                         "sh_synced_at = now() WHERE app_id = %s",
                         (fields.get("sh_median_minutes"), fields.get("sh_fastest_minutes"),
                          fields.get("sh_players_perfected"), fields.get("sh_players_started"), fields.get("sh_points"),
                          fields.get("sh_has_dlc"), fields.get("sh_unobtainable"), app_id))
            changed = conn.execute("UPDATE vg_achievements SET unobtainable = (api_name = ANY(%(gone)s)) "
                                   "WHERE app_id = %(id)s AND unobtainable <> (api_name = ANY(%(gone)s))",
                                   {"gone": list(gone), "id": app_id}).rowcount
            if changed:
                recount(conn, app_id)
        progress(f"How others did: {name}...")
        steamhunters.pause()
    return f", community numbers for {len(due)}"


def dlc_due(full: bool) -> list[dict]:
    """Started games with DLC (SteamHunters says so, or doesn't know) whose DLC list is due: never
    read or the achievements changed since - or, on a full sync, also ones over 30 days old."""
    with db() as conn:
        return conn.execute(
            "SELECT app_id, name, achievements_total, sh_has_dlc FROM vg_games WHERE achievements_done > 0 AND NOT hidden "
            "AND sh_has_dlc IS NOT false AND (exo_synced_at IS NULL"
            + (" OR exo_synced_at < now() - %s" if full else "") + ") ORDER BY last_played DESC NULLS LAST",
            (DLC_EVERY,) if full else ()).fetchall()


def sync_dlc(due: list[dict], sh_done: threading.Event | None = None, progress=step) -> str:
    """Which achievements come with a DLC, from Exophase, for the games due. Achievements Exophase
    doesn't list stay with the main game. Games SteamHunters hadn't judged yet (sh_has_dlc unknown)
    go last: once SteamHunters' side is done (sh_done), ones it says have no DLC are skipped - so a
    first sync doesn't ask Exophase about every game. Returns a note for the sync's message."""
    if not due:
        return ""
    def still_due(g):
        """A game SteamHunters hadn't judged: wait for its side to finish, then ask again."""
        if g["sh_has_dlc"] is not None:
            return True
        if sh_done is not None:
            sh_done.wait()
        with db() as conn:
            return conn.execute("SELECT sh_has_dlc FROM vg_games WHERE app_id = %s",
                                (g["app_id"],)).fetchone()["sh_has_dlc"] is not False

    read = 0
    for g in sorted(due, key=lambda g: g["sh_has_dlc"] is None):    # known DLC games first
        if not still_due(g):
            progress(f"Which achievements are DLC: {g['name']}...")
            continue
        read += 1
        try:
            dlcs = steamhunters.dlc_names(g["app_id"])     # real DLC, not free updates
            steamhunters.pause()
            url, groups = exophase.dlc_of(g["app_id"], g["name"], g["achievements_total"], dlcs)
        except (exophase.Unavailable, steamhunters.Unavailable) as e:
            log.warning("DLC lists: %s", e)
            return f" ({e} Some games' DLC lists wait for the next sync)"
        with _writes, db() as conn:
            for a in conn.execute("SELECT api_name, name FROM vg_achievements WHERE app_id = %s", (g["app_id"],)).fetchall():
                conn.execute("UPDATE vg_achievements SET dlc = %s WHERE app_id = %s AND api_name = %s",
                             (groups.get(exophase.key(a["name"])), g["app_id"], a["api_name"]))
            conn.execute("UPDATE vg_games SET exo_url = %s, exo_synced_at = now() WHERE app_id = %s", (url, g["app_id"]))
        progress(f"Which achievements are DLC: {g['name']}...")
        exophase.pause()
    return f", DLC lists for {read}" if read else ""


def sync_one(app_id: int) -> str:
    """Read one game now: its playtime (from the owned-games list - a game added by hand has none), its
    achievements with fresh rarity, then SteamHunters' numbers (if over a day old) and which achievements are
    DLC (if never read, or its achievements changed). Raises steam.SteamError; SteamHunters or Exophase not
    answering only adds a note. Returns the note."""
    with db() as conn:
        steam_id = conn.execute("SELECT steam_id FROM vg_sync WHERE id = 1").fetchone()["steam_id"]
        game = conn.execute("SELECT name, extra FROM vg_games WHERE app_id = %s", (app_id,)).fetchone()
    if not steam_id:
        raise steam.SteamError("Set your Steam profile first.")
    if not game["extra"]:
        owned = next((g for g in steam.owned_games(steam_id) if g["appid"] == app_id), None)
        steam.pause()
        if owned:
            with db() as conn:
                conn.execute("UPDATE vg_games SET playtime_minutes = %s, playtime_2weeks = %s, last_played = %s "
                             "WHERE app_id = %s", (owned.get("playtime_forever", 0), owned.get("playtime_2weeks", 0),
                                                   _ts(owned.get("rtime_last_played")), app_id))
                vgplaytime.snapshot(conn, "steam", app_id, owned.get("playtime_forever", 0))
    with db() as conn:
        sync_game(conn, steam_id, app_id, rarity_due=True)
    with db() as conn:
        g = conn.execute("SELECT app_id, name, achievements_done, achievements_total, sh_has_dlc, sh_synced_at, "
                         "exo_synced_at, hidden FROM vg_games WHERE app_id = %s", (app_id,)).fetchone()
    if not g["achievements_total"]:     # no achievements: nothing to compare
        return ""
    quiet = lambda _message: None       # noqa: E731 - SYNC's progress is the full sync's
    notes = []                          # only what went wrong: " (SteamHunters didn't answer, ...)"
    if not g["sh_synced_at"] or datetime.now(timezone.utc) - g["sh_synced_at"] > FRESH:
        notes.append(sync_community([(app_id, g["name"])], quiet))
        with db() as conn:
            g = conn.execute("SELECT * FROM vg_games WHERE app_id = %s", (app_id,)).fetchone()
    if g["achievements_done"] and g["sh_has_dlc"] is not False and not g["exo_synced_at"]:   # (started only, as the full sync)
        notes.append(sync_dlc([g], progress=quiet))
    return "; ".join(n.strip(" ()") for n in notes if n.startswith(" ("))


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
            except Exception:  # no key, database restarting...: say so, try again in an hour
                log.exception("Daily Steam sync check failed")
            threading.Event().wait(3600)
    threading.Thread(target=loop, daemon=True, name="steam-daily").start()
