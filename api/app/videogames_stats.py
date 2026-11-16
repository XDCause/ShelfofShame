"""Video games: time played, the stats page, the year's recap and the yearly goal. Split out of videogames.py
(2026-10-22)."""
import random
from datetime import date, timedelta

from fastapi import APIRouter, Query

from .db import db
from .videogames import (ALL_ACHIEVEMENTS, ALL_GAMES, COMPLETION_BANDS, GOAL_KEY, GoalIn, PLATFORMS_QUERY,
                         RARITY_BANDS, UNLOCKS, finished_median, games_where, platforms_from, played,
                         steam_ids, streaks, summary, with_estimate)

router = APIRouter(prefix="/api", tags=["video games"])


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
def recap(month: str | None = Query(None, pattern=r"^(\d{4}-\d{2}|all)$"), platforms: str | None = PLATFORMS_QUERY):
    """One month (YYYY-MM, default this one) of achievement hunting on the chosen platforms (default
    all): how many you unlocked (and the month before, to compare - only up to the same point while
    this month is still going), in how many games, the games you 100%'d, your rarest unlocks, your
    best day and the games you unlocked the most in. `first` is the earliest month with an unlock.
    month=all: the same for your whole lifetime (no month before: `previous` is None; `perfect` is the 12
    most recent 100%s, `perfect_count` all of them)."""
    chosen = platforms_from(platforms)
    lifetime = month == "all"
    with db() as conn:
        if lifetime:
            span = {"start": date(1970, 1, 1), "end": date(9999, 1, 1), "platforms": chosen}
        else:
            start = conn.execute("SELECT date_trunc('month', COALESCE(to_date(%s, 'YYYY-MM'), now()))::date AS s",
                                 (month,)).fetchone()["s"]
            span = {"start": start, "end": (start.replace(day=28) + timedelta(days=4)).replace(day=1), "platforms": chosen,
                    "before": (start - timedelta(days=1)).replace(day=1)}
        unlocked = f"{UNLOCKS} AND a.unlocked_at >= %(start)s AND a.unlocked_at < %(end)s"
        counts = conn.execute(f"SELECT count(*)::int AS achievements, count(DISTINCT a.app_id)::int AS games {unlocked}",
                              span).fetchone()
        # The month before - up to the same point when this month isn't over yet (1-14 Sept for 1-14 Oct).
        counts["previous"] = None if lifetime else conn.execute(
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
        counts["perfect_count"] = len(perfect)
        if lifetime:
            perfect = perfect[::-1][:12]                                     # the latest first
        first = conn.execute(f"SELECT to_char(min(a.unlocked_at), 'YYYY-MM') AS m {UNLOCKS}", span).fetchone()["m"]
        this_month = conn.execute("SELECT to_char(now(), 'YYYY-MM') AS m").fetchone()["m"]   # Brisbane, not UTC
    return {"month": "all" if lifetime else span["start"].strftime("%Y-%m"), "first": first, "this_month": this_month,
            **counts, "best_day": best_day, "rarest": rarest, "top_games": top, "perfect": perfect}


@router.put("/videogames/goal")
def set_goal(body: GoalIn):
    """Change the profile completion goal (a % of every achievement in your games)."""
    with db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (%s, %s) "
                     "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (GOAL_KEY, str(body.percent)))
    return summary(None)


@router.get("/videogames/backlog")
def backlog(by: str = Query("shortest", pattern="^(shortest|achievements|random)$"), platforms: str | None = PLATFORMS_QUERY):
    """What next? From the games in your Backlog (status backlog, hidden ones left out):
        shortest      the least time to play: your own estimate (beat_hours) if you gave one, else SteamHunters' median
                      time to 100%, else your own median playtime of the games you've finished (median_finished_minutes)
        achievements  the fewest achievements left (games without any come last)
        random        any one
    pick is the one to play, others the next few. (Declared before /videogames/{app_id}.)"""
    chosen = platforms_from(platforms)
    with db() as conn:
        games = games_where(conn, chosen, "NOT hidden AND status = 'backlog'", lambda g: g["name"].lower(), counted_only=False)
        median = finished_median(conn, chosen)
    for g in games:
        with_estimate(g, median)
    if by == "random":
        random.shuffle(games)
    elif by == "achievements":
        games.sort(key=lambda g: (not g["achievements_total"], g["left_to_get"] or 0))
    else:
        games.sort(key=lambda g: (g["estimate_minutes"] is None, g["estimate_minutes"] or 0))
    keep = ("platform", "app_id", "name", "header_url", "playtime_minutes", "achievements_total", "left_to_get",
            "sh_median_minutes", "estimate_minutes", "estimate_source", "beat_hours", "status")
    slim = [{k: g.get(k) for k in keep} for g in games[:5]]
    return {"by": by, "count": len(games), "median_finished_minutes": median,
            "pick": slim[0] if slim else None, "others": slim[1:]}


@router.get("/videogames/easy-achievements")
def easy_achievements(limit: int = Query(12, ge=1, le=50), platforms: str | None = PLATFORMS_QUERY):
    """Your next easiest achievements: in each game (not hidden, on the chosen platforms) the one you don't have yet
    that the most players have (Steam's / Exophase's global %), easiest first. Ones that can't be earned any more
    are left out. (Declared before /videogames/{app_id}.)"""
    with db() as conn:
        rows = conn.execute(f"""
            SELECT * FROM (
                SELECT DISTINCT ON (a.platform, a.app_id) a.platform, a.app_id, a.game, a.api_name, a.name, a.description,
                       a.icon, a.global_percent, g.achievements_done, g.achievements_total
                FROM {ALL_ACHIEVEMENTS} a
                JOIN {ALL_GAMES} g ON g.platform = a.platform AND g.app_id = a.app_id
                WHERE a.platform = ANY(%(platforms)s) AND NOT a.game_hidden AND NOT g.hidden AND NOT a.achieved
                  AND a.global_percent IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM vg_achievements u WHERE a.platform = 'steam' AND u.app_id::text = a.app_id
                                  AND u.api_name = a.api_name AND u.unobtainable)
                ORDER BY a.platform, a.app_id, a.global_percent DESC, a.name) x
            ORDER BY global_percent DESC, achievements_done DESC, game LIMIT %(limit)s""",
                            {"platforms": platforms_from(platforms), "limit": limit}).fetchall()
    return steam_ids(rows)


@router.get("/videogames/costs")
def costs(platforms: str | None = PLATFORMS_QUERY):
    """What your games cost per hour played. Only games you gave a price (price_paid) count towards spent:
        spent / hours       the price of those games and the hours you've played them; per_hour = spent / hours
        library_hours       every hour in the library (priced or not), games = how many games it is
        games               the priced games, the dearest per hour first (a game never played has no per_hour)"""
    chosen = platforms_from(platforms)
    with db() as conn:
        priced = games_where(conn, chosen, "price_paid IS NOT NULL", lambda g: 0, counted_only=False)
        library = conn.execute(f"SELECT count(*)::int AS games, COALESCE(sum(playtime_minutes), 0)::int AS minutes "
                               f"FROM {ALL_GAMES} g WHERE platform = ANY(%(p)s) AND NOT hidden", {"p": chosen}).fetchone()
    rows = []
    for g in priced:
        hours = g["playtime_minutes"] / 60
        rows.append({k: g.get(k) for k in ("platform", "app_id", "name", "header_url", "price_paid", "playtime_minutes")}
                    | {"per_hour": round(float(g["price_paid"]) / hours, 2) if hours > 0 else None})
    rows.sort(key=lambda r: (r["per_hour"] is None, -(r["per_hour"] or 0), r["name"].lower()))
    spent = sum(float(r["price_paid"]) for r in rows)
    minutes = sum(r["playtime_minutes"] for r in rows)
    return {"spent": round(spent, 2), "priced": len(rows), "hours": round(minutes / 60, 1),
            "per_hour": round(spent / (minutes / 60), 2) if minutes else None,
            "unplayed": sum(r["per_hour"] is None for r in rows),
            "library_games": library["games"], "library_hours": round(library["minutes"] / 60, 1), "games": rows}
