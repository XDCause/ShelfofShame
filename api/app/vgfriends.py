"""Video games: Steam friends - who they are, what they're playing, and how they're doing on the games
you both have with achievements. Official Steam Web API only (steam.py).

    friends     your Steam friends list (only when it's public - Steam answers 401 otherwise) plus
                anyone you add by their profile; names, pictures and online status re-read when the
                page asks (at most every 10 minutes)
    compare     on request, per friend, in the background: their games list (their Game details must
                be public), then their achievements in each game you both own that has achievements
                (one request a game, paced like the sync)

    GET    /videogames/friends                  the friends + what was compared
    POST   /videogames/friends/refresh          re-read the list and their status now
    POST   /videogames/friends                  {profile} add one by hand (a name, id or profile link)
    DELETE /videogames/friends/{id}             remove one you added; hide one from your list
    POST   /videogames/friends/{id}/compare     start comparing (202); GET /videogames/friends/{id} = the result
"""
import logging
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel, Field

from . import steam
from .db import db, found

router = APIRouter(prefix="/api", tags=["video games"])
log = logging.getLogger("vgfriends")

FRESH = timedelta(minutes=10)
STATE = {"list_public": None, "error": None}        # what the last refresh found out about your friends list
COMPARING: dict[str, dict] = {}                    # steam id -> {done, total} while a compare runs
_lock = threading.Lock()


class FriendIn(BaseModel):
    profile: str = Field(min_length=2, max_length=300)


def my_steam_id(conn) -> str:
    row = conn.execute("SELECT steam_id FROM vg_sync WHERE id = 1").fetchone()
    if not row or not row["steam_id"]:
        raise HTTPException(409, "Connect your Steam profile first (Video games > Dashboard).")
    return row["steam_id"]


FRIEND_SELECT = """
SELECT f.*, (SELECT count(*) FROM vg_friend_games x WHERE x.steam_id = f.steam_id)::int AS common,
       (SELECT count(*) FROM vg_friend_games x JOIN vg_games g USING (app_id)
         WHERE x.steam_id = f.steam_id AND x.total > 0 AND g.achievements_total > 0
           AND 1.0 * g.achievements_done / g.achievements_total > 1.0 * x.done / x.total)::int AS you_ahead,
       (SELECT count(*) FROM vg_friend_games x JOIN vg_games g USING (app_id)
         WHERE x.steam_id = f.steam_id AND x.total > 0 AND g.achievements_total > 0
           AND 1.0 * g.achievements_done / g.achievements_total < 1.0 * x.done / x.total)::int AS they_ahead,
       (SELECT count(*) FROM vg_friend_games x WHERE x.steam_id = f.steam_id AND x.total > 0 AND x.done >= x.total)::int
           AS their_perfect
FROM vg_friends f"""


def refresh(force: bool = False):
    """Re-read your friends list (when public) and everyone's name, picture and status."""
    with _lock:
        with db() as conn:
            me = my_steam_id(conn)
            newest = conn.execute("SELECT max(seen_at) AS t FROM vg_friends").fetchone()["t"]
        if not force and newest and datetime.now(timezone.utc) - newest < FRESH and STATE["list_public"] is not None:
            return
        try:
            listed = steam.friend_ids(me)
            STATE.update(list_public=True, error=None)
        except steam.FriendsPrivate as e:
            listed, STATE["list_public"], STATE["error"] = None, False, str(e)
        except steam.SteamError as e:
            STATE["error"] = str(e)
            return
        with db() as conn:
            if listed is not None:
                conn.execute("UPDATE vg_friends SET from_list = (steam_id = ANY(%s))", (listed,))
                for sid in listed:
                    conn.execute("INSERT INTO vg_friends (steam_id, from_list) VALUES (%s, true) ON CONFLICT (steam_id) "
                                 "DO UPDATE SET from_list = true", (sid,))
            ids = [r["steam_id"] for r in conn.execute("SELECT steam_id FROM vg_friends").fetchall()]
        try:
            people = steam.summaries(ids)
        except steam.SteamError as e:
            STATE["error"] = str(e)
            return
        with db() as conn:
            for sid, p in people.items():
                conn.execute("UPDATE vg_friends SET name = %s, avatar_url = %s, profile_url = %s, public = %s, status = %s, "
                             "playing = %s, seen_at = now() WHERE steam_id = %s",
                             (p["name"], p["avatar"], p["profile_url"], p["public"], p["status"], p["playing"], sid))
            # Gone from your list and never added by hand: forget them (and what was compared).
            conn.execute("DELETE FROM vg_friends WHERE NOT from_list AND NOT by_hand")


@router.get("/videogames/friends")
def list_friends():
    """Your friends: playing now first, then online, then by name. list_public: whether your Steam
    friends list could be read (None = not asked yet)."""
    with db() as conn:
        friends = conn.execute(FRIEND_SELECT + """ WHERE NOT f.hidden ORDER BY f.playing IS NULL,
                               f.status IS NULL OR f.status = 'Offline', lower(f.name)""").fetchall()
        hidden = conn.execute("SELECT count(*) AS n FROM vg_friends WHERE hidden").fetchone()["n"]
    for f in friends:
        f["comparing"] = COMPARING.get(f["steam_id"])
    return {"friends": friends, "hidden": hidden, **STATE}


@router.post("/videogames/friends/refresh")
def refresh_now(force: bool = False):
    refresh(force)
    return list_friends()


@router.post("/videogames/friends", status_code=201)
def add_friend(body: FriendIn):
    """Add someone by their Steam profile (works whether or not your friends list is public)."""
    try:
        sid = steam.resolve(body.profile)
    except steam.SteamError as e:
        raise HTTPException(422, str(e))
    with db() as conn:
        if sid == my_steam_id(conn):
            raise HTTPException(422, "That's you.")
        conn.execute("INSERT INTO vg_friends (steam_id, by_hand) VALUES (%s, true) ON CONFLICT (steam_id) "
                     "DO UPDATE SET by_hand = true, hidden = false", (sid,))
    try:
        p = steam.summaries([sid]).get(sid)
    except steam.SteamError:
        p = None
    if p:
        with db() as conn:
            conn.execute("UPDATE vg_friends SET name = %s, avatar_url = %s, profile_url = %s, public = %s, status = %s, "
                         "playing = %s, seen_at = now() WHERE steam_id = %s",
                         (p["name"], p["avatar"], p["profile_url"], p["public"], p["status"], p["playing"], sid))
    return get_friend(sid)


@router.delete("/videogames/friends/{steam_id}", status_code=204)
def remove_friend(steam_id: str):
    """One you added: removed (with what was compared). One from your Steam list: hidden."""
    with db() as conn:
        f = found(conn.execute("SELECT from_list FROM vg_friends WHERE steam_id = %s", (steam_id,)).fetchone(), "Friend")
        if f["from_list"]:
            conn.execute("UPDATE vg_friends SET hidden = true, by_hand = false WHERE steam_id = %s", (steam_id,))
        else:
            conn.execute("DELETE FROM vg_friends WHERE steam_id = %s", (steam_id,))
    return Response(status_code=204)


@router.get("/videogames/friends/{steam_id}")
def get_friend(steam_id: str):
    """A friend and the games you both have with achievements: your progress and theirs."""
    with db() as conn:
        friend = found(conn.execute(FRIEND_SELECT + " WHERE f.steam_id = %s", (steam_id,)).fetchone(), "Friend")
        friend["games"] = conn.execute("""
            SELECT x.app_id, g.name, g.header_url, x.playtime_minutes AS their_minutes, g.playtime_minutes AS my_minutes,
                   g.achievements_done AS my_done, g.achievements_total AS my_total,
                   CASE WHEN g.achievements_total > 0 THEN round(100.0 * g.achievements_done / g.achievements_total, 1) END
                       AS my_percent,
                   x.done AS their_done, x.total AS their_total,
                   CASE WHEN x.total > 0 THEN round(100.0 * x.done / x.total, 1) END AS their_percent
            FROM vg_friend_games x JOIN vg_games g USING (app_id)
            WHERE x.steam_id = %s
            ORDER BY greatest(g.achievements_done, coalesce(x.done, 0)) DESC, lower(g.name)""", (steam_id,)).fetchall()
    friend["comparing"] = COMPARING.get(steam_id)
    for g in friend["games"]:
        if not g["header_url"]:
            g["header_url"] = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{g['app_id']}/header.jpg"
    return friend


@router.post("/videogames/friends/{steam_id}/compare", status_code=202)
def start_compare(steam_id: str, background: BackgroundTasks):
    with db() as conn:
        found(conn.execute("SELECT 1 FROM vg_friends WHERE steam_id = %s", (steam_id,)).fetchone(), "Friend")
    if steam_id not in COMPARING:
        COMPARING[steam_id] = {"done": 0, "total": 0}
        background.add_task(compare, steam_id)
    return get_friend(steam_id)


def compare(steam_id: str):
    """Their games list, then their achievements in each game you both have with achievements."""
    error = None
    try:
        try:
            theirs = {g["appid"]: g for g in steam.owned_games(steam_id)}
        except steam.SteamError:
            raise steam.SteamError("Their Game details are private, so their games can't be compared.") from None
        with db() as conn:
            mine = [r["app_id"] for r in conn.execute(
                "SELECT app_id FROM vg_games WHERE achievements_total > 0 AND NOT hidden").fetchall()]
        common = [a for a in mine if a in theirs]
        COMPARING[steam_id] = {"done": 0, "total": len(common)}
        rows = []
        for app_id in common:
            try:
                got = steam.player_achievements(steam_id, app_id)
                rows.append((app_id, theirs[app_id].get("playtime_forever"), sum(1 for a in got if a.get("achieved")), len(got)))
            except steam.NoStats:
                rows.append((app_id, theirs[app_id].get("playtime_forever"), None, None))
            except steam.SteamError:
                rows.append((app_id, theirs[app_id].get("playtime_forever"), None, None))
            COMPARING[steam_id]["done"] += 1
            steam.pause()
        with db() as conn:
            conn.execute("DELETE FROM vg_friend_games WHERE steam_id = %s", (steam_id,))
            for app_id, minutes, done, total in rows:
                conn.execute("INSERT INTO vg_friend_games (steam_id, app_id, playtime_minutes, done, total) "
                             "VALUES (%s, %s, %s, %s, %s)", (steam_id, app_id, minutes, done, total))
            conn.execute("UPDATE vg_friends SET games_owned = %s WHERE steam_id = %s", (len(theirs), steam_id))
    except steam.SteamError as e:
        error = str(e)
    except Exception as e:                       # noqa: BLE001 - shown on the friend
        log.warning("Comparing with %s failed: %s", steam_id, e)
        error = "Something went wrong comparing - try again."
    finally:
        with db() as conn:
            conn.execute("UPDATE vg_friends SET compared_at = now(), compare_error = %s WHERE steam_id = %s", (error, steam_id))
        COMPARING.pop(steam_id, None)
