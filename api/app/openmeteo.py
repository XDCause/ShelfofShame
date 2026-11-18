"""Open-Meteo (https://open-meteo.com): free weather forecasts, no key (free for non-commercial use;
CC BY 4.0 - credited where the tips show). Used by Gardening for balcony tips: heat, wind, rain, UV.

    find_place(name)     -> [{name, region, country, lat, lon}]   (their geocoding API; country = its ISO code)
    care_days(lat, lon)  -> the last 2 days and the next 3 (rain, heat): for watering advice
    forecast(lat, lon)   -> the next 3 days: [{day, max, min, rain_mm, rain_chance, gusts, uv, code, sky, icon}]
                            (sky / icon: the day's weather code in words - Sunny, Cloudy, Rain...)

    marine(lat, lon)     -> 7 days of sea (waves, swell, sea temperature, tide) for Scuba diving (their Marine API);
    wind(lat, lon)       -> 7 days of strongest wind and gusts (km/h), for the same dive-day verdict

The forecast is kept for an hour (one request an hour at most, whatever the page does). The last good answer is also
kept in the database (weather_kept): while Open-Meteo can't be reached, a forecast up to KEPT_FOR old is answered from
it, each day marked as_of (when it was fetched) and the days already gone left out - the pages say how old it is.
(2026-11-16: their forecast server stopped answering this network for over a day, and every weather card went blank.)
fresh=True never does that: the website check wants to know if Open-Meteo itself answers.
"""
import time
from datetime import date, timedelta

import httpx
from psycopg.types.json import Jsonb

from .db import db
from .openlibrary import HEADERS

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
# The same forecasts from another of their servers (their historical-forecast API takes the same parameters and goes
# 16 days ahead too): asked when the forecast server can't be reached - it stopped answering this network on
# 2026-11-16 while their other servers answered (HISTORY 5zh).
BACKUP = "https://historical-forecast-api.open-meteo.com/v1/forecast"
MARINE = "https://marine-api.open-meteo.com/v1/marine"          # waves, swell, sea temperature, tide (Scuba diving)
TIMEOUT = 20
KEEP = 3600
KEPT_FOR = timedelta(days=3)
_cache: dict[tuple, tuple[float, list]] = {}


def _kept(key: tuple, fetch, fresh: bool, past_ok: bool = False):
    """The answer for key: an hour-old one from memory, else fetch() (and keep it), else - Open-Meteo unreachable - the
    last good one from the database if it's under KEPT_FOR old: each day gets as_of, and days before today go (unless
    past_ok: the watering advice wants the last two days too)."""
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < KEEP:
        return hit[1]
    name = ",".join(str(k) for k in key)
    try:
        days = fetch()
    except WeatherError:
        if fresh:
            raise
        with db() as conn:
            row = conn.execute("SELECT fetched_at, data FROM weather_kept WHERE place_key = %s AND fetched_at > now() - %s",
                               (name, KEPT_FOR)).fetchone()
        if not row:
            raise
        today = date.today().isoformat()
        as_of = row["fetched_at"].isoformat()
        return [{**d, "as_of": as_of} for d in row["data"] if past_ok or d["day"] >= today]
    _cache[key] = (time.time(), days)
    with db() as conn:
        conn.execute("INSERT INTO weather_kept (place_key, data) VALUES (%s, %s) ON CONFLICT (place_key) DO UPDATE "
                     "SET data = EXCLUDED.data, fetched_at = now()", (name, Jsonb(days)))
    return days


def kept_since(days: list[dict]) -> str | None:
    """When a forecast answered from the kept copy was fetched (None for a fresh one)."""
    return days[0].get("as_of") if days else None


# WMO weather codes (what Open-Meteo gives for a day: its worst weather) -> words and a picture.
SKY = {0: ("Sunny", "☀️"), 1: ("Mostly sunny", "🌤️"), 2: ("Partly cloudy", "⛅"), 3: ("Cloudy", "☁️"),
       45: ("Fog", "🌫️"), 48: ("Fog", "🌫️"), 51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy drizzle", "🌧️"),
       56: ("Freezing drizzle", "🌧️"), 57: ("Freezing drizzle", "🌧️"), 61: ("Light rain", "🌦️"), 63: ("Rain", "🌧️"),
       65: ("Heavy rain", "🌧️"), 66: ("Freezing rain", "🌧️"), 67: ("Freezing rain", "🌧️"), 71: ("Light snow", "🌨️"),
       73: ("Snow", "🌨️"), 75: ("Heavy snow", "🌨️"), 77: ("Snow", "🌨️"), 80: ("Showers", "🌦️"), 81: ("Showers", "🌧️"),
       82: ("Heavy showers", "🌧️"), 85: ("Snow showers", "🌨️"), 86: ("Snow showers", "🌨️"), 95: ("Storms", "⛈️"),
       96: ("Storms with hail", "⛈️"), 99: ("Storms with hail", "⛈️")}


def sky(code) -> tuple[str | None, str | None]:
    """A weather code -> ("Rain", "🌧️"); (None, None) if there isn't one."""
    return SKY.get(int(code), (None, None)) if isinstance(code, (int, float)) else (None, None)


class WeatherError(Exception):
    """Open-Meteo couldn't be asked; the message says why."""


USED = {"backup": False}              # whether the last forecast came from BACKUP (the website check says so)


def _get(url: str, params: dict) -> dict:
    return _fetch(url, params)


def _fetch(url: str, params: dict) -> dict:
    """(_get's body: the tests replace _get, and ask this one with httpx faked.)"""
    USED["backup"] = False
    try:
        r = httpx.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        if url != FORECAST:
            raise WeatherError(f"Couldn't reach Open-Meteo ({e.__class__.__name__}).") from None
        try:                          # their forecast server unreachable: the same forecast from BACKUP
            r = httpx.get(BACKUP, params=params, headers=HEADERS, timeout=TIMEOUT)
            USED["backup"] = True
        except httpx.HTTPError:
            raise WeatherError(f"Couldn't reach Open-Meteo ({e.__class__.__name__}), nor its backup server.") from None
    if r.status_code != 200:
        raise WeatherError(f"Open-Meteo didn't answer (HTTP {r.status_code}).")
    return r.json()


def find_place(name: str) -> list[dict]:
    data = _get(GEOCODE, {"name": name, "count": 6, "language": "en", "format": "json"})
    return [{"name": p["name"], "region": ", ".join(filter(None, [p.get("admin1"), p.get("country")])),
             "country": (p.get("country_code") or "").upper() or None,
             "lat": round(p["latitude"], 4), "lon": round(p["longitude"], 4)} for p in data.get("results") or []]


def forecast(lat: float, lon: float, fresh: bool = False) -> list[dict]:
    key = (round(lat, 2), round(lon, 2))
    return _kept(key, lambda: _forecast(key), fresh)


def _forecast(key) -> list[dict]:
    data = _get(FORECAST, {"latitude": key[0], "longitude": key[1], "timezone": "auto", "forecast_days": 3,
                           "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
                                    "wind_gusts_10m_max,uv_index_max,weather_code"})
    d = data.get("daily") or {}

    def col(name, i):
        values = d.get(name) or []
        return values[i] if i < len(values) else None
    days = [{"day": day, "max": col("temperature_2m_max", i), "min": col("temperature_2m_min", i),
             "rain_mm": col("precipitation_sum", i), "rain_chance": col("precipitation_probability_max", i),
             "gusts": col("wind_gusts_10m_max", i), "uv": col("uv_index_max", i), "code": col("weather_code", i),
             "sky": sky(col("weather_code", i))[0], "icon": sky(col("weather_code", i))[1]}
            for i, day in enumerate(d.get("time") or [])]
    return days


def long_forecast(lat: float, lon: float) -> list[dict]:
    """The next 16 days at a place (the calendar's events): [{day, max, min, rain_chance, code, sky, icon}]. Kept an hour."""
    key = (round(lat, 2), round(lon, 2), "16")
    return _kept(key, lambda: _long_forecast(key), False)


def _long_forecast(key) -> list[dict]:
    data = _get(FORECAST, {"latitude": key[0], "longitude": key[1], "timezone": "auto", "forecast_days": 16,
                           "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"})
    d = data.get("daily") or {}

    def col(name, i):
        values = d.get(name) or []
        return values[i] if i < len(values) else None
    days = [{"day": day, "max": col("temperature_2m_max", i), "min": col("temperature_2m_min", i),
             "rain_chance": col("precipitation_probability_max", i), "code": col("weather_code", i),
             "sky": sky(col("weather_code", i))[0], "icon": sky(col("weather_code", i))[1]}
            for i, day in enumerate(d.get("time") or [])]
    return days


def care_days(lat: float, lon: float) -> list[dict]:
    """The last 2 days and the next 3 at a place, for watering advice: [{day, max, min, rain_mm, rain_chance}]. Kept an hour."""
    key = (round(lat, 2), round(lon, 2), "care")
    return _kept(key, lambda: _care_days(key), False, past_ok=True)


def _care_days(key) -> list[dict]:
    data = _get(FORECAST, {"latitude": key[0], "longitude": key[1], "timezone": "auto", "past_days": 2, "forecast_days": 4,
                           "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"})
    d = data.get("daily") or {}

    def col(name, i):
        values = d.get(name) or []
        return values[i] if i < len(values) else None
    days = [{"day": day, "max": col("temperature_2m_max", i), "min": col("temperature_2m_min", i),
             "rain_mm": col("precipitation_sum", i), "rain_chance": col("precipitation_probability_max", i)}
            for i, day in enumerate(d.get("time") or [])]
    return days


def day_weather(lat: float, lon: float, day: str) -> dict | None:
    """One day's weather at a place (a journal page's): {sky, icon, max, min, rain_mm}. Their forecast API also keeps the
    last 92 days (and the next two weeks); None if it has nothing for that day."""
    key = (round(lat, 2), round(lon, 2), day)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < KEEP:
        return hit[1]
    data = _get(FORECAST, {"latitude": key[0], "longitude": key[1], "timezone": "auto", "start_date": day, "end_date": day,
                           "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"})
    d = data.get("daily") or {}
    times = d.get("time") or []
    if not times:
        return None
    i = times.index(day) if day in times else 0

    def col(name):
        values = d.get(name) or []
        return values[i] if i < len(values) else None
    found = {"sky": sky(col("weather_code"))[0], "icon": sky(col("weather_code"))[1], "max": col("temperature_2m_max"),
             "min": col("temperature_2m_min"), "rain_mm": col("precipitation_sum")}
    _cache[key] = (time.time(), found)
    return found


def marine(lat: float, lon: float, fresh: bool = False) -> list[dict]:
    """The next 7 days of sea at a place (Scuba diving; Open-Meteo Marine, CC BY 4.0, not for navigation):
    [{day, wave_max, swell_max, swell_period, swell_dir, sst, tide [{time, height}]}] - the biggest wave and swell (m),
    the swell's period (s) and direction (degrees) at its biggest, the day's mean sea temperature, and the tide's highs
    and lows (sea level in m above mean, found as the turning points of the hourly figures). Kept an hour like the
    forecast, and the last good one while Open-Meteo can't be reached (see _kept)."""
    key = (round(lat, 2), round(lon, 2), "marine")
    return _kept(key, lambda: _marine(key), fresh)


def _marine(key) -> list[dict]:
    data = _get(MARINE, {"latitude": key[0], "longitude": key[1], "timezone": "auto", "forecast_days": 7,
                         "hourly": "wave_height,swell_wave_height,swell_wave_period,swell_wave_direction,"
                                   "sea_surface_temperature,sea_level_height_msl"})
    h = data.get("hourly") or {}
    times = h.get("time") or []

    def col(name):
        values = h.get(name) or []
        return [values[i] if i < len(values) else None for i in range(len(times))]
    wave, swell, period, direction = col("wave_height"), col("swell_wave_height"), col("swell_wave_period"), col("swell_wave_direction")
    sst, level = col("sea_surface_temperature"), col("sea_level_height_msl")
    tides = {}
    for i in range(1, len(times) - 1):                              # turning points of the sea level
        a, b, c = level[i - 1], level[i], level[i + 1]
        if None in (a, b, c):
            continue
        if (b > a and b >= c) or (b < a and b <= c):
            tides.setdefault(times[i][:10], []).append({"time": times[i], "height": round(b, 2)})
    days = []
    for day in dict.fromkeys(t[:10] for t in times):
        idx = [i for i, t in enumerate(times) if t.startswith(day)]
        waves = [wave[i] for i in idx if wave[i] is not None]
        swells = [(swell[i], i) for i in idx if swell[i] is not None]
        temps = [sst[i] for i in idx if sst[i] is not None]
        top = max(swells)[1] if swells else None
        days.append({"day": day, "wave_max": max(waves) if waves else None,
                     "swell_max": max(swells)[0] if swells else None,
                     "swell_period": period[top] if top is not None else None,
                     "swell_dir": direction[top] if top is not None else None,
                     "sst": round(sum(temps) / len(temps), 1) if temps else None, "tide": tides.get(day, [])})
    return days


def wind(lat: float, lon: float, fresh: bool = False) -> list[dict]:
    """The next 7 days' strongest wind at a place (km/h): [{day, wind_max, gusts}]. Kept an hour, like the others."""
    key = (round(lat, 2), round(lon, 2), "wind7")
    return _kept(key, lambda: _wind(key), fresh)


def _wind(key) -> list[dict]:
    data = _get(FORECAST, {"latitude": key[0], "longitude": key[1], "timezone": "auto", "forecast_days": 7,
                           "daily": "wind_speed_10m_max,wind_gusts_10m_max"})
    d = data.get("daily") or {}

    def col(name, i):
        values = d.get(name) or []
        return values[i] if i < len(values) else None
    return [{"day": day, "wind_max": col("wind_speed_10m_max", i), "gusts": col("wind_gusts_10m_max", i)}
            for i, day in enumerate(d.get("time") or [])]


def fishing_weather(lat: float, lon: float, fresh: bool = False) -> list[dict]:
    """The next 7 days for fishing (Open-Meteo, CC BY 4.0): [{day, wind_max, wind_dir (the dominant direction the wind blows
    FROM, degrees), gusts, pressure_mean (hPa at sea level), pressure_trend ('rising' | 'falling' | 'steady': against the
    day before, 2 hPa or more), rain_mm, temp_max}]. Kept an hour like the others (and the last good one, see _kept)."""
    key = (round(lat, 2), round(lon, 2), "fishing7")
    return _kept(key, lambda: _fishing_weather(key), fresh)


def _fishing_weather(key) -> list[dict]:
    data = _get(FORECAST, {"latitude": key[0], "longitude": key[1], "timezone": "auto", "past_days": 1, "forecast_days": 7,
                           "daily": "wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,precipitation_sum,temperature_2m_max",
                           "hourly": "pressure_msl"})
    d = data.get("daily") or {}
    h = data.get("hourly") or {}
    by_day: dict[str, list[float]] = {}
    for t, v in zip(h.get("time") or [], h.get("pressure_msl") or []):
        if v is not None:
            by_day.setdefault(t[:10], []).append(v)
    means = {day: sum(v) / len(v) for day, v in by_day.items()}

    def col(name, i):
        values = d.get(name) or []
        return values[i] if i < len(values) else None
    days = sorted(d.get("time") or [])
    out = []
    for i, day in enumerate(d.get("time") or []):
        before = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        now = means.get(day)
        trend = None
        if now is not None and before in means:
            diff = now - means[before]
            trend = "rising" if diff >= 2 else "falling" if diff <= -2 else "steady"
        out.append({"day": day, "wind_max": col("wind_speed_10m_max", i), "wind_dir": col("wind_direction_10m_dominant", i),
                    "gusts": col("wind_gusts_10m_max", i), "pressure_mean": round(now, 1) if now is not None else None,
                    "pressure_trend": trend, "rain_mm": col("precipitation_sum", i), "temp_max": col("temperature_2m_max", i)})
    first = days[0] if days else None
    return [x for x in out if x["day"] != first] if len(days) > 7 else out

