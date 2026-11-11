"""Vinyl, the outside parts (split from vinyl.py): Discogs sync, what records are worth, Last.fm.

    settings   GET / PUT /vinyl/settings: the Discogs account, "keep Discogs in step", Last.fm; and how the sync and the
               value check are going
    sync       POST /vinyl/discogs/sync (in the background; GET shows how far it got): your Discogs collection and
               wantlist come in - new copies are added, ones you have get their Discogs link (your grades, notes and stars
               fill blanks; nothing of yours is overwritten). Then each new record's full pressing (tracklist, country,
               barcode, have / want) and its cover, then values. Records only in the app stay - the app is the truth.
    values     what each record you own is worth: Discogs' price suggestion for your record's grade (VG+ if not graded),
               converted to AUD (frankfurter.py), else the lowest copy for sale. Checked weekly by itself (start_weekly,
               from main.py when DISCOGS_TOKEN is set), or now (POST /vinyl/values/check). Each check goes in the
               record's value history. Wanted records get Discogs' lowest price in their wishlist price history.
    last.fm    connect (start -> allow on last.fm -> finish), disconnect; each play's tracks are scrobbled (vinyl.py
               starts it), timed to end when you logged the play; Last.fm takes plays up to 14 days old

Discogs allows 60 requests a minute with a token: calls in a row wait discogs.PAUSE.
"""
import logging
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel

from . import discogs, frankfurter, lastfm
from .db import db, insert_row, update_row
from .vinyl import apply_release, fetch_cover, save_value

router = APIRouter(prefix="/api", tags=["vinyl"])
log = logging.getLogger("vinyl")

WEEKLY = timedelta(days=7)
SYNC = {"running": False, "stage": None, "done": 0, "total": 0, "added": 0, "linked": 0, "wanted": 0, "only_here": 0,
        "error": None, "finished_at": None}
VALUES = {"running": False, "done": 0, "total": 0, "valued": 0, "error": None, "finished_at": None}
_lock = threading.Lock()


def _settings(conn) -> dict:
    return conn.execute("SELECT * FROM vinyl_settings WHERE id = 1").fetchone()


# ---------------------------------------------------------------- settings
@router.get("/vinyl/settings")
def get_settings():
    with db() as conn:
        s = _settings(conn)
        linked = conn.execute("SELECT count(*) FILTER (WHERE discogs_instance_id IS NOT NULL)::int AS linked, "
                              "count(*) FILTER (WHERE status = 'Owned' AND discogs_instance_id IS NULL)::int AS only_here "
                              "FROM vinyl_records").fetchone()
    return {"discogs": {"token": discogs.has_token(), "username": s["discogs_username"], "synced_at": s["discogs_synced_at"],
                        "error": s["discogs_error"], "mirror": s["discogs_mirror"], **linked},
            "lastfm": {"configured": lastfm.configured(), "user": s["lastfm_user"], "connected": bool(s["lastfm_session"]),
                       "waiting": bool(s["lastfm_token"]), "auto": s["lastfm_auto"]},
            "sync": SYNC, "values": VALUES}


class SettingsIn(BaseModel):
    discogs_mirror: bool | None = None
    lastfm_auto: bool | None = None


@router.put("/vinyl/settings")
def put_settings(body: SettingsIn):
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    with db() as conn:
        update_row(conn, "vinyl_settings", "id", 1, data)
    return get_settings()


# ---------------------------------------------------------------- Discogs sync
def _fill(current: dict, data: dict) -> dict:
    """Only what's still blank on the record."""
    return {k: v for k, v in data.items() if v not in (None, "", []) and current.get(k) in (None, "", [])}


def _notes(item: dict) -> dict:
    """A collection item's grades and notes (Discogs' standard fields: 1 media, 2 sleeve, 3 notes) and stars."""
    fields = {n.get("field_id"): (n.get("value") or "").strip() for n in item.get("notes") or []}
    media, sleeve = discogs.GRADES.get(fields.get(1, "")), discogs.GRADES.get(fields.get(2, ""))
    return {"media_condition": media if media not in ("Generic", "No cover") else None, "sleeve_condition": sleeve,
            "notes": fields.get(3) or None, "rating": item.get("rating") or None}


def _day(text: str | None):
    try:
        return datetime.fromisoformat(text).date() if text else None
    except ValueError:
        return None


def sync_discogs():
    """Bring your Discogs collection and wantlist in, then the details, covers and values (see the module notes)."""
    with _lock:
        if SYNC["running"]:
            return
        SYNC.update(running=True, stage="collection", done=0, total=0, added=0, linked=0, wanted=0, only_here=0, error=None)
    try:
        user = discogs.identity()
        with db() as conn:
            conn.execute("UPDATE vinyl_settings SET discogs_username = %s, discogs_error = NULL WHERE id = 1", (user,))
        discogs.pause()
        seen = set()
        for item in discogs.collection(user):
            rid, instance = item.get("id"), item.get("instance_id")
            if not rid or not instance:
                continue
            seen.add(instance)
            basic = discogs.record_from(basic=item.get("basic_information") or {})
            mine = _notes(item)
            with db() as conn:
                r = conn.execute("SELECT * FROM vinyl_records WHERE discogs_instance_id = %s", (instance,)).fetchone() or \
                    conn.execute("SELECT * FROM vinyl_records WHERE discogs_release_id = %s AND discogs_instance_id IS NULL "
                                 "AND status <> 'Gone' ORDER BY status = 'Owned' DESC, record_id LIMIT 1", (rid,)).fetchone()
                if r:
                    data = _fill(r, mine)
                    if r["discogs_instance_id"] is None:
                        data["discogs_instance_id"] = instance
                        SYNC["linked"] += 1
                    if r["status"] == "Wanted":                   # you've got it now
                        data.update(status="Owned", added_on=_day(item.get("date_added")) or r["added_on"])
                    update_row(conn, "vinyl_records", "record_id", r["record_id"], data)
                else:
                    insert_row(conn, "vinyl_records", {**basic, **{k: v for k, v in mine.items() if v is not None},
                                                       "status": "Owned", "discogs_instance_id": instance,
                                                       "added_on": _day(item.get("date_added")) or datetime.now().date()}, "record_id")
                    SYNC["added"] += 1
            SYNC["done"] += 1
        SYNC["stage"] = "wantlist"
        discogs.pause()
        for item in discogs.wants(user):
            rid = item.get("id")
            if not rid:
                continue
            with db() as conn:
                if conn.execute("SELECT 1 FROM vinyl_records WHERE discogs_release_id = %s", (rid,)).fetchone():
                    continue
                basic = discogs.record_from(basic=item.get("basic_information") or {})
                insert_row(conn, "vinyl_records", {**basic, "status": "Wanted", "notes": (item.get("notes") or "").strip() or None,
                                                   "added_on": _day(item.get("date_added")) or datetime.now().date()}, "record_id")
                SYNC["wanted"] += 1
        with db() as conn:
            SYNC["only_here"] = conn.execute(
                "SELECT count(*)::int AS n FROM vinyl_records WHERE status = 'Owned' AND NOT (discogs_instance_id = ANY(%s)) "
                "OR status = 'Owned' AND discogs_instance_id IS NULL", (list(seen),)).fetchone()["n"]
        _details()
        _values()
        with db() as conn:
            conn.execute("UPDATE vinyl_settings SET discogs_synced_at = now(), discogs_error = NULL WHERE id = 1")
    except discogs.DiscogsError as e:
        SYNC["error"] = str(e)
        with db() as conn:
            conn.execute("UPDATE vinyl_settings SET discogs_error = %s WHERE id = 1", (str(e),))
    except Exception as e:  # noqa: BLE001 - say so on the page rather than die quietly
        log.exception("Discogs sync failed")
        SYNC["error"] = f"The sync stopped ({e.__class__.__name__})."
    finally:
        SYNC.update(running=False, stage=None, finished_at=datetime.now(timezone.utc))


def _details():
    """Each record not yet read in full: its pressing from Discogs (and its master's first year), then its cover."""
    with db() as conn:
        todo = conn.execute("SELECT record_id, discogs_release_id, discogs_master_id FROM vinyl_records "
                            "WHERE discogs_release_id IS NOT NULL AND details_at IS NULL ORDER BY record_id").fetchall()
    SYNC.update(stage="details", done=0, total=len(todo))
    for r in todo:
        discogs.pause()
        full = discogs.release(r["discogs_release_id"])
        facts = discogs.record_from(full=full) if full else {}
        if facts.get("discogs_master_id"):
            discogs.pause()
            facts["original_year"] = discogs.master_year(facts["discogs_master_id"])
        with db() as conn:
            if facts:
                apply_release(conn, r["record_id"], facts)
            else:                                            # gone from Discogs: don't ask again
                conn.execute("UPDATE vinyl_records SET details_at = now() WHERE record_id = %s", (r["record_id"],))
        SYNC["done"] += 1
    with db() as conn:
        covers = [r["record_id"] for r in conn.execute(
            "SELECT record_id FROM vinyl_records WHERE photo IS NULL AND cover_url IS NOT NULL ORDER BY record_id").fetchall()]
    SYNC.update(stage="covers", done=0, total=len(covers))
    for record_id in covers:
        discogs.pause()
        fetch_cover(record_id)
        SYNC["done"] += 1


def _need_token():
    """No token: say so now, not from the background."""
    try:
        discogs.token()
    except discogs.DiscogsError as e:
        raise HTTPException(409, str(e)) from None


@router.post("/vinyl/discogs/sync", status_code=202)
def start_sync(background: BackgroundTasks):
    """Sync with your Discogs collection and wantlist now (in the background; GET shows how far it got)."""
    _need_token()
    background.add_task(sync_discogs)
    return {**SYNC, "running": True}


@router.get("/vinyl/discogs/sync")
def sync_status():
    return SYNC


# ---------------------------------------------------------------- values
def _aud(value: float, currency: str) -> float | None:
    try:
        rate = frankfurter.aud_per(currency)
    except frankfurter.RatesError:
        return None
    return round(value * rate, 2) if rate else None


def value_of(record: dict) -> tuple[float | None, str | None, dict]:
    """(value in AUD, where it came from, the release's fresh numbers) for one record."""
    full = discogs.release(record["discogs_release_id"]) or {}
    fresh = {k: v for k, v in discogs.record_from(full=full).items()
             if k in ("have_count", "want_count", "community_rating", "lowest_price", "for_sale")} if full else {}
    if record["status"] != "Owned":
        return None, None, fresh
    grade = record["media_condition"] or "VG+"
    discogs.pause()
    suggested = discogs.price_suggestion(record["discogs_release_id"]).get(grade)
    if suggested:
        aud = _aud(*suggested)
        if aud is not None:
            return aud, f"Discogs' suggested price for {grade}", fresh
    if fresh.get("lowest_price") is not None:
        return round(float(fresh["lowest_price"]), 2), "The cheapest copy for sale on Discogs", fresh
    return None, None, fresh


def check_value(record: dict):
    """Ask Discogs about one record and keep what it says (value + history; wanted: the wishlist's price history)."""
    from .wanted_more import record_price
    value, note, fresh = value_of(record)
    with db() as conn:
        data = {**fresh, "value_checked_at": datetime.now(timezone.utc)}
        if record["status"] == "Owned" and value is not None and record.get("value_note") != "Your value":
            data.update(value=value, value_note=note)
            save_value(conn, record["record_id"], value, note)
        update_row(conn, "vinyl_records", "record_id", record["record_id"], data)
        if record["status"] == "Wanted" and fresh.get("lowest_price") is not None:
            record_price(conn, "record", record["record_id"], fresh["lowest_price"], "Discogs")
    return value


def _values(force: bool = False):
    """Every record you own or want that's linked to Discogs and wasn't checked in the last week (all with force)."""
    with _lock:
        if VALUES["running"]:
            return
        VALUES.update(running=True, done=0, total=0, valued=0, error=None)
    try:
        with db() as conn:
            todo = conn.execute("""SELECT record_id, status, discogs_release_id, media_condition, value_note FROM vinyl_records
                                   WHERE status IN ('Owned', 'Wanted') AND discogs_release_id IS NOT NULL
                                     AND (%s OR value_checked_at IS NULL OR value_checked_at < now() - interval '6 days 20 hours')
                                   ORDER BY value_checked_at NULLS FIRST, record_id""", (force,)).fetchall()
        VALUES["total"] = len(todo)
        if SYNC["running"]:
            SYNC.update(stage="values", done=0, total=len(todo))
        for r in todo:
            discogs.pause()
            if check_value(r) is not None:
                VALUES["valued"] += 1
            VALUES["done"] += 1
            if SYNC["running"]:
                SYNC["done"] += 1
    except discogs.DiscogsError as e:
        VALUES["error"] = str(e)
    except Exception as e:  # noqa: BLE001
        log.exception("Vinyl value check failed")
        VALUES["error"] = f"The value check stopped ({e.__class__.__name__})."
    finally:
        VALUES.update(running=False, finished_at=datetime.now(timezone.utc))


@router.post("/vinyl/values/check", status_code=202)
def start_values(background: BackgroundTasks):
    """Check every record's value now (in the background, about two seconds a record)."""
    _need_token()
    background.add_task(_values, True)
    return {**VALUES, "running": True}


@router.get("/vinyl/values/check")
def values_status():
    return VALUES


def start_weekly():
    """While the app runs (with a Discogs token): values a week old are checked again (looked at every 6 hours)."""
    def loop():
        while True:
            try:
                if discogs.has_token() and not SYNC["running"]:
                    _values()
            except Exception:  # noqa: BLE001 - the database restarting...: try again later
                log.exception("Weekly vinyl value check failed")
            threading.Event().wait(6 * 3600)
    threading.Thread(target=loop, daemon=True, name="vinyl-values-weekly").start()


# ---------------------------------------------------------------- Last.fm
@router.post("/vinyl/lastfm/start")
def lastfm_start():
    """Step 1 of connecting: a token, and the last.fm page where you allow the app."""
    try:
        token = lastfm.get_token()
    except lastfm.LastfmError as e:
        raise HTTPException(502, str(e)) from None
    with db() as conn:
        conn.execute("UPDATE vinyl_settings SET lastfm_token = %s WHERE id = 1", (token,))
    return {"url": lastfm.allow_url(token)}


@router.post("/vinyl/lastfm/finish")
def lastfm_finish():
    """Step 2, after you've allowed it on last.fm: the session the app scrobbles with."""
    with db() as conn:
        token = _settings(conn)["lastfm_token"]
    if not token:
        raise HTTPException(409, "Start connecting first.")
    try:
        user, key = lastfm.get_session(token)
    except lastfm.LastfmError as e:
        raise HTTPException(502, str(e)) from None
    with db() as conn:
        conn.execute("UPDATE vinyl_settings SET lastfm_user = %s, lastfm_session = %s, lastfm_token = NULL WHERE id = 1", (user, key))
    return get_settings()


@router.delete("/vinyl/lastfm", status_code=204)
def lastfm_disconnect():
    with db() as conn:
        conn.execute("UPDATE vinyl_settings SET lastfm_user = NULL, lastfm_session = NULL, lastfm_token = NULL WHERE id = 1")
    return Response(status_code=204)


def _seconds(duration: str) -> int:
    """"3:41" -> 221; "1:02:03" -> 3723; blank -> 3.5 minutes."""
    try:
        parts = [int(p) for p in (duration or "").split(":") if p.strip() != ""]
    except ValueError:
        parts = []
    total = 0
    for p in parts:
        total = total * 60 + p
    return total if 0 < total < 4 * 3600 else 210


def side_of(position: str) -> str:
    """"A1" -> "A", "B" -> "B", "1-3" / "3" -> "" (no sides: CDs)."""
    letters = ""
    for ch in (position or "").strip().upper():
        if ch.isalpha():
            letters += ch
        else:
            break
    return letters


def play_tracks(play: dict, record: dict) -> list[dict]:
    """The tracks a play covers (its sides, or all), timed back from when the play was logged."""
    wanted = {s.strip().upper() for s in (play["sides"] or "").replace("/", ",").replace("&", ",").split(",") if s.strip()}
    tracks = [t for t in record["tracklist"] or [] if t.get("title") and (not wanted or side_of(t.get("position")) in wanted)]
    lengths = [_seconds(t.get("duration")) for t in tracks]
    start = play["played_at"].timestamp() - sum(lengths)
    out, at = [], start
    for t, n in zip(tracks, lengths):
        out.append({"artist": record["artist"] or "Unknown artist", "track": t["title"], "album": record["title"], "timestamp": at})
        at += n
    return out


def scrobble_play(play_id: int) -> dict:
    """Send a play's tracks to Last.fm; the play remembers how many went, or why not."""
    with db() as conn:
        play = conn.execute("SELECT * FROM vinyl_plays WHERE play_id = %s", (play_id,)).fetchone()
        s = _settings(conn)
        if not play:
            return {}
        record = conn.execute("SELECT title, artist, tracklist FROM vinyl_records WHERE record_id = %s", (play["record_id"],)).fetchone()
    count, error = None, None
    if not s["lastfm_session"]:
        error = "Last.fm isn't connected."
    elif datetime.now(timezone.utc) - play["played_at"] > timedelta(days=14):
        error = "Last.fm only takes plays from the last 14 days."
    else:
        tracks = play_tracks(play, record)
        if not tracks:
            error = "No tracklist for those sides - add it (or read it from Discogs) to scrobble."
        else:
            try:
                count = lastfm.scrobble(s["lastfm_session"], tracks)
            except lastfm.LastfmError as e:
                error = str(e)
    with db() as conn:
        conn.execute("UPDATE vinyl_plays SET scrobbled = %s, scrobble_error = %s WHERE play_id = %s", (count, error, play_id))
    return {"play_id": play_id, "scrobbled": count, "scrobble_error": error}


@router.post("/vinyl/plays/{play_id}/scrobble")
def scrobble_again(play_id: int):
    """Send a play to Last.fm now (one that failed, or one you'd chosen not to)."""
    with db() as conn:
        if not conn.execute("SELECT 1 FROM vinyl_plays WHERE play_id = %s", (play_id,)).fetchone():
            raise HTTPException(404, "Play not found.")
    return scrobble_play(play_id)
