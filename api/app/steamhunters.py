"""How other players did with a game, from SteamHunters' public JSON API (steamhunters.com/api).

    GET https://steamhunters.com/api/apps/<app id>  ->  medianCompletionTime, fastestCompletionTime
        (minutes to 100%), playersPerfectedCount, playersStartedCount, points, hasPaidDlc, ...
    GET https://steamhunters.com/api/apps/<app id>/related  ->  the game's DLCs (and trailers etc.)
    GET https://steamhunters.com/api/apps/<app id>/achievements  ->  each one's apiName and
        obtainability (3 = unobtainable; only asked for games whose unobtainableAchievementCount > 0)

SteamHunters' web pages are behind a Cloudflare bot check, but this API answers plain requests and
is what their open-source browser extension uses. No terms or rate limits are published, so it's
used gently: only the user's started games, one request a second, saved in the database and read
again only during a sync (games played since, a weekly refresh, or everything on a full sync).
Personal use only - see BEFORE_GOING_PUBLIC.md.
"""
import threading
import time

import httpx

API = "https://steamhunters.com/api/apps/{app_id}"
HEADERS = {"User-Agent": "Off the Clock (personal hobby tracker; one user, gentle)", "Accept": "application/json"}
TIMEOUT = 20
PAUSE = 1.0


class Unavailable(Exception):
    """SteamHunters can't be reached right now (or answered with a bot check): try again next sync."""


def _get(url: str):
    """One request (spaced: never two at once, at least PAUSE apart - the sync reads this site from
    two threads at times); if it times out (they're sometimes slow for a moment), one more try 5 s later."""
    for attempt in (1, 2):
        _spaced()
        try:
            return httpx.get(url, headers=HEADERS, timeout=TIMEOUT)
        except httpx.TimeoutException:
            if attempt == 1:
                time.sleep(5)
                continue
            raise Unavailable("Couldn't reach SteamHunters (it timed out twice).") from None
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
        "sh_has_dlc": d.get("hasPaidDlc"),
        "sh_unobtainable": d.get("unobtainableAchievementCount") or 0,
    }


UNOBTAINABLE = 3   # SteamHunters' obtainability for "can't be earned any more"


def unobtainable(app_id: int) -> set[str]:
    """Steam's api names of the game's achievements that can't be earned any more."""
    r = _get(API.format(app_id=app_id) + "/achievements")
    if r.status_code == 404:
        return set()
    if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
        raise Unavailable(f"SteamHunters didn't answer (HTTP {r.status_code}).")
    return {a["apiName"] for a in r.json() if a.get("obtainability") == UNOBTAINABLE and a.get("apiName")}


def dlc_names(app_id: int) -> list[str]:
    """The names of a game's DLCs (to tell real DLC from free updates on Exophase's pages)."""
    r = _get(API.format(app_id=app_id) + "/related")
    if r.status_code == 404:
        return []
    if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
        raise Unavailable(f"SteamHunters didn't answer (HTTP {r.status_code}).")
    return [a["name"] for a in r.json() if (a.get("typeString") or "").lower() == "dlc" and a.get("name")]


def pause():
    time.sleep(PAUSE)


_turn = threading.Lock()
_last = [0.0]


def _spaced():
    """Wait until PAUSE has passed since this site was last asked (any thread)."""
    with _turn:
        wait = _last[0] + PAUSE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
