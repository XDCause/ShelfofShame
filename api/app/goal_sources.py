"""What a goal can count by itself (goals.source), from the hobbies' own records - so "Read 24 books" moves when a
book is finished, without typing a number in.

Each source is a query giving (day, amount) rows:
    sum    the amounts in the goal's time add up: books finished, km hiked, plays logged...
    total  the same, but counting everything ever (games at 100% all-time): the goal moves from where you were
    level  the latest value is where you are (a chess rating); the one before the goal began is where you started

A habit goal (so many times a week / month) uses the sum sources too: "hike 20 km a week", "2 chess games a week".
"""
from datetime import date

SOURCES = {
    # key: (label, unit, hobby, mode, sql)  - sql gives day, amount
    "books_finished": ("Books finished", "books", "reading", "sum",
                       "SELECT finished_on AS day, 1 AS amount FROM books WHERE status = 'finished' AND finished_on IS NOT NULL"),
    "pages_read": ("Pages of books finished", "pages", "reading", "sum",
                   "SELECT finished_on AS day, pages AS amount FROM books WHERE status = 'finished' AND finished_on IS NOT NULL AND pages IS NOT NULL"),
    "hikes": ("Hikes", "hikes", "hiking", "sum", "SELECT hiked_on AS day, 1 AS amount FROM hikes"),
    "km_hiked": ("Kilometres hiked", "km", "hiking", "sum",
                 "SELECT hiked_on AS day, distance_m / 1000.0 AS amount FROM hikes WHERE distance_m IS NOT NULL"),
    "metres_climbed": ("Metres climbed", "m", "hiking", "sum",
                       "SELECT hiked_on AS day, ascent_m AS amount FROM hikes WHERE ascent_m IS NOT NULL"),
    "kits_finished": ("Kits finished", "kits", "models", "sum",
                      "SELECT finished_on AS day, 1 AS amount FROM models WHERE status = 'Finished' AND finished_on IS NOT NULL"),
    "bench_sessions": ("Build log entries", "entries", "models", "sum", "SELECT entry_date AS day, 1 AS amount FROM model_log"),
    "plays": ("Board game plays", "plays", "boardgames", "sum", "SELECT played_on AS day, 1 AS amount FROM board_game_plays"),
    "volleyball_games": ("Volleyball games and trainings", "games", "volleyball", "sum",
                         "SELECT played_on AS day, 1 AS amount FROM volleyball_games WHERE played_on IS NOT NULL AND bye IS NULL"),
    "chess_games": ("Chess games", "games", "chess", "sum", "SELECT played_at::date AS day, 1 AS amount FROM chess_games"),
    "chess_rapid": ("Chess rating (rapid)", "rating", "chess", "level",
                    "SELECT played_at::date AS day, my_rating AS amount FROM chess_games WHERE time_class = 'rapid' AND rated AND my_rating IS NOT NULL"),
    "chess_blitz": ("Chess rating (blitz)", "rating", "chess", "level",
                    "SELECT played_at::date AS day, my_rating AS amount FROM chess_games WHERE time_class = 'blitz' AND rated AND my_rating IS NOT NULL"),
    "chess_bullet": ("Chess rating (bullet)", "rating", "chess", "level",
                     "SELECT played_at::date AS day, my_rating AS amount FROM chess_games WHERE time_class = 'bullet' AND rated AND my_rating IS NOT NULL"),
    "chess_daily": ("Chess rating (daily)", "rating", "chess", "level",
                    "SELECT played_at::date AS day, my_rating AS amount FROM chess_games WHERE time_class = 'daily' AND rated AND my_rating IS NOT NULL"),
    "games_100": ("Games finished to 100%", "games", "videogames", "sum",
                  """SELECT completed_at::date AS day, 1 AS amount FROM vg_games WHERE completed_at IS NOT NULL AND NOT hidden
                     UNION ALL SELECT exo_completed_at::date, 1 FROM vg_other_games WHERE exo_completed_at IS NOT NULL AND NOT hidden"""),
    "games_100_total": ("Games at 100% (all-time)", "games", "videogames", "total",
                        """SELECT completed_at::date AS day, 1 AS amount FROM vg_games WHERE completed_at IS NOT NULL AND NOT hidden
                           UNION ALL SELECT exo_completed_at::date, 1 FROM vg_other_games WHERE exo_completed_at IS NOT NULL AND NOT hidden"""),
    "achievements": ("Achievements unlocked", "achievements", "videogames", "sum",
                     "SELECT unlocked_at::date AS day, 1 AS amount FROM vg_achievements WHERE achieved AND unlocked_at IS NOT NULL"),
    "hours_played": ("Hours played", "hours", "videogames", "sum", "SELECT day, minutes / 60.0 AS amount FROM vg_playtime"),
    "shooting_sessions": ("Shooting sessions", "sessions", "shooting", "sum", "SELECT shot_on AS day, 1 AS amount FROM shooting_sessions"),
    "rounds_fired": ("Rounds fired", "rounds", "shooting", "sum",
                     "SELECT shot_on AS day, rounds AS amount FROM shooting_sessions WHERE rounds IS NOT NULL"),
    "harvests": ("Harvests", "harvests", "gardening", "sum",
                 "SELECT happened_on AS day, 1 AS amount FROM garden_logs WHERE kind = 'Harvested'"),
    "trips": ("Trips taken", "trips", "travel", "sum",
              "SELECT start_date AS day, 1 AS amount FROM trips WHERE start_date IS NOT NULL AND status <> 'Cancelled'"),
    "journal_pages": ("Journal pages", "pages", None, "sum",
                      "SELECT COALESCE(entry_date, created_at::date) AS day, 1 AS amount FROM journal_pages"),
}


def catalogue() -> list[dict]:
    """The choices, for the goal page's picker."""
    return [{"key": k, "label": s[0], "unit": s[1], "hobby": s[2], "mode": s[3]} for k, s in SOURCES.items()]


def rows(conn, key: str, end: date) -> list[tuple[date, float]]:
    """Every (day, amount) up to `end`, oldest first. Days in the future (a trip not yet started) don't count."""
    sql = SOURCES[key][4]
    found = conn.execute(f"SELECT day, amount FROM ({sql}) s WHERE day IS NOT NULL AND day <= %s ORDER BY day", (end,)).fetchall()
    return [(r["day"], float(r["amount"] or 0)) for r in found]


def measure(conn, key: str, start: date, end: date) -> dict:
    """Where a source-counted goal is: {start, current, series: [(day, value)], last_day} over start..end.
    series has the running total (sum / total) or each new level, beginning with the value at the start."""
    mode = SOURCES[key][3]
    data = rows(conn, key, end)
    before = [a for d, a in data if d < start]
    inside = [(d, a) for d, a in data if d >= start]
    if mode == "level":
        first = before[-1] if before else (inside[0][1] if inside else None)
        series = ([(start, first)] if first is not None else []) + inside
        current = series[-1][1] if series else None
    else:
        first = sum(before) if mode == "total" else 0.0
        running, series = first, [(start, first)]
        for d, a in inside:
            running += a
            series.append((d, running))
        current = running
    return {"start": first, "current": current, "series": [(d, round(v, 2)) for d, v in series],
            "last_day": inside[-1][0] if inside else None}


def counted(conn, key: str, start: date, end: date) -> list[tuple[date, float]]:
    """The (day, amount) rows inside start..end - a habit goal's times."""
    return [(d, a) for d, a in rows(conn, key, end) if d >= start]
