"""What you've spent, and CSV exports of everything (for Excel or keeping a copy)."""
import csv
import io
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

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
    "history": """
        SELECT created_at AS "When", item_name AS "Item", change AS "Change", qty_after AS "Qty after",
               reason AS "Reason", unit_price AS "Price"
        FROM stock_movements ORDER BY created_at, movement_id""",
}


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
    writer.writerows([row[c] for c in columns] for row in rows)
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="shelf-of-shame-{kind}-{date.today()}.csv"'})
