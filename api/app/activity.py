"""Recent activity: one feed of what you've done, from everything the app already records.

    stock      bought / added / used / removed      (stock_movements; not edits, imports or undos)
    kits       bought / started / finished          (models' dates)
    build log  an entry for a kit                   (model_log)
    time       a session on a kit                   (model_sessions, once stopped)
    journal    a page written                       (journal_pages)

Each item: {at, kind, ref, verb, title, detail, product_info_id, photo_updated}; the photo (if any)
is the product's. Newest first. Part of the core, so the calendar can use it too.
"""
from datetime import date

from fastapi import APIRouter, Query

from .db import db

router = APIRouter(prefix="/api", tags=["activity"])

# Kit dates have no time of day: put them at midday so they sort sensibly among timed things.
NOON = "(%s::date + time '12:00')::timestamptz"

ACTIVITY = f"""
WITH feed AS (
    SELECT m.created_at AS at, 'supply' AS kind, m.supply_id AS ref,
           CASE WHEN m.reason = 'used' THEN 'Used'
                WHEN m.reason = 'deleted' THEN 'Removed'
                WHEN m.reason IN ('bought', 'bought (wishlist)') THEN 'Bought'
                ELSE 'Added' END AS verb,
           m.item_name AS title,
           CASE WHEN abs(m.change) > 1 THEN abs(m.change) || ' of them' END AS detail,
           s.brand_id, s.product_code
    FROM stock_movements m LEFT JOIN supplies s USING (supply_id)
    WHERE m.reason IN ('used', 'deleted', 'bought', 'bought (wishlist)', 'added')
  UNION ALL
    SELECT {NOON.replace('%s', 'purchase_date')}, 'model', model_id, 'Bought', name, purchased_from, brand_id, product_code
    FROM models WHERE purchase_date IS NOT NULL AND status <> 'Wanted'
  UNION ALL
    SELECT {NOON.replace('%s', 'started_on')}, 'model', model_id, 'Started', name, NULL, brand_id, product_code
    FROM models WHERE started_on IS NOT NULL
  UNION ALL
    SELECT {NOON.replace('%s', 'finished_on')}, 'model', model_id, 'Finished', name, NULL, brand_id, product_code
    FROM models WHERE finished_on IS NOT NULL
  UNION ALL
    SELECT l.created_at, 'model', l.model_id, 'Logged', m.name, left(l.text, 120), m.brand_id, m.product_code
    FROM model_log l JOIN models m USING (model_id)
  UNION ALL
    SELECT x.ended_at, 'model', x.model_id, 'Worked on', m.name,
           round(extract(epoch FROM (x.ended_at - x.started_at)) / 60)::int || ' min'
           || COALESCE(' · ' || x.note, ''), m.brand_id, m.product_code
    FROM model_sessions x JOIN models m USING (model_id) WHERE x.ended_at IS NOT NULL
  UNION ALL
    SELECT created_at, 'page', page_id, 'Wrote', COALESCE(NULLIF(title, ''), 'Untitled page'), NULL, NULL, NULL
    FROM journal_pages
)
SELECT f.at, f.kind, f.ref, f.verb, f.title, f.detail,
       p.product_info_id, CASE WHEN p.image IS NOT NULL THEN p.fetched_at END AS photo_updated
FROM feed f
LEFT JOIN product_info p ON p.brand_id = f.brand_id AND p.product_code = f.product_code AND p.image IS NOT NULL
WHERE f.at IS NOT NULL AND (%(since)s::date IS NULL OR f.at >= %(since)s::date)
ORDER BY f.at DESC
LIMIT %(limit)s
"""


@router.get("/activity")
def activity(limit: int = Query(20, ge=1, le=500), since: date | None = None):
    """What you've done lately, newest first (since = only from that day on)."""
    with db() as conn:
        return conn.execute(ACTIVITY, {"limit": limit, "since": since}).fetchall()
