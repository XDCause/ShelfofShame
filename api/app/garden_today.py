"""Gardening: today (what needs water or feed, what's ready to pick, tasks due, weather tips for the balcony), the
summary for Home, the photo timeline and every harvest. Split out of garden.py (health check, 2026-10-21)."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

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


# ---------------------------------------------------------------------------------------------
# Watering that follows the weather
# ---------------------------------------------------------------------------------------------
HOT_C, VERY_HOT_C = 32, 36      # a hot spell: 2 of yesterday / today / tomorrow at 32 or more, or any day at 36
RAIN_MM, RAIN_CHANCE = 5, 60    # rain that counts as a watering (and a forecast worth waiting for)
OUTDOOR_KINDS = ("Balcony", "Courtyard", "Rooftop", "Community plot")


def water_plan(p: dict, days: list[dict], today_: date) -> dict | None:
    """What the weather does to this plant's watering. p: a planting row (water_due_on, last_watered_on, water_every_days,
    self_watering, covered, space_kind); days: openmeteo.care_days. Rain on an open balcony counts as a watering; a hot
    spell shortens the gap (to 75% or 60%); rain forecast for tomorrow means waiting. None when the weather changes nothing.
    Answers {status: skip | wait | sooner, due_on, note}."""
    if not p.get("water_due_on") or not p.get("water_every_days") or p.get("space_kind") not in OUTDOOR_KINDS:
        return None
    by_day = {d["day"]: d for d in days}

    def on(offset):
        return by_day.get((today_ + timedelta(days=offset)).isoformat()) or {}
    interval = p["water_every_days"] * (2 if p["self_watering"] else 1)
    notes = []
    peak = [on(o).get("max") for o in (-1, 0, 1) if on(o).get("max") is not None]
    very, hot = [t for t in peak if t >= VERY_HOT_C], [t for t in peak if t >= HOT_C]
    if very or len(hot) >= 2:
        shorter = max(1, round(interval * (0.6 if very else 0.75)))
        if shorter < interval:
            notes.append(f"Hot spell ({max(peak):.0f}°): every {shorter} days instead of {interval}.")
            interval = shorter
    last = p["last_watered_on"]
    if not p["covered"]:
        for o in (0, -1, -2):                                     # the latest rain that counts
            rain = on(o).get("rain_mm")
            if rain is not None and rain >= RAIN_MM:
                rained = today_ + timedelta(days=o)
                if last is None or rained > last:
                    last = rained
                    notes.append(f"{rain:.0f} mm of rain {'today' if o == 0 else 'yesterday' if o == -1 else '2 days ago'} counts as a watering.")
                break
    due = last + timedelta(days=interval) if last else p["water_due_on"]
    status = None
    tomorrow = on(1)
    if (not p["covered"] and due <= today_ and (tomorrow.get("rain_mm") or 0) >= RAIN_MM
            and (tomorrow.get("rain_chance") or 0) >= RAIN_CHANCE):
        due, status = today_ + timedelta(days=1), "wait"
        notes.append(f"Rain forecast tomorrow ({tomorrow['rain_mm']:.0f} mm): worth waiting for it.")
    if due == p["water_due_on"]:
        return None
    status = status or ("skip" if due > p["water_due_on"] else "sooner")
    return {"status": status, "due_on": due, "note": " ".join(notes)}


def care_weather(conn) -> list[dict]:
    """The days for watering advice, or [] with no place set or Open-Meteo out of reach (then the plain schedule stands)."""
    s = garden_settings(conn)
    if s["lat"] is None:
        return []
    try:
        return openmeteo.care_days(s["lat"], s["lon"])
    except openmeteo.WeatherError:
        return []


def with_weather(plants: list[dict], days: list[dict], today_: date) -> None:
    """Each plant gets water_plan (or None) and water_due_weather: the date to water by, weather included."""
    for p in plants:
        p["water_plan"] = water_plan(p, days, today_) if days else None
        p["water_due_weather"] = p["water_plan"]["due_on"] if p["water_plan"] else p["water_due_on"]


def weather(conn) -> dict | None:
    s = garden_settings(conn)
    if s["lat"] is None:
        return None
    spaces = conn.execute("SELECT name, kind, covered FROM garden_spaces").fetchall()
    try:
        days = openmeteo.forecast(s["lat"], s["lon"])
    except openmeteo.WeatherError as e:
        return {"place": s["place_name"], "error": str(e), "days": [], "tips": [], "as_of": None}
    return {"place": s["place_name"], "error": None, "days": days, "tips": weather_tips(days, spaces),
            "as_of": openmeteo.kept_since(days)}


@router.get("/garden/today")
def garden_today():
    """What needs doing: watering and feeding due (oldest first), ready to harvest, your reminders, weather tips."""
    with db() as conn:
        current = conn.execute(PLANTING_SELECT + " WHERE p.stage NOT IN ('Planned', 'Done', 'Died') ORDER BY s.sort NULLS LAST, c.name, p.name").fetchall()
        d = today(conn)
        with_weather(current, care_weather(conn), d)
        tasks = conn.execute(TASK_SELECT + " WHERE t.done_on IS NULL AND t.due_on <= current_date + 2 ORDER BY t.due_on").fetchall()
        planned = conn.execute(PLANTING_SELECT + " WHERE p.stage = 'Planned' ORDER BY p.started_on").fetchall()
        return {
            "today": d,
            "water": sorted([p for p in current if p["water_due_weather"] and p["water_due_weather"] <= d], key=lambda p: p["water_due_weather"]),
            "water_held": [p for p in current if p["water_due_on"] and p["water_due_on"] <= d < p["water_due_weather"]],
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
        with_weather(current, care_weather(conn), d)
        return {
            "growing": len(current),
            "need_water": sum(1 for p in current if p["water_due_weather"] and p["water_due_weather"] <= d),
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


# ---------------------------------------------------------------------------------------------
# Cost against harvest ("worth it")
# ---------------------------------------------------------------------------------------------
def worth_it(spend: float, harvested: list[dict], values: dict) -> dict:
    """One planting's balance. harvested = [{unit, amount}], values = {(crop, unit): shop price of one unit}.
    Answers the harvest's shop value (only units you've priced), cost per unit of the main unit, and a verdict:
    'worth' / 'not yet' when there's a price to compare with, else None."""
    value, priced = 0.0, False
    for h in harvested:
        per = values.get(h["key"])
        if per is not None:
            value += h["amount"] * per
            priced = True
    main = max(harvested, key=lambda h: h["amount"], default=None)
    cost_per = round(spend / main["amount"], 4) if main and main["amount"] and spend else None
    verdict = None
    if priced and spend:
        verdict = "worth" if value >= spend else "not yet"
    return {"value": round(value, 2) if priced else None, "cost_per_unit": cost_per, "main_unit": main["unit"] if main else None,
            "verdict": verdict}


@router.get("/garden/harvests/worth")
def harvests_worth(year: int | None = Query(None, ge=1900, le=2200)):
    """Spend against harvest. Per planting (started or harvested in the year; all-time figures): what you paid for the
    plant plus its share of the seed packet it came from, against what you picked. Supplies (soil, fertiliser, pots)
    aren't tied to plantings and have no purchase date, so they come as a total for the year you added them."""
    with db() as conn:
        y = year or today(conn).year
        rows = conn.execute("""
            SELECT p.planting_id, p.name, p.variety, p.started_on, p.stage,
                   COALESCE(p.price, 0)::float8 AS plant_price,
                   COALESCE(i.price / NULLIF((SELECT count(*) FROM garden_plantings q WHERE q.item_id = i.item_id), 0), 0)::float8
                       AS seed_share
            FROM garden_plantings p LEFT JOIN garden_items i ON i.item_id = p.item_id
            WHERE extract(year FROM p.started_on) = %(y)s
               OR EXISTS (SELECT 1 FROM garden_logs l WHERE l.planting_id = p.planting_id AND l.kind = 'Harvested'
                          AND extract(year FROM l.happened_on) = %(y)s)
            ORDER BY p.started_on DESC, p.planting_id DESC""", {"y": y}).fetchall()
        picked = conn.execute("""SELECT planting_id, COALESCE(lower(btrim(unit)), 'times') AS unit,
                                        sum(COALESCE(amount, 1))::float8 AS amount
                                 FROM garden_logs WHERE kind = 'Harvested' AND planting_id = ANY(%s)
                                 GROUP BY 1, 2""", ([r["planting_id"] for r in rows],)).fetchall()
        values = {(v["crop"], v["unit"]): float(v["per_unit"]) for v in
                  conn.execute("SELECT crop, unit, per_unit FROM garden_crop_values").fetchall()}
        supplies = conn.execute("""SELECT COALESCE(sum(price), 0)::float8 AS total, count(*)::int AS items FROM garden_items
                                   WHERE price IS NOT NULL AND status <> 'Wanted' AND kind NOT IN ('Seeds', 'Seedling')
                                     AND extract(year FROM created_at) = %s""", (y,)).fetchone()
    plantings = []
    for r in rows:
        crop = r["name"].strip().lower()
        harvested = [{"unit": h["unit"], "amount": round(h["amount"], 2), "key": (crop, h["unit"]),
                      "per_unit": values.get((crop, h["unit"]))} for h in picked if h["planting_id"] == r["planting_id"]]
        spend = round(r["plant_price"] + r["seed_share"], 2)
        plantings.append({**r, "crop": crop, "spend": spend, **worth_it(spend, harvested, values),
                          "harvested": [{k: v for k, v in h.items() if k != "key"} for h in harvested]})
    spent = round(sum(p["spend"] for p in plantings), 2)
    valued = [p for p in plantings if p["value"] is not None]
    return {"year": y, "plantings": plantings, "planting_spend": spent,
            "supplies_spend": round(supplies["total"], 2), "supplies_items": supplies["items"],
            "value": round(sum(p["value"] for p in valued), 2), "valued": len(valued),
            "supplies_note": "Soil, fertiliser, pots and tools aren't linked to plantings, so they're a total for the "
                             "year you added them, not part of each crop's cost."}


class CropValue(BaseModel):
    crop: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=20)
    per_unit: float | None = Field(None, ge=0, le=100000)      # blank removes the price


@router.put("/garden/harvests/values")
def set_crop_value(body: CropValue):
    """What one unit of a crop would cost at the shop (blank = forget it). Crop and unit are kept in lower case."""
    crop, unit = body.crop.strip().lower(), body.unit.strip().lower()
    if not crop or not unit:
        raise HTTPException(422, "Say which crop and unit.")
    with db() as conn:
        if body.per_unit is None:
            conn.execute("DELETE FROM garden_crop_values WHERE crop = %s AND unit = %s", (crop, unit))
        else:
            conn.execute("""INSERT INTO garden_crop_values (crop, unit, per_unit) VALUES (%s, %s, %s)
                            ON CONFLICT (crop, unit) DO UPDATE SET per_unit = EXCLUDED.per_unit, updated_at = now()""",
                         (crop, unit, body.per_unit))
    return {"crop": crop, "unit": unit, "per_unit": body.per_unit}
