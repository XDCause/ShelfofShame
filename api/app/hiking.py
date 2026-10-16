"""Hiking (a hobby module): hikes imported from GPX files - AllTrails' export, or any GPS app's - or
logged by hand.

    import    POST /hiking/import?filename=   the GPX file as the body (gpx.py works out the numbers:
              distance, moving / total time, climb, highest / lowest point, per-km splits, waypoints,
              the route for drawing, loop or one way, and the AllTrails trail link if the file has one).
              The same file twice is skipped (its sha256 is kept). The file itself is kept too.
              Then, in the background, the landmarks near the track (OpenStreetMap, overpass.py) and
              photos people took near it (Wikimedia Commons, wikimedia.py) are looked up and saved.
    hikes     the list (search, year), one hike with its track, add one by hand, change, remove,
              the original GPX back
    photos    your own photos of a hike: each is placed on the track by its GPS position, or by the time
              it was taken (both read from the photo's EXIF in the browser, before it's shrunk)
    landmarks POST /hiking/hikes/{id}/landmarks   look them up again
    summary   this year and all time, km per month (last 12), personal bests, the latest hikes
"""
import logging
import math
import os
import re
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import gpx, overpass, wikimedia
from .db import db, found, insert_row, tidy_text, update_row
from .images import photo_response, read_photo

router = APIRouter(prefix="/api", tags=["hiking"])
log = logging.getLogger("hiking")
LOOKING: set[int] = set()            # hikes whose landmarks are being looked up right now

COLUMNS = """
SELECT hike_id, name, hiked_on, started_at, ended_at, distance_m::float8 AS distance_m, moving_s, elapsed_s,
       ascent_m::float8 AS ascent_m, descent_m::float8 AS descent_m, max_ele_m::float8 AS max_ele_m,
       min_ele_m::float8 AS min_ele_m, start_lat, start_lon, is_loop, points, trail_name, trail_url, location,
       difficulty, rating, companions, weather, notes, source, gpx_name, created_at,
       (SELECT count(*) FROM hike_photos p WHERE p.hike_id = hikes.hike_id) AS photos_count,
       (SELECT '/api/hiking/photos/' || p.photo_id FROM hike_photos p WHERE p.hike_id = hikes.hike_id
        ORDER BY p.along_m NULLS LAST, p.taken_at NULLS LAST, p.photo_id LIMIT 1) AS photo_url"""
PHOTOS = """
SELECT photo_id, hike_id, '/api/hiking/photos/' || photo_id AS url, taken_at, lat, lon, along_m::float8 AS along_m,
       located, caption
FROM hike_photos"""


class HikeFields(BaseModel):
    trail_name: str | None = Field(None, max_length=200)
    trail_url: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=200)
    difficulty: str | None = Field(None, pattern="^(Easy|Moderate|Hard)$")
    rating: int | None = Field(None, ge=1, le=5)
    companions: str | None = Field(None, max_length=500)
    weather: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=20000)
    distance_km: float | None = Field(None, ge=0, le=1000)
    moving_min: int | None = Field(None, ge=0, le=60 * 24 * 14)
    ascent_m: float | None = Field(None, ge=0, le=20000)


class HikeIn(HikeFields):
    """A hike logged by hand (no GPS file)."""
    name: str = Field(min_length=1, max_length=200)
    hiked_on: date


class HikePatch(HikeFields):
    name: str | None = Field(None, min_length=1, max_length=200)
    hiked_on: date | None = None


def _columns(data: dict) -> dict:
    """The form's km / minutes -> the table's metres / seconds; blank text -> None."""
    data = tidy_text(data, required=("name",))
    if "distance_km" in data:
        km = data.pop("distance_km")
        data["distance_m"] = round(km * 1000, 1) if km is not None else None
    if "moving_min" in data:
        mins = data.pop("moving_min")
        data["moving_s"] = mins * 60 if mins is not None else None
    if data.get("trail_url") and not re.match(r"^https?://", data["trail_url"]):
        raise HTTPException(422, "A trail link must start with http:// or https://.")
    return data


def fetch(conn, hike_id: int) -> dict:
    """One hike with everything: the route, splits, waypoints, your photos, landmarks and nearby photos."""
    hike = found(conn.execute(COLUMNS + ", track, splits, waypoints, landmarks, nearby_photos, landmarks_at, landmarks_error "
                              "FROM hikes WHERE hike_id = %s", (hike_id,)).fetchone(), "Hike")
    hike["photos"] = conn.execute(PHOTOS + " WHERE hike_id = %s ORDER BY along_m NULLS LAST, taken_at NULLS LAST, photo_id",
                                  (hike_id,)).fetchall()
    hike["landmarks_looking"] = hike_id in LOOKING
    return hike


@router.post("/hiking/import", status_code=201)
async def import_gpx(request: Request, response: Response, background: BackgroundTasks,
                     filename: str | None = Query(None, max_length=255)):
    """A GPX file as the body. Answers the new hike - or, for a file imported before, that hike with
    duplicate = true (nothing changes). Its landmarks are then looked up in the background."""
    raw = await request.body()
    try:
        g = gpx.parse(raw)
    except gpx.GpxError as e:
        raise HTTPException(422, str(e))
    with db() as conn:
        old = conn.execute("SELECT hike_id FROM hikes WHERE gpx_hash = %s", (g["hash"],)).fetchone()
        if old:
            response.status_code = 200
            return {**fetch(conn, old["hike_id"]), "duplicate": True}
        stem = re.sub(r"[_\-]+", " ", re.sub(r"\.gpx$", "", filename or "", flags=re.I)).strip()
        # The day it was hiked, in the app's time zone (GPX times are UTC). A route without times: today.
        hiked_on = conn.execute("SELECT COALESCE((%s::timestamptz AT TIME ZONE current_setting('TimeZone'))::date, "
                                "current_date) AS d", (g["started_at"],)).fetchone()["d"]
        data = {k: g[k] for k in ("started_at", "ended_at", "distance_m", "moving_s", "elapsed_s", "ascent_m", "descent_m",
                                  "max_ele_m", "min_ele_m", "start_lat", "start_lon", "is_loop", "points", "trail_url")}
        data.update(name=(g["name"] or stem or "Hike")[:200], hiked_on=hiked_on, notes=g["description"], source="gpx",
                    gpx_name=(filename or "track.gpx")[:255], gpx_hash=g["hash"], gpx=raw,
                    track=Jsonb(g["track"]), splits=Jsonb(g["splits"]), waypoints=Jsonb(g["waypoints"]))
        hike_id = insert_row(conn, "hikes", data, "hike_id")
        # DAILY_SYNCS=off = the walk-through's throwaway copy: it doesn't ask OpenStreetMap on every run.
        if os.environ.get("DAILY_SYNCS", "on") != "off":
            LOOKING.add(hike_id)
            background.add_task(look_up_landmarks, hike_id)
        return {**fetch(conn, hike_id), "duplicate": False}


@router.get("/hiking/hikes")
def list_hikes(q: str | None = Query(None, max_length=100), year: int | None = Query(None, ge=1900, le=2200)):
    """Every hike, newest first (q = search the name, trail, place, people and notes)."""
    with db() as conn:
        return conn.execute(COLUMNS + """ FROM hikes
            WHERE (%(q)s::text IS NULL OR concat_ws(' ', name, trail_name, location, companions, notes) ILIKE '%%' || %(q)s || '%%')
              AND (%(year)s::int IS NULL OR extract(year FROM hiked_on) = %(year)s)
            ORDER BY hiked_on DESC, started_at DESC NULLS LAST, hike_id DESC""",
                            {"q": (q or "").strip() or None, "year": year}).fetchall()


@router.post("/hiking/hikes", status_code=201)
def add_hike(body: HikeIn):
    with db() as conn:
        return fetch(conn, insert_row(conn, "hikes", {**_columns(body.model_dump()), "source": "manual"}, "hike_id"))


@router.get("/hiking/hikes/{hike_id}")
def get_hike(hike_id: int):
    with db() as conn:
        return fetch(conn, hike_id)


@router.patch("/hiking/hikes/{hike_id}")
def update_hike(hike_id: int, body: HikePatch):
    data = _columns(body.model_dump(exclude_unset=True))
    for required in ("name", "hiked_on"):
        if required in data and not data[required]:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        fetch(conn, hike_id)
        update_row(conn, "hikes", "hike_id", hike_id, data)
        return fetch(conn, hike_id)


@router.delete("/hiking/hikes/{hike_id}", status_code=204)
def delete_hike(hike_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM hikes WHERE hike_id = %s RETURNING hike_id", (hike_id,)).fetchone(), "Hike")
    return Response(status_code=204)


@router.get("/hiking/hikes/{hike_id}/gpx")
def download_gpx(hike_id: int):
    """The GPX file exactly as it was imported."""
    with db() as conn:
        row = found(conn.execute("SELECT gpx, gpx_name FROM hikes WHERE hike_id = %s", (hike_id,)).fetchone(), "Hike")
    if row["gpx"] is None:
        raise HTTPException(404, "This hike was logged by hand, so it has no GPX file.")
    name = re.sub(r"[^\w .-]+", "", row["gpx_name"] or "") or "hike.gpx"
    return Response(bytes(row["gpx"]), media_type="application/gpx+xml",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})



@router.get("/hiking/summary")
def summary():
    """This year and all time, km per month for the last 12 months, personal bests, the latest hikes."""
    totals = """SELECT count(*) AS hikes, COALESCE(sum(distance_m), 0)::float8 / 1000 AS km,
                       COALESCE(sum(ascent_m), 0)::float8 AS ascent_m, COALESCE(sum(COALESCE(moving_s, elapsed_s)), 0) AS seconds,
                       count(DISTINCT trail_name) FILTER (WHERE trail_name IS NOT NULL) AS trails
                FROM hikes"""
    with db() as conn:
        year = conn.execute("SELECT extract(year FROM current_date)::int AS y").fetchone()["y"]
        this_year = conn.execute(totals + " WHERE hiked_on >= date_trunc('year', current_date)").fetchone()
        all_time = conn.execute(totals).fetchone()
        months = conn.execute("""
            SELECT to_char(m, 'YYYY-MM') AS month, COALESCE(sum(h.distance_m), 0)::float8 / 1000 AS km, count(h.hike_id) AS hikes
            FROM generate_series(date_trunc('month', current_date) - interval '11 months', date_trunc('month', current_date),
                                 interval '1 month') m
            LEFT JOIN hikes h ON date_trunc('month', h.hiked_on) = m
            GROUP BY m ORDER BY m""").fetchall()

        def best(order: str, where: str = "TRUE"):
            return conn.execute(COLUMNS + f" FROM hikes WHERE {where} ORDER BY {order}, hiked_on DESC LIMIT 1").fetchone()
        bests = {
            "longest": best("distance_m DESC", "distance_m > 0"),
            "climb": best("ascent_m DESC", "ascent_m > 0"),
            "highest": best("max_ele_m DESC", "max_ele_m IS NOT NULL"),
            "fastest": best("moving_s / distance_m", "moving_s > 0 AND distance_m >= 3000"),
        }
        recent = conn.execute(COLUMNS + " FROM hikes ORDER BY hiked_on DESC, started_at DESC NULLS LAST, hike_id DESC LIMIT 5").fetchall()
    return {"year": year, "this_year": this_year, "all_time": all_time, "months": months, "bests": bests, "recent": recent}


# ---------------------------------------------------------------------------------------------
# Where things are along the track
# ---------------------------------------------------------------------------------------------
def nearest(track: list, lat: float, lon: float) -> tuple[int, float]:
    """The track point closest to (lat, lon): its index and how far away it is (metres)."""
    best, best_d = 0, math.inf
    for i, p in enumerate(track):
        d = gpx.metres(p, (lat, lon))
        if d < best_d:
            best, best_d = i, d
    return best, best_d


def at_time(track: list, seconds: float):
    """Where you were `seconds` after the start (between two track points, in proportion), or None."""
    timed = [p for p in track if p[3] is not None]
    if len(timed) < 2 or not (-600 <= seconds <= timed[-1][3] + 600):
        return None
    seconds = min(max(seconds, timed[0][3]), timed[-1][3])
    for a, b in zip(timed, timed[1:]):
        if a[3] <= seconds <= b[3]:
            f = (seconds - a[3]) / ((b[3] - a[3]) or 1)
            return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[4] + (b[4] - a[4]) * f
    return None


def place(track, started_at, lat, lon, taken_at):
    """(lat, lon, along_m, located) for a photo: its own GPS position (on the track if within 1 km),
    or where the track was at the time it was taken."""
    if lat is not None and lon is not None:
        if track:
            i, off = nearest(track, lat, lon)
            return lat, lon, (track[i][4] if off <= 1000 else None), "gps"
        return lat, lon, None, "gps"
    if track and taken_at and started_at:
        spot = at_time(track, (taken_at - started_at).total_seconds())
        if spot:
            return round(spot[0], 6), round(spot[1], 6), round(spot[2], 1), "time"
    return None, None, None, None


# ---------------------------------------------------------------------------------------------
# Your photos
# ---------------------------------------------------------------------------------------------
class PhotoPatch(BaseModel):
    caption: str | None = Field(None, max_length=500)


@router.post("/hiking/hikes/{hike_id}/photos", status_code=201)
async def add_photo(hike_id: int, request: Request,
                    lat: float | None = Query(None, ge=-90, le=90), lon: float | None = Query(None, ge=-180, le=180),
                    taken: str | None = Query(None, max_length=40), caption: str | None = Query(None, max_length=500)):
    """A photo (the body, shrunk by the browser). lat / lon / taken come from its EXIF; `taken` without
    a time zone is read in the app's (that's how cameras store it)."""
    image, image_type = await read_photo(request)
    with db() as conn:
        hike = found(conn.execute("SELECT track, started_at FROM hikes WHERE hike_id = %s", (hike_id,)).fetchone(), "Hike")
        taken_at = None
        if taken:
            try:
                t = datetime.fromisoformat(taken.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(422, "The photo's time isn't a date and time.") from None
            taken_at = t if t.tzinfo else conn.execute(
                "SELECT %s::timestamp AT TIME ZONE current_setting('TimeZone') AS t", (t,)).fetchone()["t"]
        plat, plon, along, located = place(hike["track"], hike["started_at"], lat, lon, taken_at)
        photo_id = insert_row(conn, "hike_photos", {
            "hike_id": hike_id, "image": image, "image_type": image_type, "taken_at": taken_at, "lat": plat, "lon": plon,
            "along_m": along, "located": located, "caption": (caption or "").strip() or None}, "photo_id")
        return conn.execute(PHOTOS + " WHERE photo_id = %s", (photo_id,)).fetchone()


@router.get("/hiking/photos/{photo_id}")
def get_photo(photo_id: int):
    """A photo never changes (a new one gets a new id), so it's cached for a year."""
    with db() as conn:
        row = found(conn.execute("SELECT image, image_type FROM hike_photos WHERE photo_id = %s", (photo_id,)).fetchone(),
                    "Photo")
    return photo_response(row["image"], row["image_type"])


@router.patch("/hiking/photos/{photo_id}")
def update_photo(photo_id: int, body: PhotoPatch):
    with db() as conn:
        found(conn.execute("UPDATE hike_photos SET caption = %s WHERE photo_id = %s RETURNING photo_id",
                           ((body.caption or "").strip() or None, photo_id)).fetchone(), "Photo")
        return conn.execute(PHOTOS + " WHERE photo_id = %s", (photo_id,)).fetchone()


@router.delete("/hiking/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM hike_photos WHERE photo_id = %s RETURNING photo_id", (photo_id,)).fetchone(), "Photo")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Landmarks and photos near the track
# ---------------------------------------------------------------------------------------------
LANDMARK_RADIUS = 250       # metres from the track
PHOTO_RADIUS = 200
MAX_LANDMARKS = 60
MAX_NEARBY = 12
PER_AUTHOR = 2              # nearby photos from any one photographer
# Facilities count only when they're on the track, and an unnamed one at most once a kilometre per kind
# (a trailhead can have a dozen picnic tables and toilet blocks).
FACILITIES = {"picnic_site", "toilets", "shelter", "drinking_water", "camp_site"}
FACILITY_RADIUS = 80


def spread(track: list, n: int) -> list:
    """n points evenly along the track (for a short query line)."""
    if len(track) <= n:
        return track
    if n == 1:
        return [track[len(track) // 2]]
    return [track[round(i * (len(track) - 1) / (n - 1))] for i in range(n)]


def find_landmarks(track: list) -> list[dict]:
    """Landmarks within LANDMARK_RADIUS of the track, in the order you pass them, with their photo if
    OpenStreetMap links one (wikimedia_commons, or the wikidata item's photo)."""
    found_ = overpass.landmarks(overpass.near_line([(p[0], p[1]) for p in spread(track, 60)], LANDMARK_RADIUS))
    near = []
    for lm in found_:
        i, off = nearest(track, lm["lat"], lm["lon"])
        if off <= (FACILITY_RADIUS if lm["kind"] in FACILITIES else LANDMARK_RADIUS + 50):
            near.append({**lm, "along_m": track[i][4], "off_m": round(off)})
    near.sort(key=lambda lm: lm["along_m"])
    out, last = [], {}
    for lm in near:
        if lm["kind"] in FACILITIES and not lm["name"]:
            if lm["along_m"] - last.get(lm["kind"], -1e9) < 1000:
                continue
            last[lm["kind"]] = lm["along_m"]
        out.append(lm)
    out = out[:MAX_LANDMARKS]
    files = wikimedia.wikidata_images([lm["wikidata"] for lm in out if lm["wikidata"] and not lm["commons"]])
    for lm in out:
        lm["commons"] = lm["commons"] or files.get(lm["wikidata"])
    info = wikimedia.images([lm["commons"] for lm in out if lm["commons"]])
    for lm in out:
        lm["photo"] = info.get(lm.pop("commons"))
    return out


def find_nearby_photos(track: list) -> list[dict]:
    """Up to MAX_NEARBY Commons photos taken within PHOTO_RADIUS of the track, spread along it. Asked
    around up to 4 points along the way (each search reaches at most 10 km)."""
    total = track[-1][4] or 1
    centres = spread(track, max(1, min(4, math.ceil(total / 15000))))
    seen, near = set(), []
    for c in centres:
        reach = max((gpx.metres(c, p) for p in track), default=0) if len(centres) == 1 else 10000
        for f in wikimedia.near(c[0], c[1], reach + PHOTO_RADIUS, limit=200):
            if f["title"] in seen:
                continue
            seen.add(f["title"])
            i, off = nearest(track, f["lat"], f["lon"])
            if off <= PHOTO_RADIUS:
                near.append({**f, "along_m": track[i][4], "off_m": round(off)})
    near.sort(key=lambda f: f["along_m"])
    if len(near) > MAX_NEARBY * 4:               # evenly along the way, not all at the car park
        near = [near[round(i * (len(near) - 1) / (MAX_NEARBY * 4 - 1))] for i in range(MAX_NEARBY * 4)]
    info = wikimedia.images([f["title"] for f in near])
    # One from each stretch of the track in turn, at most PER_AUTHOR per photographer.
    buckets = [[] for _ in range(MAX_NEARBY)]
    for f in near:
        if f["title"] in info:
            buckets[min(MAX_NEARBY - 1, int(f["along_m"] / total * MAX_NEARBY))].append({**f, **info[f["title"]]})
    picked, by = [], {}
    while len(picked) < MAX_NEARBY and any(buckets):
        for b in buckets:
            while b and len(picked) < MAX_NEARBY:
                f = b.pop(0)
                if by.get(f["author"], 0) < PER_AUTHOR:
                    by[f["author"]] = by.get(f["author"], 0) + 1
                    picked.append(f)
                    break
    return sorted(picked, key=lambda f: f["along_m"])


def look_up_landmarks(hike_id: int):
    """In the background: landmarks and nearby photos for one hike, saved with any error (each part
    is kept even if the other fails)."""
    LOOKING.add(hike_id)
    try:
        with db() as conn:
            row = conn.execute("SELECT track FROM hikes WHERE hike_id = %s", (hike_id,)).fetchone()
        track = row and row["track"]
        if not track or len(track) < 2:
            return
        landmarks = photos = None
        errors = []
        try:
            landmarks = find_landmarks(track)
        except Exception as e:  # noqa: BLE001 - shown on the hike; the photos may still work
            log.warning("Landmarks for hike %s: %s", hike_id, e)
            errors.append(str(e))
        try:
            photos = find_nearby_photos(track)
        except Exception as e:  # noqa: BLE001
            log.warning("Nearby photos for hike %s: %s", hike_id, e)
            errors.append(str(e))
        with db() as conn:
            conn.execute("""UPDATE hikes SET landmarks = COALESCE(%s, landmarks), nearby_photos = COALESCE(%s, nearby_photos),
                                landmarks_at = now(), landmarks_error = %s WHERE hike_id = %s""",
                         (Jsonb(landmarks) if landmarks is not None else None, Jsonb(photos) if photos is not None else None,
                          " ".join(errors)[:500] or None, hike_id))
    finally:
        LOOKING.discard(hike_id)


@router.post("/hiking/hikes/{hike_id}/landmarks", status_code=202)
def refresh_landmarks(hike_id: int, background: BackgroundTasks):
    """Look for landmarks and nearby photos again (in the background; the hike says when it's done)."""
    with db() as conn:
        hike = found(conn.execute("SELECT track FROM hikes WHERE hike_id = %s", (hike_id,)).fetchone(), "Hike")
    if not hike["track"]:
        raise HTTPException(409, "This hike has no GPS track to look along.")
    if hike_id not in LOOKING:
        LOOKING.add(hike_id)
        background.add_task(look_up_landmarks, hike_id)
    return {"looking": True}
