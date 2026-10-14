"""chess.com's official public API (https://www.chess.com/news/view/published-data-api): read-only,
no login - just the username.

    GET /pub/player/<user>                 profile (name, avatar, title, url, joined)
    GET /pub/player/<user>/stats           rating / best / record per time control, puzzles
    GET /pub/player/<user>/games/archives  the months that have games
    GET /pub/player/<user>/games/YYYY/MM   that month's games (players, ratings, results, PGN,
                                           opening link, accuracies when reviewed)

chess.com asks for requests one at a time (parallel ones can get HTTP 429) and a User-Agent that
says who's asking; past months are cached by the caller and never asked again.
"""
import re
import time
from datetime import datetime, timezone
from urllib.parse import unquote

import httpx

API = "https://api.chess.com/pub/player/{user}"
HEADERS = {"User-Agent": "Off the Clock (personal hobby tracker; one user)", "Accept": "application/json"}
TIMEOUT = 30
PAUSE = 0.5

DRAWS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


class ChessError(Exception):
    """A message for the user: no such player, chess.com unreachable..."""


class NotFound(ChessError):
    pass


def _get(url: str):
    try:
        r = httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError as e:
        raise ChessError(f"Couldn't reach chess.com ({e.__class__.__name__}).") from None
    if r.status_code == 404:
        raise NotFound("chess.com has no player by that name.")
    if r.status_code == 429:
        raise ChessError("chess.com says too many requests. Try again in a minute.")
    if r.status_code != 200:
        raise ChessError(f"chess.com didn't answer (HTTP {r.status_code}).")
    return r.json()


def pause():
    time.sleep(PAUSE)


def username_from(text: str) -> str | None:
    """"Some_Player" or "https://www.chess.com/member/Some_Player" -> "some_player" (chess.com's
    usernames aren't case-sensitive; the API wants lower case)."""
    m = re.search(r"chess\.com/(?:member|stats/\w+/\w+)/([A-Za-z0-9_-]+)", text)
    name = (m.group(1) if m else text).strip()
    return name.lower() if re.fullmatch(r"[A-Za-z0-9_-]{3,25}", name) else None


def profile(user: str) -> dict:
    return _get(API.format(user=user))


def stats(user: str) -> dict:
    return _get(API.format(user=user) + "/stats")


def archives(user: str) -> list[str]:
    """The months with games, oldest first, as 'YYYY-MM'."""
    urls = _get(API.format(user=user) + "/games/archives").get("archives") or []
    return [f"{u.rstrip('/').split('/')[-2]}-{u.rstrip('/').split('/')[-1]}" for u in urls]


def month(user: str, ym: str) -> list[dict]:
    """One month's games, as chess.com sends them."""
    y, m = ym.split("-")
    return _get(API.format(user=user) + f"/games/{y}/{m}").get("games") or []


FAMILY_END = re.compile(r"\b(Opening|Defense|Defence|Gambit|Game|Attack|System|Variation)\b")


def opening_names(eco_url: str | None) -> tuple[str | None, str | None]:
    """chess.com's opening link -> (opening, family):
    ".../openings/Sicilian-Defense-Najdorf-Variation-6.Be3" -> ("Sicilian Defense Najdorf Variation",
    "Sicilian Defense"). The moves at the end are dropped."""
    if not eco_url or "/openings/" not in eco_url:
        return None, None
    words = unquote(eco_url.rstrip("/").split("/openings/")[-1]).split("-")
    kept = []
    for w in words:
        if re.match(r"^\d+\.", w) or re.match(r"^\d+\.\.\.", w):     # "6.Be3", "3...e6": the moves begin
            break
        kept.append(w)
    name = " ".join(kept).strip() or None
    return (name, family_of(name)) if name else (None, None)


def family_of(opening: str) -> str:
    """"Sicilian Defense Najdorf Variation" -> "Sicilian Defense"; "Italian Game Two Knights" ->
    "Italian Game"; a name with no such word stays whole (up to " Variation")."""
    m = FAMILY_END.search(opening)
    return opening[:m.end()] if m and m.group(1) != "Variation" else opening.split(" Variation")[0]


def _pgn_tag(pgn: str, tag: str) -> str | None:
    m = re.search(rf'\[{tag} "([^"]*)"\]', pgn or "")
    return m.group(1) if m and m.group(1) not in ("", "?") else None


def game_row(g: dict, user: str) -> dict | None:
    """One chess.com game as a chess_games row (from your side), or None if you're not in it."""
    white, black = g.get("white") or {}, g.get("black") or {}
    if (white.get("username") or "").lower() == user:
        me, them, colour = white, black, "white"
    elif (black.get("username") or "").lower() == user:
        me, them, colour = black, white, "black"
    else:
        return None
    mine, theirs = me.get("result"), them.get("result")
    result = "win" if mine == "win" else "draw" if mine in DRAWS else "loss"
    pgn = g.get("pgn") or ""
    eco_url = g.get("eco") or _pgn_tag(pgn, "ECOUrl")
    opening, family = opening_names(eco_url)
    full_moves = len(re.findall(r"\b\d+\.(?!\.)", re.sub(r"\{[^}]*\}", "", pgn.split("\n\n", 1)[-1]))) if pgn else None
    accuracies = g.get("accuracies") or {}
    time_class = g.get("time_class")
    return {
        "uuid": g.get("uuid") or g.get("url"), "url": g.get("url"),
        "played_at": datetime.fromtimestamp(g["end_time"], timezone.utc),
        "time_class": time_class if time_class in ("bullet", "blitz", "rapid", "daily") else "rapid",
        "time_control": g.get("time_control"), "rated": bool(g.get("rated", True)), "rules": g.get("rules") or "chess",
        "colour": colour, "my_rating": me.get("rating"), "opp_name": them.get("username") or "?",
        "opp_rating": them.get("rating"), "result": result, "how": theirs if result == "win" else mine,
        "eco": _pgn_tag(pgn, "ECO"), "opening": opening, "opening_family": family, "pgn": pgn or None,
        "moves": full_moves, "accuracy": accuracies.get(colour), "opp_accuracy": accuracies.get("black" if colour == "white" else "white"),
    }
