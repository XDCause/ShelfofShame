"""Scouting a game before you own it: search Steam by name (like Shop Tamiya), then see what its
100% takes - how many achievements, how rare they are (Steam's global %), and SteamHunters' median /
fastest time to 100% and 100% rate. Nothing is saved: answers are kept in memory for a while.

    GET /api/videogames/find?q=hollow knight   ->  Steam's store search, games only, with "yours"
    GET /api/videogames/scout/{app_id}         ->  one game's achievements + other players' numbers
"""
import re
import time

from fastapi import APIRouter, HTTPException, Query

from . import steam, steamhunters
from .db import db

router = APIRouter(prefix="/api", tags=["video games"])

NOT_GAMES = re.compile(r"\b(soundtrack|ost|artbook|art book)\b", re.I)   # sold as "apps" too
KEEP = 3600            # seconds an answer is kept (searches and scouted games)
_found: dict[str, tuple[float, list]] = {}
_scouted: dict[int, tuple[float, dict]] = {}


def _cached(store: dict, key):
    hit = store.get(key)
    if hit and time.monotonic() - hit[0] < KEEP:
        return hit[1]
    store.pop(key, None)
    return None


def yours(app_ids: list[int]) -> dict[int, dict]:
    """{app id: {"id", "platform"}} for the games you already track: on Steam (the panel id is the
    app id), or an Epic / Ubisoft game whose Steam version it is ("ubisoft-12")."""
    if not app_ids:
        return {}
    with db() as conn:
        rows = conn.execute("""
            SELECT app_id, app_id::text AS id, 'steam' AS platform, 0 AS pick FROM vg_games WHERE app_id = ANY(%(ids)s)
            UNION ALL
            SELECT steam_app_id, platform || '-' || game_id, platform, 1 FROM vg_other_games WHERE steam_app_id = ANY(%(ids)s)
            ORDER BY pick""", {"ids": app_ids}).fetchall()
    mine = {}
    for r in rows:
        mine.setdefault(r["app_id"], {"id": int(r["id"]) if r["platform"] == "steam" else r["id"], "platform": r["platform"]})
    return mine


@router.get("/videogames/find")
def find(q: str = Query(..., min_length=2, max_length=80)):
    """Games on Steam matching the words (Steam's own store search; up to about 10, best first)."""
    key = " ".join(q.casefold().split())
    results = _cached(_found, key)
    if results is None:
        try:
            items = steam.store_search(key)
        except steam.SteamError as e:
            raise HTTPException(502, str(e))
        results = [{"app_id": int(i["id"]), "name": i.get("name") or f"App {i['id']}", "picture": i.get("tiny_image"),
                    "price": (i.get("price") or {}).get("final", 0) / 100 if i.get("price") else None}
                   for i in items if i.get("type") == "app" and i.get("id") and not NOT_GAMES.search(i.get("name") or "")]
        _found[key] = (time.monotonic(), results)
    mine = yours([r["app_id"] for r in results])
    return [{**r, "yours": mine.get(r["app_id"])} for r in results]


@router.get("/videogames/scout/{app_id}")
def scout(app_id: int):
    """One Steam game, owned or not: picture, its achievements (most players have them first) with
    rarity, and SteamHunters' numbers. Steam's parts need the API key; SteamHunters is optional."""
    game = _cached(_scouted, app_id)
    if game is None:
        game = _read(app_id)
        _scouted[app_id] = (time.monotonic(), game)
    return {**game, "yours": yours([app_id]).get(app_id)}


def _read(app_id: int) -> dict:
    try:
        item = steam.store_items([app_id]).get(app_id)
        if not item:
            raise HTTPException(404, "Steam's store doesn't know that game.")
        listed = steam.schema(app_id)
        percents = steam.global_percentages(app_id) if listed else {}
    except steam.SteamError as e:
        raise HTTPException(502, str(e))
    notes = []
    community = {}
    gone = set()
    if listed:
        try:
            community = steamhunters.game(app_id) or {}
            if community.get("sh_unobtainable"):
                gone = steamhunters.unobtainable(app_id)
        except steamhunters.Unavailable as e:
            notes.append(f"{e} Other players' times aren't shown.")
    achievements = sorted(({
        "api_name": a["name"], "name": a.get("displayName") or a["name"], "description": a.get("description"),
        "icon": a.get("icon"), "hidden": bool(a.get("hidden")),          # colour icons: nothing is "locked" here
        "global_percent": round(percents[a["name"]], 1) if a["name"] in percents else None,
        "achieved": False, "unobtainable": a["name"] in gone,
    } for a in listed), key=lambda a: (a["global_percent"] is None, -(a["global_percent"] or 0)))
    known = [a["global_percent"] for a in achievements if a["global_percent"] is not None and not a["unobtainable"]]
    started, perfected = community.get("sh_players_started"), community.get("sh_players_perfected")
    return {
        "app_id": app_id, "name": item["name"] or f"App {app_id}", "header_url": item["header"],
        "achievements_total": sum(1 for a in achievements if not a["unobtainable"]),
        "unobtainable_count": len(gone),
        "ultra_rare": sum(1 for p in known if p <= 5),
        "rarest_percent": min(known) if known else None,
        "perfect_rate": round(100.0 * perfected / started, 1) if started and perfected is not None else None,
        **{k: community.get(k) for k in ("sh_median_minutes", "sh_fastest_minutes", "sh_players_perfected",
                                         "sh_players_started", "sh_points", "sh_has_dlc")},
        "achievements": achievements, "notes": notes,
    }
