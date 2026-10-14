"""How other players did with a game, from SteamHunters' public JSON API (steamhunters.com/api).

    GET https://steamhunters.com/api/apps/<app id>  ->  medianCompletionTime, fastestCompletionTime
        (minutes to 100%), playersPerfectedCount, playersStartedCount, points, ...

SteamHunters' web pages are behind a Cloudflare bot check, but this API answers plain requests and
is what their open-source browser extension uses. No terms or rate limits are published, so it's
used gently: only the user's started games, one request a second, saved in the database and read
again only during a sync (games played since, a weekly refresh, or everything on a full sync).
Personal use only - see BEFORE_GOING_PUBLIC.md.
"""
import time

import httpx

API = "https://steamhunters.com/api/apps/{app_id}"
HEADERS = {"User-Agent": "Off the Clock (personal hobby tracker; one user, gentle)", "Accept": "application/json"}
TIMEOUT = 20
PAUSE = 1.0


class Unavailable(Exception):
    """SteamHunters can't be reached right now (or answered with a bot check): try again next sync."""


def _get(url: str):
    try:
        return httpx.get(url, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise Unavailable(f"Couldn't reach SteamHunters ({e.__class__.__name__}).") from None


def game(app_id: int) -> dict | None:
    """The community numbers for a game, or None if SteamHunters doesn't know it."""
    r = _get(API.format(app_id=app_id))
    if r.status_code == 404:
        return None
    if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
        raise Unavailable(f"SteamHunters didn't answer (HTTP {r.status_code}).")
    d = r.json()
    return {
        "sh_median_minutes": d.get("medianCompletionTime"),
        "sh_fastest_minutes": d.get("fastestCompletionTime"),
        "sh_players_perfected": d.get("playersPerfectedCount"),
        "sh_players_started": d.get("playersStartedCount"),
        "sh_points": d.get("points"),
    }


def pause():
    time.sleep(PAUSE)
