"""Video games: time played, the stats page, the year's recap and the yearly goal. Split out of videogames.py
(2026-10-22)."""
from datetime import timedelta

from fastapi import APIRouter, Query

from .db import db
from .videogames import (ALL_GAMES, COMPLETION_BANDS, GOAL_KEY, GoalIn, PLATFORMS_QUERY,
                         RARITY_BANDS, UNLOCKS, games_where, platforms_from, played,
                         steam_ids, streaks, summary)

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


@router.put("/videogames/goal")
def set_goal(body: GoalIn):
    """Change the profile completion goal (a % of every achievement in your games)."""
    with db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (%s, %s) "
                     "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (GOAL_KEY, str(body.percent)))
    return summary(None)
