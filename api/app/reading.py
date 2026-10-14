"""Reading (a hobby module): your books, where you're up to, what you thought.

    books     every book (want to read / reading / finished / didn't finish), found on Open Library
              (openlibrary.py) by title, author or ISBN - or typed in - with its cover and pages
    progress  "I'm on page 120": a reading_log entry (pages read since the last one, on a day);
              starting a book you wanted to read moves it to Reading
    quotes    lines you saved, with the page
    goal      books to finish this year (settings reading_goal_<year>), and whether you're on pace
    stats     pages per month, books per year, genres, ratings
    goodreads import Goodreads' "Export library" CSV: shelves, ratings, dates read, reviews.
              Covers and genres are then looked up on Open Library in the background, one a second.
"""
import csv
import io
import logging
import re
import threading
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel, Field

from . import openlibrary
from .db import db, found, insert_row, tidy_text, update_row
from .videogames import streaks

router = APIRouter(prefix="/api", tags=["reading"])
log = logging.getLogger("reading")

STATUSES = ("want", "reading", "finished", "dnf")
COVER = "'https://covers.openlibrary.org/b/id/' || b.cover_id || '-M.jpg'"

# A book as lists show it: progress (0-100, from the page you're on), when you last read it, and
# how many quotes you've saved.
LIST = f"""
SELECT b.*, CASE WHEN b.cover_id IS NOT NULL THEN {COVER} END AS cover_url,
       CASE WHEN b.status = 'finished' THEN 100
            WHEN b.pages > 0 AND b.current_page IS NOT NULL THEN least(100, round(100.0 * b.current_page / b.pages))::int
       END AS percent,
       l.last_read, COALESCE(q.quotes, 0) AS quotes
FROM books b
LEFT JOIN LATERAL (SELECT max(logged_on) AS last_read FROM reading_log WHERE book_id = b.book_id) l ON true
LEFT JOIN LATERAL (SELECT count(*)::int AS quotes FROM book_quotes WHERE book_id = b.book_id) q ON true"""

SORTS = {
    "recent": "COALESCE(l.last_read, b.finished_on, b.started_on, b.created_at::date) DESC, b.book_id DESC",
    "finished": "b.finished_on DESC NULLS LAST, b.book_id DESC",
    "added": "b.created_at DESC, b.book_id DESC",
    "title": "lower(b.title)",
    "author": "lower(b.author) NULLS LAST, lower(b.title)",
    "rating": "b.rating DESC NULLS LAST, b.finished_on DESC NULLS LAST",
}


class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    author: str | None = Field(None, max_length=300)
    isbn: str | None = Field(None, max_length=40)
    ol_work: str | None = Field(None, max_length=40, pattern=r"^OL\d+W$")
    cover_id: int | None = Field(None, gt=0)
    pages: int | None = Field(None, gt=0, le=50000)
    year: int | None = Field(None, ge=-3000, le=3000)
    genres: list[str] = Field(default_factory=list, max_length=10)
    format: str | None = Field(None, pattern="^(paper|ebook|audio)$")
    status: str = Field("want", pattern="^(want|reading|finished|dnf)$")
    rating: int | None = Field(None, ge=1, le=5)     # adding a book you've read
    review: str | None = Field(None, max_length=20000)


class BookPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    author: str | None = Field(None, max_length=300)
    isbn: str | None = Field(None, max_length=40)
    cover_id: int | None = Field(None, gt=0)
    pages: int | None = Field(None, gt=0, le=50000)
    year: int | None = Field(None, ge=-3000, le=3000)
    genres: list[str] | None = Field(None, max_length=10)
    format: str | None = Field(None, pattern="^(paper|ebook|audio)$")
    status: str | None = Field(None, pattern="^(want|reading|finished|dnf)$")
    current_page: int | None = Field(None, ge=0, le=50000)
    started_on: date | None = None
    finished_on: date | None = None
    rating: int | None = Field(None, ge=1, le=5)
    review: str | None = Field(None, max_length=20000)


class ProgressIn(BaseModel):
    page: int = Field(ge=0, le=50000)          # the page you got to
    logged_on: date | None = None             # default today
    minutes: int | None = Field(None, gt=0, le=1440)
    note: str | None = Field(None, max_length=2000)


class QuoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    page: int | None = Field(None, ge=0, le=50000)


class GoalIn(BaseModel):
    books: int = Field(ge=1, le=1000)
    year: int | None = Field(None, ge=2000, le=2100)


def _today(conn) -> date:
    return conn.execute("SELECT current_date AS d").fetchone()["d"]      # Brisbane, not UTC


def _isbn(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    isbn = openlibrary.isbn13(value)
    if not isbn:
        raise HTTPException(422, "That isn't a valid ISBN (10 or 13 digits, from the back of the book).")
    return isbn


def _genres(names: list[str] | None) -> list[str]:
    out = []
    for g in names or []:
        g = g.strip()[:40]
        if g and g.lower() not in [x.lower() for x in out]:
            out.append(g)
    return out


def fetch_book(conn, book_id: int) -> dict:
    book = found(conn.execute(LIST + " WHERE b.book_id = %s", (book_id,)).fetchone(), "Book")
    book["log"] = conn.execute("SELECT * FROM reading_log WHERE book_id = %s ORDER BY logged_on DESC, log_id DESC",
                               (book_id,)).fetchall()
    book["quotes_list"] = conn.execute("SELECT * FROM book_quotes WHERE book_id = %s ORDER BY page NULLS LAST, quote_id",
                                       (book_id,)).fetchall()
    return book


def _status_dates(conn, data: dict, book: dict | None = None) -> dict:
    """Moving to Reading sets the start day, to Finished / Didn't finish the end day (only if not
    set); finishing also puts you on the last page."""
    status = data.get("status")
    today = _today(conn)
    old = book or {}
    if status == "reading" and not old.get("started_on") and "started_on" not in data:
        data["started_on"] = today
    if status in ("finished", "dnf") and "finished_on" not in data and old.get("status") != status:
        data["finished_on"] = today
    if status in ("want", "reading") and old.get("status") in ("finished", "dnf") and "finished_on" not in data:
        data["finished_on"] = None
    pages = data.get("pages", old.get("pages"))
    if status == "finished" and pages and "current_page" not in data:
        data["current_page"] = pages
    return data


# ---- books ----------------------------------------------------------------------------------

@router.get("/reading/lookup")
def lookup(q: str = Query(min_length=2, max_length=200)):
    """Find a book on Open Library: an ISBN (typed or scanned) gives that edition; anything else is
    a title / author search. Each result says if it's already in your books (`book_id`)."""
    isbn = openlibrary.isbn13(q) if re.fullmatch(r"[\d\s=\"'-]{10,20}[Xx]?", q.strip()) else None
    try:
        if isbn:
            one = openlibrary.by_isbn(isbn)
            results = [one] if one else []
        else:
            results = openlibrary.search(q)
    except openlibrary.BookError as e:
        raise HTTPException(502, str(e))
    with db() as conn:
        for r in results:
            mine = conn.execute(
                "SELECT book_id, status FROM books WHERE (isbn IS NOT NULL AND isbn = %s) OR (ol_work IS NOT NULL AND ol_work = %s) "
                "OR (lower(title) = lower(%s) AND lower(COALESCE(author, '')) = lower(COALESCE(%s, ''))) LIMIT 1",
                (r["isbn"], r["ol_work"], r["title"], r["author"])).fetchone()
            r["book_id"], r["my_status"] = (mine["book_id"], mine["status"]) if mine else (None, None)
    return {"isbn": isbn, "results": results}


@router.get("/reading/books")
def list_books(status: str | None = Query(None, pattern="^(want|reading|finished|dnf)$"),
               q: str | None = Query(None, max_length=200), sort: str = Query("recent", pattern="^(" + "|".join(SORTS) + ")$"),
               year: int | None = Query(None, ge=1900, le=2100)):
    """Your books (all, or one shelf), searched by title / author / genre, finished in `year`."""
    where, params = ["true"], {}
    if status:
        where.append("b.status = %(status)s")
        params["status"] = status
    if q and q.strip():
        where.append("(b.title ILIKE %(q)s OR b.author ILIKE %(q)s OR array_to_string(b.genres, ' ') ILIKE %(q)s)")
        params["q"] = f"%{q.strip()}%"
    if year:
        where.append("extract(year FROM b.finished_on) = %(year)s AND b.status = 'finished'")
        params["year"] = year
    with db() as conn:
        books = conn.execute(f"{LIST} WHERE {' AND '.join(where)} ORDER BY {SORTS[sort]}", params).fetchall()
        counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, count(*)::int AS n FROM books GROUP BY status")}
    return {"books": books, "counts": {s: counts.get(s, 0) for s in STATUSES}}


@router.post("/reading/books", status_code=201)
def add_book(body: BookIn):
    data = tidy_text(body.model_dump(), required=("title",))
    data["isbn"] = _isbn(data["isbn"])
    data["genres"] = _genres(data["genres"])
    with db() as conn:
        data = _status_dates(conn, data)
        data["looked_up_at"] = datetime.now(timezone.utc) if data.get("ol_work") else None
        return fetch_book(conn, insert_row(conn, "books", data, "book_id"))


@router.get("/reading/books/{book_id}")
def get_book(book_id: int):
    with db() as conn:
        return fetch_book(conn, book_id)


@router.patch("/reading/books/{book_id}")
def update_book(book_id: int, body: BookPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    if "isbn" in data:
        data["isbn"] = _isbn(data["isbn"])
    if "genres" in data:
        data["genres"] = _genres(data["genres"])
    with db() as conn:
        book = found(conn.execute("SELECT * FROM books WHERE book_id = %s", (book_id,)).fetchone(), "Book")
        if "status" in data:
            data = _status_dates(conn, data, book)
        update_row(conn, "books", "book_id", book_id, data)
        # Finishing a book you've been logging: the rest of it counts as read on the day you finished
        # (books never logged count whole, in pages_read).
        pages = data.get("pages", book["pages"])
        if data.get("status") == "finished" and book["status"] != "finished" and pages:
            last = conn.execute("SELECT max(page) AS p FROM reading_log WHERE book_id = %s", (book_id,)).fetchone()["p"]
            if last is not None and last < pages:
                insert_row(conn, "reading_log", {"book_id": book_id, "logged_on": data.get("finished_on") or _today(conn),
                                                 "page": pages, "pages": pages - last, "note": "Finished"}, "log_id")
        return fetch_book(conn, book_id)


@router.delete("/reading/books/{book_id}", status_code=204)
def delete_book(book_id: int):
    with db() as conn:
        if not conn.execute("DELETE FROM books WHERE book_id = %s", (book_id,)).rowcount:
            raise HTTPException(404, "Book not found.")


# ---- progress and quotes --------------------------------------------------------------------

@router.post("/reading/books/{book_id}/progress", status_code=201)
def add_progress(book_id: int, body: ProgressIn):
    """You got to page N: logs the pages read since the page you were on. A book you only wanted
    to read moves to Reading (started today, or on the day given). The reply's `at_the_end` says
    you've reached the last page (the page offers Finished)."""
    with db() as conn:
        book = found(conn.execute("SELECT * FROM books WHERE book_id = %s", (book_id,)).fetchone(), "Book")
        if book["pages"] and body.page > book["pages"]:
            raise HTTPException(422, f"This book has {book['pages']} pages. (Change it in Edit details if your copy has more.)")
        day = body.logged_on or _today(conn)
        insert_row(conn, "reading_log", {"book_id": book_id, "logged_on": day, "page": body.page,
                                         "pages": max(0, body.page - (book["current_page"] or 0)),
                                         "minutes": body.minutes, "note": (body.note or "").strip() or None}, "log_id")
        changes = {"current_page": body.page}
        if book["status"] in ("want", "dnf"):
            changes["status"] = "reading"
            changes["finished_on"] = None
        if not book["started_on"]:
            changes["started_on"] = day
        update_row(conn, "books", "book_id", book_id, changes)
        result = fetch_book(conn, book_id)
    result["at_the_end"] = bool(book["pages"]) and body.page >= book["pages"]
    return result


@router.delete("/reading/log/{log_id}", status_code=204)
def delete_progress(log_id: int):
    """Take back an update: the book goes back to the page of the latest one left."""
    with db() as conn:
        row = conn.execute("DELETE FROM reading_log WHERE log_id = %s RETURNING book_id", (log_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Update not found.")
        conn.execute("UPDATE books SET current_page = (SELECT page FROM reading_log WHERE book_id = %(b)s "
                     "ORDER BY logged_on DESC, log_id DESC LIMIT 1) WHERE book_id = %(b)s AND status <> 'finished'",
                     {"b": row["book_id"]})


@router.post("/reading/books/{book_id}/quotes", status_code=201)
def add_quote(book_id: int, body: QuoteIn):
    with db() as conn:
        found(conn.execute("SELECT 1 FROM books WHERE book_id = %s", (book_id,)).fetchone(), "Book")
        insert_row(conn, "book_quotes", {"book_id": book_id, "text": body.text.strip(), "page": body.page}, "quote_id")
        return fetch_book(conn, book_id)


@router.delete("/reading/quotes/{quote_id}", status_code=204)
def delete_quote(quote_id: int):
    with db() as conn:
        if not conn.execute("DELETE FROM book_quotes WHERE quote_id = %s", (quote_id,)).rowcount:
            raise HTTPException(404, "Quote not found.")


@router.get("/reading/quotes")
def list_quotes(q: str | None = Query(None, max_length=200)):
    """Every saved quote, newest first, with its book (searches the quote, title and author)."""
    like = f"%{(q or '').strip()}%"
    with db() as conn:
        return conn.execute(f"""
            SELECT x.quote_id, x.text, x.page, x.created_at, b.book_id, b.title, b.author,
                   CASE WHEN b.cover_id IS NOT NULL THEN {COVER} END AS cover_url
            FROM book_quotes x JOIN books b USING (book_id)
            WHERE x.text ILIKE %(q)s OR b.title ILIKE %(q)s OR b.author ILIKE %(q)s
            ORDER BY x.created_at DESC, x.quote_id DESC""", {"q": like}).fetchall()


# ---- the goal, the dashboard, stats ---------------------------------------------------------

def goal_key(year: int) -> str:
    return f"reading_goal_{year}"


def goal_progress(goal: int | None, finished: int, today: date) -> dict:
    """This year's goal: books finished against it, and against where you'd be reading steadily
    (on_pace = the goal x the share of the year gone)."""
    start, end = date(today.year, 1, 1), date(today.year + 1, 1, 1)
    gone = ((today - start).days + 1) / (end - start).days
    if not goal:
        return {"year": today.year, "goal": None, "finished": finished}
    on_pace = goal * gone
    return {"year": today.year, "goal": goal, "finished": finished, "percent": round(100 * finished / goal, 1),
            "on_pace": round(on_pace, 1), "ahead_by": round(finished - on_pace, 1), "reached": finished >= goal,
            "left": max(0, goal - finished), "days_left": (end - today).days - 1}


@router.put("/reading/goal")
def set_goal(body: GoalIn):
    with db() as conn:
        year = body.year or _today(conn).year
        conn.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                     (goal_key(year), str(body.books)))
    return summary()


@router.get("/reading/summary")
def summary():
    """For the dashboard and Home: what you're reading now, the year's goal, this year and this
    week in numbers, your reading streak, the latest finished and the next up."""
    with db() as conn:
        today = _today(conn)
        reading = conn.execute(LIST + " WHERE b.status = 'reading' ORDER BY COALESCE(l.last_read, b.started_on) DESC NULLS LAST").fetchall()
        year = conn.execute("""
            SELECT count(*)::int AS books, COALESCE(sum(pages), 0)::int AS pages, round(avg(rating), 1) AS rating
            FROM books WHERE status = 'finished' AND finished_on >= date_trunc('year', current_date)""").fetchone()
        year["pages_read"] = pages_read(conn, "date_trunc('year', current_date)")
        week = {"pages": conn.execute("SELECT COALESCE(sum(pages), 0)::int AS n FROM reading_log "
                                      "WHERE logged_on > current_date - 7").fetchone()["n"],
                "finished": conn.execute("SELECT count(*)::int AS n FROM books WHERE status = 'finished' "
                                         "AND finished_on > current_date - 7").fetchone()["n"]}
        goal = conn.execute("SELECT value FROM settings WHERE key = %s", (goal_key(today.year),)).fetchone()
        days = [r["d"] for r in conn.execute("SELECT DISTINCT logged_on AS d FROM reading_log WHERE pages > 0").fetchall()]
        finished = conn.execute(LIST + " WHERE b.status = 'finished' ORDER BY b.finished_on DESC NULLS LAST, b.book_id DESC LIMIT 6").fetchall()
        next_up = conn.execute(LIST + " WHERE b.status = 'want' ORDER BY b.created_at DESC LIMIT 5").fetchall()
        counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, count(*)::int AS n FROM books GROUP BY status")}
        quotes = conn.execute("SELECT count(*)::int AS n FROM book_quotes").fetchone()["n"]
    return {"reading": reading, "year": year, "week": week, "goal": goal_progress(int(goal["value"]) if goal else None,
            year["books"], today), "streak": streaks(days, today), "finished": finished, "next_up": next_up,
            "counts": {s: counts.get(s, 0) for s in STATUSES}, "quotes": quotes, "covers": COVERS}


def pages_read(conn, since_sql: str) -> int:
    """Pages read since a day: logged pages, plus finished books you never logged (all their pages,
    on the day you finished - Goodreads imports, books added as already read)."""
    return conn.execute(f"""
        SELECT COALESCE((SELECT sum(pages) FROM reading_log WHERE logged_on >= {since_sql}), 0)
             + COALESCE((SELECT sum(b.pages) FROM books b WHERE b.status = 'finished' AND b.finished_on >= {since_sql}
                         AND NOT EXISTS (SELECT 1 FROM reading_log l WHERE l.book_id = b.book_id)), 0) AS n""").fetchone()["n"]


@router.get("/reading/stats")
def stats(months: int = Query(24, ge=1, le=120)):
    """The Stats page's charts:
        by_month   pages read each month (logged pages, plus unlogged finished books on their
                   finish day), oldest first, months with none included
        by_year    books finished each year
        genres     finished books per genre (a book can have up to three)
        ratings    finished books by stars
        facts      totals, average rating and length, longest book, quickest read"""
    with db() as conn:
        by_month = conn.execute("""
            WITH pages AS (
                SELECT logged_on AS day, pages FROM reading_log
                UNION ALL
                SELECT b.finished_on, b.pages FROM books b WHERE b.status = 'finished' AND b.finished_on IS NOT NULL
                   AND b.pages IS NOT NULL AND NOT EXISTS (SELECT 1 FROM reading_log l WHERE l.book_id = b.book_id))
            SELECT to_char(m, 'YYYY-MM') AS month, COALESCE(sum(p.pages), 0)::int AS pages
            FROM generate_series(date_trunc('month', current_date) - make_interval(months => %(months)s - 1),
                                 date_trunc('month', current_date), interval '1 month') m
            LEFT JOIN pages p ON date_trunc('month', p.day) = m
            GROUP BY m ORDER BY m""", {"months": months}).fetchall()
        by_year = conn.execute("""
            SELECT extract(year FROM finished_on)::int AS year, count(*)::int AS books, COALESCE(sum(pages), 0)::int AS pages
            FROM books WHERE status = 'finished' AND finished_on IS NOT NULL GROUP BY 1 ORDER BY 1""").fetchall()
        genres = conn.execute("""
            SELECT g AS genre, count(*)::int AS books FROM books, unnest(genres) g
            WHERE status = 'finished' GROUP BY g ORDER BY 2 DESC, 1 LIMIT 10""").fetchall()
        ratings = conn.execute("""
            SELECT r AS stars, count(b.book_id)::int AS books FROM generate_series(1, 5) r
            LEFT JOIN books b ON b.rating = r AND b.status = 'finished' GROUP BY r ORDER BY r""").fetchall()
        facts = conn.execute("""
            SELECT count(*)::int AS finished, round(avg(rating), 2) AS average_rating, round(avg(pages))::int AS average_pages,
                   COALESCE(sum(pages), 0)::int AS pages
            FROM books WHERE status = 'finished'""").fetchone()
        facts["longest"] = conn.execute(LIST + " WHERE b.status = 'finished' AND b.pages IS NOT NULL "
                                        "ORDER BY b.pages DESC LIMIT 1").fetchone()
        facts["quickest"] = conn.execute(LIST + " WHERE b.status = 'finished' AND b.started_on IS NOT NULL "
                                         "AND b.finished_on >= b.started_on AND b.pages >= 100 "
                                         "ORDER BY b.finished_on - b.started_on, b.pages DESC LIMIT 1").fetchone()
        if facts["quickest"]:
            facts["quickest"]["days"] = (facts["quickest"]["finished_on"] - facts["quickest"]["started_on"]).days + 1
        today = _today(conn)
        days = conn.execute("SELECT logged_on AS day, sum(pages)::int AS pages FROM reading_log "
                            "WHERE logged_on > current_date - 371 GROUP BY 1 HAVING sum(pages) > 0 ORDER BY 1").fetchall()
    return {"by_month": by_month, "by_year": by_year, "genres": genres, "ratings": ratings, "facts": facts,
            "today": today, "days": days}


# ---- Goodreads import, and covers from Open Library -----------------------------------------

# Covers and details looked up for books that don't have them yet (imports): one at a time.
COVERS = {"running": False, "done": 0, "total": 0, "found": 0, "error": None}
_covers_lock = threading.Lock()

SHELVES = {"read": "finished", "currently-reading": "reading", "to-read": "want"}


def _goodreads_date(text: str | None) -> date | None:
    try:
        return datetime.strptime(text.strip(), "%Y/%m/%d").date() if text and text.strip() else None
    except ValueError:
        return None


def _format(binding: str) -> str | None:
    b = (binding or "").lower()
    if "kindle" in b or "ebook" in b or "e-book" in b or "nook" in b:
        return "ebook"
    if "audio" in b or "audible" in b:
        return "audio"
    return "paper" if b else None


def goodreads_rows(text: str) -> list[dict]:
    """Goodreads' CSV export -> book rows. Shelves: read = Finished, currently-reading = Reading,
    to-read = Want to read, a shelf named like dnf / did-not-finish / abandoned = Didn't finish."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not reader.fieldnames or "Title" not in reader.fieldnames or "Exclusive Shelf" not in reader.fieldnames:
        raise HTTPException(422, "That doesn't look like Goodreads' export (My Books → Import and export → Export library).")
    out = []
    for r in reader:
        title = (r.get("Title") or "").strip()
        if not title:
            continue
        shelf = (r.get("Exclusive Shelf") or "").strip().lower()
        status = SHELVES.get(shelf) or ("dnf" if re.search(r"dnf|did-not-finish|abandon|gave-up", shelf) else "want")
        pages = (r.get("Number of Pages") or "").strip()
        year = (r.get("Original Publication Year") or r.get("Year Published") or "").strip()
        rating = int(re.sub(r"\D", "", r.get("My Rating") or "") or 0)
        added = _goodreads_date(r.get("Date Added"))
        out.append({
            "goodreads_id": (r.get("Book Id") or "").strip() or None,
            "title": title, "author": (r.get("Author") or "").strip() or None,
            "isbn": openlibrary.isbn13(r.get("ISBN13")) or openlibrary.isbn13(r.get("ISBN")),
            "pages": int(pages) if pages.isdigit() and int(pages) > 0 else None,
            "year": int(year) if re.fullmatch(r"-?\d{1,4}", year) else None,
            "format": _format(r.get("Binding")), "status": status,
            "finished_on": _goodreads_date(r.get("Date Read")) or (added if status in ("finished", "dnf") else None),
            "rating": rating if 1 <= rating <= 5 else None,
            "review": re.sub(r"<br\s*/?>", "\n", (r.get("My Review") or "")).strip() or None,
            "created_at": datetime.combine(added, datetime.min.time(), timezone.utc) if added else None,
        })
    return out


@router.post("/reading/import/goodreads")
async def import_goodreads(request: Request, background: BackgroundTasks):
    """Goodreads' "Export library" CSV as the body. New books are added; books imported before
    (same Goodreads id) get Goodreads' shelf, rating, date read and review again - your covers,
    progress and quotes stay. Covers are then looked up in the background."""
    raw = await request.body()
    if len(raw) > 10_000_000:
        raise HTTPException(413, "That file is too big for a Goodreads export.")
    rows = goodreads_rows(raw.decode("utf-8", errors="replace"))
    added = updated = 0
    with db() as conn:
        for row in rows:
            data = {k: v for k, v in row.items() if v is not None or k in ("rating", "review", "finished_on")}
            if row["status"] == "finished" and row["pages"]:
                data["current_page"] = row["pages"]
            old = conn.execute("SELECT book_id FROM books WHERE goodreads_id = %s", (row["goodreads_id"],)).fetchone() \
                if row["goodreads_id"] else None
            if old:
                update_row(conn, "books", "book_id", old["book_id"],
                           {k: data.get(k) for k in ("status", "rating", "review", "finished_on")})
                updated += 1
            else:
                data.setdefault("created_at", datetime.now(timezone.utc))
                insert_row(conn, "books", data, "book_id")
                added += 1
    background.add_task(look_up_covers)
    return {"added": added, "updated": updated, "covers": COVERS}


def look_up_covers():
    """Open Library details for books that haven't been looked up: cover, genres, and pages / year
    / ISBN where they're missing. One request a second; a book that isn't found is marked looked up."""
    with _covers_lock:
        if COVERS["running"]:
            return
        with db() as conn:
            todo = conn.execute("SELECT book_id, title, author, isbn FROM books WHERE looked_up_at IS NULL "
                                "ORDER BY status = 'reading' DESC, created_at DESC").fetchall()
        COVERS.update(running=True, done=0, total=len(todo), found=0, error=None)
    try:
        for i, b in enumerate(todo):
            if i:
                openlibrary.pause()
            try:
                hit = (openlibrary.by_isbn(b["isbn"]) if b["isbn"] else None) or openlibrary.find(b["title"], b["author"])
            except openlibrary.BookError as e:
                COVERS["error"] = str(e)
                break
            with db() as conn:
                if hit:
                    conn.execute("""
                        UPDATE books SET cover_id = COALESCE(cover_id, %(cover_id)s), ol_work = COALESCE(ol_work, %(ol_work)s),
                               pages = COALESCE(pages, %(pages)s), year = COALESCE(year, %(year)s),
                               isbn = COALESCE(isbn, %(isbn)s),
                               genres = CASE WHEN genres = '{}' THEN %(genres)s ELSE genres END, looked_up_at = now()
                        WHERE book_id = %(book_id)s""", {**hit, "book_id": b["book_id"]})
                    COVERS["found"] += 1
                else:
                    conn.execute("UPDATE books SET looked_up_at = now() WHERE book_id = %s", (b["book_id"],))
            COVERS["done"] = i + 1
    except Exception as e:                     # noqa: BLE001 - the page shows it; the books stay
        log.exception("Cover look-up failed")
        COVERS["error"] = str(e)
    finally:
        COVERS["running"] = False


@router.post("/reading/covers", status_code=202)
def start_covers(background: BackgroundTasks):
    """Look up covers for books that don't have one yet (after an import, or if one stopped)."""
    background.add_task(look_up_covers)
    return {"covers": COVERS}


@router.get("/reading/covers")
def covers_status():
    return COVERS
