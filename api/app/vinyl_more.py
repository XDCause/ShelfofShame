"""Vinyl, more (market review, 2026-11-16): the listening year in review and the collection's value, week by week.

    review         /vinyl/review?year=      plays per month, most played records and artists, new arrivals, hours listened,
                   busiest day; Last.fm: the tracks scrobbled from your plays (the app keeps a count per play, not the scrobbles)
    value-history  /vinyl/value-history    the collection's total value each week (Discogs is read weekly: vinyl_sync.py),
                   what it paid, the change over a month / a quarter / a year, and the records that moved most
"""
from collections import Counter
from datetime import date

from fastapi import APIRouter, Query

from .db import db
from .vinyl import LIST
from .vinyl_care import play_minutes

router = APIRouter(prefix="/api", tags=["vinyl"])

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def top(counter: Counter, n: int) -> list[dict]:
    return [{"label": k, "plays": v} for k, v in sorted(counter.items(), key=lambda x: (-x[1], x[0]))[:n]]


def year_numbers(plays: list[dict], year: int) -> dict:
    """A year's listening from its plays (each: played_at, record_id, title, artist, sides, tracklist, size, discs, medium).
    Pure, so it can be tested without a database."""
    months = [{"month": f"{year}-{m:02d}", "plays": 0} for m in range(1, 13)]
    by_record, by_artist, by_day = Counter(), Counter(), Counter()
    minutes = 0.0
    days = set()
    for p in plays:
        months[p["played_at"].month - 1]["plays"] += 1
        by_record[(p["record_id"], p["title"], p["artist"])] += 1
        if p["artist"]:
            by_artist[p["artist"]] += 1
        by_day[p["played_at"].weekday()] += 1
        days.add(p["played_at"].date())
        minutes += play_minutes(p["sides"], p["tracklist"], p["size"], p["discs"])
    records = [{"record_id": k[0], "title": k[1], "artist": k[2], "plays": n}
               for k, n in sorted(by_record.items(), key=lambda x: (-x[1], x[0][1]))[:8]]
    busiest = max(by_day.items(), key=lambda x: (x[1], -x[0]), default=None)
    return {"year": year, "plays": len(plays), "records_played": len(by_record), "days": len(days), "hours": round(minutes / 60, 1),
            "by_month": months, "top_records": records, "top_artists": top(by_artist, 6),
            "busiest_day": {"day": WEEKDAYS[busiest[0]], "plays": busiest[1]} if busiest else None,
            "scrobbled": sum(p["scrobbled"] or 0 for p in plays)}


@router.get("/vinyl/review")
def review(year: int | None = Query(None, ge=1900, le=2100)):
    """The listening year (default: this year), the records that joined the collection in it, and the years with plays."""
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
        year = year or today.year
        plays = conn.execute("""
            SELECT p.played_at, p.record_id, p.sides, p.scrobbled, r.title, r.artist, r.tracklist, r.size, r.discs
            FROM vinyl_plays p JOIN vinyl_records r USING (record_id)
            WHERE extract(year FROM p.played_at) = %s ORDER BY p.played_at""", (year,)).fetchall()
        # CDs and cassettes count as plays, but not as hours on the stylus - hours here are listening time, so all count.
        out = year_numbers(plays, year)
        out["new_arrivals"] = conn.execute(LIST + " WHERE r.status = 'Owned' AND extract(year FROM r.added_on) = %s "
                                           "ORDER BY r.added_on DESC, r.record_id DESC", (year,)).fetchall()
        out["new_unplayed"] = sum(1 for r in out["new_arrivals"] if not r["plays"])
        out["years"] = [r["y"] for r in conn.execute("""
            SELECT DISTINCT y FROM (SELECT extract(year FROM played_at)::int AS y FROM vinyl_plays UNION SELECT %s) x
            ORDER BY y DESC""", (today.year,)).fetchall()]
        out["today"] = today
    return out


def change(series: list[dict], days: int, today: date) -> dict | None:
    """The total's change since `days` ago (the nearest week at or before), or None if the history is shorter."""
    if not series:
        return None
    then = [w for w in series if (today - w["week"]).days >= days]
    if not then:
        return None
    was, now = then[-1]["value"], series[-1]["value"]
    return {"days": days, "was": was, "change": round(now - was, 2), "percent": round(100 * (now - was) / was, 1) if was else None}


@router.get("/vinyl/value-history")
def value_history(weeks: int = Query(104, ge=2, le=520)):
    """The collection's value at the end of each week (each record's latest value by then; records you own now)."""
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
        series = conn.execute("""
            WITH wk AS (SELECT generate_series(date_trunc('week', current_date)::date - (%(w)s - 1) * 7,
                                               date_trunc('week', current_date)::date, interval '7 days')::date AS week)
            SELECT wk.week, (SELECT COALESCE(sum(v.value), 0)::float8 FROM vinyl_records r
                             JOIN LATERAL (SELECT value FROM vinyl_values x WHERE x.record_id = r.record_id
                                           AND x.seen_on < wk.week + 7 ORDER BY x.seen_on DESC LIMIT 1) v ON true
                             WHERE r.status = 'Owned') AS value
            FROM wk ORDER BY wk.week""", {"w": weeks}).fetchall()
        first = next((i for i, w in enumerate(series) if w["value"] > 0), None)
        series = series[first:] if first is not None else []     # from the first week with any value
        paid = conn.execute("SELECT COALESCE(sum(price_paid), 0)::float8 AS n FROM vinyl_records WHERE status = 'Owned'").fetchone()["n"]
        movers = conn.execute("""
            SELECT m.*, m.value - m.was AS moved FROM (
                SELECT r.record_id, r.title, r.artist, r.value::float8 AS value,
                       (SELECT x.value::float8 FROM vinyl_values x WHERE x.record_id = r.record_id
                        AND x.seen_on <= current_date - 90 ORDER BY x.seen_on DESC LIMIT 1) AS was
                FROM vinyl_records r WHERE r.status = 'Owned' AND r.value IS NOT NULL) m
            WHERE m.was IS NOT NULL AND m.value <> m.was ORDER BY abs(m.value - m.was) DESC LIMIT 8""").fetchall()
    return {"series": series, "paid": paid, "now": series[-1]["value"] if series else 0,
            "changes": [c for c in (change(series, d, today) for d in (30, 90, 365)) if c], "movers": movers}
