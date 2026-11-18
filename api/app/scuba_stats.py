"""Scuba diving stats (A12_scuba.sql).

    GET /scuba/stats?year=    totals, records, dives by year and by month, depth bands, SAC trend, top sites, tags, temperatures

`year` narrows the totals, records, depth bands, SAC trend, top sites, tags and temperatures to that year; the by-year
and by-month charts always show everything. The totals count the dives logged before the app (settings) only without a year.
"""
from fastapi import APIRouter, Query

from .db import db
from .scuba_dives import BRIEF_SELECT, SAC_SQL

router = APIRouter(prefix="/api", tags=["scuba"])

BANDS = [("0-10", 0, 10), ("10-18", 10, 18), ("18-30", 18, 30), ("30-40", 30, 40), ("40+", 40, None)]


@router.get("/scuba/stats")
def stats(year: int | None = Query(None, ge=1900, le=2200)):
    where = "WHERE extract(year FROM d.dived_on) = %(year)s" if year is not None else "WHERE true"
    args = {"year": year}
    with db() as conn:
        s = conn.execute("SELECT dives_before, minutes_before FROM scuba_settings WHERE id = 1").fetchone()
        t = conn.execute(f"""SELECT count(*)::int AS logged, COALESCE(sum(d.minutes), 0)::int AS minutes,
                                    round(avg(d.max_depth), 1)::float8 AS avg_depth, round(avg(d.minutes), 1)::float8 AS avg_minutes,
                                    count(DISTINCT d.site_id)::int AS sites, count(DISTINCT d.trip_id)::int AS trips,
                                    count(DISTINCT d.dived_on)::int AS dive_days
                             FROM scuba_dives d {where}""", args).fetchone()
        before = (0, 0) if year is not None else (s["dives_before"], s["minutes_before"])
        species = conn.execute(f"""SELECT count(DISTINCT lower(g.species))::int AS n FROM scuba_sightings g
                                   JOIN scuba_dives d USING (dive_id) {where}""", args).fetchone()["n"]
        totals = {"dives": before[0] + t["logged"], "dives_logged": t["logged"], "minutes": before[1] + t["minutes"],
                  "hours": round((before[1] + t["minutes"]) / 60, 1), "avg_depth": t["avg_depth"], "avg_minutes": t["avg_minutes"],
                  "sites": t["sites"], "trips": t["trips"], "dive_days": t["dive_days"], "species": species}

        def record(column: str, order: str):
            return conn.execute(f"{BRIEF_SELECT} {where} AND d.{column} IS NOT NULL "
                                f"ORDER BY d.{column} {order}, d.dived_on, d.dive_id LIMIT 1", args).fetchone()
        records = {"deepest": record("max_depth", "DESC"), "longest": record("minutes", "DESC"),
                   "coldest": record("water_temp", "ASC"), "warmest": record("water_temp", "DESC"),
                   "best_vis": record("visibility_m", "DESC")}

        by_year = conn.execute("""SELECT extract(year FROM dived_on)::int AS year, count(*)::int AS dives,
                                         COALESCE(sum(minutes), 0)::int AS minutes
                                  FROM scuba_dives GROUP BY 1 ORDER BY 1""").fetchall()
        by_month = conn.execute("""
            SELECT to_char(m, 'YYYY-MM') AS month, count(d.dive_id)::int AS dives, COALESCE(sum(d.minutes), 0)::int AS minutes
            FROM generate_series(date_trunc('month', current_date) - interval '23 months', date_trunc('month', current_date),
                                 interval '1 month') m
            LEFT JOIN scuba_dives d ON date_trunc('month', d.dived_on) = m GROUP BY m ORDER BY m""").fetchall()
        depth_bands = []
        for name, low, high in BANDS:
            n = conn.execute(f"""SELECT count(*)::int AS n FROM scuba_dives d {where} AND d.max_depth >= %(low)s
                                 AND (%(high)s::numeric IS NULL OR d.max_depth < %(high)s)""",
                             {**args, "low": low, "high": high}).fetchone()["n"]
            depth_bands.append({"band": name, "dives": n})
        sac_trend = conn.execute(f"""SELECT dive_id, dived_on, sac FROM (
                                         SELECT d.dive_id, d.dived_on, d.time_in, {SAC_SQL} AS sac FROM scuba_dives d {where}) x
                                     WHERE sac IS NOT NULL ORDER BY dived_on, time_in NULLS FIRST, dive_id""", args).fetchall()
        top_sites = conn.execute(f"""SELECT s.site_id, s.name, count(*)::int AS dives FROM scuba_dives d
                                     JOIN scuba_sites s USING (site_id) {where}
                                     GROUP BY s.site_id, s.name ORDER BY count(*) DESC, lower(s.name) LIMIT 10""", args).fetchall()
        tags = conn.execute(f"""SELECT tag, count(*)::int AS dives FROM scuba_dives d, unnest(d.tags) tag {where}
                                GROUP BY tag ORDER BY count(*) DESC, tag""", args).fetchall()
        temps = conn.execute(f"""SELECT d.dived_on, d.water_temp FROM scuba_dives d {where} AND d.water_temp IS NOT NULL
                                 ORDER BY d.dived_on, d.time_in NULLS FIRST, d.dive_id""", args).fetchall()
        return {"year": year, "totals": totals, "records": records, "by_year": by_year, "by_month": by_month,
                "depth_bands": depth_bands, "sac_trend": sac_trend, "top_sites": top_sites, "tags": tags, "temps": temps}
