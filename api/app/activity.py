"""What you've done: one feed from everything the app already records.

    stock       bought / added / used / removed      (stock_movements; not edits, imports or undos)
    kits        bought / started / finished          (models' dates)
    build log   an entry for a kit                   (model_log)
    time        a session on a kit                   (model_sessions, once stopped)
    journal     a page written                       (journal_pages, on the day it's about)
    board games a play                               (board_game_plays)
    volleyball  a game or training                   (volleyball_games)
    gear        bought                               (gear's purchase date)
    video games achievements unlocked (one entry per game per day), and games 100%'d (vg_*)
    chess       online games: one entry per time control per day ("Blitz chess: 12 games · 7-4-1");
                over the board: each game                    (chess_games)
    reading     pages read (one entry per book per day), started, finished / stopped   (reading_log, books)
    goals       reached, and each progress note                                     (goals, goal_updates)

Each item: {at, day, kind, ref, verb, title, detail, photo_url}; the photo (if any) is the
product's, the game's or the gear's. Newest first. Part of the core: Home shows the latest, and
the calendar shows what happened on each day (rows(conn, since=, until=)).
"""
from datetime import date

from fastapi import APIRouter, Query

from .db import db

router = APIRouter(prefix="/api", tags=["activity"])

# Days with no time of day: put them at midday so they sort sensibly among timed things.
# A thing written down the same day keeps its real time.
NOON = "({}::date + time '12:00')::timestamptz"


def _on_day(day: str, created: str) -> str:
    return f"CASE WHEN {day} = {created}::date THEN {created} ELSE {NOON.format(day)} END"


ACTIVITY = f"""
WITH feed AS (
    SELECT m.created_at AS at, 'supply' AS kind, m.supply_id AS ref,
           CASE WHEN m.reason = 'used' THEN 'Used'
                WHEN m.reason = 'deleted' THEN 'Removed'
                WHEN m.reason IN ('bought', 'bought (wishlist)') THEN 'Bought'
                ELSE 'Added' END AS verb,
           m.item_name AS title,
           CASE WHEN abs(m.change) > 1 THEN abs(m.change) || ' of them' END AS detail,
           s.brand_id, s.product_code, NULL AS photo_url
    FROM stock_movements m LEFT JOIN supplies s USING (supply_id)
    WHERE m.reason IN ('used', 'deleted', 'bought', 'bought (wishlist)', 'added')
  UNION ALL
    SELECT {NOON.format('purchase_date')}, 'model', model_id, 'Bought', name, purchased_from, brand_id, product_code, NULL
    FROM models WHERE purchase_date IS NOT NULL AND status <> 'Wanted'
  UNION ALL
    SELECT {NOON.format('started_on')}, 'model', model_id, 'Started', name, NULL, brand_id, product_code, NULL
    FROM models WHERE started_on IS NOT NULL
  UNION ALL
    SELECT {NOON.format('finished_on')}, 'model', model_id, 'Finished', name, NULL, brand_id, product_code, NULL
    FROM models WHERE finished_on IS NOT NULL
  UNION ALL
    SELECT l.created_at, 'model', l.model_id, 'Logged', m.name, left(l.text, 120), m.brand_id, m.product_code, NULL
    FROM model_log l JOIN models m USING (model_id)
  UNION ALL
    SELECT x.ended_at, 'model', x.model_id, 'Worked on', m.name,
           round(extract(epoch FROM (x.ended_at - x.started_at)) / 60)::int || ' min'
           || COALESCE(' · ' || x.note, ''), m.brand_id, m.product_code, NULL
    FROM model_sessions x JOIN models m USING (model_id) WHERE x.ended_at IS NOT NULL
  UNION ALL
    SELECT {_on_day('entry_date', 'created_at')}, 'page', page_id,
           CASE WHEN kind = 'whiteboard' THEN 'Drew' ELSE 'Wrote' END,
           COALESCE(NULLIF(title, ''), 'Untitled page'), NULL, NULL, NULL, NULL
    FROM journal_pages
  UNION ALL
    SELECT {_on_day('p.played_on', 'p.created_at')}, 'game', p.game_id, 'Played', g.name,
           concat_ws(' · ', 'Won by ' || NULLIF(p.winner, ''), NULLIF(p.players, ''), p.minutes || ' min'),
           NULL, NULL,
           CASE WHEN g.photo IS NOT NULL THEN '/api/board-games/' || g.game_id || '/photo?v='
                || (extract(epoch FROM g.photo_updated) * 1000)::bigint END
    FROM board_game_plays p JOIN board_games g USING (game_id)
  UNION ALL
    SELECT {_on_day('v.played_on', 'v.created_at')}, 'volleyball', v.game_id,
           CASE WHEN v.bye IS NOT NULL THEN 'Had' WHEN v.kind = 'Training' THEN 'Trained' ELSE 'Played' END,
           CASE WHEN v.bye IS NOT NULL THEN 'Volleyball bye'
                WHEN v.kind = 'Training' THEN 'Volleyball training'
                WHEN NULLIF(v.opponent, '') IS NOT NULL THEN 'Volleyball vs ' || v.opponent
                ELSE 'Volleyball ' || lower(v.kind) END,
           concat_ws(' · ',
               CASE v.bye WHEN 'win' THEN 'Counted as a win' WHEN 'no result' THEN 'No result' END,
               CASE WHEN v.sets_won > v.sets_lost THEN 'Won ' WHEN v.sets_won < v.sets_lost THEN 'Lost '
                    WHEN v.sets_won IS NOT NULL THEN 'Drew ' END || v.sets_won || '–' || v.sets_lost,
               NULLIF(v.venue, '')),
           NULL, NULL, NULL
    FROM volleyball_games v
  UNION ALL
    SELECT {NOON.format('purchase_date')}, 'gear', gear_id, 'Bought', name, NULLIF(kind, ''), NULL, NULL,
           CASE WHEN photo IS NOT NULL THEN '/api/gear/' || gear_id || '/photo?v='
                || (extract(epoch FROM photo_updated) * 1000)::bigint END
    FROM gear WHERE purchase_date IS NOT NULL
  UNION ALL
    SELECT max(a.unlocked_at), 'videogame', a.app_id, 'Unlocked', g.name,
           CASE WHEN count(*) = 1 THEN min(a.name) ELSE count(*) || ' achievements' END, NULL, NULL,
           COALESCE(NULLIF(g.header_url, ''), 'https://cdn.cloudflare.steamstatic.com/steam/apps/' || a.app_id || '/header.jpg')
    FROM vg_achievements a JOIN vg_games g USING (app_id)
    WHERE a.achieved AND a.unlocked_at IS NOT NULL AND NOT g.hidden
    GROUP BY a.app_id, g.name, g.header_url, (a.unlocked_at AT TIME ZONE current_setting('TimeZone'))::date
  UNION ALL
    SELECT completed_at, 'videogame', app_id, 'Perfected', name, '100%% · ' || achievements_total || ' achievements',
           NULL, NULL, COALESCE(NULLIF(header_url, ''), 'https://cdn.cloudflare.steamstatic.com/steam/apps/' || app_id || '/header.jpg')
    FROM vg_games WHERE completed_at IS NOT NULL AND NOT hidden
  UNION ALL
    SELECT max(c.played_at), 'chess', (array_agg(c.game_id ORDER BY c.played_at DESC))[1], 'Played',
           initcap(c.time_class) || ' chess',
           count(*) || CASE WHEN count(*) = 1 THEN ' game · ' ELSE ' games · ' END
               || count(*) FILTER (WHERE c.result = 'win') || '–' || count(*) FILTER (WHERE c.result = 'loss')
               || '–' || count(*) FILTER (WHERE c.result = 'draw'),
           NULL, NULL, NULL
    FROM chess_games c WHERE c.source = 'chesscom'
    GROUP BY c.time_class, (c.played_at AT TIME ZONE current_setting('TimeZone'))::date
  UNION ALL
    SELECT c.played_at, 'chess', c.game_id, 'Played', 'Chess vs ' || c.opp_name,
           concat_ws(' · ', CASE c.result WHEN 'win' THEN 'Won' WHEN 'loss' THEN 'Lost' ELSE 'Drew' END,
                     NULLIF(c.event, '')), NULL, NULL, NULL
    FROM chess_games c WHERE c.source = 'otb'
  UNION ALL
    SELECT {_on_day('l.logged_on', 'max(l.created_at)')}, 'book', l.book_id, 'Read', b.title,
           sum(l.pages) || CASE WHEN sum(l.pages) = 1 THEN ' page' ELSE ' pages' END
               || COALESCE(' · ' || sum(l.minutes) || ' min', ''), NULL, NULL, CASE WHEN b.cover_id IS NOT NULL THEN 'https://covers.openlibrary.org/b/id/' || b.cover_id || '-M.jpg' END
    FROM reading_log l JOIN books b USING (book_id) WHERE l.pages > 0
    GROUP BY l.book_id, l.logged_on, b.title, b.cover_id
  UNION ALL
    SELECT {NOON.format('b.started_on')}, 'book', b.book_id, 'Started reading', b.title, b.author, NULL, NULL, CASE WHEN b.cover_id IS NOT NULL THEN 'https://covers.openlibrary.org/b/id/' || b.cover_id || '-M.jpg' END
    FROM books b WHERE b.started_on IS NOT NULL
  UNION ALL
    SELECT {NOON.format('b.finished_on')}, 'book', b.book_id,
           CASE WHEN b.status = 'dnf' THEN 'Stopped reading' ELSE 'Finished' END, b.title,
           concat_ws(' · ', b.author, repeat('★', floor(b.rating)::int) || CASE WHEN b.rating > floor(b.rating) THEN '½' ELSE '' END), NULL, NULL, CASE WHEN b.cover_id IS NOT NULL THEN 'https://covers.openlibrary.org/b/id/' || b.cover_id || '-M.jpg' END
    FROM books b WHERE b.finished_on IS NOT NULL AND b.status IN ('finished', 'dnf')
  UNION ALL
    SELECT {NOON.format('g.done_on')}, 'goal', g.goal_id, 'Reached', g.title, NULL, NULL, NULL, NULL
    FROM goals g WHERE g.done_on IS NOT NULL AND g.status = 'done'
  UNION ALL
    SELECT {_on_day('u.day', 'u.created_at')}, 'goal', u.goal_id, 'Progress on', g.title,
           concat_ws(' · ', CASE WHEN u.value IS NOT NULL THEN trim_scale(u.value) || COALESCE(' ' || g.unit, '') END, left(u.text, 120)),
           NULL, NULL, NULL
    FROM goal_updates u JOIN goals g USING (goal_id)
)
SELECT f.at, (f.at AT TIME ZONE current_setting('TimeZone'))::date AS day,
       f.kind, f.ref, f.verb, f.title, NULLIF(f.detail, '') AS detail,
       COALESCE(f.photo_url, '/api/product-images/' || p.product_info_id || '?v='
                || (extract(epoch FROM p.fetched_at) * 1000)::bigint) AS photo_url
FROM feed f
LEFT JOIN product_info p ON p.brand_id = f.brand_id AND p.product_code = f.product_code AND p.image IS NOT NULL
WHERE f.at IS NOT NULL
  AND (%(since)s::date IS NULL OR f.at >= %(since)s::date)
  AND (%(until)s::date IS NULL OR f.at < %(until)s::date + 1)
ORDER BY f.at DESC
LIMIT %(limit)s
"""


def rows(conn, limit: int = 20, since: date | None = None, until: date | None = None) -> list[dict]:
    """The feed, newest first, optionally only from `since` to `until` (whole days)."""
    return conn.execute(ACTIVITY, {"limit": limit, "since": since, "until": until}).fetchall()


@router.get("/activity")
def activity(limit: int = Query(20, ge=1, le=500), since: date | None = None, until: date | None = None):
    """What you've done lately, newest first (since / until = only between those days)."""
    with db() as conn:
        return rows(conn, limit, since, until)
