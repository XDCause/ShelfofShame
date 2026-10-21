"""Gardening: today (what needs water or feed, what's ready to pick, tasks due, weather tips for the balcony), the
summary for Home, the photo timeline and every harvest. Split out of garden.py (health check, 2026-10-21)."""

from fastapi import APIRouter, Query

from . import openmeteo
from .db import db
from .garden import LOG_SELECT, PLANTING_SELECT, TASK_SELECT, garden_settings, today

router = APIRouter(prefix="/api", tags=["gardening"])


# ---------------------------------------------------------------------------------------------
# Today, weather tips, summary, timeline, harvests
# ---------------------------------------------------------------------------------------------
def weather_tips(days: list[dict], spaces: list[dict]) -> list[dict]:
    """Plain advice for pots on a balcony from the next two days' forecast."""
    tips = []
    open_air = [s["name"] for s in spaces if not s["covered"] and s["kind"] not in ("Indoor", "Shelf", "Grow tent", "Windowsill")]
    outdoor = any(s["kind"] not in ("Indoor", "Shelf", "Grow tent", "Windowsill") for s in spaces) or not spaces
    for d, when in zip(days[:2], ("Today", "Tomorrow")):
        hot, gusts, rain, low, uv = d.get("max"), d.get("gusts"), d.get("rain_mm"), d.get("min"), d.get("uv")
        if outdoor and (d.get("code") or 0) >= 95:
            tips.append({"day": when, "kind": "storm", "text": "Storms" + (" with hail" if d["code"] >= 96 else "") +
                         " forecast: bring hanging baskets and light pots inside or against the wall, and cover seedlings."})
        if hot is not None and hot >= 35:
            tips.append({"day": when, "kind": "heat", "text": f"Very hot ({hot:.0f}°): water pots early in the morning and again in the "
                         "evening; move seedlings and lettuce into shade."})
        elif hot is not None and hot >= 30:
            tips.append({"day": when, "kind": "heat", "text": f"Hot ({hot:.0f}°): check pots morning and evening - small pots and "
                         "hanging baskets dry out first."})
        if outdoor and gusts is not None and gusts >= 60:
            tips.append({"day": when, "kind": "wind", "text": f"Strong gusts up to {gusts:.0f} km/h: move light pots and tall plants "
                         "against the wall or inside, and take down hanging baskets."})
        elif outdoor and gusts is not None and gusts >= 45:
            tips.append({"day": when, "kind": "wind", "text": f"Windy (gusts {gusts:.0f} km/h): pots dry out faster; stake tall plants."})
        if open_air and rain is not None and rain >= 5:
            tips.append({"day": when, "kind": "rain", "text": f"Rain ({rain:.0f} mm): {', '.join(open_air)} may not need watering."})
        if low is not None and low <= 5:
            tips.append({"day": when, "kind": "cold", "text": f"Cold night ({low:.0f}°): bring basil, chillies and other tender "
                         "plants inside or against the wall."})
        if outdoor and uv is not None and uv >= 11:
            tips.append({"day": when, "kind": "uv", "text": "Extreme UV: shade seedlings from the midday sun."})
    return tips


def weather(conn) -> dict | None:
    s = garden_settings(conn)
    if s["lat"] is None:
        return None
    spaces = conn.execute("SELECT name, kind, covered FROM garden_spaces").fetchall()
    try:
        days = openmeteo.forecast(s["lat"], s["lon"])
    except openmeteo.WeatherError as e:
        return {"place": s["place_name"], "error": str(e), "days": [], "tips": []}
    return {"place": s["place_name"], "error": None, "days": days, "tips": weather_tips(days, spaces)}


@router.get("/garden/today")
def garden_today():
    """What needs doing: watering and feeding due (oldest first), ready to harvest, your reminders, weather tips."""
    with db() as conn:
        current = conn.execute(PLANTING_SELECT + " WHERE p.stage NOT IN ('Planned', 'Done', 'Died') ORDER BY s.sort NULLS LAST, c.name, p.name").fetchall()
        d = today(conn)
        tasks = conn.execute(TASK_SELECT + " WHERE t.done_on IS NULL AND t.due_on <= current_date + 2 ORDER BY t.due_on").fetchall()
        planned = conn.execute(PLANTING_SELECT + " WHERE p.stage = 'Planned' ORDER BY p.started_on").fetchall()
        return {
            "today": d,
            "water": sorted([p for p in current if p["water_due_on"] and p["water_due_on"] <= d], key=lambda p: p["water_due_on"]),
            "feed": sorted([p for p in current if p["feed_due_on"] and p["feed_due_on"] <= d], key=lambda p: p["feed_due_on"]),
            "harvest": [p for p in current if p["harvest_ready"]],
            "tasks": tasks, "planned": planned,
            "weather": weather(conn),
            "growing": len(current),
        }


@router.get("/garden/summary")
def garden_summary():
    """For Home: plants growing, how many need water, ready to pick, reminders due, harvests this year."""
    with db() as conn:
        current = conn.execute(PLANTING_SELECT + " WHERE p.stage NOT IN ('Planned', 'Done', 'Died')").fetchall()
        d = today(conn)
        return {
            "growing": len(current),
            "need_water": sum(1 for p in current if p["water_due_on"] and p["water_due_on"] <= d),
            "need_feed": sum(1 for p in current if p["feed_due_on"] and p["feed_due_on"] <= d),
            "ready": sum(1 for p in current if p["harvest_ready"]),
            "tasks_due": conn.execute("SELECT count(*) AS n FROM garden_tasks WHERE done_on IS NULL AND due_on <= current_date").fetchone()["n"],
            "harvests_this_year": conn.execute("SELECT count(*) AS n FROM garden_logs WHERE kind = 'Harvested' "
                                               "AND happened_on >= date_trunc('year', current_date)").fetchone()["n"],
            "spaces": conn.execute("SELECT count(*) AS n FROM garden_spaces").fetchone()["n"],
        }


@router.get("/garden/harvests")
def harvests(year: int | None = Query(None, ge=1900, le=2200)):
    """Every harvest (newest first), with totals per plant and per month, by unit."""
    with db() as conn:
        y = year or today(conn).year
        rows = conn.execute(LOG_SELECT.replace("FROM garden_logs l", ", p.name AS planting_name, p.variety FROM garden_logs l "
                                               "JOIN garden_plantings p ON p.planting_id = l.planting_id")
                            + " WHERE l.kind = 'Harvested' AND extract(year FROM l.happened_on) = %s "
                            "ORDER BY l.happened_on DESC, l.log_id DESC", (y,)).fetchall()
    by_plant: dict = {}
    by_month: dict = {}
    for r in rows:
        unit = r["unit"] or "times"
        amount = r["amount"] if r["amount"] is not None else 1
        key = (r["planting_name"], unit)
        by_plant[key] = by_plant.get(key, 0) + amount
        mkey = (r["happened_on"].strftime("%Y-%m"), unit)
        by_month[mkey] = by_month.get(mkey, 0) + amount
    years = list(range(y - 3, y + 1))
    return {"year": y, "years": years, "harvests": rows,
            "by_plant": sorted([{"name": n, "unit": u, "amount": round(a, 2)} for (n, u), a in by_plant.items()],
                               key=lambda x: (-x["amount"], x["name"])),
            "by_month": [{"month": m, "unit": u, "amount": round(a, 2)} for (m, u), a in sorted(by_month.items())]}
