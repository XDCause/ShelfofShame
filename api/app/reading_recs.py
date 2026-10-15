"""Book suggestions for the Reading hobby, from Open Library (openlibrary.py) - no AI, no account.

    authors  more books by the authors you rated 4★ or more (their other books, so usually the
             rest of a series you loved), best known first
    genres   well-rated books in the genres you read most, one per author, from authors you don't
             already have on your shelves

Your seeds (top authors and genres) come from your shelves: finished books count by your rating,
want-to-read / reading ones a little. Suggestions are kept in book_recs and refreshed in the
background - weekly, or when your seeds change (a new 5★ author) - one Open Library request a second.
"+ Want to read" adds one to your books; "Not interested" hides it for good (book_rec_dismissed).
"""
import json
import logging
import re
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path

from . import openlibrary
from .db import db, insert_row
from .reading import fetch_book

router = APIRouter(prefix="/api", tags=["reading"])
log = logging.getLogger("reading")

SEEDS_KEY = "reading_recs_seeds"       # settings: the seeds the stored suggestions were made from
FRESH_FOR = timedelta(days=7)
AUTHORS, GENRES = 5, 3                 # seeds used
PER_AUTHOR, PER_GENRE = 6, 8           # suggestions kept for each
GENRE_SHARE = 0.4                      # a genre counts if it weighs at least this much of your top one
MIN_RATINGS = 20                       # a genre suggestion needs this many Open Library ratings
MIN_PAGES = 120                        # shorter = a story, a poem, a sampler (when the length is known)
WORK = r"^OL\d+W$"

# Not books to read: summaries, study guides, box sets, colouring books...
JUNK = re.compile(r"summary|study guide|analysis|workbook|colou?ring|box(ed)? ?set|books? set|collection|omnibus|"
                  r"sampler|trilogy|\bseries\b|\bbooks? \d|#\s*\d+\s*[-–]|^works\b|calendar|notebook|journal\b|"
                  r"cliffs ?notes|sparknotes|companion|unofficial", re.I)

# A title in another script (Japanese, Cyrillic...): Open Library lists translations as their own works.
OTHER_SCRIPT = re.compile(r"[Ͱ-῿⺀-￿]")

REFRESH = {"running": False, "done": 0, "total": 0, "error": None}
_refresh_lock = threading.Lock()


def _key(text: str | None) -> str:
    """A title or name to compare: no series in brackets, no subtitle, no case / punctuation.
    "Red Rising (Red Rising Saga, #1)" -> "redrising"."""
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text or "").split(":")[0]
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _first_author(author: str | None) -> str:
    return (author or "").split(",")[0].strip()


def _plain_title(title: str) -> str:
    return re.sub(r"\s*\([^)]*#\d+[^)]*\)\s*$", "", title)


def seeds(conn) -> dict:
    """Your top authors (finished books you gave 4★+, by total stars) and genres (by your ratings:
    a book's first genre counts in full, others half; books you want to read / are reading count
    half again)."""
    books = conn.execute("SELECT title, author, status, rating, genres FROM books ORDER BY finished_on NULLS LAST, book_id").fetchall()
    authors: dict[str, dict] = {}
    genres: dict[str, float] = defaultdict(float)
    for b in books:
        stars = float(b["rating"]) if b["rating"] is not None else 3.0
        if b["status"] == "finished" and b["rating"] is not None and b["rating"] >= 4 and b["author"]:
            name = _first_author(b["author"])
            a = authors.setdefault(_key(name), {"name": name, "weight": 0.0, "seed": None, "seed_rating": 0})
            a["weight"] += stars
            title = _plain_title(b["title"])
            if a["seed"] is None or stars > a["seed_rating"]:
                a["seed"], a["seed_rating"] = title, stars       # their best-rated (the first finished on a tie)
        if b["status"] == "dnf":
            continue
        share = 1.0 if b["status"] == "finished" else 0.5
        for i, g in enumerate(b["genres"] or []):
            genres[g] += stars * share * (1.0 if i == 0 else 0.5)
    top_authors = sorted(authors.values(), key=lambda a: -a["weight"])[:AUTHORS]
    ranked = sorted(genres.items(), key=lambda g: -g[1])
    top_genres = [g for g, w in ranked if w >= GENRE_SHARE * ranked[0][1]][:GENRES] if ranked else []
    return {"authors": [{k: a[k] for k in ("name", "seed", "seed_rating")} for a in top_authors], "genres": top_genres}


def signature(s: dict) -> str:
    return json.dumps([[a["name"] for a in s["authors"]], s["genres"]])


def _shelf(conn) -> dict:
    """What not to suggest: books you have (by work or title), authors you have (for genre
    suggestions), and ones you said no to."""
    rows = conn.execute("SELECT title, author, ol_work FROM books").fetchall()
    dismissed = {r["ol_work"] for r in conn.execute("SELECT ol_work FROM book_rec_dismissed")}
    return {"works": {r["ol_work"] for r in rows if r["ol_work"]} | dismissed,
            "titles": {_key(r["title"]) for r in rows},
            "authors": {_key(_first_author(r["author"])) for r in rows if r["author"]}}


def _usable(book: dict, shelf: dict, seen: set) -> bool:
    return bool(book["ol_work"] and book["cover_id"] and book["title"] and not JUNK.search(book["title"])
                and book["ol_work"] not in shelf["works"] and _key(book["title"]) not in shelf["titles"]
                and _key(book["title"]) not in seen and len(book["authors"]) <= 3
                and not (book["pages"] and book["pages"] < MIN_PAGES)
                and not OTHER_SCRIPT.search(book["title"]))


def pick_by_author(name: str, books: list[dict], shelf: dict, seen: set) -> list[dict]:
    """Books by that author alone (not comics / anthologies they're one of several on), oldest first -
    so a series you're part-way through comes in order. Ones nobody has rated on Open Library (early
    or obscure books, or not out yet) go after the rest. The same title twice: the better known."""
    best: dict[str, dict] = {}
    for b in books:
        if len(b["authors"]) == 1 and _key(b["authors"][0]) == _key(name) and _usable(b, shelf, seen):
            k = _key(b["title"])
            if k not in best or b["ol_ratings"] > best[k]["ol_ratings"]:
                best[k] = b
    return sorted(best.values(), key=lambda b: (b["ol_ratings"] == 0, b["year"] or 9999, -b["ol_ratings"]))[:PER_AUTHOR]


def pick_in_genre(books: list[dict], shelf: dict, seen: set, shown: set) -> list[dict]:
    """One book per author - their most-rated one, which is usually a series' first book - from
    authors you don't have yet and not already suggested (`shown`, across genres), in Open
    Library's order (best rated first)."""
    best: dict[str, dict] = {}
    order: list[str] = []
    for b in books:
        if not b["authors"] or b["ol_ratings"] < MIN_RATINGS or not _usable(b, shelf, seen):
            continue
        who = _key(b["authors"][0])
        if who in shelf["authors"] or who in shown:
            continue
        if who not in best:
            order.append(who)
            best[who] = b
        elif b["ol_ratings"] > best[who]["ol_ratings"]:
            best[who] = b
    picked = [best[w] for w in order][:PER_GENRE]
    shown.update(_key(b["authors"][0]) for b in picked)
    return picked


def refresh():
    """Ask Open Library for each seed and replace the stored suggestions. On an error the old ones stay."""
    with _refresh_lock:
        if REFRESH["running"]:
            return
        with db() as conn:
            s = seeds(conn)
            shelf = _shelf(conn)
        REFRESH.update(running=True, done=0, total=len(s["authors"]) + len(s["genres"]), error=None)
    try:
        rows, seen, shown = [], set(), set()

        def keep(section, reason, picked, seed=None, seed_rating=None):
            for b in picked:
                seen.add(_key(b["title"]))
                rows.append({"section": section, "reason": reason, "seed": seed, "seed_rating": seed_rating,
                             "rank": len(rows), **{k: b[k] for k in ("ol_work", "title", "author", "year", "pages",
                                                                       "cover_id", "isbn", "genres", "ol_rating", "ol_ratings")}})
        asked = 0
        for a in s["authors"]:
            if asked:
                openlibrary.pause()
            asked += 1
            keep("author", a["name"], pick_by_author(a["name"], openlibrary.by_author(a["name"]), shelf, seen),
                 a["seed"], a["seed_rating"])
            REFRESH["done"] = asked
        for g in s["genres"]:
            if asked:
                openlibrary.pause()
            asked += 1
            keep("genre", g, pick_in_genre(openlibrary.popular_in(g), shelf, seen, shown))
            REFRESH["done"] = asked
        with db() as conn:
            conn.execute("DELETE FROM book_recs")
            for r in rows:
                insert_row(conn, "book_recs", r, "ol_work")
            conn.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                         (SEEDS_KEY, signature(s)))
    except openlibrary.BookError as e:
        REFRESH["error"] = str(e)
    except Exception as e:                     # noqa: BLE001 - the page shows it; old suggestions stay
        log.exception("Book suggestions failed")
        REFRESH["error"] = str(e)
    finally:
        REFRESH["running"] = False


@router.get("/reading/recommendations")
def recommendations():
    """Suggestions grouped as the page shows them: one section per author you loved, then one per
    genre. `stale` = they should be refreshed (none yet, a week old, or your top authors / genres
    changed); the page then starts a refresh and polls `refresh`."""
    with db() as conn:
        s = seeds(conn)
        shelf = _shelf(conn)
        rows = conn.execute("SELECT *, 'https://covers.openlibrary.org/b/id/' || cover_id || '-M.jpg' AS cover_url "
                            "FROM book_recs ORDER BY rank").fetchall()
        made_from = conn.execute("SELECT value FROM settings WHERE key = %s", (SEEDS_KEY,)).fetchone()
        dismissed = conn.execute("SELECT count(*)::int AS n FROM book_rec_dismissed").fetchone()["n"]
    sections: dict[tuple, dict] = {}
    for r in rows:
        if r["ol_work"] in shelf["works"] or _key(r["title"]) in shelf["titles"]:
            continue                            # added to your books since (any way)
        sec = sections.setdefault((r["section"], r["reason"]), {"kind": r["section"], "reason": r["reason"], "seed": r["seed"],
                                                               "seed_rating": r["seed_rating"], "books": []})
        sec["books"].append(r)
    refreshed_at = max((r["fetched_at"] for r in rows), default=None)
    has_seeds = bool(s["authors"] or s["genres"])
    stale = has_seeds and (made_from is None or made_from["value"] != signature(s) or refreshed_at is None
                           or datetime.now(timezone.utc) - refreshed_at > FRESH_FOR)
    return {"sections": list(sections.values()), "seeds": s, "has_seeds": has_seeds, "refreshed_at": refreshed_at,
            "stale": stale, "dismissed": dismissed, "refresh": REFRESH}


@router.post("/reading/recommendations/refresh", status_code=202)
def start_refresh(background: BackgroundTasks):
    background.add_task(refresh)
    return {"refresh": REFRESH}


@router.post("/reading/recommendations/{ol_work}/want", status_code=201)
def want_it(ol_work: str = Path(pattern=WORK)):
    """Add a suggestion to your books as Want to read."""
    with db() as conn:
        r = conn.execute("SELECT * FROM book_recs WHERE ol_work = %s", (ol_work,)).fetchone()
        if not r:
            raise HTTPException(404, "That suggestion has gone - refresh the page.")
        if conn.execute("SELECT 1 FROM books WHERE ol_work = %s", (ol_work,)).fetchone():
            raise HTTPException(409, "That book is already on your shelves.")
        book_id = insert_row(conn, "books", {
            **{k: r[k] for k in ("title", "author", "isbn", "ol_work", "cover_id", "pages", "year", "genres")},
            "status": "want", "looked_up_at": datetime.now(timezone.utc)}, "book_id")
        conn.execute("DELETE FROM book_recs WHERE ol_work = %s", (ol_work,))
        return fetch_book(conn, book_id)


@router.post("/reading/recommendations/{ol_work}/dismiss", status_code=204)
def not_interested(ol_work: str = Path(pattern=WORK)):
    with db() as conn:
        r = conn.execute("DELETE FROM book_recs WHERE ol_work = %s RETURNING title", (ol_work,)).fetchone()
        conn.execute("INSERT INTO book_rec_dismissed (ol_work, title) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                     (ol_work, r["title"] if r else None))


@router.delete("/reading/recommendations/dismissed", status_code=204)
def bring_back():
    """Forget every "Not interested" (they can be suggested again from the next refresh, which this
    makes due)."""
    with db() as conn:
        conn.execute("DELETE FROM book_rec_dismissed")
        conn.execute("DELETE FROM settings WHERE key = %s", (SEEDS_KEY,))
