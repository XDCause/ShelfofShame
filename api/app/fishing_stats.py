"""Fishing stats: what works for YOU (A13_fishing.sql) - your own catches by month, species, time of day, moon phase, tide
stage and lure, the spots ranked by fish per hour. The moon and tide come from the conditions saved with each trip.

    GET /fishing/stats?year=&species_id=    year narrows everything but by_month (always the last 24 months); species_id picks
                                            the species of length_trend (empty without one)

A catch's time is its own caught_at, or the start of its trip. Kept = fate 'kept'; released counts released and tagged.
A "blank" is a trip with no fish. Fish per hour counts only finished trips.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from .db import db

router = APIRouter(prefix="/api", tags=["fishing"])

MOON_PHASES = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous", "Full moon", "Waning gibbous", "Last quarter",
               "Waning crescent"]
LOCAL = ZoneInfo("Australia/Brisbane")
NEAR_EXTREME = timedelta(minutes=45)       # this close to a high or low tide it is "high" or "low" water
MAX_GAP = timedelta(hours=7)               # further than this from any known tide, the stage is unknown


def _local(value) -> datetime | None:
    """A time as a naive Brisbane datetime: from a datetime or an ISO string (without a zone it already is local)."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.astimezone(LOCAL).replace(tzinfo=None) if value.tzinfo else value


def tide_stage(tides, at: datetime) -> str | None:
    """'rising', 'high', 'falling' or 'low' for a time (naive, Brisbane), from the day's high and low waters
    [{time, kind 'high'|'low'}]: within 45 minutes of one it is that; otherwise it's heading to the next one. None when the
    tides are missing or the nearest is more than 7 hours away."""
    points = []
    for t in tides if isinstance(tides, list) else []:
        if not isinstance(t, dict):
            continue
        when, kind = _local(t.get("time")), str(t.get("kind") or t.get("type") or "").lower()
        if when and kind in ("high", "low"):
            points.append((when, kind))
    if not points or at is None:
        return None
    points.sort()
    nearest = min(points, key=lambda p: abs(p[0] - at))
    if abs(nearest[0] - at) > MAX_GAP:
        return None
    if abs(nearest[0] - at) <= NEAR_EXTREME:
        return nearest[1]
    later = [p for p in points if p[0] > at]
    if later:                                   # heading for the next one
        return "rising" if later[0][1] == "high" else "falling"
    return "falling" if points[-1][1] == "high" else "rising"     # after the last one: leaving it


@router.get("/fishing/stats")
def stats(year: int | None = Query(None, ge=1900, le=2200), species_id: int | None = None):
    where = "WHERE extract(year FROM t.started_at::timestamp) = %(year)s" if year is not None else "WHERE true"
    args = {"year": year, "species": species_id}
    fish = "COALESCE(c.species_id::text, lower(btrim(c.species)))"
    name = "COALESCE(sp.name, c.species)"
    when = "COALESCE(c.caught_at, t.started_at)"
    catches_from = ("FROM fishing_catches c JOIN fishing_trips t USING (trip_id) LEFT JOIN fishing_species sp USING (species_id) "
                    + where)
    with db() as conn:
        t = conn.execute(f"""SELECT count(*)::int AS trips,
                                    COALESCE(sum(extract(epoch FROM (t.ended_at - t.started_at)) / 3600), 0)::float8 AS hours,
                                    count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM fishing_catches c WHERE c.trip_id = t.trip_id))::int AS blanks
                             FROM fishing_trips t {where}""", args).fetchone()
        c = conn.execute(f"""SELECT count(*)::int AS catches, count(*) FILTER (WHERE c.fate = 'kept')::int AS kept,
                                    count(*) FILTER (WHERE c.fate IN ('released', 'tagged'))::int AS released {catches_from}""",
                         args).fetchone()
        totals = {"trips": t["trips"], "catches": c["catches"], "kept": c["kept"], "released": c["released"],
                  "hours": round(t["hours"], 1), "blanks": t["blanks"]}

        by_month = conn.execute("""
            SELECT to_char(m, 'YYYY-MM') AS month,
                   (SELECT count(*) FROM fishing_trips t WHERE date_trunc('month', t.started_at::timestamp) = m)::int AS trips,
                   (SELECT count(*) FROM fishing_catches c JOIN fishing_trips t USING (trip_id)
                    WHERE date_trunc('month', COALESCE(c.caught_at, t.started_at)::timestamp) = m)::int AS catches
            FROM generate_series(date_trunc('month', current_date) - interval '23 months', date_trunc('month', current_date),
                                 interval '1 month') m ORDER BY m""").fetchall()

        by_species = conn.execute(f"""
            SELECT (array_agg({name} ORDER BY c.catch_id))[1] AS species, count(*)::int AS catches,
                   count(*) FILTER (WHERE c.fate = 'kept')::int AS kept, max(c.length_cm)::float8 AS best_cm,
                   round(avg(c.length_cm), 1)::float8 AS avg_cm
            {catches_from} GROUP BY {fish} ORDER BY count(*) DESC, 1""", args).fetchall()

        by_month_species = conn.execute(f"""
            SELECT {fish} AS k, extract(month FROM {when}::timestamp)::int AS month, count(*)::int AS n
            {catches_from} GROUP BY 1, 2""", args).fetchall()
        keys = conn.execute(f"SELECT {fish} AS k {catches_from} GROUP BY {fish} ORDER BY count(*) DESC, {fish} LIMIT 8", args).fetchall()
        names = {}
        for r in conn.execute(f"SELECT {fish} AS k, (array_agg({name} ORDER BY c.catch_id))[1] AS species {catches_from} GROUP BY {fish}",
                              args).fetchall():
            names[r["k"]] = r["species"]
        seasons = []
        for k in (r["k"] for r in keys):
            months = [0] * 12
            for r in by_month_species:
                if r["k"] == k:
                    months[r["month"] - 1] = r["n"]
            seasons.append({"species": names[k], "months": months})

        by_hour = [0] * 24
        for r in conn.execute(f"SELECT extract(hour FROM {when}::timestamp)::int AS h, count(*)::int AS n {catches_from} GROUP BY 1",
                              args).fetchall():
            by_hour[r["h"]] = r["n"]

        moon = {p: {"phase": p, "catches": 0, "trips": 0} for p in MOON_PHASES}
        for r in conn.execute(f"SELECT t.conditions->>'moon_phase' AS phase, count(*)::int AS n FROM fishing_trips t {where} GROUP BY 1",
                              args).fetchall():
            if r["phase"] in moon:
                moon[r["phase"]]["trips"] = r["n"]
        for r in conn.execute(f"SELECT t.conditions->>'moon_phase' AS phase, count(*)::int AS n {catches_from} GROUP BY 1", args).fetchall():
            if r["phase"] in moon:
                moon[r["phase"]]["catches"] = r["n"]

        stages = {s: 0 for s in ("rising", "high", "falling", "low")}
        for r in conn.execute(f"""SELECT t.conditions->'tide' AS tide, {when} AS at {catches_from}
                                  AND jsonb_typeof(t.conditions->'tide') = 'array'""", args).fetchall():
            stage = tide_stage(r["tide"], _local(r["at"]))
            if stage:
                stages[stage] += 1

        top_lures = conn.execute(f"""SELECT l.lure_id, l.name, count(*)::int AS catches
                                     FROM fishing_catches c JOIN fishing_trips t USING (trip_id) JOIN fishing_lures l USING (lure_id)
                                     {where} GROUP BY l.lure_id, l.name ORDER BY count(*) DESC, lower(l.name) LIMIT 10""", args).fetchall()
        top_spots = conn.execute(f"""
            SELECT s.spot_id, s.name, sum(n)::int AS catches,
                   CASE WHEN sum(h) > 0 THEN round((sum(n) FILTER (WHERE h IS NOT NULL) / sum(h))::numeric, 2)::float8 END AS fish_per_hour
            FROM (SELECT t.spot_id, extract(epoch FROM (t.ended_at - t.started_at)) / 3600 AS h,
                         (SELECT count(*) FROM fishing_catches c WHERE c.trip_id = t.trip_id) AS n
                  FROM fishing_trips t {where} AND t.spot_id IS NOT NULL) x
            JOIN fishing_spots s USING (spot_id) GROUP BY s.spot_id, s.name
            ORDER BY fish_per_hour DESC NULLS LAST, sum(n) DESC, lower(s.name) LIMIT 10""", args).fetchall()
        trend = []
        if species_id is not None:
            trend = conn.execute(f"""SELECT {when} AS caught_at, {name} AS species, c.length_cm::float8 AS length_cm
                                     {catches_from} AND c.species_id = %(species)s AND c.length_cm IS NOT NULL
                                     ORDER BY {when}, c.catch_id""", args).fetchall()
        return {"year": year, "totals": totals, "by_month": by_month, "by_species": by_species, "seasons": seasons,
                "by_hour": by_hour, "by_moon": list(moon.values()),
                "by_tide": [{"stage": s, "catches": n} for s, n in stages.items()],
                "top_lures": top_lures, "top_spots": top_spots, "length_trend": trend}
