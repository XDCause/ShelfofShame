"""Video games: playtime over time (78_vg_playtime.sql). Steam, Exophase and your typed-in hours only ever give a
game's TOTAL, so each sync (and each time you type hours in) saves that day's total; what you played on a day is that
day's total less the previous one. Used by videogames.py (the dashboard, a game's history) and fed by vgsync.py and
othergames.py.
"""
SNAPSHOT = """INSERT INTO vg_playtime (platform, app_id, minutes) VALUES (%s, %s, %s)
              ON CONFLICT (platform, app_id, day) DO UPDATE SET minutes = EXCLUDED.minutes"""

# Each day's playing: the day's total less the one before it (never below 0 - a total that drops is a reset).
PLAYED = """
WITH s AS (
    SELECT platform, app_id, day,
           minutes - lag(minutes) OVER (PARTITION BY platform, app_id ORDER BY day) AS played
    FROM vg_playtime)
SELECT platform, app_id, day, played FROM s WHERE played > 0"""


def snapshot(conn, platform: str, app_id, minutes):
    """Today's total for a game (a later one today replaces it)."""
    if minutes is not None:
        conn.execute(SNAPSHOT, (platform, str(app_id), int(minutes)))


def history(conn, platform: str, app_id, days: int = 90) -> dict:
    """One game: what you played each day lately, the last 7 and 30 days, and since when it's known."""
    rows = conn.execute(f"SELECT day, played::int AS minutes FROM ({PLAYED}) x "
                        "WHERE platform = %s AND app_id = %s AND day > current_date - %s ORDER BY day",
                        (platform, str(app_id), days)).fetchall()
    since = conn.execute("SELECT min(day) AS d, current_date AS today FROM vg_playtime WHERE platform = %s AND app_id = %s",
                         (platform, str(app_id))).fetchone()
    today = since["today"]
    return {"days": rows, "since": since["d"],
            "last_7_days": sum(r["minutes"] for r in rows if (today - r["day"]).days < 7),
            "last_30_days": sum(r["minutes"] for r in rows if (today - r["day"]).days < 30)}
