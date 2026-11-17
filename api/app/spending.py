"""What you've spent, and CSV exports of everything (for Excel or keeping a copy)."""
import csv
import io
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from . import othergames, vgplaytime
from .db import db

router = APIRouter(prefix="/api", tags=["spending"])

# What you paid, from the stock history (each change remembers the price at that moment - see
# db/init/12_spend.sql). Purchases count; Undo of a purchase takes it back off. Using things up,
# removing them or fixing a miscount ('edited', 'manual') doesn't change what you spent.
PURCHASES = ["added", "bought", "bought (wishlist)", "starting stock", "import"]
SPEND = """
WITH spend AS (
    SELECT created_at, item_name, reason, unit_price,
           CASE WHEN reason = ANY(%(purchases)s) AND change > 0 THEN change
                WHEN reason = 'undo' AND change < 0 THEN change   -- undoing a +1
                ELSE 0 END AS qty
    FROM stock_movements
)
"""


@router.get("/spending")
def spending():
    """Supplies: lifetime spend, this year, this month, how much was your starting stock, and
    the latest purchases. Kits: what the kits in your stash cost (models.price_paid)."""
    params = {"purchases": PURCHASES}
    with db() as conn:
        totals = conn.execute(SPEND + """
            SELECT COALESCE(sum(qty * unit_price), 0) AS all_time,
                   COALESCE(sum(qty * unit_price) FILTER (WHERE created_at >= date_trunc('year', now())), 0) AS this_year,
                   COALESCE(sum(qty * unit_price) FILTER (WHERE created_at >= date_trunc('month', now())), 0) AS this_month,
                   COALESCE(sum(qty * unit_price) FILTER (WHERE reason IN ('starting stock', 'import')), 0) AS starting_stock,
                   count(*) FILTER (WHERE qty > 0 AND unit_price IS NULL) AS unpriced
            FROM spend WHERE qty <> 0""", params).fetchone()
        by_year = conn.execute(SPEND + """
            SELECT extract(year FROM created_at)::int AS year, sum(qty * unit_price) AS spent
            FROM spend WHERE qty <> 0 AND unit_price IS NOT NULL
            GROUP BY 1 ORDER BY 1 DESC""", params).fetchall()
        recent = conn.execute(SPEND + """
            SELECT created_at, item_name, qty, unit_price, qty * unit_price AS spent
            FROM spend WHERE qty <> 0 AND reason NOT IN ('starting stock', 'import')
            ORDER BY created_at DESC LIMIT 10""", params).fetchall()
        kits = conn.execute("SELECT COALESCE(sum(price_paid), 0) AS kits_spent, count(price_paid) AS kits_priced "
                            "FROM models WHERE status <> 'Wanted'").fetchone()
        return {**totals, **kits, "by_year": by_year, "recent": recent}


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------
EXPORTS = {
    "inventory": """
        SELECT v.item_ref AS "Ref", s.name AS "Name", v.brand AS "Brand", s.product_code AS "Code",
               v.category AS "Category", s.paint_type AS "Paint type", s.finish AS "Finish",
               s.size AS "Size", s.qty_on_hand AS "Qty", s.condition AS "Condition",
               v.stock_status AS "Status", s.unit_price AS "Price", v.total_value AS "Value",
               s.purchase_date AS "Last purchased", s.purchased_from AS "Last bought from",
               v.location AS "Location", s.notes AS "Notes"
        FROM supplies s JOIN v_supplies v USING (supply_id) ORDER BY s.supply_id""",
    "wishlist": """
        SELECT w.name AS "Name", b.name AS "Brand", w.product_code AS "Code", c.name AS "Category",
               w.size AS "Size", w.qty_wanted AS "Qty", w.est_price AS "Expected price",
               w.priority AS "Priority", w.got_it AS "Ticked", w.notes AS "Notes"
        FROM wishlist w JOIN categories c USING (category_id) LEFT JOIN brands b USING (brand_id)
        ORDER BY w.got_it, w.created_at""",
    "models": """
        SELECT m.name AS "Model", m.hobby AS "Hobby", b.name AS "Brand", m.product_code AS "Kit code",
               m.scale AS "Scale", m.grade AS "Grade", m.faction AS "Army", m.status AS "Status",
               m.stage AS "Build step", m.figures AS "Minis", m.figures_done AS "Minis done", m.price_paid AS "Price paid", m.purchase_date AS "Bought",
               m.purchased_from AS "Bought from", m.started_on AS "Started", m.finished_on AS "Finished",
               round(COALESCE((SELECT sum(extract(epoch FROM (COALESCE(ended_at, now()) - started_at)))
                               FROM model_sessions x WHERE x.model_id = m.model_id), 0) / 3600.0, 1) AS "Hours",
               m.notes AS "Notes"
        FROM models m LEFT JOIN brands b USING (brand_id) ORDER BY m.created_at""",
    "model-paints": """
        SELECT m.name AS "Model", mp.paint_name AS "Paint", b.name AS "Brand", mp.product_code AS "Code",
               mp.purpose AS "What it's for", x.name AS "Mix"
        FROM model_paints mp JOIN models m USING (model_id) LEFT JOIN brands b ON b.brand_id = mp.brand_id
        LEFT JOIN mixes x ON x.mix_id = mp.mix_id
        ORDER BY m.created_at, mp.sort_order, mp.model_paint_id""",
    "builds": """
        SELECT m.name AS "Model", m.hobby AS "Hobby", x.started_at AS "Started", x.ended_at AS "Ended",
               round(extract(epoch FROM (COALESCE(x.ended_at, now()) - x.started_at)) / 60) AS "Minutes",
               x.stage AS "Last step done", x.note AS "Note"
        FROM model_sessions x JOIN models m USING (model_id) ORDER BY x.started_at, x.session_id""",
    "paint-recipes": """
        SELECT r.name AS "Recipe", m.name AS "Model", r.unit AS "Unit", st.sort_order + 1 AS "Step",
               st.label AS "Kind of step", st.paint_text AS "Paint", b.name AS "Brand", st.product_code AS "Code",
               st.note AS "Note"
        FROM paint_recipe_steps st JOIN paint_recipes r USING (recipe_id) LEFT JOIN models m USING (model_id)
        LEFT JOIN brands b ON b.brand_id = st.brand_id ORDER BY r.created_at, r.recipe_id, st.sort_order""",
    "history": """
        SELECT created_at AS "When", item_name AS "Item", change AS "Change", qty_after AS "Qty after",
               reason AS "Reason", unit_price AS "Price"
        FROM stock_movements ORDER BY created_at, movement_id""",
    "board-games": """
        SELECT g.name AS "Game", g.status AS "Status", g.publisher AS "Publisher", g.year AS "Year",
               g.min_players AS "Fewest players", g.max_players AS "Most players", g.play_minutes AS "Minutes",
               g.rating AS "Rating", g.price_paid AS "Price paid", g.purchase_date AS "Bought",
               (SELECT count(*) FROM board_game_plays p WHERE p.game_id = g.game_id) AS "Plays", g.notes AS "Notes"
        FROM board_games g ORDER BY lower(g.name)""",
    "plays": """
        SELECT p.played_on AS "Day", g.name AS "Game", p.players AS "Players", p.winner AS "Winner",
               p.minutes AS "Minutes", p.notes AS "Notes"
        FROM board_game_plays p JOIN board_games g USING (game_id) ORDER BY p.played_on, p.play_id""",
    "volleyball": """
        SELECT v.played_on AS "Day", v.kind AS "Kind", t.name AS "Team", v.opponent AS "Against",
               v.sets_won AS "Sets won", v.sets_lost AS "Sets lost", v.venue AS "Where", v.notes AS "Notes"
        FROM volleyball_games v LEFT JOIN volleyball_teams t USING (team_id) ORDER BY v.played_on, v.game_id""",
    "gear": """
        SELECT name AS "Gear", kind AS "Kind", brand AS "Brand", size AS "Size", condition AS "Condition",
               purchase_date AS "Bought", price_paid AS "Price paid", notes AS "Notes"
        FROM gear ORDER BY lower(name)""",
    # Video games: Steam's and the other platforms' (Epic, Ubisoft) in one list, as the Games page counts them.
    "video-games": """
        SELECT "Game", "Platform", initcap(status) AS "Status", "Hours played", "Last played", "Achievements", "Out of",
               "Percent", "Completed", "Hours to beat", "Price paid", "Hidden" FROM (
            SELECT g.name AS "Game", 'Steam' AS "Platform", """ + othergames.status_sql(
                "g.completed_at IS NOT NULL", "g.playtime_minutes", "g.last_played", "g.play_status") + """ AS status,
                   round(g.playtime_minutes / 60.0, 1) AS "Hours played", g.last_played AS "Last played",
                   g.achievements_done AS "Achievements", g.achievements_total AS "Out of",
                   CASE WHEN g.achievements_total > 0 THEN round(100.0 * g.achievements_done / g.achievements_total, 1) END
                       AS "Percent", g.completed_at AS "Completed", g.beat_hours AS "Hours to beat",
                   g.price_paid AS "Price paid", g.hidden AS "Hidden"
            FROM vg_games g
            UNION ALL
            SELECT o.name, initcap(o.platform), o.status, round(o.playtime_minutes / 60.0, 1), o.last_played,
                   o.achievements_done, o.achievements_total, o.percent, o.completed_at, o.beat_hours, o.price_paid, o.hidden
            FROM (""" + othergames.SELECT + """) o
        ) x ORDER BY lower("Game"), "Platform" """,
    "video-game-achievements": """
        SELECT * FROM (
            SELECT g.name AS "Game", 'Steam' AS "Platform", a.name AS "Achievement", a.description AS "Description",
                   a.dlc AS "DLC", a.achieved AS "Unlocked", a.unlocked_at AS "When", a.global_percent AS "% of players"
            FROM vg_achievements a JOIN vg_games g USING (app_id)
            UNION ALL
            SELECT o.name, initcap(o.platform), a.name, a.description, NULL, a.achieved, a.unlocked_at, a.global_percent
            FROM vg_other_achievements a JOIN vg_other_games o USING (game_id)
        ) x ORDER BY lower("Game"), "Platform", "Unlocked" DESC, "When", "Achievement" """,
    # What you played each day (the change in a game's total: vgplaytime.PLAYED), since the app started keeping it.
    "video-game-playtime": """
        SELECT p.day AS "Day", COALESCE(g.name, o.name, p.app_id) AS "Game", initcap(p.platform) AS "Platform",
               p.played AS "Minutes"
        FROM (""" + vgplaytime.PLAYED + """) p
        LEFT JOIN vg_games g ON p.platform = 'steam' AND g.app_id::text = p.app_id
        LEFT JOIN vg_other_games o ON p.platform <> 'steam' AND p.platform || '-' || o.game_id = p.app_id
        ORDER BY p.day, 2""",
    # Golf: each round (Stableford points and the differential are worked out by the app: see the round's scorecard)
    "golf-rounds": """
        SELECT r.played_on AS "Date", c.name AS "Course", t.name AS "Tees",
               CASE r.holes WHEN '18' THEN '18 holes' WHEN 'front' THEN 'Front 9' ELSE 'Back 9' END AS "Holes",
               r.format AS "Format", r.competition AS "Competition", r.handicap AS "Handicap",
               r.daily_handicap AS "Daily handicap",
               CASE WHEN bool_and(NOT h.picked_up) THEN sum(h.strokes) END AS "Strokes",
               sum(h.putts) AS "Putts", count(*) FILTER (WHERE h.fairway = 'hit') AS "Fairways hit",
               count(*) FILTER (WHERE h.strokes - h.putts <= gh.par - 2) AS "Greens in regulation",
               sum(h.penalties) AS "Penalties", count(h.hole_no) AS "Holes scored",
               CASE WHEN r.counts THEN 'Yes' ELSE 'No' END AS "Counts", r.partners AS "Partners", r.notes AS "Notes"
        FROM golf_rounds r JOIN golf_courses c USING (course_id) LEFT JOIN golf_tees t ON t.tee_id = r.tee_id
        LEFT JOIN golf_round_holes h ON h.round_id = r.round_id
        LEFT JOIN golf_holes gh ON gh.course_id = r.course_id AND gh.hole_no = h.hole_no
        WHERE r.status = 'done'
        GROUP BY r.round_id, c.name, t.name ORDER BY r.played_on, r.round_id""",
    "golf-holes": """
        SELECT r.played_on AS "Date", c.name AS "Course", h.hole_no AS "Hole", gh.par AS "Par", gh.stroke_index AS "Index",
               CASE WHEN h.picked_up THEN 'Picked up' ELSE h.strokes::text END AS "Strokes", h.putts AS "Putts",
               h.fairway AS "Fairway", h.penalties AS "Penalties", h.sand AS "Bunker shots", h.first_putt_m AS "First putt (m)"
        FROM golf_round_holes h JOIN golf_rounds r USING (round_id) JOIN golf_courses c USING (course_id)
        LEFT JOIN golf_holes gh ON gh.course_id = r.course_id AND gh.hole_no = h.hole_no
        ORDER BY r.played_on, r.round_id, h.hole_no""",
    # Language learning: the deck (each card's memory as FSRS keeps it) and the study log (reviews' time not included)
    "language-cards": """
        SELECT l.name AS "Language", c.kind AS "Kind", c.front AS "Front", c.back AS "Back", c.example AS "Example",
               c.example_meaning AS "Example means", array_to_string(c.tags, ' ') AS "Tags", c.notes AS "Notes",
               c.state AS "State", c.due::date AS "Due", round(c.stability::numeric, 1) AS "Stability (days)",
               round(c.difficulty::numeric, 1) AS "Difficulty", c.reps AS "Reviews", c.lapses AS "Lapses",
               c.learned_on AS "Learned", c.suspended AS "Suspended", c.created_at::date AS "Added"
        FROM lang_cards c JOIN lang_languages l USING (language_id) ORDER BY l.name, c.created_at, c.card_id""",
    "language-study": """
        SELECT s.studied_on AS "Date", l.name AS "Language", s.activity AS "Activity", s.minutes AS "Minutes",
               r.title AS "Resource", s.with_whom AS "With", s.notes AS "Notes"
        FROM lang_study s JOIN lang_languages l USING (language_id) LEFT JOIN lang_resources r USING (resource_id)
        ORDER BY s.studied_on, s.study_id""",
}


def cell(value):
    """One CSV cell. Text starting with = + - @ (or a tab / return) would run as a formula when
    Excel opens the file, so it gets a ' in front, which Excel shows as plain text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@router.get("/export/{kind}.csv")
def export_csv(kind: str):
    """Download a table as CSV. Excel opens it directly (UTF-8 with a BOM so ° and × survive)."""
    if kind not in EXPORTS:
        raise HTTPException(404, f"Nothing called '{kind}' to export. Try: {', '.join(EXPORTS)}.")
    with db() as conn:
        cur = conn.execute(EXPORTS[kind])
        rows = cur.fetchall()
        columns = [c.name for c in cur.description]
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out)
    writer.writerow(columns)
    writer.writerows([cell(row[c]) for c in columns] for row in rows)
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="off-the-clock-{kind}-{date.today()}.csv"'})
