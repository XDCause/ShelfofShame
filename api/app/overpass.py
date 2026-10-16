"""OpenStreetMap's Overpass API (https://wiki.openstreetmap.org/wiki/Overpass_API): landmarks near a
hike's track - peaks, lookouts, waterfalls, huts, campsites, trig points... No key. Data (c)
OpenStreetMap contributors, ODbL.

    near_line(points, radius)   everything we show within `radius` metres of a line of (lat, lon)
    landmarks(elements)         -> [{osm, kind, label, name, ele, lat, lon, wikidata, commons}]

The public server is busy at times (it answers 429 / 504 when its queue is full) and asks for back-off,
not hammering: one request per hike, after an import, in the background; a busy answer is retried after
20 s, then 60 s. It's meant for human-started requests - which these are - not bulk downloads.
"""
import re
import time

import httpx

from .openlibrary import HEADERS

URL = "https://overpass-api.de/api/interpreter"
TIMEOUT = 120
RETRY_WAITS = (20, 60)
BUSY = {429, 502, 503, 504}

# (tag, values, label): what counts as a landmark, and what to call it.
KINDS = [
    ("natural", {"peak": "Peak", "volcano": "Volcano", "saddle": "Saddle", "waterfall": "Waterfall",
                 "cave_entrance": "Cave", "spring": "Spring"}),
    ("waterway", {"waterfall": "Waterfall"}),
    ("tourism", {"viewpoint": "Lookout", "alpine_hut": "Hut", "wilderness_hut": "Hut", "camp_site": "Campsite",
                 "picnic_site": "Picnic area"}),
    ("amenity", {"shelter": "Shelter", "drinking_water": "Drinking water", "toilets": "Toilets"}),
    ("man_made", {"survey_point": "Trig point"}),
]


class OverpassError(Exception):
    """OpenStreetMap's Overpass couldn't be asked; the message says why."""


def query(points: list[tuple[float, float]], radius: int) -> str:
    """Overpass QL: each kind within `radius` m of the line through `points` (or of one point)."""
    line = ",".join(f"{lat:.5f},{lon:.5f}" for lat, lon in points)
    parts = [f'nwr(around:{radius},{line})["{tag}"~"^({"|".join(values)})$"];' for tag, values in KINDS]
    parts.append(f'nwr(around:{radius},{line})["historic"]["name"];')
    return f"[out:json][timeout:90];({''.join(parts)});out center tags 300;"


def _post(data: str) -> dict:
    try:
        r = httpx.post(URL, data={"data": data}, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise OverpassError(f"Couldn't reach OpenStreetMap's Overpass ({e.__class__.__name__}).") from None
    if r.status_code in BUSY:
        raise OverpassError(f"OpenStreetMap's Overpass is busy (HTTP {r.status_code}).")
    if r.status_code != 200:
        raise OverpassError(f"OpenStreetMap's Overpass didn't answer (HTTP {r.status_code}).")
    return r.json()


def near_line(points: list[tuple[float, float]], radius: int = 250) -> list[dict]:
    """The raw elements near the line; a busy server is asked again after RETRY_WAITS."""
    data = query(points, radius)
    for wait in (0, *RETRY_WAITS):
        if wait:
            time.sleep(wait)
        try:
            return _post(data).get("elements", [])
        except OverpassError as e:
            last = e
            if "busy" not in str(e) and "reach" not in str(e):
                break
    raise last


def landmarks(elements: list[dict]) -> list[dict]:
    """Overpass elements -> landmarks we can show (a position, and a name or a kind worth showing unnamed)."""
    out, seen = [], set()
    for el in elements:
        tags = el.get("tags") or {}
        lat, lon = el.get("lat") or (el.get("center") or {}).get("lat"), el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        kind = label = None
        for tag, values in KINDS:
            if tags.get(tag) in values:
                kind, label = tags[tag], values[tags[tag]]
                break
        if kind is None and tags.get("historic"):
            kind, label = "historic", "Historic site"
        if kind is None:
            continue
        name = tags.get("name")
        key = (kind, name or f"{lat:.4f},{lon:.4f}")
        if key in seen:
            continue
        seen.add(key)
        ele = re.match(r"^\s*(-?\d+(?:\.\d+)?)", tags.get("ele", ""))
        commons = tags.get("wikimedia_commons", "")
        out.append({
            "osm": f"{el.get('type')}/{el.get('id')}", "kind": kind, "label": label, "name": name,
            "ele": round(float(ele.group(1))) if ele else None, "lat": lat, "lon": lon,
            "wikidata": tags.get("wikidata") if re.fullmatch(r"Q\d+", tags.get("wikidata", "")) else None,
            "commons": commons if commons.startswith("File:") else None,
        })
    return out
