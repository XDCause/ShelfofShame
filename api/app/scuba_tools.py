"""Scuba diving: the tools (maths, import, sea conditions, dive sites from OpenStreetMap). The logbook itself is in
scuba.py. ALL OF IT FOR LEARNING AND CHECKING - your dive computer and your training are the rule.

    GET  /scuba/ndl?gas_o2=&gf_high=             no-decompression limits by depth (9 ... 39 m) for a gas
    POST /scuba/plan                             a planned dive: stops, time to surface, gas, turn / rock bottom, oxygen, warnings
    GET  /scuba/dives/{id}/analysis              a logged dive's profile: ascent warnings, safety stop, tissue loading, CNS
    POST /scuba/import[?dry=1]                   a UDDF / Subsurface file (the request body, or a multipart "file"); dry = preview
    GET  /scuba/conditions?site_id= | lat=&lon=  7 days of sea (Open-Meteo Marine) + wind, with a dive-day verdict
    GET  /scuba/osm/near?lat=&lon=&km=           dive sites mapped on OpenStreetMap (sport=scuba_diving)
    POST /scuba/osm/import                       {osm: 'node/123'}: that site as a new scuba site (or the one already there)

The maths is in divemath.py, the file reading in diveimport.py.
"""
import email
import email.policy
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from . import divemath as dm, diveimport, openmeteo, overpass
from .db import db, found, insert_row
from .golfmath import metres_between

router = APIRouter(prefix="/api", tags=["scuba"])

NDL_DEPTHS = [9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39]
CAUTION = "For learning and checking - your dive computer and your training are the rule."
CREDIT = "Sea forecast: Open-Meteo Marine (CC BY 4.0). Not for navigation."


def _settings(conn) -> dict:
    return conn.execute("SELECT * FROM scuba_settings WHERE id = 1").fetchone() or {
        "gas_o2": 21, "tank_l": 12, "start_bar": 200, "sac_l_min": 20, "gf_low": 40, "gf_high": 85, "ppo2_max": 1.4}


# ---------------------------------------------------------------- NDL and the planner

@router.get("/scuba/ndl")
def ndl_table(gas_o2: int | None = Query(None, ge=21, le=100), gf_high: int | None = Query(None, ge=10, le=100)):
    """No-decompression time (minutes from leaving the surface, descent included) at each depth, null where the gas is
    over your ppO2 limit (1.4 unless you changed it in the settings). 300 means 300 or more."""
    with db() as conn:
        s = _settings(conn)
    o2 = gas_o2 or s["gas_o2"]
    gf = gf_high or s["gf_high"]
    limit = float(s["ppo2_max"])
    return [{"depth": d, "ndl": None if dm.ppo2(d, o2) > limit + 1e-9 else dm.ndl(d, o2, gf)} for d in NDL_DEPTHS]


class PlanIn(BaseModel):
    depth: float = Field(ge=1, le=100)
    minutes: float = Field(ge=1, le=600)
    gas_o2: int | None = Field(None, ge=21, le=100)
    gf_low: int | None = Field(None, ge=10, le=100)
    gf_high: int | None = Field(None, ge=10, le=100)
    sac: float | None = Field(None, ge=5, le=60)
    tank_l: float | None = Field(None, ge=1, le=30)
    start_bar: int | None = Field(None, ge=50, le=300)
    repetitive: bool = False


def _dive_start(row: dict, now: datetime) -> datetime:
    start = datetime.combine(row["dived_on"], row["time_in"] or datetime.min.time().replace(hour=12))
    return min(start, now - timedelta(minutes=row["minutes"] or 0))


def tissues_now(conn, now: datetime | None = None) -> tuple[dm.Tissues, int]:
    """The tissues left by the logbook's dives in the last 24 hours, rested at the surface until now -> (tissues, dives
    counted). A dive with a recorded profile is walked sample by sample; one without is a square profile (its deepest
    depth for its whole time). Dives from before the 24 hours are taken as long gone; a dive with no start time is
    taken to have started at noon."""
    now = now or datetime.now()
    rows = conn.execute("SELECT dived_on, time_in, minutes, max_depth, gas_o2, samples FROM scuba_dives "
                        "WHERE dived_on >= %s ORDER BY dived_on, time_in NULLS FIRST", ((now - timedelta(days=2)).date(),)).fetchall()
    dives = sorted(((_dive_start(r, now), r) for r in rows), key=lambda x: x[0])
    dives = [(s, r) for s, r in dives if s + timedelta(minutes=r["minutes"] or 0) > now - timedelta(hours=24)]
    t = dm.new_tissues()
    last_end = None
    for start, r in dives:
        if last_end is not None:
            dm.offgas(t, max(0.0, (start - last_end).total_seconds() / 60.0))
        samples = r["samples"] if isinstance(r["samples"], list) and len(r["samples"]) > 1 else None
        minutes = r["minutes"] or 0
        if samples:
            t, _ = dm.tissues_after(samples, r["gas_o2"], t)
            minutes = samples[-1][0] / 60.0
        elif r["max_depth"] and minutes:
            td = float(r["max_depth"]) / dm.DESCENT
            dm.schreiner(t, 0.0, float(r["max_depth"]), td, r["gas_o2"])
            dm.schreiner(t, float(r["max_depth"]), float(r["max_depth"]), max(0.0, minutes - td), r["gas_o2"])
            dm.schreiner(t, float(r["max_depth"]), 0.0, float(r["max_depth"]) / dm.ASCENT, r["gas_o2"])
        last_end = start + timedelta(minutes=minutes)
    if last_end is not None:
        dm.offgas(t, max(0.0, (now - last_end).total_seconds() / 60.0))
    return t, len(dives)


@router.post("/scuba/plan")
def plan(body: PlanIn):
    """Plan a square dive (down, level, up). Anything left out comes from your scuba settings. With repetitive, you start
    from the tissues your logbook's dives of the last 24 hours left."""
    with db() as conn:
        s = _settings(conn)
        tissues, counted = tissues_now(conn) if body.repetitive else (None, 0)
    lo = body.gf_low or s["gf_low"]
    hi = body.gf_high or s["gf_high"]
    if lo > hi:
        raise HTTPException(422, "GF low can't be higher than GF high.")
    out = dm.plan(body.depth, body.minutes, body.gas_o2 or s["gas_o2"], lo, hi, body.sac or float(s["sac_l_min"]),
                  body.tank_l or float(s["tank_l"]), body.start_bar or s["start_bar"], tissues, float(s["ppo2_max"]))
    out.update(gas_o2=body.gas_o2 or s["gas_o2"], gf_low=lo, gf_high=hi, repetitive=body.repetitive, note=CAUTION)
    if body.repetitive:
        out["prior_dives"] = counted
        out["start_surface_gf"] = round(max(0.0, dm.surface_gf(tissues)), 1)
        if counted and out["ndl"] == 0:
            out["warnings"].insert(0, "Your tissues still hold a lot from the last 24 hours: no no-stop time is left at this depth.")
    return out


# ---------------------------------------------------------------- a logged dive's profile

@router.get("/scuba/dives/{dive_id}/analysis")
def analysis(dive_id: int):
    with db() as conn:
        row = found(conn.execute("SELECT gas_o2, samples FROM scuba_dives WHERE dive_id = %s", (dive_id,)).fetchone(), "Dive")
    samples = row["samples"]
    if not isinstance(samples, list) or len(samples) < 2:
        raise HTTPException(409, "This dive has no recorded profile (import it from a dive computer's file to get one).")
    o2 = row["gas_o2"]
    tissues, series = dm.tissues_after(samples, o2)
    cns, otu, peak = dm.profile_exposure(samples, o2)
    return {"profile": dm.downsample(samples, 400), "ascent_warnings": dm.ascent_warnings(samples),
            "safety_stop": dm.safety_stop(samples), "tissues": series,
            "surface_gf": round(max(0.0, dm.surface_gf(tissues)), 1), "cns": round(cns, 1), "otu": round(otu),
            "max_ppo2": round(peak, 2), "note": CAUTION}


# ---------------------------------------------------------------- import

def _file_bytes(body: bytes, content_type: str) -> bytes:
    """The file from a request: the body itself, or the "file" part of a multipart form (read without a form library)."""
    if not content_type.lower().startswith("multipart/form-data"):
        return body
    msg = email.message_from_bytes(b"Content-Type: " + content_type.encode("latin-1", "replace") + b"\r\n\r\n" + body,
                                   policy=email.policy.HTTP)
    parts = list(msg.iter_parts()) if msg.is_multipart() else []
    for part in parts:
        if part.get_param("name", header="content-disposition") == "file":
            return part.get_payload(decode=True) or b""
    if parts:
        return parts[0].get_payload(decode=True) or b""
    raise HTTPException(422, "No file came with that request.")


def next_dive_no(conn) -> int:
    row = conn.execute("SELECT (SELECT max(dive_no) FROM scuba_dives) AS top, "
                       "(SELECT dives_before FROM scuba_settings WHERE id = 1) AS before").fetchone()
    return max(row["top"] or 0, row["before"] or 0) + 1


@router.post("/scuba/import")
async def import_file(request: Request, dry: bool = False):
    """A dive log file -> dives in the logbook. UDDF (.uddf / .xml) and Subsurface (.ssrf / .xml) are read; the file is
    the request body (or a multipart "file"). A dive already imported (same computer and start time) is skipped; new
    sites are made by name (with their position when the file has it); dives take the next free numbers in date order.
    dry=1 only shows what would happen."""
    try:
        if int(request.headers.get("content-length") or 0) > diveimport.MAX_BYTES + 4096:
            raise HTTPException(413, "That file is over 20 MB.")
    except ValueError:
        pass
    raw = _file_bytes(await request.body(), request.headers.get("content-type") or "")
    if not raw.strip():
        raise HTTPException(422, "That file is empty.")
    try:
        parsed = diveimport.parse(raw)
    except diveimport.DiveFileError as e:
        raise HTTPException(422, str(e))
    dives = sorted(parsed["dives"], key=lambda d: (d["dived_on"], d["time_in"] or ""))
    if not dives:
        raise HTTPException(422, "No dives found in that file.")
    added = skipped = 0
    listing = []
    with db() as conn:
        have = {r["import_key"] for r in conn.execute("SELECT import_key FROM scuba_dives WHERE import_key IS NOT NULL")}
        site_ids = {r["name"].strip().lower(): r["site_id"] for r in conn.execute("SELECT site_id, name FROM scuba_sites")}
        number = next_dive_no(conn)
        for d in dives:
            item = {"dived_on": d["dived_on"], "time_in": d["time_in"], "max_depth": d["max_depth"], "minutes": d["minutes"],
                    "site": d["site"]["name"] if d["site"] else None, "skipped": d["import_key"] in have}
            if item["skipped"]:
                skipped += 1
                listing.append(item)
                continue
            have.add(d["import_key"])
            added += 1
            if not dry:
                site_id = None
                if d["site"]:
                    key = d["site"]["name"].strip().lower()
                    if key not in site_ids:
                        site_ids[key] = insert_row(conn, "scuba_sites", {"name": d["site"]["name"].strip(), "lat": d["site"]["lat"],
                                                                         "lon": d["site"]["lon"]}, "site_id")
                    site_id = site_ids[key]
                row = {"dive_no": number, "dived_on": d["dived_on"], "time_in": d["time_in"], "site_id": site_id,
                       "max_depth": d["max_depth"], "avg_depth": d["avg_depth"], "minutes": d["minutes"],
                       "water_temp": d["water_temp"], "gas_o2": d["gas_o2"], "tank_l": d["tank_l"], "start_bar": d["start_bar"],
                       "end_bar": d["end_bar"], "suit": d["suit"], "buddy": d["buddy"], "guide": d["guide"], "rating": d["rating"],
                       "tags": d["tags"], "notes": d["notes"], "computer": d["computer"], "import_key": d["import_key"],
                       "samples": Jsonb(d["samples"]) if d["samples"] else None}
                item["dive_id"] = insert_row(conn, "scuba_dives", row, "dive_id")
                item["dive_no"] = number
                number += 1
            listing.append(item)
    return {"format": parsed["format"], "found": len(dives), "added": added, "skipped": skipped, "dry": dry, "dives": listing}


# ---------------------------------------------------------------- sea conditions

def verdict(wave, swell, wind, period=None) -> tuple[str, str]:
    """('good' | 'fair' | 'poor', why) for a day's biggest wave and swell (m) and strongest wind (km/h): a rough guide for
    boat and shore diving in SE Queensland, not a safety call. Missing figures are left out of the sum."""
    poor, fair = [], []
    if wave is not None:
        (poor if wave >= 2.0 else fair if wave >= 1.2 else []).append(f"waves to {wave:.1f} m")
    if swell is not None:
        (poor if swell >= 2.5 else fair if swell >= 1.5 else []).append(f"swell {swell:.1f} m")
    if wind is not None:
        (poor if wind >= 35 else fair if wind >= 25 else []).append(f"wind to {wind:.0f} km/h")
    if period is not None and swell is not None and swell >= 1.0 and period < 6:
        fair.append(f"short swell period ({period:.0f} s)")
    if poor:
        return "poor", "Rough: " + ", ".join(poor + fair)
    if fair:
        return "fair", "Marginal: " + ", ".join(fair)
    if wave is None and swell is None:
        return "fair", "No sea data for this spot (too close to land?)" + ("" if wind is None else f"; wind to {wind:.0f} km/h")
    return "good", "Small seas and light wind"


@router.get("/scuba/conditions")
def conditions(site_id: int | None = Query(None, ge=1, le=2147483647), lat: float | None = Query(None, ge=-90, le=90),
               lon: float | None = Query(None, ge=-180, le=180)):
    """The next 7 days' sea at a dive site (site_id) or a point (lat, lon): the biggest wave and swell, swell period and
    direction, sea temperature, tide highs and lows, the wind, and a verdict for the day."""
    place = None
    if site_id is not None:
        with db() as conn:
            site = found(conn.execute("SELECT name, lat, lon FROM scuba_sites WHERE site_id = %s", (site_id,)).fetchone(), "Dive site")
        if site["lat"] is None or site["lon"] is None:
            raise HTTPException(422, "That site has no position yet: add it, then the sea forecast can be found.")
        lat, lon, place = site["lat"], site["lon"], site["name"]
    elif lat is None or lon is None:
        raise HTTPException(422, "Give a dive site, or a latitude and longitude.")
    else:
        place = f"{lat:.2f}, {lon:.2f}"
    try:
        sea = openmeteo.marine(lat, lon)
    except openmeteo.WeatherError as e:
        raise HTTPException(502, str(e))
    try:
        winds = {d["day"]: d for d in openmeteo.wind(lat, lon)}
    except openmeteo.WeatherError:
        winds = {}                                       # the sea is the point: a day without wind figures still shows
    days = []
    for d in sea:
        w = (winds.get(d["day"]) or {}).get("wind_max")
        v, why = verdict(d["wave_max"], d["swell_max"], w, d["swell_period"])
        days.append({"date": d["day"], "wave_max": d["wave_max"], "swell_max": d["swell_max"], "swell_period": d["swell_period"],
                     "swell_dir": d["swell_dir"], "sst": d["sst"], "wind_max_kmh": w, "tide": d["tide"], "verdict": v, "why": why})
    return {"place": place, "lat": lat, "lon": lon, "days": days, "kept_since": openmeteo.kept_since(sea),
            "credit": CREDIT, "note": CAUTION}


# ---------------------------------------------------------------- dive sites from OpenStreetMap

def osm_site(el: dict) -> dict | None:
    """An Overpass element -> {osm, name, lat, lon, kind, depth_max, place}, None if it has no position."""
    tags = el.get("tags") or {}
    lat = el.get("lat") if el.get("lat") is not None else (el.get("center") or {}).get("lat")
    lon = el.get("lon") if el.get("lon") is not None else (el.get("center") or {}).get("lon")
    if lat is None or lon is None or el.get("type") not in ("node", "way", "relation") or not isinstance(el.get("id"), int):
        return None
    kind = None
    if tags.get("historic") == "wreck" or "wreck" in tags.get("seamark:type", "") or tags.get("wreck") or "wreck" in tags.get("name", "").lower():
        kind = "Wreck"
    elif tags.get("natural") == "reef" or "reef" in tags.get("name", "").lower():
        kind = "Reef"
    elif tags.get("natural") == "cave_entrance":
        kind = "Cave"
    depth = None
    for key in ("maxdepth", "depth"):
        try:
            v = float(str(tags.get(key, "")).split()[0].replace(",", "."))
        except (ValueError, IndexError):
            continue
        if 0 <= v <= 350:
            depth = v
            break
    return {"osm": f"{el['type']}/{el['id']}", "name": (tags.get("name") or "").strip() or None, "lat": lat, "lon": lon,
            "kind": kind, "depth_max": depth, "place": tags.get("addr:suburb") or tags.get("addr:city") or tags.get("is_in")}


@router.get("/scuba/osm/near")
def osm_near(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180), km: float = Query(30, ge=1, le=100)):
    """Named dive sites within km of a point, as OpenStreetMap has them (sport=scuba_diving; dive shops left out), nearest
    first, each with site_id if it's already one of yours. (Data (c) OpenStreetMap contributors, ODbL.)"""
    try:
        elements = overpass.scuba_sites_near(lat, lon, int(km * 1000))
    except overpass.OverpassError as e:
        raise HTTPException(502, str(e))
    with db() as conn:
        have = {r["osm"]: r["site_id"] for r in conn.execute("SELECT osm, site_id FROM scuba_sites WHERE osm IS NOT NULL")}
    sites, seen = [], set()
    for el in elements:
        s = osm_site(el)
        if not s or not s["name"] or s["osm"] in seen:
            continue
        seen.add(s["osm"])
        s["km"] = round(metres_between((lat, lon), (s["lat"], s["lon"])) / 1000, 1)
        s["site_id"] = have.get(s["osm"])
        sites.append(s)
    return sorted(sites, key=lambda s: s["km"])


class OsmImportIn(BaseModel):
    osm: str = Field(pattern=r"^(node|way|relation)/[0-9]{1,12}$")


@router.post("/scuba/osm/import", status_code=201)
def osm_import(body: OsmImportIn, response: Response):
    """One OpenStreetMap dive site as a new scuba site (name, position, kind, depth). Already imported: the site you have
    (200, existing true) - nothing of yours is overwritten."""
    with db() as conn:
        row = conn.execute("SELECT * FROM scuba_sites WHERE osm = %s", (body.osm,)).fetchone()
    if row:
        response.status_code = 200
        return {**row, "existing": True}
    try:
        elements = overpass.element(body.osm)
    except overpass.OverpassError as e:
        raise HTTPException(502, str(e))
    site = osm_site(elements[0]) if elements else None
    if not site:
        raise HTTPException(404, "OpenStreetMap has no such place (or it has no position).")
    with db() as conn:
        site_id = insert_row(conn, "scuba_sites", {
            "name": site["name"] or "Dive site", "place": site["place"], "lat": site["lat"], "lon": site["lon"],
            "kind": site["kind"], "depth_max": site["depth_max"], "osm": body.osm,
            "notes": "From OpenStreetMap (c) OpenStreetMap contributors, ODbL."}, "site_id")
        row = conn.execute("SELECT * FROM scuba_sites WHERE site_id = %s", (site_id,)).fetchone()
    return {**row, "existing": False}
