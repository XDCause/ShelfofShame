"""Reading dive files: UDDF (the Universal Dive Data Format, .uddf / .xml - what most dive computer programs export) and
Subsurface's own XML (.ssrf / .xml). Parsing only, no database: scuba_tools.py saves what comes out.

    parse(raw_bytes) -> {"format": "uddf" | "subsurface", "dives": [dive...]}   (DiveFileError says what's wrong)

A dive is {dived_on, time_in, max_depth, avg_depth, minutes, water_temp, gas_o2, tank_l, start_bar, end_bar, computer,
site {name, lat, lon} | None, buddy, guide, suit, rating, tags, notes, samples [[seconds, depth_m, temp_c|None]...],
import_key}. Values outside what the database accepts are left out (None), never guessed.

The files come from outside, so the XML is read safely: a document type declaration (where entity tricks live) is
refused outright, and the file is limited to 20 MB (checked by the caller too).
"""
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat
from datetime import datetime

MAX_BYTES = 20 * 1024 * 1024
MAX_SAMPLES = 8000                 # a profile longer than this is thinned (a 1-second computer on a 2 hour dive)


class DiveFileError(Exception):
    """The file isn't a dive log we can read; the message says why."""


def _no_doctype(*_a):
    raise DiveFileError("This file has a DOCTYPE declaration, which isn't accepted (it's not a normal dive log export).")


def read_xml(raw: bytes) -> ET.Element:
    """The root element, with no DOCTYPE / entities allowed and namespaces stripped from the tags."""
    if len(raw) > MAX_BYTES:
        raise DiveFileError("That file is over 20 MB.")
    guard = expat.ParserCreate()                  # first a pass that refuses a DOCTYPE / entities (ElementTree's own
    guard.StartDoctypeDeclHandler = _no_doctype   # parser doesn't let us hook in), then the real read
    guard.EntityDeclHandler = _no_doctype
    try:
        guard.Parse(raw, True)
        root = ET.fromstring(raw)
    except DiveFileError:
        raise
    except (ET.ParseError, expat.ExpatError, ValueError, UnicodeError):
        raise DiveFileError("That isn't a readable XML file (a UDDF or Subsurface export).") from None
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def parse(raw: bytes) -> dict:
    root = read_xml(raw)
    tag = (root.tag or "").lower()
    if tag == "uddf":
        return {"format": "uddf", "dives": _uddf(root)}
    if tag == "divelog":
        return {"format": "subsurface", "dives": _subsurface(root)}
    raise DiveFileError("That's neither a UDDF file nor a Subsurface dive log.")


# ---------------------------------------------------------------- shared

def _num(text, lo=None, hi=None):
    """A number from text ('18.3', '18.3 m', '12 l'), or None - also None when outside lo..hi."""
    if text is None:
        return None
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(text))
    if not m:
        return None
    v = float(m.group(1))
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        return None
    return v


def _text(el, path):
    found = el.find(path) if el is not None else None
    return (found.text or "").strip() if found is not None and found.text else None


def _when(date_text: str | None, time_text: str | None = None) -> datetime | None:
    try:
        if date_text and "T" in date_text and not time_text:
            return datetime.fromisoformat(date_text.strip().replace("Z", "")[:19])
        if date_text:
            return datetime.fromisoformat(f"{date_text.strip()}T{(time_text or '00:00:00').strip()[:8]}")
    except ValueError:
        return None
    return None


def _finish(d: dict, computer: str | None, when: datetime) -> dict:
    """Put a dive's numbers inside what the database accepts, work out what's missing, and give it its import key."""
    s = d["samples"]
    if len(s) > MAX_SAMPLES:
        step = -(-len(s) // MAX_SAMPLES)
        deepest = max(range(len(s)), key=lambda i: s[i][1])
        keep = sorted(set(range(0, len(s), step)) | {len(s) - 1, deepest})
        s = d["samples"] = [s[i] for i in keep]
    if s:
        if d.get("max_depth") is None:
            d["max_depth"] = round(max(x[1] for x in s), 1)
        if d.get("avg_depth") is None and len(s) > 1:
            area = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(s, s[1:]))
            span = s[-1][0] - s[0][0]
            d["avg_depth"] = round(area / span, 1) if span > 0 else None
        if d.get("minutes") is None and s[-1][0] > 0:
            d["minutes"] = max(1, round(s[-1][0] / 60))
    if d.get("max_depth") is not None and not 0 <= d["max_depth"] <= 350:
        d["max_depth"] = None
    if d.get("avg_depth") is not None and (d["avg_depth"] > 350 or (d.get("max_depth") is not None and d["avg_depth"] > d["max_depth"])):
        d["avg_depth"] = None if d.get("max_depth") is None else min(d["avg_depth"], d["max_depth"])
    if d.get("minutes") is not None:
        d["minutes"] = max(1, min(1440, int(round(d["minutes"]))))
    if d.get("water_temp") is not None and not -3 <= d["water_temp"] <= 40:
        d["water_temp"] = None
    if d.get("tank_l") is not None and not 1 <= d["tank_l"] <= 30:
        d["tank_l"] = None
    for key in ("start_bar", "end_bar"):
        if d.get(key) is not None:
            d[key] = int(round(d[key])) if 0 <= d[key] <= 350 else None
    if d.get("start_bar") is not None and d.get("end_bar") is not None and d["end_bar"] > d["start_bar"]:
        d["end_bar"] = None
    o2 = d.get("gas_o2")
    d["gas_o2"] = int(round(o2)) if o2 is not None and 21 <= o2 <= 100 else 21
    d["dived_on"] = when.date().isoformat()
    d["time_in"] = when.strftime("%H:%M") if (when.hour or when.minute or when.second) else None
    d["computer"] = computer
    d["import_key"] = f"{computer or 'import'}|{when.isoformat()}"
    return d


def _samples(rows: list[tuple]) -> list[list]:
    """[(seconds, depth, temp)] -> [[seconds, depth, temp]] in time order, whole seconds, depth to 0.1 m."""
    out = []
    for s, depth, temp in sorted((r for r in rows if r[0] is not None and r[1] is not None), key=lambda r: r[0]):
        out.append([int(round(s)), round(max(depth, 0.0), 1), None if temp is None else round(temp, 1)])
    return out


# ---------------------------------------------------------------- UDDF

def _kelvin(text):
    v = _num(text)
    return None if v is None else round(v - 273.15, 1) if v > 100 else round(v, 1)     # (UDDF is Kelvin; be forgiving)


def _uddf(root: ET.Element) -> list[dict]:
    sites = {}
    for site in root.iter("site"):
        if site.get("id"):
            sites[site.get("id")] = {"name": _text(site, "name"), "lat": _num(_text(site, "geography/latitude"), -90, 90),
                                     "lon": _num(_text(site, "geography/longitude"), -180, 180)}
    mixes = {}
    for mix in root.iter("mix"):
        if mix.get("id"):
            o2 = _num(_text(mix, "o2"))
            mixes[mix.get("id")] = None if o2 is None else (o2 * 100 if o2 <= 1 else o2)
    computers = {}
    for dc in root.iter("divecomputer"):
        if dc.get("id"):
            computers[dc.get("id")] = _text(dc, "name") or _text(dc, "model")
    default_computer = next(iter(computers.values()), None)
    dives = []
    for dive in root.iter("dive"):
        before = dive.find("informationbeforedive")
        after = dive.find("informationafterdive")
        when = _when(_text(before, "datetime"))
        if when is None:
            continue
        rows, tank_mix = [], None
        temp = None
        for wp in dive.iterfind("samples/waypoint"):
            t = _kelvin(_text(wp, "temperature"))
            temp = t if t is not None else temp
            rows.append((_num(_text(wp, "divetime")), _num(_text(wp, "depth")), temp))
            sw = wp.find("switchmix")
            if sw is not None and tank_mix is None:
                tank_mix = sw.get("ref")
        tank = dive.find("tankdata")
        if tank is None:
            tank = dive.find(".//tankdata")
        link = tank.find("link") if tank is not None else None
        if link is not None and link.get("ref"):
            tank_mix = link.get("ref") or tank_mix
        vol = _num(_text(tank, "tankvolume"))
        p0, p1 = _num(_text(tank, "tankpressurebegin")), _num(_text(tank, "tankpressureend"))
        site_ref = (before.find("link").get("ref") if before is not None and before.find("link") is not None else None)
        site = sites.get(site_ref)
        duration = _num(_text(after, "diveduration"))
        d = {"max_depth": _num(_text(after, "greatestdepth")), "avg_depth": _num(_text(after, "averagedepth")),
             "minutes": duration / 60 if duration else None, "water_temp": _kelvin(_text(after, "lowesttemperature")),
             "gas_o2": mixes.get(tank_mix), "tank_l": round(vol * 1000, 1) if vol else None,
             "start_bar": p0 / 1e5 if p0 else None, "end_bar": p1 / 1e5 if p1 is not None else None,
             "site": site if site and site.get("name") else None, "buddy": None, "guide": None, "suit": None,
             "rating": None, "tags": [], "notes": _text(after, "notes/para") or _text(dive, "notes/para"),
             "samples": _samples(rows)}
        dives.append(_finish(d, default_computer, when))
    return dives


# ---------------------------------------------------------------- Subsurface

def _clock(text) -> float | None:
    """'45:30 min' / '1:02:03' / '30 s' -> seconds."""
    if not text:
        return None
    m = re.match(r"^\s*(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", text)
    if m:
        return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(min|s)?", text)
    if m:
        return float(m.group(1)) * (60 if m.group(2) == "min" else 1)
    return None


def _subsurface(root: ET.Element) -> list[dict]:
    sites = {}
    for site in root.iter("site"):
        uuid, name, gps = site.get("uuid"), (site.get("name") or "").strip(), (site.get("gps") or "").split()
        if uuid and name:
            lat = _num(gps[0], -90, 90) if len(gps) == 2 else None
            lon = _num(gps[1], -180, 180) if len(gps) == 2 else None
            sites[uuid] = {"name": name, "lat": lat, "lon": lon}
    dives = []
    for dive in root.iter("dive"):
        when = _when(dive.get("date"), dive.get("time"))
        if when is None:
            continue
        dc = next((c for c in dive.iterfind("divecomputer") if c.find("sample") is not None), dive.find("divecomputer"))
        rows, temp = [], None
        if dc is not None:
            for s in dc.iterfind("sample"):
                t = _num(s.get("temp"))
                temp = t if t is not None else temp
                rows.append((_clock(s.get("time")), _num(s.get("depth")), temp))
        cyl = dive.find("cylinder")
        o2 = _num(cyl.get("o2")) if cyl is not None else None
        depth = dc.find("depth") if dc is not None else None
        water = dc.find("temperature") if dc is not None else None
        duration = _clock(dive.get("duration"))
        rating = _num(dive.get("rating"))
        tags = [t.strip() for t in (dive.get("tags") or "").split(",") if t.strip()]
        d = {"max_depth": _num(depth.get("max")) if depth is not None else None,
             "avg_depth": _num(depth.get("mean")) if depth is not None else None,
             "minutes": duration / 60 if duration else None,
             "water_temp": _num(water.get("water")) if water is not None else None,
             "gas_o2": o2, "tank_l": _num(cyl.get("size")) if cyl is not None else None,
             "start_bar": _num(cyl.get("start")) if cyl is not None else None,
             "end_bar": _num(cyl.get("end")) if cyl is not None else None,
             "site": sites.get(dive.get("divesiteid")), "buddy": _text(dive, "buddy"), "guide": _text(dive, "divemaster"),
             "suit": _text(dive, "suit"), "rating": int(rating) if rating and 1 <= rating <= 5 else None, "tags": tags,
             "notes": _text(dive, "notes"), "samples": _samples(rows)}
        dives.append(_finish(d, (dc.get("model") if dc is not None else None) or None, when))
    return dives
