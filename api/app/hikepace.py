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
