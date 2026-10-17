"""Open-Meteo (https://open-meteo.com): free weather forecasts, no key (free for non-commercial use;
CC BY 4.0 - credited where the tips show). Used by Gardening for balcony tips: heat, wind, rain, UV.

    find_place(name)     -> [{name, region, lat, lon}]   (their geocoding API; to set where you are)
    forecast(lat, lon)   -> the next 3 days: [{day, max, min, rain_mm, rain_chance, gusts, uv}]

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
             "lat": round(p["latitude"], 4), "lon": round(p["longitude"], 4)} for p in data.get("results") or []]


def forecast(lat: float, lon: float) -> list[dict]:
    key = (round(lat, 2), round(lon, 2))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < KEEP:
        return hit[1]
    data = _get(FORECAST, {"latitude": key[0], "longitude": key[1], "timezone": "auto", "forecast_days": 3,
                           "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
                                    "wind_gusts_10m_max,uv_index_max"})
    d = data.get("daily") or {}

    def col(name, i):
        values = d.get(name) or []
        return values[i] if i < len(values) else None
    days = [{"day": day, "max": col("temperature_2m_max", i), "min": col("temperature_2m_min", i),
             "rain_mm": col("precipitation_sum", i), "rain_chance": col("precipitation_probability_max", i),
             "gusts": col("wind_gusts_10m_max", i), "uv": col("uv_index_max", i)} for i, day in enumerate(d.get("time") or [])]
    _cache[key] = (time.time(), days)
    return days
