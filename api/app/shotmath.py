"""Precision shooting's arithmetic (pure: no database, no web).

    metres(distance, unit)        yards -> metres
    moa(size_mm, metres)          a size at a distance as an angle: 1 MOA = 29.09 mm at 100 m
    mil(size_mm, metres)          1 mil (milliradian) = 100 mm at 100 m
    velocity_stats([m/s ...])     average, SD (sample), ES - the chronograph numbers that matter at long range
    group_stats([(x, y)...])      from shot positions: size, centre, mean radius, width and height
    estimate(rows, distance)      elevation between distances you've confirmed (straight line between the nearest
                                  two - close enough between nearby distances; never beyond the furthest)
"""
import math

MM_PER_MOA_AT_100M = 29.0888        # 100 m x tan(1/60 degree)
YARD = 0.9144


def metres(distance: float, unit: str = "m") -> float:
    return distance * YARD if unit == "yd" else float(distance)


def moa(size_mm: float | None, at_m: float) -> float | None:
    if size_mm is None or not at_m:
        return None
    return size_mm / (MM_PER_MOA_AT_100M * at_m / 100)


def mil(size_mm: float | None, at_m: float) -> float | None:
    if size_mm is None or not at_m:
        return None
    return size_mm / at_m          # 1 mrad = 1 mm per metre of distance


def angle(size_mm: float | None, at_m: float, unit: str) -> float | None:
    """The size in the rifle's scope unit (MOA or MIL)."""
    return mil(size_mm, at_m) if unit == "MIL" else moa(size_mm, at_m)


def velocity_stats(values) -> dict | None:
    """{n, avg, sd, es, fps} from chronograph velocities (m/s); None for fewer than 2."""
    v = [float(x) for x in values or [] if x is not None]
    if len(v) < 2:
        return None
    avg = sum(v) / len(v)
    sd = math.sqrt(sum((x - avg) ** 2 for x in v) / (len(v) - 1))
    return {"n": len(v), "avg": round(avg, 1), "sd": round(sd, 1), "es": round(max(v) - min(v), 1), "fps": round(avg / 0.3048)}


def estimate(rows: list[dict], at_m: float) -> float | None:
    """Elevation at a distance from confirmed [{m, elevation}], straight between the nearest two around it.
    None outside what's confirmed (no guessing past your furthest or before your nearest)."""
    pts = sorted((r["m"], float(r["elevation"])) for r in rows if r.get("elevation") is not None)
    for (m1, e1), (m2, e2) in zip(pts, pts[1:]):
        if m1 <= at_m <= m2 and m2 > m1:
            return round(e1 + (e2 - e1) * (at_m - m1) / (m2 - m1), 2)
    return next((e for m, e in pts if m == at_m), None)


def group_stats(points) -> dict | None:
    """From shot positions [(x_mm, y_mm)...] (right / up of the aim point): the group's size (centre to centre of the
    two furthest apart), its centre, mean radius (the average distance of each shot from the centre - steadier
    than size, which only looks at two shots), and how wide and tall it is."""
    pts = [(float(x), float(y)) for x, y in points]
    if not pts:
        return None
    cx = sum(x for x, _ in pts) / len(pts)
    cy = sum(y for _, y in pts) / len(pts)
    size = max((math.dist(a, b) for i, a in enumerate(pts) for b in pts[i + 1:]), default=0.0)
    return {"size_mm": round(size, 1), "right_mm": round(cx, 1), "up_mm": round(cy, 1),
            "mean_radius_mm": round(sum(math.dist(p, (cx, cy)) for p in pts) / len(pts), 1),
            "width_mm": round(max(x for x, _ in pts) - min(x for x, _ in pts), 1),
            "height_mm": round(max(y for _, y in pts) - min(y for _, y in pts), 1)}
