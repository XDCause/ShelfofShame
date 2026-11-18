"""Fishing: the tools (solunar times, the fishing forecast, the conditions snapshot a trip keeps, boat ramps and fishing
spots from OpenStreetMap). The trip log itself is in fishing.py. NOT FOR NAVIGATION; solunar times are angling folklore.

    GET  /fishing/forecast?spot_id= | lat=&lon=     7 days: solunar periods, tide, wind, pressure, best windows, a score
    GET  /fishing/solunar?lat=&lon=&date=           one day's sun / moon / periods / rating, for ANY date (no outside site)
    GET  /fishing/osm/near?lat=&lon=&km=&what=      boat ramps (what=ramps) or fishing spots (what=spots) on OpenStreetMap
    POST /fishing/osm/import                        {osm: 'node/123'}: that place as a new fishing spot (or the one already there)

    snapshot(conn, spot, started_at)                the conditions a trip keeps (fishing.py calls it; it never raises)

The astronomy is in solunar.py; the weather and tide are Open-Meteo's (openmeteo.fishing_weather, openmeteo.marine).
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import openmeteo, overpass, solunar
from .db import db, found, insert_row
from .golfmath import metres_between

router = APIRouter(prefix="/api", tags=["fishing"])

CREDIT = ("Weather and tide: Open-Meteo (CC BY 4.0). Solunar times are calculated here. Not for navigation.")
FOLKLORE = "Solunar tables are an old angling theory, not science: your own log (Stats) shows what works for you."
DAYS = 7


def _home(conn) -> tuple[float | None, float | None]:
    row = conn.execute("SELECT home_lat, home_lon FROM fishing_settings WHERE id = 1").fetchone() or {}
    return row.get("home_lat"), row.get("home_lon")


def _place(spot_id, lat, lon):
    """-> (name, water, lat, lon) from a spot, or a point, or the home position in the settings."""
    if spot_id is not None:
        with db() as conn:
            spot = found(conn.execute("SELECT name, water, lat, lon FROM fishing_spots WHERE spot_id = %s", (spot_id,)).fetchone(), "Spot")
        if spot["lat"] is None or spot["lon"] is None:
            raise HTTPException(422, "That spot has no position yet: add it, then the forecast can be found.")
        return spot["name"], spot["water"], spot["lat"], spot["lon"]
    if lat is None and lon is None:
        with db() as conn:
            lat, lon = _home(conn)
        if lat is None or lon is None:
            raise HTTPException(422, "Give a spot, or a latitude and longitude (or set your home position in the settings).")
        return "Home", None, lat, lon
    if lat is None or lon is None:
        raise HTTPException(422, "Give both a latitude and a longitude.")
    return f"{lat:.2f}, {lon:.2f}", None, lat, lon


# ---------------------------------------------------------------- the tide

def with_kinds(days: list[dict]) -> dict[str, list[dict]]:
    """Open-Meteo Marine's turning points ([{time, height}] a day) -> {day: [{time, height, kind 'high' | 'low'}]}: a turning
    point is a high when it's above the one before (or after, for the first), a low when below."""
    flat = [(d["day"], t) for d in days for t in d.get("tide") or []]
    out: dict[str, list[dict]] = {d["day"]: [] for d in days}
    for i, (day, t) in enumerate(flat):
        other = flat[i - 1][1] if i > 0 else flat[i + 1][1] if len(flat) > 1 else None
        if other is None:
            continue
        out[day].append({"time": t["time"], "height": t["height"], "kind": "high" if t["height"] > other["height"] else "low"})
    return out


def _marine(lat, lon, water):
    """(marine days, trouble): fresh water has no tide and isn't asked; any failure leaves the sea out."""
    if water == "fresh":
        return [], None
    try:
        return openmeteo.marine(lat, lon), None
    except openmeteo.WeatherError as e:
        return [], None if water is None else f"No tide or sea figures: {e}"


# ---------------------------------------------------------------- best windows and the score

def _t(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M")


def best_windows(sol: dict, tide: list[dict]) -> list[dict]:
    """The majors and minors that meet a tide change (high or low) within an hour, or dawn / dusk (an hour before to half an
    hour after sunrise, half an hour before to an hour after sunset) -> [{start, end, why}], in time order."""
    marks = []
    for key, before, after in (("sunrise", 30, 60), ("sunset", 60, 30)):
        if sol.get(key):
            at = _t(sol[key])
            marks.append((at - timedelta(minutes=before), at + timedelta(minutes=after), "dawn" if key == "sunrise" else "dusk"))
    out = []
    for kind, periods in (("major", sol["majors"]), ("minor", sol["minors"])):
        for p in periods:
            a, b = _t(p["start"]), _t(p["end"])
            why = []
            for t in tide:
                at = _t(t["time"])
                if a - timedelta(hours=1) <= at <= b + timedelta(hours=1):
                    why.append(f"{t['kind']} tide {at:%H:%M}")
            for lo, hi, name in marks:
                if a <= hi and b >= lo:
                    why.append(name)
            if why:
                out.append({"start": p["start"], "end": p["end"], "why": f"{kind.capitalize()} period at " + " and ".join(why)})
    return sorted(out, key=lambda w: w["start"])


def score(sol: dict, best: list[dict], wind_max, rain_mm, trend) -> tuple[int, str]:
    """1-5 for the day: the solunar rating, a point for two or more good windows, minus for a strong wind or a lot of rain."""
    s = sol["rating"]
    why = [f"solunar rating {s}/4"]
    if len(best) >= 2:
        s += 1
        why.append(f"{len(best)} good windows (periods at dawn, dusk or a tide change)")
    if wind_max is not None and wind_max >= 40:
        s -= 2
        why.append(f"strong wind to {wind_max:.0f} km/h")
    elif wind_max is not None and wind_max >= 30:
        s -= 1
        why.append(f"windy ({wind_max:.0f} km/h)")
    if rain_mm is not None and rain_mm >= 20:
        s -= 1
        why.append(f"heavy rain ({rain_mm:.0f} mm)")
    if trend == "falling":
        why.append("pressure falling")
    return max(1, min(5, s)), "; ".join(why)


# ---------------------------------------------------------------- routes

@router.get("/fishing/forecast")
def forecast(spot_id: int | None = Query(None, ge=1, le=2147483647), lat: float | None = Query(None, ge=-90, le=90),
             lon: float | None = Query(None, ge=-180, le=180)):
    """The next 7 days (today first) for fishing at a spot (spot_id) or a point (lat, lon; with neither, your home position):
    sun, moon, the solunar majors and minors, a rating, the tide highs and lows (not for freshwater spots), wind, pressure
    and its trend, rain, sea temperature, the best windows and a 1-5 score. The weather being out of reach leaves those
    figures empty (and says so in `notices`): the solunar part never needs a website."""
    name, water, lat, lon = _place(spot_id, lat, lon)
    notices = []
    try:
        weather = {d["day"]: d for d in openmeteo.fishing_weather(lat, lon)}
    except openmeteo.WeatherError as e:
        weather = {}
        notices.append(f"No weather figures: {e}")
    sea, trouble = _marine(lat, lon, water)
    if trouble:
        notices.append(trouble)
    seas = {d["day"]: d for d in sea}
    tides = with_kinds(sea) if sea else {}
    today = datetime.now(solunar.zone(None)).date()
    days = []
    for i in range(DAYS):
        d = today + timedelta(days=i)
        key = d.isoformat()
        sol = solunar.day(d, lat, lon)
        w, s = weather.get(key) or {}, seas.get(key) or {}
        tide = tides.get(key, [])
        best = best_windows(sol, tide)
        sc, why = score(sol, best, w.get("wind_max"), w.get("rain_mm"), w.get("pressure_trend"))
        days.append({"date": key, "sunrise": sol["sunrise"], "sunset": sol["sunset"], "moon": sol["moon"], "majors": sol["majors"],
                     "minors": sol["minors"], "rating": sol["rating"], "tide": tide, "wind_max": w.get("wind_max"),
                     "wind_dir": w.get("wind_dir"), "gusts": w.get("gusts"), "pressure_mean": w.get("pressure_mean"),
                     "pressure_trend": w.get("pressure_trend"), "rain_mm": w.get("rain_mm"), "temp_max": w.get("temp_max"),
                     "sst": s.get("sst"), "swell_max": s.get("swell_max"), "best": best, "score": sc, "why": why})
    return {"place": name, "water": water, "lat": lat, "lon": lon, "days": days, "notices": notices,
            "kept_since": openmeteo.kept_since(sea) or openmeteo.kept_since(list(weather.values())),
            "credit": CREDIT, "note": FOLKLORE}


@router.get("/fishing/solunar")
def solunar_day(lat: float | None = Query(None, ge=-90, le=90), lon: float | None = Query(None, ge=-180, le=180),
                date_: str | None = Query(None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
                tz: str | None = Query(None, max_length=60)):
    """One day's sun, moon, solunar periods and rating at a point (the home position when none is given), for any date
    from 1900 to 2100 (default today; past trips too). No outside website: it's calculated. Times are local to tz
    (default Australia/Brisbane)."""
    _, _, lat, lon = _place(None, lat, lon)
    try:
        d = date.fromisoformat(date_) if date_ else datetime.now(solunar.zone(None)).date()
    except ValueError:
        raise HTTPException(422, "That isn't a date (use YYYY-MM-DD).")
    if not 1900 <= d.year <= 2100:
        raise HTTPException(422, "Dates from 1900 to 2100 only.")
    try:
        out = solunar.day(d, lat, lon, tz)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {**out, "lat": lat, "lon": lon, "note": FOLKLORE}


# ---------------------------------------------------------------- the trip's snapshot

def snapshot(conn, spot: dict | None, started_at) -> dict:
    """The conditions to keep with a trip that started at started_at (a datetime) at a spot ({lat, lon, water, ...}):
    {moon_phase, moon_pct, rating, sunrise, sunset, tide [{time, height, kind}], wind_kmh, wind_dir, pressure_hpa,
    pressure_trend, sst}. The solunar part is always there (any date); the weather and tide only when the day is today or
    within the next 6 (a past day is never asked for - no archive). Parts that can't be had are left out; it never raises."""
    try:
        lat, lon = spot["lat"], spot["lon"]
        if lat is None or lon is None:
            return {}
        tz = solunar.zone(None)
        when = started_at if isinstance(started_at, datetime) else datetime.fromisoformat(str(started_at))
        when = when.replace(tzinfo=tz) if when.tzinfo is None else when.astimezone(tz)
        sol = solunar.day(when.date(), lat, lon)
        phase, pct, _ = solunar.moon_phase(when)
        out = {"moon_phase": phase, "moon_pct": pct, "rating": sol["rating"], "sunrise": sol["sunrise"], "sunset": sol["sunset"]}
    except Exception:                                  # a snapshot is a bonus: never the reason a trip isn't saved
        return {}
    key = when.date().isoformat()
    ahead = (when.date() - datetime.now(tz).date()).days
    if not 0 <= ahead < DAYS:
        return out
    try:
        w = next((d for d in openmeteo.fishing_weather(lat, lon) if d["day"] == key), None)
        if w:
            out.update(wind_kmh=w["wind_max"], wind_dir=w["wind_dir"], pressure_hpa=w["pressure_mean"], pressure_trend=w["pressure_trend"])
    except Exception:
        pass
    try:
        sea, _ = _marine(lat, lon, (spot or {}).get("water"))
        if sea:
            out["tide"] = with_kinds(sea).get(key, [])
            sst = next((d["sst"] for d in sea if d["day"] == key), None)
            if sst is not None:
                out["sst"] = sst
    except Exception:
        pass
    return {k: v for k, v in out.items() if v is not None}


# ---------------------------------------------------------------- boat ramps and fishing spots from OpenStreetMap

KINDS = {"ramps": "Boat ramp", "spots": "Fishing spot"}


def osm_place(el: dict) -> dict | None:
    """An Overpass element -> {osm, name, kind, lat, lon, place}, None if it has no position."""
    tags = el.get("tags") or {}
    lat = el.get("lat") if el.get("lat") is not None else (el.get("center") or {}).get("lat")
    lon = el.get("lon") if el.get("lon") is not None else (el.get("center") or {}).get("lon")
    if lat is None or lon is None or el.get("type") not in ("node", "way", "relation") or not isinstance(el.get("id"), int):
        return None
    kind = KINDS["ramps"] if tags.get("leisure") == "slipway" else KINDS["spots"]
    return {"osm": f"{el['type']}/{el['id']}", "name": (tags.get("name") or "").strip() or kind, "kind": kind, "lat": lat, "lon": lon,
            "named": bool((tags.get("name") or "").strip()), "place": tags.get("addr:suburb") or tags.get("addr:city") or tags.get("is_in")}


@router.get("/fishing/osm/near")
def osm_near(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180), km: float = Query(20, ge=1, le=100),
             what: str = Query("ramps", pattern="^(ramps|spots)$")):
    """Boat ramps (what=ramps: leisure=slipway) or fishing spots (what=spots: leisure=fishing) within km of a point, as
    OpenStreetMap has them, nearest first, each with `already` = the spot_id if it's already one of yours. Unnamed ones are
    called "Boat ramp" / "Fishing spot". (Data (c) OpenStreetMap contributors, ODbL.)"""
    try:
        elements = overpass.fishing_near(lat, lon, int(km * 1000), what)
    except overpass.OverpassError as e:
        raise HTTPException(502, str(e))
    with db() as conn:
        have = {r["osm"]: r["spot_id"] for r in conn.execute("SELECT osm, spot_id FROM fishing_spots WHERE osm IS NOT NULL")}
    places, seen = [], set()
    for el in elements:
        p = osm_place(el)
        if not p or p["osm"] in seen:
            continue
        seen.add(p["osm"])
        p["km"] = round(metres_between((lat, lon), (p["lat"], p["lon"])) / 1000, 1)
        p["already"] = have.get(p["osm"])
        places.append(p)
    return sorted(places, key=lambda p: p["km"])


class OsmImportIn(BaseModel):
    osm: str = Field(pattern=r"^(node|way|relation)/[0-9]{1,12}$")


@router.post("/fishing/osm/import", status_code=201)
def osm_import(body: OsmImportIn, response: Response):
    """One OpenStreetMap boat ramp or fishing spot as a new fishing spot (name, position, kind 'Boat ramp' / 'Fishing spot').
    Already imported: the spot you have (200, existing true) - nothing of yours is overwritten."""
    with db() as conn:
        row = conn.execute("SELECT * FROM fishing_spots WHERE osm = %s", (body.osm,)).fetchone()
    if row:
        response.status_code = 200
        return {**row, "existing": True}
    try:
        elements = overpass.element(body.osm)
    except overpass.OverpassError as e:
        raise HTTPException(502, str(e))
    place = osm_place(elements[0]) if elements else None
    if not place:
        raise HTTPException(404, "OpenStreetMap has no such place (or it has no position).")
    with db() as conn:
        spot_id = insert_row(conn, "fishing_spots", {
            "name": place["name"], "place": place["place"], "lat": place["lat"], "lon": place["lon"], "kind": place["kind"],
            "osm": body.osm, "notes": "From OpenStreetMap (c) OpenStreetMap contributors, ODbL."}, "spot_id")
        row = conn.execute("SELECT * FROM fishing_spots WHERE spot_id = %s", (spot_id,)).fetchone()
    return {**row, "existing": False}
