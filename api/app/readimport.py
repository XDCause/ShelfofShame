"""Reading: the Goodreads import, and covers / details from Open Library for books without them.

    POST /reading/import/goodreads   Goodreads' "Export library" CSV (the request body): Exclusive Shelf ->
                                     status (shelf names like owned / on-my-shelf -> On my shelf), rating,
                                     dates, review. A re-import updates shelf / rating / date read / review only.
                                     Then covers and genres are looked up in the background, one a second.
    POST /reading/covers             look up covers now;  GET /reading/covers  how it's going (COVERS)
"""
import csv
import io
import logging
import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from . import openlibrary
from .db import db, insert_row, update_row
from .reading import COVERS, _covers_lock, split_series

router = APIRouter(prefix="/api", tags=["reading"])
log = logging.getLogger("reading")

SHELVES = {"read": "finished", "currently-reading": "reading", "to-read": "want"}
OWNED_SHELF = re.compile(r"owned|own-|on-my-shelf|my-shelf|physical|tbr-own|bought")


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
        status = SHELVES.get(shelf) or ("dnf" if re.search(r"dnf|did-not-finish|abandon|gave-up", shelf)
                                        else "owned" if OWNED_SHELF.search(shelf) else "want")
        title, series, number = split_series(title)
        pages = (r.get("Number of Pages") or "").strip()
        year = (r.get("Original Publication Year") or r.get("Year Published") or "").strip()
        rating = int(re.sub(r"\D", "", r.get("My Rating") or "") or 0)
        added = _goodreads_date(r.get("Date Added"))
        out.append({
            "goodreads_id": (r.get("Book Id") or "").strip() or None,
            "title": title, "series": series, "series_number": number, "author": (r.get("Author") or "").strip() or None,
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
