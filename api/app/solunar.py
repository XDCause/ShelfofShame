"""Sun, moon and solunar periods for fishing: pure maths, no database, no outside site. AN APPROXIMATION, GOOD TO A FEW
MINUTES (sunrise / sunset) and about 10-20 minutes for the moon - plenty for planning a fish, not for navigation.

The sun and moon positions are the low-precision series of Montenbruck and Pfleger, "Astronomy on the Personal
Computer" (MiniSun, MiniMoon: a few arc-minutes), turned into rise / set / transit times by stepping through the local
day and refining each crossing. Times come back as the place's local time, "YYYY-MM-DDTHH:MM" (the same shape Open-Meteo
uses), for the zone you give (Brisbane: UTC+10, no daylight saving).

The solunar theory itself (fish feed more around moon overhead / underfoot and moonrise / moonset) is angling folklore,
not science: the periods are what the tables print, and your own log is what shows whether they work for you.

    day(date, lat, lon, tz) -> everything for one day: sun, moon, majors, minors, rating
    moon_phase(when)        -> (phase name, illuminated %, age in days) at a moment
"""
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SYNODIC = 29.530589
PHASES = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous", "Full moon", "Waning gibbous", "Last quarter",
          "Waning crescent"]
DEFAULT_TZ = "Australia/Brisbane"
RAD = math.pi / 180.0
EPS = 23.43929111 * RAD                  # the obliquity of the ecliptic (it moves 0.013 deg a century: fine)
MOON_H0 = 0.125                          # the moon's centre at rise / set: parallax - refraction - semi-diameter, in degrees
SUN_H0 = -0.833


def zone(name: str | None):
    """A tzinfo for a zone name. Raises ValueError for an unknown one (Brisbane is also known without the tz database)."""
    name = name or DEFAULT_TZ
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        if name == DEFAULT_TZ:
            return timezone(timedelta(hours=10), "AEST")
        raise ValueError(f"Unknown time zone: {name}") from None


def _frac(x: float) -> float:
    return x - math.floor(x)


def _julian(when: datetime) -> float:
    """Julian date of an aware datetime (UT; the seconds of difference from ephemeris time don't matter here)."""
    return when.astimezone(timezone.utc).timestamp() / 86400.0 + 2440587.5


def _sun_lon(T: float) -> float:
    """The sun's ecliptic longitude, radians."""
    m = 2 * math.pi * _frac(0.993133 + 99.997361 * T)
    return 2 * math.pi * _frac(0.7859453 + m / (2 * math.pi) + (6893.0 * math.sin(m) + 72.0 * math.sin(2 * m) + 6191.2 * T) / 1296.0e3)


def _moon_lonlat(T: float) -> tuple[float, float]:
    """The moon's ecliptic longitude and latitude, radians (MiniMoon)."""
    arc = 206264.8062
    l0 = _frac(0.606433 + 1336.855225 * T)
    l = 2 * math.pi * _frac(0.374897 + 1325.552410 * T)       # the moon's mean anomaly
    ls = 2 * math.pi * _frac(0.993133 + 99.997361 * T)        # the sun's mean anomaly
    d = 2 * math.pi * _frac(0.827361 + 1236.853086 * T)       # the moon - sun longitude difference
    f = 2 * math.pi * _frac(0.259086 + 1342.227825 * T)       # the argument of latitude
    dl = (22640 * math.sin(l) - 4586 * math.sin(l - 2 * d) + 2370 * math.sin(2 * d) + 769 * math.sin(2 * l)
          - 668 * math.sin(ls) - 412 * math.sin(2 * f) - 212 * math.sin(2 * l - 2 * d) - 206 * math.sin(l + ls - 2 * d)
          + 192 * math.sin(l + 2 * d) - 165 * math.sin(ls - 2 * d) - 125 * math.sin(d) - 110 * math.sin(l + ls)
          + 148 * math.sin(l - ls) - 55 * math.sin(2 * f - 2 * d))
    s = f + (dl + 412 * math.sin(2 * f) + 541 * math.sin(ls)) / arc
    h = f - 2 * d
    n = (-526 * math.sin(h) + 44 * math.sin(l + h) - 31 * math.sin(-l + h) - 23 * math.sin(ls + h) + 11 * math.sin(-ls + h)
         - 25 * math.sin(-2 * l + f) + 21 * math.sin(-l + f))
    return 2 * math.pi * _frac(l0 + dl / 1296.0e3), (18520.0 * math.sin(s) + n) / arc


def _equatorial(lon: float, lat: float) -> tuple[float, float]:
    """Ecliptic longitude / latitude -> (right ascension, declination), radians."""
    x, y, z = math.cos(lon) * math.cos(lat), math.sin(lon) * math.cos(lat), math.sin(lat)
    y, z = y * math.cos(EPS) - z * math.sin(EPS), y * math.sin(EPS) + z * math.cos(EPS)
    return math.atan2(y, x), math.atan2(z, math.hypot(x, y))


def _body(when: datetime, which: str) -> tuple[float, float]:
    t = (_julian(when) - 2451545.0) / 36525.0
    if which == "sun":
        return _equatorial(_sun_lon(t), 0.0)
    return _equatorial(*_moon_lonlat(t))


def _hour_angle(when: datetime, which: str, lon_deg: float) -> float:
    ra, _ = _body(when, which)
    gmst = (280.46061837 + 360.98564736629 * (_julian(when) - 2451545.0)) % 360.0
    return (gmst + lon_deg) * RAD - ra


def _altitude(when: datetime, which: str, lat_deg: float, lon_deg: float) -> float:
    """The body's centre above the horizon, degrees (no refraction)."""
    _, dec = _body(when, which)
    h = _hour_angle(when, which, lon_deg)
    s = math.sin(lat_deg * RAD) * math.sin(dec) + math.cos(lat_deg * RAD) * math.cos(dec) * math.cos(h)
    return math.asin(max(-1.0, min(1.0, s))) / RAD


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def _crossings(fn, t0: datetime, t1: datetime, step_min: int = 10):
    """Where fn goes from negative to positive ('up') or the other way ('down') between t0 and t1 -> [(datetime, 'up'|'down')],
    each found to the second by halving. Steps where fn jumps by more than 1 (a wrap-around) aren't crossings."""
    out = []
    step = timedelta(minutes=step_min)
    a, fa = t0, fn(t0)
    while a < t1:
        b = min(a + step, t1)
        fb = fn(b)
        if (fa < 0) != (fb < 0) and abs(fb - fa) < 180:
            lo, hi, flo = a, b, fa
            for _ in range(12):
                mid = lo + (hi - lo) / 2
                fm = fn(mid)
                if (fm < 0) == (flo < 0):
                    lo, flo = mid, fm
                else:
                    hi = mid
            out.append((hi, "up" if fb > fa else "down"))
        a, fa = b, fb
    return out


def _local(when: datetime, tz) -> str:
    return when.astimezone(tz).strftime("%Y-%m-%dT%H:%M")


def _day_window(d: date, tz) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=tz)
    nxt = d + timedelta(days=1)
    return start, datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz)


def moon_phase(when: datetime) -> tuple[str, float, float]:
    """(name, % of the disc lit, age in days since the new moon) at a moment (an aware datetime)."""
    t = (_julian(when) - 2451545.0) / 36525.0
    elong = math.degrees(_moon_lonlat(t)[0] - _sun_lon(t)) % 360.0
    name = PHASES[int(((elong + 22.5) % 360.0) // 45.0)]
    return name, round((1 - math.cos(elong * RAD)) / 2 * 100, 1), round(elong / 360.0 * SYNODIC, 1)


def _elongation(when: datetime) -> float:
    t = (_julian(when) - 2451545.0) / 36525.0
    return math.degrees(_moon_lonlat(t)[0] - _sun_lon(t)) % 360.0


def sun_times(d: date, lat: float, lon: float, tz) -> dict:
    """{sunrise, sunset}: local times, None in the polar day / night."""
    t0, t1 = _day_window(d, tz)
    out = {"sunrise": None, "sunset": None}
    for when, kind in _crossings(lambda t: _altitude(t, "sun", lat, lon) - SUN_H0, t0, t1):
        key = "sunrise" if kind == "up" else "sunset"
        if out[key] is None:
            out[key] = when
    return out


def _moon_events(d: date, lat: float, lon: float, tz) -> dict:
    t0, t1 = _day_window(d, tz)
    rises, sets = [], []
    for when, kind in _crossings(lambda t: _altitude(t, "moon", lat, lon) - MOON_H0, t0, t1):
        (rises if kind == "up" else sets).append(when)
    upper = [w for w, k in _crossings(lambda t: math.degrees(_wrap(_hour_angle(t, "moon", lon))), t0, t1) if k == "up"]
    lower = [w for w, k in _crossings(lambda t: math.degrees(_wrap(_hour_angle(t, "moon", lon) - math.pi)), t0, t1) if k == "up"]
    return {"rise": rises[0] if rises else None, "set": sets[0] if sets else None, "overhead": upper[0] if upper else None,
            "underfoot": lower[0] if lower else None}


def _overlaps(period: tuple[datetime, datetime], around: datetime | None, slack: timedelta) -> bool:
    return around is not None and period[0] <= around + slack and period[1] >= around - slack


def day(d: date, lat: float, lon: float, tz_name: str | None = None) -> dict:
    """Everything for one local day at a place:
    {date, tz, sunrise, sunset, moon {phase, pct, age_days, rise, set, overhead, underfoot}, majors [{start, end}],
     minors [{start, end}], rating 1-4}. Majors are 2 hours centred on the moon overhead and underfoot, minors 1 hour
    centred on moonrise and moonset. The rating is higher near the new and full moon, with a bonus when a major or a
    minor overlaps sunrise or sunset. Times are local 'YYYY-MM-DDTHH:MM' (a time that doesn't happen that day is None)."""
    tz = zone(tz_name)
    sun = sun_times(d, lat, lon, tz)
    ev = _moon_events(d, lat, lon, tz)
    noon = datetime(d.year, d.month, d.day, 12, tzinfo=tz)
    name, pct, age = moon_phase(noon)
    majors = [(w - timedelta(hours=1), w + timedelta(hours=1)) for w in (ev["overhead"], ev["underfoot"]) if w]
    minors = [(w - timedelta(minutes=30), w + timedelta(minutes=30)) for w in (ev["rise"], ev["set"]) if w]
    majors.sort()
    minors.sort()
    el = _elongation(noon)
    off = min(el, abs(el - 180), 360 - el)                      # degrees from the nearest new / full moon
    rating = 3 if off <= 25 else 2 if off <= 65 else 1
    near_dawn_dusk = any(_overlaps(p, sun[k], timedelta(minutes=30)) for p in majors + minors for k in ("sunrise", "sunset"))
    rating = min(4, rating + (1 if near_dawn_dusk else 0))

    def span(p):
        return {"start": _local(p[0], tz), "end": _local(p[1], tz)}
    return {"date": d.isoformat(), "tz": tz_name or DEFAULT_TZ,
            "sunrise": _local(sun["sunrise"], tz) if sun["sunrise"] else None,
            "sunset": _local(sun["sunset"], tz) if sun["sunset"] else None,
            "moon": {"phase": name, "pct": pct, "age_days": age,
                     "rise": _local(ev["rise"], tz) if ev["rise"] else None, "set": _local(ev["set"], tz) if ev["set"] else None,
                     "overhead": _local(ev["overhead"], tz) if ev["overhead"] else None,
                     "underfoot": _local(ev["underfoot"], tz) if ev["underfoot"] else None},
            "majors": [span(p) for p in majors], "minors": [span(p) for p in minors], "rating": rating}
