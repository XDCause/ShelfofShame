"""The official Steam Web API (https://steamcommunity.com/dev): your games and achievements.

Needs a free key (STEAM_API_KEY in .env, passed in by docker-compose) and a profile whose "Game
details" are public. Steam allows 100,000 calls a day per key; a sync makes about three per game
the first time and then only for games you've played since. The key never appears in logs or
error messages.

    resolve(profile)          a profile name ("SomeGamer"), id or profile URL -> SteamID64
    persona(steam_id)         the account's display name
    owned_games(steam_id)     every game owned, with playtime and when it was last played
    player_achievements(...)  which achievements you have, and when you unlocked them
    schema(app_id)            each achievement's name, description and icons
    global_percentages(...)   how many players have each achievement (its rarity)
    store_items(app_ids)      each game's name and header picture address (store API, 50 a call)
    header_pictures(app_ids)  just the pictures
    app_id_from(text)         a store link, community link or plain number -> the app id
"""
import json
import os
import re
import time

import httpx

API = "https://api.steampowered.com"
# Store pictures live under per-game hashed paths these days; the store API says which.
PICTURES = "https://shared.akamai.steamstatic.com/store_item_assets/"
TIMEOUT = 20
PAUSE = 0.15          # between calls during a sync: gentle on Steam
HEADERS = {"User-Agent": "Off the Clock (personal hobby tracker)"}


class SteamError(Exception):
    """Something the user can act on: no key, profile not found or private, Steam unreachable."""


class NoStats(Exception):
    """The game has no achievements (Steam: "Requested app has no stats")."""


def key() -> str:
    k = os.environ.get("STEAM_API_KEY", "").strip()
    if not k:
        raise SteamError("No Steam API key yet: add STEAM_API_KEY to the .env file, then restart.")
    return k


def _get(path: str, params: dict, with_key: bool = True):
    """GET an API method, returning its JSON. Errors never include the key."""
    query = {**params, **({"key": key()} if with_key else {}), "format": "json"}
    try:
        r = httpx.get(f"{API}/{path}", params=query, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise SteamError(f"Couldn't reach Steam ({e.__class__.__name__}).") from None
    if r.status_code == 403 and with_key and "playerstats" not in r.text:
        raise SteamError("Steam refused the API key. Check STEAM_API_KEY in .env.")
    if r.status_code == 429:
        raise SteamError("Steam says too many requests. Try again later.")
    try:
        return r.status_code, r.json()
    except ValueError:
        raise SteamError(f"Steam sent something unexpected (HTTP {r.status_code}).") from None


def resolve(profile: str) -> str:
    """A profile name, 17-digit id, or a steamcommunity.com /id/ or /profiles/ URL -> SteamID64."""
    text = profile.strip().rstrip("/")
    m = re.search(r"steamcommunity\.com/(id|profiles)/([^/?#]+)", text)
    if m:
        text = m.group(2)
    if re.fullmatch(r"7656\d{13}", text):
        return text
    _, data = _get("ISteamUser/ResolveVanityURL/v1/", {"vanityurl": text})
    res = data.get("response", {})
    if res.get("success") != 1:
        raise SteamError(f"No Steam profile called '{text}'. Use the name in your profile's address.")
    return res["steamid"]


def persona(steam_id: str) -> str | None:
    _, data = _get("ISteamUser/GetPlayerSummaries/v2/", {"steamids": steam_id})
    players = data.get("response", {}).get("players", [])
    return players[0].get("personaname") if players else None


def owned_games(steam_id: str) -> list[dict]:
    """[{appid, name, img_icon_url, playtime_forever, playtime_2weeks, rtime_last_played}]"""
    # skip_unvetted_apps=0: Steam leaves some small games out of the list unless asked (3 of the user's,
    # e.g. HoloCure - Save the Fans!); SteamHunters counts them.
    _, data = _get("IPlayerService/GetOwnedGames/v1/",
                   {"steamid": steam_id, "include_appinfo": 1, "include_played_free_games": 1, "skip_unvetted_apps": 0})
    res = data.get("response", {})
    if "games" not in res:
        if res.get("game_count") == 0:
            return []
        raise SteamError("Steam didn't share the games list. Set your profile's Game details to Public "
                         "(Steam > Profile > Edit Profile > Privacy Settings).")
    return res["games"]


def player_achievements(steam_id: str, app_id: int) -> list[dict]:
    """[{apiname, achieved (0/1), unlocktime (unix)}]. NoStats if the game has none."""
    _, data = _get("ISteamUserStats/GetPlayerAchievements/v1/", {"steamid": steam_id, "appid": app_id})
    stats = data.get("playerstats", {})
    if stats.get("success"):
        return stats.get("achievements", [])
    error = str(stats.get("error", ""))
    if "no stats" in error.lower():
        raise NoStats(error)
    if "not public" in error.lower():
        raise SteamError("Steam says your profile isn't public. Set Game details to Public.")
    raise SteamError(f"Steam couldn't give the achievements for game {app_id}: {error or 'no reason given'}.")


def schema(app_id: int) -> list[dict]:
    """[{name (api name), displayName, description, hidden, icon, icongray}]"""
    _, data = _get("ISteamUserStats/GetSchemaForGame/v2/", {"appid": app_id})
    return data.get("game", {}).get("availableGameStats", {}).get("achievements", []) or []


def global_percentages(app_id: int) -> dict[str, float]:
    """{api name: % of players who have it}. Public data: no key needed."""
    _, data = _get("ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/", {"gameid": app_id}, with_key=False)
    rows = data.get("achievementpercentages", {}).get("achievements", []) or []
    return {r["name"]: float(r["percent"]) for r in rows if "name" in r and "percent" in r}


def app_id_from(text: str) -> int | None:
    """730, "https://store.steampowered.com/app/730/CounterStrike_2/", ".../stats/730/achievements" -> 730."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    m = re.search(r"/(?:app|stats)/(\d+)", text)
    return int(m.group(1)) if m else None


def store_items(app_ids: list[int]) -> dict[int, dict]:
    """{app id: {"name", "header"}} from the store (IStoreBrowseService/GetItems, 50 games a call).
    header is None when the store has no picture (e.g. a game removed from the store); games the
    store doesn't know at all are left out."""
    found = {}
    for start in range(0, len(app_ids), 50):
        batch = app_ids[start:start + 50]
        request = {"ids": [{"appid": a} for a in batch], "context": {"language": "english", "country_code": "AU"},
                   "data_request": {"include_assets": True}}
        _, data = _get("IStoreBrowseService/GetItems/v1/", {"input_json": json.dumps(request)})
        for item in data.get("response", {}).get("store_items", []) or []:
            if not item.get("appid"):
                continue
            assets = item.get("assets") or {}
            form, header = assets.get("asset_url_format"), assets.get("header")
            found[item["appid"]] = {"name": item.get("name"),
                                    "header": PICTURES + form.replace("${FILENAME}", header) if form and header else None}
        pause()
    return found


def header_pictures(app_ids: list[int]) -> dict[int, str | None]:
    """{app id: the game's header picture address, or None if the store has none}."""
    items = store_items(app_ids)
    return {a: (items.get(a) or {}).get("header") for a in app_ids}


def pause():
    time.sleep(PAUSE)
