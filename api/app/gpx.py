"""GPX files -> a hike's numbers (AllTrails' export, or any GPS app's: Strava, Garmin, Samsung Health...).
Pure functions, no database: hiking.py stores what parse() returns.

GPX is XML: <trk> (a recording) holds <trkseg> segments (a new one after a pause) of <trkpt lat lon>
points, each with <ele> (metres) and <time>. A planned route (<rte>, or a track without times) has
no times, so only distance and climb are worked out. <wpt> = a named point (a lookout, the car park).

    distance   along the track, segment by segment (a pause's gap isn't walked)
    moving     time between points while going faster than MOVING (about 1 km/h); elapsed = start to end
    climb      elevation smoothed over 5 points, then only changes of CLIMB_STEP or more count (GPS
               elevation wobbles a few metres even standing still - counting every wobble doubles the climb)
    splits     each kilometre: moving time and metres up / down
    track      at most KEEP points, evenly spread along the way, for drawing the route and the profile
"""
import hashlib
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

MAX_BYTES = 30_000_000
EARTH = 6_371_000.0         # metres
MOVING = 0.3                # metres a second
CLIMB_STEP = 3.0            # metres
KEEP = 1500
LOOP_GAP = 250              # metres between the start and the end: a loop, not one way


class GpxError(ValueError):
    """The file isn't a GPX file we can read; the message says why, for the person importing it."""


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _children(el, name: str):
    return [c for c in el if _local(c.tag) == name]


def _text(el, name: str) -> str | None:
    if el is None:
        return None
    for c in _children(el, name):
        if c.text and c.text.strip():
            return c.text.strip()
    return None


def _float(text: str | None) -> float | None:
    try:
        v = float(text) if text is not None else None
    except ValueError:
        return None
    return v if v is not None and math.isfinite(v) else None


def _time(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)      # GPX times are UTC


def metres(a, b) -> float:
    """Straight-line distance between two (lat, lon, ...) points over the earth's surface (haversine)."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH * math.asin(min(1.0, math.sqrt(h)))


def _point(el):
    lat, lon = _float(el.get("lat")), _float(el.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return (lat, lon, _float(_text(el, "ele")), _time(_text(el, "time")))


def _smooth(values: list[float | None], width: int = 5) -> list[float | None]:
    """A moving average over the points that have an elevation (the others stay None). The window
    narrows evenly at the ends, so the first and last points (the start and the summit) keep their height."""
    have = [i for i, v in enumerate(values) if v is not None]
    out = [None] * len(values)
    for n, i in enumerate(have):
        half = min(width // 2, n, len(have) - 1 - n)
        near = [values[have[j]] for j in range(n - half, n + half + 1)]
        out[i] = sum(near) / len(near)
    return out


def measure(segments: list[list[tuple]]) -> dict:
    """The numbers for a track: segments of (lat, lon, ele, time) points."""
    flat, moving, total = [], 0.0, 0.0        # flat: (lat, lon, ele, time, metres so far, moving seconds so far)
    for seg in segments:
        prev = None
        for p in seg:
            if prev is not None:
                d = metres(prev, p)
                total += d
                if p[3] and prev[3]:
                    dt = (p[3] - prev[3]).total_seconds()
                    if dt > 0 and d / dt >= MOVING:
                        moving += dt
            flat.append((*p, total, moving))
            prev = p
    ele = _smooth([p[2] for p in flat])
    ascent = descent = 0.0
    ref = None
    for e in ele:
        if e is None:
            continue
        if ref is None or e - ref >= CLIMB_STEP:
            ascent += e - ref if ref is not None else 0
            ref = e
        elif ref - e >= CLIMB_STEP:
            descent += ref - e
            ref = e
    known = [e for e in ele if e is not None]
    times = [p[3] for p in flat if p[3]]
    start, end = (min(times), max(times)) if times else (None, None)
    timed = start is not None and end > start

    splits, km, last_i = [], 1, 0
    for i, p in enumerate(flat):
        if p[4] >= km * 1000 or (i == len(flat) - 1 and p[4] - flat[last_i][4] >= 50):
            ups = [ele[j] for j in range(last_i, i + 1) if ele[j] is not None]
            splits.append({
                "km": km, "metres": round(p[4] - flat[last_i][4]),
                "seconds": round(p[5] - flat[last_i][5]) if timed else None,
                "ascent": round(sum(max(0, b - a) for a, b in zip(ups, ups[1:]))),
                "descent": round(sum(max(0, a - b) for a, b in zip(ups, ups[1:]))),
            })
            km, last_i = km + 1, i

    keep = list(range(len(flat)))
    if len(flat) > KEEP:
        gap, keep, at = total / KEEP, [0], 0.0
        for i in range(1, len(flat) - 1):
            if flat[i][4] - at >= gap:
                keep.append(i)
                at = flat[i][4]
        keep.append(len(flat) - 1)
    track = [[round(flat[i][0], 6), round(flat[i][1], 6), round(ele[i], 1) if ele[i] is not None else None,
              round((flat[i][3] - start).total_seconds()) if flat[i][3] and start else None, round(flat[i][4], 1)]
             for i in keep]

    return {
        "distance_m": round(total, 1),
        "moving_s": round(moving) if timed else None,
        "elapsed_s": round((end - start).total_seconds()) if timed else None,
        "started_at": start, "ended_at": end if timed else None,
        "ascent_m": round(ascent, 1) if known else None, "descent_m": round(descent, 1) if known else None,
        "max_ele_m": round(max(known), 1) if known else None, "min_ele_m": round(min(known), 1) if known else None,
        "start_lat": flat[0][0], "start_lon": flat[0][1],
        "is_loop": total >= 1000 and metres(flat[0], flat[-1]) <= LOOP_GAP,
        "points": len(flat), "track": track, "splits": splits,
    }


def parse(raw: bytes) -> dict:
    """A GPX file's bytes -> its name, description, AllTrails link, waypoints and measure()'s numbers."""
    if len(raw) > MAX_BYTES:
        raise GpxError("That file is too big for a GPX file (30 MB at most).")
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:      # GPX never needs them; they're how XML bombs work
        raise GpxError("That file has XML declarations a GPX file doesn't use, so it wasn't read.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise GpxError("That isn't a GPX file (it isn't valid XML).") from None
    if _local(root.tag) != "gpx":
        raise GpxError("That isn't a GPX file.")

    meta = (_children(root, "metadata") or [None])[0]
    tracks, routes = _children(root, "trk"), _children(root, "rte")
    segments = [[p for p in map(_point, (x for x in seg if _local(x.tag) == "trkpt")) if p]
                for trk in tracks for seg in _children(trk, "trkseg")]
    if not any(segments):
        segments = [[p for p in map(_point, _children(rte, "rtept")) if p] for rte in routes]
    segments = [s for s in segments if s]
    if sum(map(len, segments)) < 2:
        raise GpxError("There's no track in that GPX file (it needs at least two points).")

    links = [el.get("href", "") for el in root.iter() if _local(el.tag) == "link"]
    links = [h for h in links if h.startswith(("http://", "https://"))]
    first = (tracks or routes or [None])[0]
    waypoints = [{"name": _text(w, "name"), "lat": p[0], "lon": p[1], "ele": p[2]}
                 for w in _children(root, "wpt") if (p := _point(w))]
    return {
        "name": _text(meta, "name") or _text(first, "name"),
        "description": _text(meta, "desc") or _text(first, "desc"),
        "trail_url": next((h for h in links if "alltrails.com" in h), links[0] if links else None),
        "waypoints": waypoints[:200],
        "hash": hashlib.sha256(raw).hexdigest(),
        **measure(segments),
    }
