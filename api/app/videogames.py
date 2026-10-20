"""Video games (a hobby module): your Steam games and achievements, for a 100% dashboard.

    sync      (vgsync.py) reads Steam (steam.py) into vg_games / vg_achievements, then how other players did
              (steamhunters.py: median and fastest time to 100%, how many 100%'d it) for started
              games - played since, a week old or never read (all of them on a full sync); then
              which achievements come with a DLC (exophase.py) for started games with DLC - once,
              again when their achievements change, and on a full sync. The first sync reads every
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
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import othergames, steam, vgplaytime
from .db import db, found
from .vgsync import SYNC, start_sync, sync_game, sync_one
from .settings import get_setting

router = APIRouter(prefix="/api", tags=["video games"])
log = logging.getLogger("videogames")

HEADER = "https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"
ICON = "https://media.steampowered.com/steamcommunity/public/images/apps/{app_id}/{hash}.jpg"

class ProfileIn(BaseModel):
    profile: str = Field(min_length=2, max_length=200)   # a name, id or profile address


class GamePatch(BaseModel):
    hidden: bool


class ExtraIn(BaseModel):
    game: str = Field(min_length=1, max_length=300)   # its store link, or its app id


class GoalIn(BaseModel):
    percent: int = Field(ge=1, le=100)   # % of every achievement in your games


GOAL_KEY, GOAL_DEFAULT = "vg_goal_percent", 50


# perfect_rate: the % of SteamHunters' players who started the game and 100%'d it. rarest_percent:
# Steam's cross-check - its rarest achievement's global %, the most players that can have 100%'d it.
# dlc_count / dlc_achievements: DLCs with achievements (from Exophase) and how many those add.
# dlc_done: how many of those you have. unobtainable_count: ones that can't be earned any more.
GAME_SELECT = """
SELECT g.*, CASE WHEN g.achievements_total > 0
                 THEN round(100.0 * g.achievements_done / g.achievements_total, 1) END AS percent,
       g.achievements_total - g.achievements_done AS left_to_get,
       round(100.0 * g.sh_players_perfected / NULLIF(g.sh_players_started, 0), 1) AS perfect_rate,
       a.rarest_percent, a.dlc_count, a.dlc_achievements, a.dlc_done, a.unobtainable_count
FROM vg_games g
LEFT JOIN LATERAL (SELECT min(global_percent) AS rarest_percent, count(DISTINCT dlc)::int AS dlc_count,
                          count(dlc)::int AS dlc_achievements, count(dlc) FILTER (WHERE achieved)::int AS dlc_done,
                          count(*) FILTER (WHERE unobtainable AND NOT achieved)::int AS unobtainable_count
                   FROM vg_achievements WHERE app_id = g.app_id) a ON true"""


def with_pictures(game: dict) -> dict:
    """The game's pictures: its header from the store API (header_url), else the old fixed address
    (older games still have one; the page shows a placeholder if that fails too)."""
    game["header_url"] = game.get("header_url") or HEADER.format(app_id=game["app_id"])
    game["icon_url"] = ICON.format(app_id=game["app_id"], hash=game["icon_hash"]) if game.get("icon_hash") else None
    return game


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


PLATFORMS = ("steam", "epic", "ubisoft")
PLATFORMS_QUERY = Query(None, max_length=40, description="steam,epic,ubisoft - which to count (default all)")


def platforms_from(text: str | None) -> list[str]:
    """?platforms=steam,epic -> ["steam", "epic"]; none given = all three."""
    if not text:
        return list(PLATFORMS)
    asked = {p.strip().lower() for p in text.split(",")}
    chosen = [p for p in PLATFORMS if p in asked]
    if not chosen:
        raise HTTPException(422, "Pick at least one platform: steam, epic or ubisoft.")
    return chosen


# Every game and every achievement - Steam's, Epic's and Ubisoft's - in one shape, for the
# dashboard, the stats and the recap (each query filters platform = ANY(%(platforms)s)). app_id is
# text here ("730", "epic-12"); steam_ids() turns Steam's back into numbers.
ALL_GAMES = f"""(
    SELECT 'steam' AS platform, app_id::text AS app_id, name, hidden, has_achievements, achievements_done,
           achievements_total, completed_at, playtime_minutes FROM vg_games
    UNION ALL
    SELECT platform, app_id, name, hidden, has_achievements AND counted,
           -- achievements you ticked yourself and chose not to count: not in the totals (the playtime still is)
           CASE WHEN counted THEN achievements_done END, CASE WHEN counted THEN achievements_total END,
           CASE WHEN counted THEN completed_at END, playtime_minutes FROM ({othergames.SELECT}) o
    WHERE NOT on_steam)"""
# (on_steam: a Ubisoft game you also own on Steam - counted once, as the Steam game; no SQL comments in these two:
# they're pasted into the middle of lines, where a comment would swallow the rest)
ALL_ACHIEVEMENTS = """(
    SELECT 'steam' AS platform, a.app_id::text AS app_id, g.name AS game, g.hidden AS game_hidden, a.api_name,
           a.name, a.description, a.icon, a.global_percent, a.achieved, a.unlocked_at
    FROM vg_achievements a JOIN vg_games g USING (app_id)
    UNION ALL
    SELECT o.platform, o.platform || '-' || o.game_id, o.name, o.hidden, a.api_name, a.name, a.description,
           a.icon, a.global_percent, a.achieved, a.unlocked_at
    FROM vg_other_achievements a JOIN vg_other_games o USING (game_id)
    WHERE o.counted AND NOT (o.platform = 'ubisoft' AND EXISTS (SELECT 1 FROM vg_games s WHERE s.app_id = o.steam_app_id)))"""
# Your unlocks on the chosen platforms, in games you haven't hidden.
UNLOCKS = f"FROM {ALL_ACHIEVEMENTS} a WHERE a.platform = ANY(%(platforms)s) AND NOT a.game_hidden AND a.achieved"


def steam_ids(rows: list[dict]) -> list[dict]:
    for r in rows:
        if r.get("platform") == "steam":
            r["app_id"] = int(r["app_id"])
    return rows


def games_where(conn, platforms: list[str], where: str, sort, limit: int | None = None, params: dict | None = None,
                counted_only: bool = True):
    """Whole game rows (as the Games list has them) on the chosen platforms that match `where` (in
    the columns both shapes share: hidden, achievements_done, completed_at...), sorted by `sort`.
    counted_only: leave out Epic / Ubisoft games whose ticked achievements you chose not to count."""
    params = {**(params or {}), "others": [p for p in platforms if p != "steam"]}
    rows = []
    if "steam" in platforms:
        rows += [with_pictures({**g, "platform": "steam"})
                 for g in conn.execute(f"SELECT * FROM ({GAME_SELECT}) x WHERE {where}", params).fetchall()]
    if params["others"]:
        rows += conn.execute(f"SELECT * FROM ({othergames.SELECT}) x WHERE x.platform = ANY(%(others)s) AND NOT x.on_steam "
                             f"AND {where}" + (" AND x.counted" if counted_only else ""), params).fetchall()
    rows.sort(key=sort)
    return rows[:limit] if limit else rows


def _ratio(g):
    return g["achievements_done"] / g["achievements_total"]


@router.get("/videogames/summary")
def summary(platforms: str | None = PLATFORMS_QUERY):
    """For the dashboard and Home: totals, the games closest to 100%, recent unlocks, the rarest you
    have - from Steam, Epic and Ubisoft together, or only the platforms in ?platforms=. Steam alone
    matches SteamHunters' numbers. `available` = the platforms you have games on."""
    chosen = platforms_from(platforms)
    p = {"platforms": chosen}
    with db() as conn:
        totals = conn.execute(f"""
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
            FROM {ALL_GAMES} g WHERE platform = ANY(%(platforms)s) AND NOT hidden""", p).fetchone()
        totals["unlocked_this_month"] = conn.execute(
            f"SELECT count(*)::int AS n {UNLOCKS} AND a.unlocked_at >= date_trunc('month', now())", p).fetchone()["n"]
        totals["unlocked_last_30_days"] = conn.execute(
            f"SELECT count(*)::int AS n {UNLOCKS} AND a.unlocked_at >= now() - interval '30 days'", p).fetchone()["n"]
        started = [(r["achievements_done"], r["achievements_total"]) for r in conn.execute(
            f"SELECT achievements_done, achievements_total FROM {ALL_GAMES} g "
            "WHERE platform = ANY(%(platforms)s) AND NOT hidden AND achievements_done > 0", p).fetchall()]
        totals["goal"] = goal_progress(started, totals["unlocked_last_30_days"],
                                       int(get_setting(conn, GOAL_KEY) or GOAL_DEFAULT))
        # A week ago: each started game's achievements less those unlocked in the last 7 days
        # (Steam and Epic date every unlock; Ubisoft ticks have no date, so they never show as new).
        totals["week"] = week_change(conn.execute(f"""
            SELECT g.achievements_done AS done, g.achievements_total AS total,
                   g.achievements_done - count(a.app_id) FILTER (WHERE a.achieved
                       AND a.unlocked_at >= now() - interval '7 days')::int AS done_then
            FROM {ALL_GAMES} g LEFT JOIN {ALL_ACHIEVEMENTS} a ON a.platform = g.platform AND a.app_id = g.app_id
            WHERE g.platform = ANY(%(platforms)s) AND NOT g.hidden AND g.achievements_done > 0
            GROUP BY g.platform, g.app_id, g.achievements_done, g.achievements_total""", p).fetchall())
        started_where = "NOT hidden AND achievements_done > 0 AND completed_at IS NULL"
        closest = games_where(conn, chosen, started_where,
                              lambda g: (-_ratio(g), g["achievements_total"] - g["achievements_done"]), 6)
        quick = games_where(conn, chosen, started_where + " AND sh_median_minutes > 0", lambda g: 0)
        perfect = games_where(conn, chosen, "NOT hidden AND completed_at IS NOT NULL",
                              lambda g: -g["completed_at"].timestamp(), 6)
        achievement = f"SELECT a.platform, a.app_id, a.game, a.api_name, a.name, a.description, a.icon, " \
                      f"a.global_percent, a.unlocked_at {UNLOCKS}"
        recent = steam_ids(conn.execute(achievement + " ORDER BY a.unlocked_at DESC NULLS LAST LIMIT 8", p).fetchall())
        rarest = steam_ids(conn.execute(achievement + " AND a.global_percent IS NOT NULL "
                                        "ORDER BY a.global_percent, a.unlocked_at LIMIT 8", p).fetchall())
        totals["streak"] = streaks([r["day"] for r in conn.execute(
            f"SELECT DISTINCT a.unlocked_at::date AS day {UNLOCKS} AND a.unlocked_at IS NOT NULL", p).fetchall()],
            conn.execute("SELECT now()::date AS d").fetchone()["d"])
        others = [r["platform"] for r in conn.execute(
            "SELECT DISTINCT platform FROM vg_other_games WHERE NOT hidden").fetchall()]
        totals["played"] = played(conn, chosen, 31)["totals"]
    return {**totals, "platforms": chosen, "available": [x for x in PLATFORMS if x == "steam" or x in others],
            "closest": closest, "recent": recent, "rarest": rarest, "recent_perfect": perfect,
            "quick_wins": quick_wins(quick)}


def quick_wins(games: list[dict], limit: int = 6) -> list[dict]:
    """Started games ranked by the time left to 100%: SteamHunters' median time to 100% times the
    share of achievements you have left (a rough guide - the last ones are often the slow ones)."""
    for g in games:
        g["minutes_left"] = math.ceil(g["sh_median_minutes"] * g["left_to_get"] / g["achievements_total"])
    games.sort(key=lambda g: (g["minutes_left"], -float(g["perfect_rate"] or 0)))
    return games[:limit]


def streaks(days: list[date], today: date) -> dict:
    """Days in a row with at least one unlock: the current run (still alive if the last unlock was
    yesterday - today isn't over) and the longest ever, with the day it ended."""
    days = sorted(set(days))
    longest, longest_end, run = 0, None, 0
    for i, d in enumerate(days):
        run = run + 1 if i and d - days[i - 1] == timedelta(days=1) else 1
        if run > longest:
            longest, longest_end = run, d
    current = run if days and today - days[-1] <= timedelta(days=1) else 0
    return {"current": current, "longest": longest, "longest_end": longest_end,
            "unlocked_today": bool(days) and days[-1] == today}


# Rarity bands (the % of all players who have an achievement) and completion bands for the charts.
RARITY_BANDS = [(0, 1, "Under 1%"), (1, 5, "1–5%"), (5, 10, "5–10%"), (10, 20, "10–20%"), (20, 50, "20–50%"),
                (50, 101, "50% or more")]
COMPLETION_BANDS = [(0, 10, "Under 10%"), (10, 25, "10–24%"), (25, 50, "25–49%"), (50, 75, "50–74%"),
                    (75, 100, "75–99%"), (100, 101, "100%")]


def played(conn, platforms: list[str], days: int) -> dict:
    """Playtime over the last `days` days on the chosen platforms (games you haven't hidden): each day's minutes
    (days with none included), totals for today / the last 7 days / this week (from Monday) / this month, the most
    played games in that time, and the day the history starts (vgplaytime.py)."""
    rows = conn.execute(f"""
        SELECT x.day, x.played::int AS minutes, g.platform, g.app_id, g.name
        FROM ({vgplaytime.PLAYED}) x JOIN {ALL_GAMES} g ON g.platform = x.platform AND g.app_id = x.app_id
        WHERE x.platform = ANY(%(platforms)s) AND NOT g.hidden AND x.day > current_date - %(days)s""",
        {"platforms": platforms, "days": max(days, 31)}).fetchall()
    meta = conn.execute("SELECT current_date AS today, (SELECT min(day) FROM vg_playtime) AS since").fetchone()
    today = meta["today"]
    by_day = {}
    for r in rows:
        by_day[r["day"]] = by_day.get(r["day"], 0) + r["minutes"]
    window = [today - timedelta(days=n) for n in range(days - 1, -1, -1)]
    games = {}
    for r in rows:
        if (today - r["day"]).days < days:
            g = games.setdefault((r["platform"], r["app_id"]), {"platform": r["platform"], "app_id": r["app_id"],
                                                                 "name": r["name"], "minutes": 0})
            g["minutes"] += r["minutes"]

    def since(first: date) -> int:
        return sum(m for d, m in by_day.items() if d >= first)
    return {
        "days": [{"day": d, "minutes": by_day.get(d, 0)} for d in window],
        "games": steam_ids(sorted(games.values(), key=lambda g: -g["minutes"])[:8]),
        "totals": {"today": since(today), "last_7_days": since(today - timedelta(days=6)),
                   "this_week": since(today - timedelta(days=today.weekday())), "this_month": since(today.replace(day=1)),
                   "since": meta["since"]},
    }


@router.get("/videogames/playtime")
def playtime(days: int = Query(30, ge=1, le=366), platforms: str | None = PLATFORMS_QUERY):
    """What you've played each day lately, across the chosen platforms (default all). Steam, Epic and your typed-in
    hours only give totals, so the history starts from the first sync that saved one."""
    with db() as conn:
        return played(conn, platforms_from(platforms), days)


@router.get("/videogames/stats")
def stats(months: int = Query(24, ge=1, le=120), platforms: str | None = PLATFORMS_QUERY):
    """The Stats page's charts, from games you haven't hidden on the chosen platforms (default all):
        by_month    achievements unlocked each month, oldest first (months with none included)
        rarity      your achievements by how many players have them
        completion  your started games by how much of each you've done
        most_played the ten games with the most playtime"""
    chosen = platforms_from(platforms)
    p = {"platforms": chosen, "months": months}
    with db() as conn:
        by_month = conn.execute(f"""
            SELECT to_char(m, 'YYYY-MM') AS month, COALESCE(n.count, 0)::int AS count
            FROM generate_series(date_trunc('month', now()) - make_interval(months => %(months)s - 1),
                                 date_trunc('month', now()), interval '1 month') m
            LEFT JOIN (SELECT date_trunc('month', a.unlocked_at) AS m, count(*) AS count {UNLOCKS} GROUP BY 1) n USING (m)
            ORDER BY m""", p).fetchall()
        percents = [float(r["global_percent"]) for r in conn.execute(
            f"SELECT a.global_percent {UNLOCKS} AND a.global_percent IS NOT NULL", p).fetchall()]
        games = [float(r["p"]) for r in conn.execute(
            f"SELECT 100.0 * achievements_done / achievements_total AS p FROM {ALL_GAMES} g "
            "WHERE platform = ANY(%(platforms)s) AND NOT hidden AND achievements_done > 0", p).fetchall()]
        most_played = games_where(conn, chosen, "NOT hidden AND playtime_minutes > 0",
                                  lambda g: -g["playtime_minutes"], 10, counted_only=False)
        today = conn.execute("SELECT now()::date AS d").fetchone()["d"]
        days = conn.execute(f"""
            SELECT a.unlocked_at::date AS day, count(*)::int AS count {UNLOCKS} AND a.unlocked_at IS NOT NULL
            GROUP BY 1 ORDER BY 1""", p).fetchall()
    band = lambda bands, values: [{"label": label, "count": sum(lo <= v < hi for v in values)}  # noqa: E731
                                  for lo, hi, label in bands]
    year_ago = today - timedelta(days=370)
    return {"by_month": by_month, "rarity": band(RARITY_BANDS, percents),
            "completion": band(COMPLETION_BANDS, games), "most_played": most_played,
            "today": today, "days": [d for d in days if d["day"] >= year_ago],
            "streak": streaks([d["day"] for d in days], today)}


@router.get("/videogames/recap")
def recap(month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"), platforms: str | None = PLATFORMS_QUERY):
    """One month (YYYY-MM, default this one) of achievement hunting on the chosen platforms (default
    all): how many you unlocked (and the month before, to compare - only up to the same point while
    this month is still going), in how many games, the games you 100%'d, your rarest unlocks, your
    best day and the games you unlocked the most in. `first` is the earliest month with an unlock."""
    chosen = platforms_from(platforms)
    with db() as conn:
        start = conn.execute("SELECT date_trunc('month', COALESCE(to_date(%s, 'YYYY-MM'), now()))::date AS s",
                             (month,)).fetchone()["s"]
        span = {"start": start, "end": (start.replace(day=28) + timedelta(days=4)).replace(day=1), "platforms": chosen}
        span["before"] = (start - timedelta(days=1)).replace(day=1)
        unlocked = f"{UNLOCKS} AND a.unlocked_at >= %(start)s AND a.unlocked_at < %(end)s"
        counts = conn.execute(f"SELECT count(*)::int AS achievements, count(DISTINCT a.app_id)::int AS games {unlocked}",
                              span).fetchone()
        # The month before - up to the same point when this month isn't over yet (1-14 Sept for 1-14 Oct).
        counts["previous"] = conn.execute(
            f"SELECT count(*)::int AS n {UNLOCKS} AND a.unlocked_at >= %(before)s AND a.unlocked_at < %(start)s "
            "AND a.unlocked_at < %(before)s::timestamptz + (now() - %(start)s::timestamptz)", span).fetchone()["n"]
        best_day = conn.execute(f"SELECT a.unlocked_at::date AS day, count(*)::int AS count {unlocked} "
                                "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 1", span).fetchone()
        rarest = steam_ids(conn.execute(f"""
            SELECT a.platform, a.app_id, a.game, a.api_name, a.name, a.description, a.icon, a.global_percent,
                   a.unlocked_at {unlocked} AND a.global_percent IS NOT NULL
            ORDER BY a.global_percent, a.unlocked_at LIMIT 3""", span).fetchall())
        top = steam_ids(conn.execute(f"""SELECT a.platform, a.app_id, a.game AS name, count(*)::int AS count {unlocked}
                                         GROUP BY 1, 2, 3 ORDER BY 4 DESC, 3 LIMIT 5""", span).fetchall())
        perfect = games_where(conn, chosen, "NOT hidden AND completed_at >= %(start)s AND completed_at < %(end)s",
                              lambda g: g["completed_at"], params=span)
        first = conn.execute(f"SELECT to_char(min(a.unlocked_at), 'YYYY-MM') AS m {UNLOCKS}", span).fetchone()["m"]
        this_month = conn.execute("SELECT to_char(now(), 'YYYY-MM') AS m").fetchone()["m"]   # Brisbane, not UTC
    return {"month": start.strftime("%Y-%m"), "first": first, "this_month": this_month,
            **counts, "best_day": best_day, "rarest": rarest, "top_games": top, "perfect": perfect}


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


def week_change(games: list[dict]) -> dict:
    """What changed in the last 7 days, from each started game's achievements now (done) and a week
    ago (done_then), out of its total: achievements gained, games at 100%, games in progress, and
    the average and total completion (the same sums as goal_progress, a week ago and now)."""
    def state(pairs):
        pairs = [(d, t) for d, t in pairs if d > 0 and t > 0]
        done, total = sum(d for d, _ in pairs), sum(t for _, t in pairs)
        return {"achievements": done,
                "perfect": sum(1 for d, t in pairs if d >= t),
                "in_progress": sum(1 for d, t in pairs if d < t),
                "percent": sum(100 * d / t for d, t in pairs) / len(pairs) if pairs else 0.0,
                "total_percent": 100 * done / total if total else 0.0}
    now = state([(g["done"], g["total"]) for g in games])
    then = state([(g["done_then"], g["total"]) for g in games])
    return {k: round(now[k] - then[k], 1) if "percent" in k else now[k] - then[k] for k in now}


@router.put("/videogames/goal")
def set_goal(body: GoalIn):
    """Change the profile completion goal (a % of every achievement in your games)."""
    with db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (%s, %s) "
                     "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (GOAL_KEY, str(body.percent)))
    return summary(None)


# Sync bookkeeping the Games list never shows (the game's own page still has it all).
LIST_LEAVES_OUT = ("synced_at", "rarity_synced_at", "sh_synced_at", "exo_synced_at", "exo_url", "sh_has_dlc",
                   "icon_hash", "playtime_2weeks", "sh_players_perfected", "sh_players_started", "sh_points")


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
    return [{k: v for k, v in with_pictures(g).items() if k not in LIST_LEAVES_OUT} for g in rows]


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
            SELECT api_name, name, description, icon, icon_gray, hidden, global_percent, achieved, unlocked_at, dlc,
                   unobtainable
            FROM vg_achievements WHERE app_id = %s
            ORDER BY achieved DESC, unlocked_at DESC NULLS LAST, global_percent DESC NULLS LAST, name""",
            (app_id,)).fetchall()
        game["played"] = vgplaytime.history(conn, "steam", app_id)
    return game


@router.post("/videogames/{app_id}/sync")
def sync_one_game(app_id: int):
    """Sync just this game now (the one you're playing), without waiting for the whole library."""
    with db() as conn:
        found(conn.execute("SELECT 1 FROM vg_games WHERE app_id = %s", (app_id,)).fetchone(), "Game")
    if SYNC["running"]:
        raise HTTPException(409, "A full sync is running - this game will be read by it.")
    try:
        note = sync_one(app_id)
    except steam.SteamError as e:
        raise HTTPException(422, str(e))
    return {**get_game(app_id), "sync_note": note}


@router.patch("/videogames/{app_id}")
def update_game(app_id: int, body: GamePatch):
    """Hide a game from the dashboard (a demo, a game you'll never 100%), or show it again."""
    with db() as conn:
        found(conn.execute("UPDATE vg_games SET hidden = %s WHERE app_id = %s RETURNING app_id",
                           (body.hidden, app_id)).fetchone(), "Game")
    return get_game(app_id)
