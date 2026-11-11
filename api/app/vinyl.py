"""Vinyl (a hobby module, 2026-11-11): your records, the listening log, and the collection in numbers.

    records   vinyl_records: Owned / Wanted / Gone; the pressing (from Discogs: discogs.py), your copy's grades, what you
              paid, the shelf it's on (a storage place), stars, notes, its cover; filters for the crate
    lookup    find a pressing on Discogs by words or the barcode on the back; adding one fills in its facts and fetches
              its cover in the background (and, if you chose that, adds it to your Discogs collection too)
    plays     vinyl_plays: you played it - when, which sides, a note; scrobbled to Last.fm if you've connected it
    pick      "What should I play?": something you haven't played for longest
    summary   for Home and the dashboard; stats: genres, decades, formats, artists, labels, plays per month, value
    export    every record you own as CSV (for insurance): pressing, grades, paid, today's value

The Discogs sync, the weekly value check and Last.fm are in vinyl_sync.py. Plays show on the calendar and in Recent
activity (activity.py); records can be @mentioned in the journal, and wanted ones are on the wishlist (kind 'record').
"""
import csv
import io
import random
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import discogs
from .db import db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["vinyl"])

STATUSES = ("Owned", "Wanted", "Gone")
MEDIUMS = ("Vinyl", "CD", "Cassette", "Other")
FORMATS = ("LP", "EP", "Single", "Box set", "Other")
SIZES = ('12"', '10"', '7"')
GRADES = ("M", "NM", "VG+", "VG", "G+", "G", "F", "P")
SLEEVE_GRADES = GRADES + ("Generic", "No cover")
Status = Literal[STATUSES]
Medium = Literal[MEDIUMS]
Format = Literal[FORMATS]
Size = Literal[SIZES]
Grade = Literal[GRADES]
SleeveGrade = Literal[SLEEVE_GRADES]


class Track(BaseModel):
    position: str = Field("", max_length=20)
    title: str = Field("", max_length=300)
    duration: str = Field("", max_length=12)


class RecordIn(BaseModel):
    title: str | None = Field(None, max_length=300)        # may be left out when a Discogs release is given
    artist: str | None = Field(None, max_length=300)
    status: Status = "Owned"
    medium: Medium | None = None
    format: Format | None = None
    size: Size | None = None
    discs: int | None = Field(None, ge=1, le=100)
    year: int | None = Field(None, ge=1880, le=2200)
    original_year: int | None = Field(None, ge=1880, le=2200)
    country: str | None = Field(None, max_length=80)
    label: str | None = Field(None, max_length=200)
    catno: str | None = Field(None, max_length=80)
    barcode: str | None = Field(None, max_length=40)
    variant: str | None = Field(None, max_length=300)
    genres: list[str] | None = Field(None, max_length=20)
    styles: list[str] | None = Field(None, max_length=30)
    media_condition: Grade | None = None
    sleeve_condition: SleeveGrade | None = None
    price_paid: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    purchase_date: date | None = None
    bought_from: str | None = Field(None, max_length=200)
    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=5000)
    location_id: int | None = None
    discogs_release_id: int | None = Field(None, gt=0, lt=10 ** 12)   # found on Discogs: its facts and cover are read there


class RecordPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    artist: str | None = Field(None, max_length=300)
    status: Status | None = None
    medium: Medium | None = None
    format: Format | None = None
    size: Size | None = None
    discs: int | None = Field(None, ge=1, le=100)
    year: int | None = Field(None, ge=1880, le=2200)
    original_year: int | None = Field(None, ge=1880, le=2200)
    country: str | None = Field(None, max_length=80)
    label: str | None = Field(None, max_length=200)
    catno: str | None = Field(None, max_length=80)
    barcode: str | None = Field(None, max_length=40)
    variant: str | None = Field(None, max_length=300)
    genres: list[str] | None = Field(None, max_length=20)
    styles: list[str] | None = Field(None, max_length=30)
    tracklist: list[Track] | None = Field(None, max_length=200)
    media_condition: Grade | None = None
    sleeve_condition: SleeveGrade | None = None
    price_paid: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    purchase_date: date | None = None
    bought_from: str | None = Field(None, max_length=200)
    added_on: date | None = None
    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=5000)
    location_id: int | None = None
    value: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)    # your own idea of its value


class PlayIn(BaseModel):
    played_at: datetime | None = None       # default now
    sides: str | None = Field(None, max_length=40)   # "A, B" - empty = the whole record
    note: str | None = Field(None, max_length=2000)
    scrobble: bool | None = None            # None = your Last.fm setting


PHOTO = "CASE WHEN r.photo IS NOT NULL THEN '/api/vinyl/records/' || r.record_id || '/photo?v=' " \
        "|| (extract(epoch FROM r.photo_updated) * 1000)::bigint END"

LIST = f"""
SELECT r.record_id, r.title, r.artist, r.status, r.medium, r.format, r.size, r.discs, r.year, r.original_year, r.country,
       r.label, r.catno, r.variant, r.genres, r.styles, r.media_condition, r.sleeve_condition, r.price_paid::float8 AS price_paid,
       r.purchase_date, r.added_on, r.rating, r.value::float8 AS value, r.lowest_price::float8 AS lowest_price,
       r.discogs_release_id, r.location_id, {PHOTO} AS photo_url,
       COALESCE(p.plays, 0) AS plays, p.last_played
FROM vinyl_records r
LEFT JOIN LATERAL (SELECT count(*)::int AS plays, max(played_at) AS last_played FROM vinyl_plays WHERE record_id = r.record_id) p ON true"""

SORTS = {
    "artist": "lower(COALESCE(r.artist, '')), COALESCE(r.original_year, r.year), lower(r.title)",
    "title": "lower(r.title)",
    "added": "r.added_on DESC, r.record_id DESC",
    "year": "COALESCE(r.original_year, r.year) NULLS LAST, lower(COALESCE(r.artist, ''))",
    "played": "p.last_played DESC NULLS LAST, lower(COALESCE(r.artist, ''))",
    "dusty": "p.last_played NULLS FIRST, r.added_on",
    "plays": "COALESCE(p.plays, 0) DESC, lower(COALESCE(r.artist, ''))",
    "value": "r.value DESC NULLS LAST, lower(COALESCE(r.artist, ''))",
    "rating": "r.rating DESC NULLS LAST, lower(COALESCE(r.artist, ''))",
}


def _clean_list(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def fetch_record(conn, record_id: int) -> dict:
    r = found(conn.execute(f"""
        SELECT r.*, r.price_paid::float8 AS price_paid, r.value::float8 AS value, r.lowest_price::float8 AS lowest_price,
               r.community_rating::float8 AS community_rating, {PHOTO} AS photo_url, r.photo IS NOT NULL AS has_photo,
               l.name AS location
        FROM vinyl_records r LEFT JOIN storage_locations l ON l.location_id = r.location_id
        WHERE r.record_id = %s""", (record_id,)).fetchone(), "Record")
    del r["photo"]
    r["plays"] = conn.execute("SELECT play_id, played_at, sides, note, scrobbled, scrobble_error FROM vinyl_plays "
                              "WHERE record_id = %s ORDER BY played_at DESC, play_id DESC", (record_id,)).fetchall()
    r["values"] = conn.execute("SELECT seen_on, value::float8 AS value, note FROM vinyl_values WHERE record_id = %s "
                               "ORDER BY seen_on", (record_id,)).fetchall()
    r["discogs_url"] = r["discogs_release_id"] and f"https://www.discogs.com/release/{r['discogs_release_id']}"
    return r


def _check_location(conn, location_id):
    if location_id is not None:
        found(conn.execute("SELECT 1 FROM storage_locations WHERE location_id = %s", (location_id,)).fetchone(), "Storage place")


# ---------------------------------------------------------------- the crate
@router.get("/vinyl/records")
def list_records(status: Status | Literal["all"] | None = None, q: str | None = Query(None, max_length=200),
                 genre: str | None = Query(None, max_length=100), decade: int | None = Query(None, ge=1880, le=2200),
                 format: Format | None = None, medium: Medium | None = None,
                 sort: Literal[tuple(SORTS)] = "artist"):
    """Your records (Owned unless `status` says otherwise; "all" = every one), searched and filtered; with the
    counts per status and what the filters can be (genres, decades, formats) among them."""
    where, params = [], {}
    if status != "all":
        where.append("r.status = %(status)s")
        params["status"] = status or "Owned"
    if q and q.strip():
        where.append("(r.title ILIKE %(q)s OR r.artist ILIKE %(q)s OR r.label ILIKE %(q)s OR r.catno ILIKE %(q)s "
                     "OR array_to_string(r.genres || r.styles, ' ') ILIKE %(q)s OR r.notes ILIKE %(q)s)")
        params["q"] = f"%{q.strip()}%"
    if genre:
        where.append("(%(genre)s = ANY(r.genres) OR %(genre)s = ANY(r.styles))")
        params["genre"] = genre
    if decade:
        where.append("COALESCE(r.original_year, r.year) / 10 * 10 = %(decade)s")
        params["decade"] = decade // 10 * 10
    if format:
        where.append("r.format = %(format)s")
        params["format"] = format
    if medium:
        where.append("r.medium = %(medium)s")
        params["medium"] = medium
    sql = LIST + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {SORTS[sort]}, r.record_id"
    with db() as conn:
        records = conn.execute(sql, params).fetchall()
        counts = {s: 0 for s in STATUSES} | {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, count(*)::int AS n FROM vinyl_records GROUP BY status").fetchall()}
        mine = "WHERE status = %(s)s" if status != "all" else ""
        s = {"s": status or "Owned"}
        facets = {
            "genres": [r["g"] for r in conn.execute(f"SELECT DISTINCT unnest(genres) AS g FROM vinyl_records {mine} ORDER BY 1", s).fetchall()],
            "decades": [r["d"] for r in conn.execute(f"SELECT DISTINCT COALESCE(original_year, year) / 10 * 10 AS d FROM vinyl_records "
                                                       f"{mine} {'AND' if mine else 'WHERE'} COALESCE(original_year, year) IS NOT NULL ORDER BY 1", s).fetchall()],
            "formats": [r["f"] for r in conn.execute(f"SELECT DISTINCT format AS f FROM vinyl_records {mine} ORDER BY 1", s).fetchall()],
            "mediums": [r["m"] for r in conn.execute(f"SELECT DISTINCT medium AS m FROM vinyl_records {mine} ORDER BY 1", s).fetchall()],
        }
    return {"records": records, "counts": counts, "facets": facets}


@router.get("/vinyl/lookup")
def lookup(q: str | None = Query(None, min_length=2, max_length=200), barcode: str | None = Query(None, max_length=40)):
    """Pressings on Discogs matching the words or the barcode, each with `record_id` (and its status) if it's
    already one of yours."""
    code = "".join(ch for ch in (barcode or "") if ch.isdigit()) or None
    if not q and not code:
        raise HTTPException(422, "Type some words (artist, title, catalogue number) or a barcode.")
    try:
        results = discogs.search(q, code)
    except discogs.DiscogsError as e:
        raise HTTPException(502, str(e)) from None
    with db() as conn:
        for r in results:
            mine = conn.execute("SELECT record_id, status FROM vinyl_records WHERE discogs_release_id = %s "
                                "ORDER BY status = 'Gone', record_id LIMIT 1", (r["discogs_release_id"],)).fetchone()
            r["record_id"], r["my_status"] = (mine["record_id"], mine["status"]) if mine else (None, None)
    return {"results": results, "barcode": code}


# The pressing's facts Discogs gives (blanks are filled from it; refresh with replace=True puts all of them back) and
# what's only ever Discogs' (always taken).
FACTS = ("title", "artist", "medium", "format", "size", "discs", "year", "country", "label", "catno", "barcode", "variant",
         "genres", "styles")
DISCOGS_ONLY = ("tracklist", "discogs_master_id", "have_count", "want_count", "community_rating", "lowest_price", "for_sale",
                "cover_url")


def apply_release(conn, record_id: int, facts: dict, replace: bool = False):
    """Discogs' facts onto a record: blanks only (or all with replace); its own numbers always. details_at = now."""
    from psycopg.types.json import Jsonb
    current = conn.execute("SELECT * FROM vinyl_records WHERE record_id = %s", (record_id,)).fetchone()
    data = {k: facts[k] for k in FACTS if k in facts and facts[k] not in (None, "", [])
            and (replace or current[k] in (None, "", []) or (k in ("medium", "format", "discs") and current["details_at"] is None))}
    data.update({k: facts[k] for k in DISCOGS_ONLY if k in facts})
    if "tracklist" in data:
        data["tracklist"] = Jsonb(data["tracklist"])
    if facts.get("original_year") and (replace or not current["original_year"]):
        data["original_year"] = facts["original_year"]
    if facts.get("cover_url") and facts["cover_url"] != current["cover_url"] and replace:
        data["photo"] = None                   # a new cover: fetched again
    if facts.get("discogs_release_id"):
        data["discogs_release_id"] = facts["discogs_release_id"]
    data["details_at"] = datetime.now().astimezone()
    update_row(conn, "vinyl_records", "record_id", record_id, data)


def read_release(release_id: int) -> dict:
    """A release's facts from Discogs (one call, two with its master's first year), or a 4xx/502 the user can read."""
    try:
        full = discogs.release(release_id)
        if not full:
            raise HTTPException(404, "Discogs doesn't have that release.")
        facts = discogs.record_from(full=full)
        if facts.get("discogs_master_id"):
            discogs.pause()
            facts["original_year"] = discogs.master_year(facts["discogs_master_id"])
    except discogs.DiscogsError as e:
        raise HTTPException(502, str(e)) from None
    return facts


def fetch_cover(record_id: int):
    """In the background: the record's cover from Discogs, if it still has none."""
    with db() as conn:
        r = conn.execute("SELECT cover_url FROM vinyl_records WHERE record_id = %s AND photo IS NULL", (record_id,)).fetchone()
    if not r or not r["cover_url"]:
        return
    image, image_type = discogs.cover(r["cover_url"])
    if image:
        with db() as conn:
            conn.execute("UPDATE vinyl_records SET photo = %s, photo_type = %s, photo_updated = now() "
                         "WHERE record_id = %s AND photo IS NULL", (image, image_type, record_id))


@router.post("/vinyl/records", status_code=201)
def add_record(body: RecordIn, background: BackgroundTasks):
    """Add a record. With a Discogs release, its facts fill in what you left blank and its cover is fetched in the
    background; with "keep Discogs in step" on (vinyl_sync settings) an owned one goes into your Discogs collection too."""
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    for k in ("genres", "styles"):
        if k in data:
            data[k] = _clean_list(data[k])
    release_id = data.pop("discogs_release_id", None)
    facts = read_release(release_id) if release_id else None
    if not data.get("title") and not facts:
        raise HTTPException(422, "A record needs a title (or pick it on Discogs).")
    if not data.get("title"):
        data["title"] = facts["title"]
    data.setdefault("status", "Owned")
    instance = None
    with db() as conn:
        _check_location(conn, data.get("location_id"))
        mirror = conn.execute("SELECT discogs_username, discogs_mirror FROM vinyl_settings WHERE id = 1").fetchone()
    if facts and data["status"] == "Owned" and mirror["discogs_mirror"] and mirror["discogs_username"]:
        try:
            discogs.pause()
            instance = discogs.add_to_collection(mirror["discogs_username"], release_id)
        except discogs.DiscogsError as e:
            raise HTTPException(502, f"Not added: {e}") from None
    with db() as conn:
        record_id = insert_row(conn, "vinyl_records", {**data, "discogs_instance_id": instance}, "record_id")
        if facts:
            apply_release(conn, record_id, facts)
        record = fetch_record(conn, record_id)
    if facts and facts.get("cover_url"):
        background.add_task(fetch_cover, record_id)
    return record


@router.get("/vinyl/records/{record_id}")
def get_record(record_id: int):
    with db() as conn:
        return fetch_record(conn, record_id)


@router.patch("/vinyl/records/{record_id}")
def update_record(record_id: int, body: RecordPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    if "title" in data and not data["title"]:
        raise HTTPException(422, "A record needs a title.")
    for k in ("status", "medium", "format", "discs", "genres", "styles", "tracklist", "added_on"):
        if k in data and data[k] is None:
            raise HTTPException(422, f"{k.replace('_', ' ').capitalize()} can't be empty.")
    for k in ("genres", "styles"):
        if k in data:
            data[k] = _clean_list(data[k])
    if "tracklist" in data:
        from psycopg.types.json import Jsonb
        data["tracklist"] = Jsonb([t.model_dump() if hasattr(t, "model_dump") else t for t in data["tracklist"]])
    with db() as conn:
        fetch_record(conn, record_id)
        _check_location(conn, data.get("location_id"))
        if "value" in data:                      # your own value: kept in the history too
            data.update(value_note="Your value" if data["value"] is not None else None, value_checked_at=None)
            if data["value"] is not None:
                save_value(conn, record_id, data["value"], "Your value")
        update_row(conn, "vinyl_records", "record_id", record_id, data)
        return fetch_record(conn, record_id)


def save_value(conn, record_id: int, value, note: str):
    """Today's value for a record, in its history (one a day: a later one replaces it)."""
    conn.execute("""INSERT INTO vinyl_values (record_id, value, note) VALUES (%s, %s, %s)
                    ON CONFLICT (record_id, seen_on) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note""",
                 (record_id, value, note))


@router.delete("/vinyl/records/{record_id}", status_code=204)
def delete_record(record_id: int):
    """Delete a record and its plays (to keep the plays, mark it Gone instead). Your Discogs collection isn't changed."""
    with db() as conn:
        found(conn.execute("DELETE FROM vinyl_records WHERE record_id = %s RETURNING record_id", (record_id,)).fetchone(), "Record")
        conn.execute("DELETE FROM journal_links WHERE target_kind = 'record' AND target_id = %s", (record_id,))
    return Response(status_code=204)


@router.post("/vinyl/records/{record_id}/refresh")
def refresh_record(record_id: int, background: BackgroundTasks):
    """Read the pressing from Discogs again: its facts replace yours (your copy - grades, paid, notes - stays)."""
    with db() as conn:
        r = fetch_record(conn, record_id)
    if not r["discogs_release_id"]:
        raise HTTPException(409, "This record isn't linked to a Discogs release.")
    facts = read_release(r["discogs_release_id"])
    with db() as conn:
        apply_release(conn, record_id, facts, replace=True)
        record = fetch_record(conn, record_id)
    if not record["has_photo"]:
        background.add_task(fetch_cover, record_id)
    return record


add_photo_routes(router, "/vinyl/records", "vinyl_records", "record_id", "Record")


# ---------------------------------------------------------------- plays
@router.post("/vinyl/records/{record_id}/plays", status_code=201)
def log_play(record_id: int, body: PlayIn, background: BackgroundTasks):
    """You played it. Scrobbled to Last.fm in the background when you've connected it (and didn't say not to)."""
    from . import vinyl_sync
    data = tidy_text(body.model_dump(exclude={"scrobble"}))
    data["played_at"] = data["played_at"] or datetime.now().astimezone()
    with db() as conn:
        fetch_record(conn, record_id)
        play_id = insert_row(conn, "vinyl_plays", {"record_id": record_id, **data}, "play_id")
        s = conn.execute("SELECT lastfm_session, lastfm_auto FROM vinyl_settings WHERE id = 1").fetchone()
        play = conn.execute(PLAY_SELECT + " WHERE p.play_id = %s", (play_id,)).fetchone()
    if s["lastfm_session"] and (body.scrobble if body.scrobble is not None else s["lastfm_auto"]):
        background.add_task(vinyl_sync.scrobble_play, play_id)
        play["scrobbling"] = True
    return play


PLAY_SELECT = f"""
SELECT p.play_id, p.record_id, p.played_at, p.sides, p.note, p.scrobbled, p.scrobble_error, r.title, r.artist, r.format,
       {PHOTO} AS photo_url
FROM vinyl_plays p JOIN vinyl_records r USING (record_id)"""


@router.get("/vinyl/plays")
def list_plays(limit: int = Query(100, ge=1, le=2000)):
    """The listening log, newest first."""
    with db() as conn:
        return conn.execute(PLAY_SELECT + " ORDER BY p.played_at DESC, p.play_id DESC LIMIT %s", (limit,)).fetchall()


@router.delete("/vinyl/plays/{play_id}", status_code=204)
def delete_play(play_id: int):
    """Remove a play (Last.fm keeps a scrobble that was sent)."""
    with db() as conn:
        found(conn.execute("DELETE FROM vinyl_plays WHERE play_id = %s RETURNING play_id", (play_id,)).fetchone(), "Play")
    return Response(status_code=204)


@router.get("/vinyl/pick")
def pick(skip: list[int] = Query([])):
    """Something to play, at random: one you've never played, else one of the ten you've gone longest without playing.
    `skip` = ones already suggested."""
    with db() as conn:
        rows = conn.execute(LIST + " WHERE r.status = 'Owned' AND r.medium = 'Vinyl' AND NOT (r.record_id = ANY(%s)) "
                            "ORDER BY p.last_played NULLS FIRST, r.added_on LIMIT 10", (skip,)).fetchall()
        if not rows and skip:
            rows = conn.execute(LIST + " WHERE r.status = 'Owned' AND r.medium = 'Vinyl' ORDER BY p.last_played NULLS FIRST LIMIT 10").fetchall()
    never = [r for r in rows if r["last_played"] is None]
    return random.choice(never or rows) if rows else None


# ---------------------------------------------------------------- numbers
@router.get("/vinyl/summary")
def summary():
    """For Home and the dashboard: how many, plays this month / year, how much of the collection you've played this
    year, what it cost and what it's worth, now spinning, recently played and added, gathering dust."""
    with db() as conn:
        s = conn.execute("""
            SELECT count(*) FILTER (WHERE status = 'Owned')::int AS owned,
                   count(*) FILTER (WHERE status = 'Wanted')::int AS wanted,
                   count(*) FILTER (WHERE status = 'Gone')::int AS gone,
                   count(*) FILTER (WHERE status = 'Owned' AND added_on >= date_trunc('year', current_date))::int AS added_this_year,
                   COALESCE(sum(price_paid) FILTER (WHERE status = 'Owned'), 0)::float8 AS paid,
                   COALESCE(sum(value) FILTER (WHERE status = 'Owned'), 0)::float8 AS value,
                   count(*) FILTER (WHERE status = 'Owned' AND value IS NOT NULL)::int AS valued,
                   count(*) FILTER (WHERE status = 'Owned' AND price_paid IS NOT NULL)::int AS priced
            FROM vinyl_records""").fetchone()
        p = conn.execute("""
            SELECT count(*) FILTER (WHERE played_at >= date_trunc('month', now()))::int AS plays_this_month,
                   count(*) FILTER (WHERE played_at >= date_trunc('year', now()))::int AS plays_this_year,
                   count(*)::int AS plays,
                   count(DISTINCT record_id) FILTER (WHERE played_at >= date_trunc('year', now()))::int AS spun_this_year
            FROM vinyl_plays""").fetchone()
        s.update(p)
        s["year"] = conn.execute("SELECT extract(year FROM current_date)::int AS y").fetchone()["y"]
        s["recent_plays"] = conn.execute(PLAY_SELECT + " ORDER BY p.played_at DESC, p.play_id DESC LIMIT 6").fetchall()
        s["now_spinning"] = s["recent_plays"][0] if s["recent_plays"] and \
            (datetime.now().astimezone() - s["recent_plays"][0]["played_at"]).total_seconds() < 3 * 3600 else None
        s["recently_added"] = conn.execute(LIST + " WHERE r.status = 'Owned' ORDER BY r.added_on DESC, r.record_id DESC LIMIT 8").fetchall()
        s["dusty"] = conn.execute(LIST + " WHERE r.status = 'Owned' AND r.medium = 'Vinyl' "
                                  "AND (p.last_played IS NULL OR p.last_played < now() - interval '1 year') "
                                  "ORDER BY p.last_played NULLS FIRST, r.added_on LIMIT 6").fetchall()
        s["dusty_count"] = conn.execute("""SELECT count(*)::int AS n FROM vinyl_records r WHERE r.status = 'Owned' AND r.medium = 'Vinyl'
            AND NOT EXISTS (SELECT 1 FROM vinyl_plays p WHERE p.record_id = r.record_id AND p.played_at >= now() - interval '1 year')""").fetchone()["n"]
    return s


def _ym(d) -> str:
    return d.strftime("%Y-%m")


@router.get("/vinyl/stats")
def stats(months: int = Query(24, ge=1, le=120)):
    """The collection in numbers (records you own): genres, styles, decades, formats, artists, labels, countries, grades;
    the collection's growth; plays per month; the most played; value over time and the most valuable."""
    owned = "FROM vinyl_records WHERE status = 'Owned'"
    with db() as conn:
        def rows(sql, params=None):
            return conn.execute(sql, params or {}).fetchall()
        out = {
            "genres": rows(f"SELECT g AS label, count(*)::int AS n FROM (SELECT unnest(genres) AS g {owned}) x GROUP BY g ORDER BY n DESC, g LIMIT 15"),
            "styles": rows(f"SELECT s AS label, count(*)::int AS n FROM (SELECT unnest(styles) AS s {owned}) x GROUP BY s ORDER BY n DESC, s LIMIT 15"),
            "decades": rows(f"SELECT COALESCE(original_year, year) / 10 * 10 AS decade, count(*)::int AS n {owned} "
                            "AND COALESCE(original_year, year) IS NOT NULL GROUP BY 1 ORDER BY 1"),
            "formats": rows(f"SELECT CASE WHEN medium = 'Vinyl' THEN format ELSE medium END AS label, count(*)::int AS n {owned} GROUP BY 1 ORDER BY n DESC"),
            "artists": rows(f"SELECT artist AS label, count(*)::int AS n {owned} AND artist IS NOT NULL GROUP BY artist ORDER BY n DESC, artist LIMIT 12"),
            "labels": rows(f"SELECT label, count(*)::int AS n {owned} AND label IS NOT NULL GROUP BY 1 ORDER BY n DESC, 1 LIMIT 12"),
            "countries": rows(f"SELECT country AS label, count(*)::int AS n {owned} AND country IS NOT NULL GROUP BY 1 ORDER BY n DESC, 1 LIMIT 12"),
            "grades": rows(f"SELECT media_condition AS label, count(*)::int AS n {owned} AND media_condition IS NOT NULL GROUP BY 1"),
            "growth": rows("""SELECT year, added, (sum(added) OVER (ORDER BY year))::int AS total
                              FROM (SELECT extract(year FROM added_on)::int AS year, count(*)::int AS added
                                    FROM vinyl_records WHERE status IN ('Owned', 'Gone') GROUP BY 1) y ORDER BY year"""),
            "most_played": rows(LIST + " WHERE p.plays > 0 ORDER BY p.plays DESC, p.last_played DESC LIMIT 10"),
            "most_valuable": rows(LIST + " WHERE r.status = 'Owned' AND r.value IS NOT NULL ORDER BY r.value DESC LIMIT 10"),
            "best_buys": rows(LIST + " WHERE r.status = 'Owned' AND r.value IS NOT NULL AND r.price_paid IS NOT NULL "
                              "ORDER BY r.value - r.price_paid DESC LIMIT 5"),
        }
        order = {g: i for i, g in enumerate(GRADES)}
        out["grades"].sort(key=lambda g: order.get(g["label"], 99))
        by_month = {r["m"]: r["n"] for r in rows("""SELECT to_char(played_at, 'YYYY-MM') AS m, count(*)::int AS n FROM vinyl_plays
                                                      WHERE played_at >= date_trunc('month', now()) - make_interval(months => %(m)s - 1)
                                                      GROUP BY 1""", {"m": months})}
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
        start = date(today.year, today.month, 1)
        month_list = []
        for i in range(months - 1, -1, -1):
            y, m = divmod(start.year * 12 + start.month - 1 - i, 12)
            month_list.append(f"{y:04d}-{m + 1:02d}")
        out["plays_by_month"] = [{"month": m, "plays": by_month.get(m, 0)} for m in month_list]
        # The collection's value at the end of each month: each record's latest value by then (records you own now).
        out["value_by_month"] = rows("""
            WITH months AS (SELECT generate_series(date_trunc('month', min(seen_on)), date_trunc('month', current_date), interval '1 month')::date AS m
                            FROM vinyl_values)
            SELECT to_char(m.m, 'YYYY-MM') AS month,
                   (SELECT COALESCE(sum(v.value), 0)::float8 FROM vinyl_records r
                    JOIN LATERAL (SELECT value FROM vinyl_values x WHERE x.record_id = r.record_id
                                  AND x.seen_on < m.m + interval '1 month' ORDER BY x.seen_on DESC LIMIT 1) v ON true
                    WHERE r.status = 'Owned') AS value
            FROM months m ORDER BY m.m""")
        out["facts"] = conn.execute(f"""
            SELECT count(*)::int AS records, COALESCE(sum(discs), 0)::int AS discs, count(DISTINCT artist)::int AS artists,
                   min(COALESCE(original_year, year)) AS oldest_year, max(COALESCE(original_year, year)) AS newest_year,
                   round(avg(price_paid), 2)::float8 AS average_paid, COALESCE(sum(price_paid), 0)::float8 AS paid,
                   COALESCE(sum(value), 0)::float8 AS value {owned}""").fetchone()
        out["oldest"] = conn.execute(LIST + " WHERE r.status = 'Owned' AND COALESCE(r.original_year, r.year) IS NOT NULL "
                                     "ORDER BY COALESCE(r.original_year, r.year), r.record_id LIMIT 1").fetchone()
    return out


# ---------------------------------------------------------------- export
@router.get("/vinyl/export.csv")
def export_csv():
    """Every record you own, for insurance or a spreadsheet: the pressing, your copy, what you paid, today's value."""
    cols = ["Artist", "Title", "Format", "Discs", "Year", "Label", "Catalogue number", "Country", "Variant", "Barcode",
            "Record grade", "Sleeve grade", "Paid (AUD)", "Bought", "Bought from", "Value (AUD)", "Value from", "Value checked",
            "Shelf", "Notes", "Discogs"]
    with db() as conn:
        rows = conn.execute("""
            SELECT r.*, l.name AS location FROM vinyl_records r LEFT JOIN storage_locations l USING (location_id)
            WHERE r.status = 'Owned' ORDER BY lower(COALESCE(r.artist, '')), lower(r.title)""").fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols)
    for r in rows:
        fmt = r["format"] if r["medium"] == "Vinyl" else r["medium"]
        w.writerow([r["artist"] or "", r["title"], " ".join(x for x in (r["size"], fmt) if x), r["discs"], r["year"] or "",
                    r["label"] or "", r["catno"] or "", r["country"] or "", r["variant"] or "", r["barcode"] or "",
                    r["media_condition"] or "", r["sleeve_condition"] or "", r["price_paid"] if r["price_paid"] is not None else "",
                    r["purchase_date"] or "", r["bought_from"] or "", r["value"] if r["value"] is not None else "", r["value_note"] or "",
                    r["value_checked_at"].date() if r["value_checked_at"] else "", r["location"] or "", r["notes"] or "",
                    f"https://www.discogs.com/release/{r['discogs_release_id']}" if r["discogs_release_id"] else ""])
    return Response(content="﻿" + out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="vinyl-{date.today().isoformat()}.csv"'})
