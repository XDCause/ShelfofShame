"""Last.fm's official API (https://www.last.fm/api): scrobbling the records you play.

Needs an API account (https://www.last.fm/api/account/create - free): LASTFM_API_KEY and LASTFM_API_SECRET in .env,
passed in by docker-compose. Connecting is Last.fm's desktop flow - the app asks for a token, you allow it on last.fm,
then the app swaps the token for a session key (kept in vinyl_settings, never sent to the browser). The key and secret
never appear in logs or error messages.

    configured()          both set in .env
    get_token()           a token to allow on last.fm
    allow_url(token)      the page where you allow it
    get_session(token)    -> (username, session key)
    scrobble(sk, tracks)  [{artist, track, album, timestamp}] -> how many Last.fm accepted (50 a call)
"""
import hashlib
import os

import httpx

API = "https://ws.audioscrobbler.com/2.0/"
TIMEOUT = 20
HEADERS = {"User-Agent": "OffTheClock/1.0 +https://github.com/XDCause/ShelfofShame"}


class LastfmError(Exception):
    """Something the user can act on: not set up, the session refused, Last.fm unreachable."""


def _keys() -> tuple[str, str]:
    key, secret = os.environ.get("LASTFM_API_KEY", "").strip(), os.environ.get("LASTFM_API_SECRET", "").strip()
    if not key or not secret:
        raise LastfmError("Last.fm isn't set up yet: add LASTFM_API_KEY and LASTFM_API_SECRET to the .env file, then restart.")
    return key, secret


def configured() -> bool:
    return bool(os.environ.get("LASTFM_API_KEY", "").strip() and os.environ.get("LASTFM_API_SECRET", "").strip())


def _signed(params: dict) -> dict:
    """Last.fm's signature: md5 of every parameter (name + value, sorted by name) and the secret."""
    key, secret = _keys()
    params = {**params, "api_key": key}
    base = "".join(f"{k}{params[k]}" for k in sorted(params)) + secret
    return {**params, "api_sig": hashlib.md5(base.encode("utf-8")).hexdigest(), "format": "json"}


def _post(params: dict) -> dict:
    try:
        r = httpx.post(API, data=_signed(params), headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise LastfmError(f"Couldn't reach Last.fm ({e.__class__.__name__}).") from None
    try:
        data = r.json()
    except ValueError:
        raise LastfmError(f"Last.fm sent something unexpected (HTTP {r.status_code}).") from None
    if isinstance(data, dict) and data.get("error"):
        code = data["error"]
        if code in (4, 14, 15):
            raise LastfmError("Last.fm hasn't been allowed yet - open the link, press Yes, allow access, then try again.")
        if code == 9:
            raise LastfmError("Last.fm no longer accepts this connection - connect again.")
        if code == 29:
            raise LastfmError("Last.fm is limiting requests right now - try again later.")
        if code in (10, 26):
            raise LastfmError("Last.fm refused the API key. Check LASTFM_API_KEY and LASTFM_API_SECRET in .env.")
        raise LastfmError(f"Last.fm said no ({str(data.get('message') or code)[:120]}).")
    return data


def get_token() -> str:
    _keys()                                     # not set up: say so before asking
    token = (_post({"method": "auth.getToken"}) or {}).get("token")
    if not token:
        raise LastfmError("Last.fm didn't give a token.")
    return token


def allow_url(token: str) -> str:
    key, _ = _keys()
    return f"https://www.last.fm/api/auth/?api_key={key}&token={token}"


def get_session(token: str) -> tuple[str, str]:
    _keys()
    s = (_post({"method": "auth.getSession", "token": token}) or {}).get("session") or {}
    if not s.get("key"):
        raise LastfmError("Last.fm didn't give a session.")
    return s.get("name") or "", s["key"]


def scrobble(session_key: str, tracks: list[dict]) -> int:
    accepted = 0
    for start in range(0, len(tracks), 50):
        params = {"method": "track.scrobble", "sk": session_key}
        for i, t in enumerate(tracks[start:start + 50]):
            params.update({f"artist[{i}]": t["artist"], f"track[{i}]": t["track"], f"timestamp[{i}]": str(int(t["timestamp"]))})
            if t.get("album"):
                params[f"album[{i}]"] = t["album"]
        data = _post(params)
        accepted += int((((data.get("scrobbles") or {}).get("@attr") or {}).get("accepted")) or 0)
    return accepted
