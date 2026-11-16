"""Hiking time estimates: Naismith's rule, Tobler's downhill speed, and your own pace fitted from past hikes.

Naismith's rule: 5 km/h on the flat plus 1 hour for every 600 m climbed.
Tobler's hiking function: walking speed (km/h) = 6 * exp(-3.5 * |slope + 0.05|), so a gentle downhill is the
fastest ground and a steep one slows you down again. We use it only for the DOWNHILL stretches, as an
adjustment on top of the flat time (steep descents cost time, gentle ones save some).

Your own pace: a least-squares fit over hikes that have a timed track,
    moving hours - descent adjustment = km / flat_speed + metres_up / climb_rate
which gives your moving speed on the flat (km/h) and the metres you climb per hour. With too few hikes, or
silly answers, we fall back to Naismith's numbers.
"""
import math

from .gpx import metres as _apart

NAISMITH_KMH = 5.0
NAISMITH_UP_MPH = 600.0
MIN_HIKES = 3                        # fewer timed hikes than this: use Naismith's numbers
FLAT_RANGE = (2.0, 8.0)              # km/h a fitted flat speed must lie in
CLIMB_RANGE = (150.0, 1200.0)        # metres per hour a fitted climb rate must lie in
STRETCH_M = 50.0                     # downhill stretches are judged over at least this far


def tobler_kmh(slope: float) -> float:
    """Tobler's walking speed (km/h) for a slope (rise over run; downhill is negative)."""
    return 6.0 * math.exp(-3.5 * abs(slope + 0.05))


def descent_adjustment_h(track: list, base_kmh: float = NAISMITH_KMH) -> float:
    """Hours to ADD (or take off, if negative) for the downhill stretches of a track, against walking them
    flat at base_kmh. The track is the stored list of [lat, lon, ele, seconds, metres along]."""
    pts = [p for p in track if p[2] is not None and p[4] is not None]
    if len(pts) < 2:
        return 0.0
    scale = base_kmh / NAISMITH_KMH            # a slower walker is slower downhill too
    total, start = 0.0, 0
    for i in range(1, len(pts)):
        run = pts[i][4] - pts[start][4]
        if run < STRETCH_M and i < len(pts) - 1:
            continue
        if run > 0:
            slope = (pts[i][2] - pts[start][2]) / run
            if slope < 0:
                total += run / 1000 / (tobler_kmh(slope) * scale) - run / 1000 / base_kmh
        start = i
    return total


def naismith_h(distance_m: float, ascent_m: float) -> float:
    return distance_m / 1000 / NAISMITH_KMH + (ascent_m or 0) / NAISMITH_UP_MPH


def fit_pace(rows: list[dict]) -> dict:
    """rows: one per timed hike: {distance_m, ascent_m, moving_s, descent_h} (descent_h = descent_adjustment_h).
    Answers {flat_kmh, climb_mph, hikes, fitted}: fitted False means Naismith's numbers (too little to go on)."""
    fallback = {"flat_kmh": NAISMITH_KMH, "climb_mph": NAISMITH_UP_MPH, "hikes": len(rows), "fitted": False}
    rows = [r for r in rows if (r["moving_s"] or 0) > 0 and (r["distance_m"] or 0) >= 2000]
    fallback["hikes"] = len(rows)
    if len(rows) < MIN_HIKES:
        return fallback
    # y = a * km + b * up, with a = 1 / flat speed and b = 1 / climb rate. Solve the 2x2 normal equations.
    sxx = sxy = syy = sx_y = sy_y = 0.0
    for r in rows:
        x1, x2 = r["distance_m"] / 1000, (r["ascent_m"] or 0)
        y = r["moving_s"] / 3600 - r.get("descent_h", 0.0)
        sxx += x1 * x1
        sxy += x1 * x2
        syy += x2 * x2
        sx_y += x1 * y
        sy_y += x2 * y
    det = sxx * syy - sxy * sxy
    if abs(det) < 1e-9:                         # every hike equally steep: can't tell flat from climbing apart
        return fallback
    a = (sx_y * syy - sy_y * sxy) / det
    b = (sy_y * sxx - sx_y * sxy) / det
    if a <= 0 or b <= 0:
        return fallback
    flat, climb = 1 / a, 1 / b
    if not (FLAT_RANGE[0] <= flat <= FLAT_RANGE[1] and CLIMB_RANGE[0] <= climb <= CLIMB_RANGE[1]):
        return fallback
    return {"flat_kmh": round(flat, 2), "climb_mph": round(climb), "hikes": len(rows), "fitted": True}


def estimate(distance_m: float, ascent_m: float, track: list, pace: dict) -> dict:
    """Seconds for a route: Naismith's rule (with Tobler's downhill adjustment) and your own pace."""
    ascent = ascent_m or 0
    naismith = naismith_h(distance_m, ascent) + descent_adjustment_h(track)
    flat, climb = pace["flat_kmh"], pace["climb_mph"]
    yours = distance_m / 1000 / flat + ascent / climb + descent_adjustment_h(track, flat)
    return {"naismith_s": round(max(naismith, 0) * 3600), "personal_s": round(max(yours, 0) * 3600)}


# ---------------------------------------------------------------------------------------------
# The same trail again, and the year's tracks
# ---------------------------------------------------------------------------------------------
SAME_TRAIL_M = 200          # two hikes whose starts and finishes are this close (and about as long) are the same trail
LENGTH_SLACK = 0.35         # ...and their distances may differ by this much (a loop isn't its short cut)


def _clock(h: dict):
    """The time to compare: moving time, else the whole time."""
    return h.get("moving_s") or h.get("elapsed_s") or None


def same_trail(a: dict, b: dict) -> bool:
    """Are two hikes on the same trail? The same trail name, or starts and finishes within 200 m. Either way the
    distances must be alike (when both are known). Hikes: {trail_name, start_lat, start_lon, end_lat, end_lon, distance_m}."""
    da, db = a.get("distance_m"), b.get("distance_m")
    if da and db and abs(da - db) > LENGTH_SLACK * max(da, db):
        return False
    na, nb = (a.get("trail_name") or "").strip().casefold(), (b.get("trail_name") or "").strip().casefold()
    if na and na == nb:
        return True
    keys = ("start_lat", "start_lon", "end_lat", "end_lon")
    if any(h.get(k) is None for h in (a, b) for k in keys):
        return False
    return (_apart((a["start_lat"], a["start_lon"]), (b["start_lat"], b["start_lon"])) <= SAME_TRAIL_M
            and _apart((a["end_lat"], a["end_lon"]), (b["end_lat"], b["end_lon"])) <= SAME_TRAIL_M)


def compare_runs(this: dict, others: list[dict]) -> dict | None:
    """This hike against your other hikes on the trail: every run (oldest first) with its time, the best, this one's
    rank, and how far off the best and the average it was. Needs a timed hike and one other timed run; else None."""
    runs = [h for h in [this, *others] if _clock(h)]
    if _clock(this) is None or len(runs) < 2:
        return None
    best = min(runs, key=lambda h: (_clock(h), h["hiked_on"]))
    times = sorted(_clock(h) for h in runs)
    rows = [{"hike_id": h["hike_id"], "name": h["name"], "hiked_on": h["hiked_on"], "seconds": _clock(h),
             "distance_m": h.get("distance_m"), "ascent_m": h.get("ascent_m"), "is_this": h["hike_id"] == this["hike_id"],
             "is_best": h["hike_id"] == best["hike_id"]} for h in sorted(runs, key=lambda h: (h["hiked_on"], h["hike_id"]))]
    return {"runs": rows, "best_id": best["hike_id"], "rank": times.index(_clock(this)) + 1, "of": len(runs),
            "behind_best_s": _clock(this) - _clock(best), "average_s": round(sum(times) / len(times))}


def split_gaps(this: list | None, best: list | None) -> list[dict]:
    """Kilometre by kilometre: your split against the best run's (seconds; negative = you were quicker). Whole
    kilometres only, as far as both have them."""
    out = []
    for a, b in zip(this or [], best or []):
        if a.get("metres", 0) >= 900 and b.get("metres", 0) >= 900 and a.get("seconds") and b.get("seconds"):
            out.append({"km": a["km"], "seconds": a["seconds"], "best_seconds": b["seconds"], "gap_s": a["seconds"] - b["seconds"]})
    return out


def thin_track(track: list | None, n: int = 120) -> list[list[float]]:
    """At most about n [lat, lon] points of a stored track (every k-th, always keeping the last), for drawing."""
    pts = [p for p in track or [] if p and p[0] is not None and p[1] is not None]
    if len(pts) <= n:
        return [[round(p[0], 5), round(p[1], 5)] for p in pts]
    step = len(pts) / (n - 1)
    keep = [pts[int(i * step)] for i in range(n - 1)] + [pts[-1]]
    return [[round(p[0], 5), round(p[1], 5)] for p in keep]
