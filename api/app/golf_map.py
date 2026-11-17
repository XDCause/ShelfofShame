"""A golf course from OpenStreetMap's shapes (overpass.golf_course's elements) -> its holes, each with its map.

Mappers draw each hole as a line from the tee to the green (golf=hole, with ref = its number, par, and handicap = its
stroke index), and the green, tees, fairways and bunkers as shapes (golf=green / tee / fairway / bunker; water as
golf=water_hazard / lateral_water_hazard or natural=water). The shapes aren't tied to a hole, so each goes to the
nearest hole line: a green to the hole that ends nearest it, a tee to the one that starts nearest, the rest to the
nearest line within reach. A course with no hole lines gives no holes (typed by hand instead).

    holes(elements) -> {"name", "lat", "lon", "holes": [{hole_no, par (None: not mapped), stroke_index, map: {line, green, tees, fairways,
                         bunkers, water}}]}   (shapes as [[lat, lon], ...], rounded to ~10 cm)
    place_of(tags)  -> "Suburb, State" from the course's address tags, when it has them
"""
import math

from .golfmath import centre, metres_between

GREEN_REACH = 120      # metres from a hole line's end (the flag) to the green's middle
TEE_REACH = 120
NEAR_REACH = 70        # fairways, bunkers, water: this close to the hole's line
MAX_POINTS = 160       # a shape with more corners is thinned (a lake's shoreline)


def _pts(el) -> list[list[float]]:
    if el.get("geometry"):
        pts = [[round(p["lat"], 6), round(p["lon"], 6)] for p in el["geometry"] if p]
    elif el.get("members"):          # a multipolygon: its outer rings, end to end
        pts = [[round(p["lat"], 6), round(p["lon"], 6)] for m in el["members"] if m.get("role", "outer") == "outer"
               for p in (m.get("geometry") or []) if p]
    elif el.get("lat") is not None:
        pts = [[round(el["lat"], 6), round(el["lon"], 6)]]
    else:
        return []
    if len(pts) > MAX_POINTS:
        step = math.ceil(len(pts) / MAX_POINTS)
        pts = pts[::step] + [pts[-1]]
    return pts


def _to_line(p, a, b) -> float:
    """Metres from point p to the segment a-b (flat earth: fine across a golf hole)."""
    k = math.cos(math.radians(a[0])) * 111320
    ax, ay, bx, by, px, py = a[1] * k, a[0] * 110540, b[1] * k, b[0] * 110540, p[1] * k, p[0] * 110540
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _near_line(shape, line) -> float:
    return min(_to_line(p, a, b) for p in shape for a, b in zip(line, line[1:] or line))


def _int(text, lo, hi):
    try:
        v = int(str(text).strip().split(";")[0])
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


def place_of(tags: dict) -> str | None:
    parts = [tags.get("addr:suburb") or tags.get("addr:city"), tags.get("addr:state")]
    return ", ".join(p for p in parts if p) or None


def holes(elements: list[dict]) -> dict:
    course = next((e for e in elements if (e.get("tags") or {}).get("leisure") == "golf_course"), {})
    tags = course.get("tags") or {}
    lines, shapes = {}, {"green": [], "tee": [], "fairway": [], "bunker": [], "water": []}
    for el in elements:
        t = el.get("tags") or {}
        golf = t.get("golf")
        if golf == "hole":
            no = _int(t.get("ref"), 1, 18)
            pts = _pts(el)
            if no and len(pts) >= 2 and no not in lines:
                lines[no] = {"pts": pts, "par": _int(t.get("par"), 3, 6), "si": _int(t.get("handicap"), 1, 18)}
        elif golf in ("green", "tee", "fairway", "bunker"):
            pts = _pts(el)
            if pts:
                shapes[golf].append(pts)
        elif golf in ("water_hazard", "lateral_water_hazard") or t.get("natural") == "water":
            pts = _pts(el)
            if len(pts) >= 3:
                shapes["water"].append(pts)

    maps = {no: {"line": h["pts"], "green": None, "tees": [], "fairways": [], "bunkers": [], "water": []} for no, h in lines.items()}
    if lines:
        for g in shapes["green"]:
            mid = centre(g)
            no, d = min(((no, metres_between(mid, h["pts"][-1])) for no, h in lines.items()), key=lambda x: x[1])
            if d <= GREEN_REACH and (maps[no]["green"] is None or d < metres_between(centre(maps[no]["green"]), lines[no]["pts"][-1])):
                maps[no]["green"] = g
        for tee in shapes["tee"]:
            mid = centre(tee)
            no, d = min(((no, metres_between(mid, h["pts"][0])) for no, h in lines.items()), key=lambda x: x[1])
            if d <= TEE_REACH:
                maps[no]["tees"].append(tee)
        for kind, key in (("fairway", "fairways"), ("bunker", "bunkers"), ("water", "water")):
            for shape in shapes[kind]:
                no, d = min(((no, _near_line(shape, h["pts"])) for no, h in lines.items()), key=lambda x: x[1])
                if d <= NEAR_REACH:
                    maps[no][key].append(shape)

    mid = course.get("center") or {}
    return {
        "name": tags.get("name"), "lat": mid.get("lat"), "lon": mid.get("lon"), "place": place_of(tags),
        "website": tags.get("website") or tags.get("contact:website"),
        "holes": [{"hole_no": no, "par": lines[no]["par"], "stroke_index": lines[no]["si"], "map": maps[no]}
                  for no in sorted(lines)],
    }


def courses(elements: list[dict]) -> list[dict]:
    """overpass.golf_courses_near's elements -> [{osm, name, lat, lon, place}] (named ones; mini golf left out)."""
    out = []
    for el in elements:
        t = el.get("tags") or {}
        mid = el.get("center") or ({"lat": el["lat"], "lon": el["lon"]} if el.get("lat") is not None else None)
        if not t.get("name") or not mid or el.get("type") not in ("way", "relation") or t.get("golf:course") == "miniature":
            continue
        out.append({"osm": f"{el['type']}/{el['id']}", "name": t["name"], "lat": round(mid["lat"], 5),
                    "lon": round(mid["lon"], 5), "place": place_of(t)})
    return out
