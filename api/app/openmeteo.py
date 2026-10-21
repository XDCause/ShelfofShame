"""Open-Meteo (https://open-meteo.com): free weather forecasts, no key (free for non-commercial use;
CC BY 4.0 - credited where the tips show). Used by Gardening for balcony tips: heat, wind, rain, UV.

    find_place(name)     -> [{name, region, country, lat, lon}]   (their geocoding API; country = its ISO code)
    forecast(lat, lon)   -> the next 3 days: [{day, max, min, rain_mm, rain_chance, gusts, uv, code, sky, icon}]
                            (sky / icon: the day's weather code in words - Sunny, Cloudy, Rain...)

The forecast is kept for an hour (one request an hour at most, whatever the page does).
"""
import time

import httpx

from .openlibrary import HEADERS

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 20
KEEP = 3600
_cache: dict[tuple, tuple[float, list]] = {}


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


def _get(url: str, params: dict) -> dict:
    try:
        r = httpx.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise WeatherError(f"Couldn't reach Open-Meteo ({e.__class__.__name__}).") from None
    if r.status_code != 200:
        raise WeatherError(f"Open-Meteo didn't answer (HTTP {r.status_code}).")
    return r.json()


def find_place(name: str) -> list[dict]:
    data = _get(GEOCODE, {"name": name, "count": 6, "language": "en", "format": "json"})
    return [{"name": p["name"], "region": ", ".join(filter(None, [p.get("admin1"), p.get("country")])),
             "country": (p.get("country_code") or "").upper() or None,
             "lat": round(p["latitude"], 4), "lon": round(p["longitude"], 4)} for p in data.get("results") or []]


def forecast(lat: float, lon: float) -> list[dict]:
    key = (round(lat, 2), round(lon, 2))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < KEEP:
        return hit[1]
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
    _cache[key] = (time.time(), days)
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
