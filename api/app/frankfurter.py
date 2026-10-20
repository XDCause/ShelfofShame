"""Frankfurter (https://frankfurter.dev): exchange rates published by the European Central Bank, free, no key.
Used by Travel to turn what a trip costs in yen or dollars into AUD.

    rates()            -> {"date": "2026-10-19", "aud_per": {"JPY": 0.009046, "USD": 1.4315, ...}}
    aud_per(currency)  -> AUD for one unit of it (1 for AUD), or None if the ECB doesn't publish it (VND...)

One request every 12 hours at most: the ECB publishes once a working day.
"""
import time

import httpx

from .openlibrary import HEADERS

URL = "https://api.frankfurter.dev/v1/latest"
TIMEOUT = 20
KEEP = 12 * 3600
_cache: dict[str, tuple[float, dict]] = {}


class RatesError(Exception):
    """Frankfurter couldn't be asked; the message says why."""


def _get(url: str, params: dict) -> dict:
    try:
        r = httpx.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise RatesError(f"Couldn't reach the exchange rates (Frankfurter: {e.__class__.__name__}).") from None
    if r.status_code != 200:
        raise RatesError(f"The exchange rates didn't answer (Frankfurter: HTTP {r.status_code}).")
    return r.json()


def rates() -> dict:
    hit = _cache.get("AUD")
    if hit and time.time() - hit[0] < KEEP:
        return hit[1]
    data = _get(URL, {"base": "AUD"})
    per_aud = data.get("rates") or {}
    answer = {"date": data.get("date"),
              "aud_per": {c: round(1 / v, 8) for c, v in per_aud.items() if isinstance(v, (int, float)) and v > 0}}
    if not answer["aud_per"]:
        raise RatesError("The exchange rates came back empty (Frankfurter).")
    _cache["AUD"] = (time.time(), answer)
    return answer


def aud_per(currency: str) -> float | None:
    if currency == "AUD":
        return 1.0
    return rates()["aud_per"].get(currency)
