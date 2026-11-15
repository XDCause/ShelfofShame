"""The Lichess opening explorer (https://explorer.lichess.ovh): what people really play from a position, from every
rated Lichess game (/lichess, filtered by rating and speed) and from master games (/masters).

    explore(fen, source, ratings, speeds)   {total, white, draws, black, moves: [{san, uci, games, share, white, draws, black,
                                            avg_rating}]} - asked once, then kept in the database for 30 days
    band_for(rating)                        the explorer's rating groups around a player (1450 -> "1400,1600")

Lichess wants a personal token (LICHESS_TOKEN in .env: lichess.org/account/oauth/token, no scopes needed) and a polite
client: one request at a time, about one a second, and a User-Agent that says who's asking. No token, or the site
down: LichessError, which the trainer shows as "the explorer can't be reached" while everything else keeps working
from the bundled opening list (chess_openings.py). Tests fake _get (api/tests/conftest.py); the walk-through's
stand-ins answer instead (stand_ins.py).
"""
import os
import threading
import time
from datetime import timedelta

import httpx
from psycopg.types.json import Jsonb

from .db import db

URL = "https://explorer.lichess.ovh/{source}"
HEADERS = {"User-Agent": "Off the Clock (personal hobby tracker; one user)", "Accept": "application/json"}
TIMEOUT = 20
PAUSE = 1.1                          # seconds between live requests
KEEP = timedelta(days=30)
SOURCES = ("lichess", "masters")
BANDS = (0, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500)      # the explorer's rating groups
SPEEDS = "blitz,rapid,classical"
UNREACHABLE = "The Lichess explorer can't be reached - showing the opening list only."

_gate = threading.Lock()
_last = [0.0]


class LichessError(Exception):
    """A message for the user: no token, Lichess unreachable, too many requests..."""


def token() -> str:
    return os.environ.get("LICHESS_TOKEN", "").strip()


def _get(source: str, params: dict) -> dict:
    """One live request. Waits its turn (one at a time, ~1 a second). Never logs the token."""
    t = token()
    if not t:
        raise LichessError(UNREACHABLE + " (No Lichess token is set.)")
    with _gate:
        wait = PAUSE - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            r = httpx.get(URL.format(source=source), params=params, headers={**HEADERS, "Authorization": f"Bearer {t}"},
                          timeout=TIMEOUT, follow_redirects=True)
        except httpx.HTTPError as e:
            raise LichessError(f"{UNREACHABLE} ({e.__class__.__name__})") from None
        finally:
            _last[0] = time.monotonic()
    if r.status_code == 429:
        raise LichessError("Lichess says too many requests. Try again in a minute.")
    if r.status_code in (401, 403):
        raise LichessError("Lichess didn't accept the token (check LICHESS_TOKEN).")
    if r.status_code != 200:
        raise LichessError(f"{UNREACHABLE} (HTTP {r.status_code})")
    try:
        return r.json()
    except ValueError:
        raise LichessError(UNREACHABLE) from None


def band_for(rating: int | None) -> str:
    """The explorer's rating groups around a rating: the group it's in and the next one up."""
    if not rating:
        return "1400,1600,1800"
    i = max(i for i, b in enumerate(BANDS) if b <= rating)
    return ",".join(str(b) for b in BANDS[i:i + 2])


def _clean(raw: dict) -> dict:
    """The explorer's answer, cut down to what the app uses."""
    moves = []
    total = (raw.get("white") or 0) + (raw.get("draws") or 0) + (raw.get("black") or 0)
    for m in raw.get("moves") or []:
        n = (m.get("white") or 0) + (m.get("draws") or 0) + (m.get("black") or 0)
        if not n or not m.get("uci") or not m.get("san"):
            continue
        moves.append({"san": m["san"], "uci": m["uci"], "games": n, "share": round(100 * n / total, 1) if total else 0,
                      "white": round(100 * m["white"] / n), "draws": round(100 * m["draws"] / n),
                      "black": round(100 * m["black"] / n), "avg_rating": m.get("averageRating")})
    return {"total": total, "white": raw.get("white") or 0, "draws": raw.get("draws") or 0, "black": raw.get("black") or 0,
            "moves": moves}


def explore(fen: str, source: str = "lichess", ratings: str | None = None, speeds: str = SPEEDS,
            fresh: bool = False) -> dict:
    """What's played from this position. Kept 30 days: a position is only asked once (fresh=True asks again - the
    weekly site check). The answer has "live": True when it came from Lichess just now, not from the cache."""
    if source not in SOURCES:
        raise LichessError("Unknown explorer source.")
    epd = " ".join(fen.split()[:4])                      # (the move counters don't change what's played)
    key = f"{source}|{epd}|{ratings or ''}|{speeds}" if source == "lichess" else f"masters|{epd}"
    if not fresh:
        with db() as conn:
            row = conn.execute("SELECT answer FROM chess_explorer_cache WHERE key = %s AND fetched_at > now() - %s::interval",
                               (key, KEEP)).fetchone()
        if row:
            return {**row["answer"], "live": False}
    params = {"fen": fen, "moves": 12, "topGames": 0, "recentGames": 0}
    if source == "lichess":
        params.update(ratings=ratings or band_for(None), speeds=speeds)
    answer = _clean(_get(source, params))
    with db() as conn:
        conn.execute("""INSERT INTO chess_explorer_cache (key, answer, fetched_at) VALUES (%s, %s, now())
                        ON CONFLICT (key) DO UPDATE SET answer = EXCLUDED.answer, fetched_at = now()""", (key, Jsonb(answer)))
        conn.execute("DELETE FROM chess_explorer_cache WHERE fetched_at < now() - %s::interval", (KEEP,))
    return {**answer, "live": True}
