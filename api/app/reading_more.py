"""Reading, more (market review, 2026-11-16): the year in review, your own tags, and your own challenges.

    review      /reading/review?year=   a year of reading: books and pages (by month), formats, short / medium / long,
                longest and favourite, genres, authors, pages a day, re-reads
    tags        /reading/tags           every private tag with how many books carry it (set them on a book: PATCH tags)
    challenges  /reading/challenges     a name, a target and a rule - a tag, a genre, "pages over N" or ticked by hand -
                counted over the books you finished (in one year, or any time), with the books that count

Everything here is private, like the rest of the app. The tables are in db/init/A06_reading_vinyl_volleyball.sql.
"""
from collections import Counter
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .reading import COVER, LIST, _today

router = APIRouter(prefix="/api", tags=["reading"])

SHORT_BELOW, LONG_FROM = 250, 500          # pages: short < 250, medium 250-499, long 500 and up
Rule = Literal["tag", "genre", "pages_over", "manual"]


def length_of(pages: int | None) -> str | None:
    """"short", "medium" or "long" for a page count (None when the book has no pages)."""
    if not pages:
        return None
    return "short" if pages < SHORT_BELOW else "long" if pages >= LONG_FROM else "medium"


# ---- the year in review ---------------------------------------------------------------------

def year_facts(reads: list[dict], pages_by_day: list[dict], today: date, year: int) -> dict:
    """A year's numbers from its finished reads (each: title, author, pages, format, genres, rating, finished_on,
    reread) and its pages read each day. Pure, so it can be tested without a database."""
    books = len(reads)
    pages = sum(r["pages"] or 0 for r in reads)
    months = [{"month": f"{year}-{m:02d}", "books": 0, "pages": 0} for m in range(1, 13)]
    for r in reads:
        months[r["finished_on"].month - 1]["books"] += 1
    for d in pages_by_day:
        months[d["day"].month - 1]["pages"] += d["pages"]
    pages_read = sum(m["pages"] for m in months)
    start, end = date(year, 1, 1), date(year, 12, 31)
    days = max(1, ((min(today, end) if today.year == year else end) - start).days + 1)
    lengths = Counter(length_of(r["pages"]) for r in reads if r["pages"])
    formats = Counter(r["format"] or "unknown" for r in reads)
    genres = Counter(g for r in reads for g in (r["genres"] or []))
    authors = Counter(r["author"] for r in reads if r["author"])
    rated = [r for r in reads if r["rating"]]
    longest = max((r for r in reads if r["pages"]), key=lambda r: r["pages"], default=None)
    favourite = max(rated, key=lambda r: (float(r["rating"]), r["pages"] or 0), default=None)
    return {
        "year": year, "books": books, "pages": pages, "pages_read": pages_read, "days": days,
        "pages_a_day": round(pages_read / days, 1), "rereads": sum(1 for r in reads if r["reread"]),
        "average_rating": round(sum(float(r["rating"]) for r in rated) / len(rated), 2) if rated else None,
        "average_pages": round(pages / sum(1 for r in reads if r["pages"])) if any(r["pages"] for r in reads) else None,
        "by_month": months,
        "by_length": [{"label": k, "books": lengths.get(k, 0)} for k in ("short", "medium", "long")],
        "by_format": [{"label": k, "books": n} for k, n in formats.most_common()],
        "genres": [{"label": k, "books": n} for k, n in sorted(genres.items(), key=lambda x: (-x[1], x[0]))[:8]],
        "authors": [{"label": k, "books": n} for k, n in sorted(authors.items(), key=lambda x: (-x[1], x[0]))[:6]],
        "longest": longest, "favourite": favourite,
        "five_stars": sum(1 for r in rated if float(r["rating"]) >= 5),
    }


@router.get("/reading/review")
def review(year: int | None = Query(None, ge=1900, le=2100)):
    """A year of reading (default: this year), and which years have anything to show."""
    with db() as conn:
        today = _today(conn)
        year = year or today.year
        reads = conn.execute(f"""
            SELECT b.book_id, b.title, b.author, b.pages, b.format, b.genres, b.rating::float8 AS rating, b.finished_on, false AS reread,
                   CASE WHEN b.cover_id IS NOT NULL THEN {COVER} END AS cover_url
            FROM books b WHERE b.status = 'finished' AND extract(year FROM b.finished_on) = %(y)s
            UNION ALL
            SELECT b.book_id, b.title, b.author, b.pages, b.format, b.genres, r.rating::float8, r.finished_on, true,
                   CASE WHEN b.cover_id IS NOT NULL THEN {COVER} END
            FROM book_reads r JOIN books b USING (book_id) WHERE r.outcome = 'finished' AND extract(year FROM r.finished_on) = %(y)s
            ORDER BY finished_on""", {"y": year}).fetchall()
        # Pages a day: logged pages, plus finished books you never logged (all their pages, the day you finished).
        pages_by_day = conn.execute("""
            SELECT day, sum(pages)::int AS pages FROM (
                SELECT logged_on AS day, pages FROM reading_log
                UNION ALL
                SELECT b.finished_on, b.pages FROM books b WHERE b.status = 'finished' AND b.pages IS NOT NULL
                   AND NOT EXISTS (SELECT 1 FROM reading_log l WHERE l.book_id = b.book_id)) p
            WHERE extract(year FROM day) = %s GROUP BY day""", (year,)).fetchall()
        gave_up = conn.execute("SELECT count(*)::int AS n FROM books WHERE status = 'dnf' AND extract(year FROM finished_on) = %s",
                               (year,)).fetchone()["n"]
        years = [r["y"] for r in conn.execute("""
            SELECT DISTINCT y FROM (SELECT extract(year FROM finished_on)::int AS y FROM books WHERE status = 'finished'
                                    UNION SELECT extract(year FROM finished_on)::int FROM book_reads WHERE outcome = 'finished'
                                    UNION SELECT %s) x WHERE y IS NOT NULL ORDER BY y DESC""", (today.year,)).fetchall()]
        # Authors new to you this year: none of their books was finished before it.
        before = {r["author"].lower() for r in conn.execute(
            "SELECT DISTINCT author FROM books WHERE status = 'finished' AND author IS NOT NULL AND finished_on < make_date(%s, 1, 1)",
            (year,)).fetchall()}
    out = year_facts(reads, pages_by_day, today, year)
    out.update(gave_up=gave_up, years=years, today=today,
               new_authors=len({r["author"].lower() for r in reads if r["author"]} - before))
    return out


# ---- tags -----------------------------------------------------------------------------------

@router.get("/reading/tags")
def list_tags():
    """Every private tag you've used, with how many books carry it."""
    with db() as conn:
        return conn.execute("SELECT t AS tag, count(*)::int AS books FROM books, unnest(tags) t GROUP BY t "
                            "ORDER BY count(*) DESC, lower(t)").fetchall()


# ---- challenges -----------------------------------------------------------------------------

class ChallengeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target: int = Field(ge=1, le=1000)
    rule: Rule
    rule_value: str | None = Field(None, max_length=60)     # the tag or genre, or the page count
    year: int | None = Field(None, ge=2000, le=2100)


class ChallengePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    target: int | None = Field(None, ge=1, le=1000)
    rule_value: str | None = Field(None, max_length=60)
    year: int | None = Field(None, ge=2000, le=2100)


def _check_rule(rule: str, value: str | None) -> str | None:
    """A tag / genre needs a word; "pages over" a whole number; a manual challenge has none."""
    value = (value or "").strip() or None
    if rule == "manual":
        return None
    if not value:
        raise HTTPException(422, "Say which " + {"tag": "tag", "genre": "genre", "pages_over": "page count"}[rule] + " counts.")
    if rule == "pages_over" and not (value.isdigit() and 0 < int(value) <= 50000):
        raise HTTPException(422, "Pages over needs a whole number, like 500.")
    return value


def matching(conn, c: dict) -> list[dict]:
    """The books that count towards a challenge (finished ones - in its year, if it has one)."""
    where, params = ["b.status = 'finished'"], {"id": c["challenge_id"], "v": c["rule_value"]}
    if c["year"]:
        where.append("extract(year FROM b.finished_on) = %(y)s")
        params["y"] = c["year"]
    if c["rule"] == "tag":
        where.append("lower(%(v)s) = ANY (SELECT lower(t) FROM unnest(b.tags) t)")
    elif c["rule"] == "genre":
        where.append("lower(%(v)s) = ANY (SELECT lower(g) FROM unnest(b.genres) g)")
    elif c["rule"] == "pages_over":
        where.append("b.pages > %(v)s::int")
    else:
        where.append("EXISTS (SELECT 1 FROM reading_challenge_books x WHERE x.challenge_id = %(id)s AND x.book_id = b.book_id)")
    return conn.execute(f"{LIST} WHERE {' AND '.join(where)} ORDER BY b.finished_on, b.book_id", params).fetchall()


def with_progress(conn, c: dict) -> dict:
    books = matching(conn, c)
    c["books"] = books
    c["done"] = len(books)
    c["percent"] = min(100, round(100 * len(books) / c["target"]))
    c["reached"] = len(books) >= c["target"]
    return c


@router.get("/reading/challenges")
def list_challenges():
    """Your challenges with their progress and the books that count (this year's first)."""
    with db() as conn:
        rows = conn.execute("SELECT * FROM reading_challenges ORDER BY year DESC NULLS LAST, challenge_id DESC").fetchall()
        return [with_progress(conn, c) for c in rows]


@router.post("/reading/challenges", status_code=201)
def add_challenge(body: ChallengeIn):
    data = tidy_text(body.model_dump(), required=("name",))
    data["rule_value"] = _check_rule(data["rule"], data["rule_value"])
    with db() as conn:
        new = insert_row(conn, "reading_challenges", data, "challenge_id")
        return with_progress(conn, conn.execute("SELECT * FROM reading_challenges WHERE challenge_id = %s", (new,)).fetchone())


@router.patch("/reading/challenges/{challenge_id}")
def update_challenge(challenge_id: int, body: ChallengePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    with db() as conn:
        c = found(conn.execute("SELECT * FROM reading_challenges WHERE challenge_id = %s", (challenge_id,)).fetchone(), "Challenge")
        if "rule_value" in data:
            data["rule_value"] = _check_rule(c["rule"], data["rule_value"])
        update_row(conn, "reading_challenges", "challenge_id", challenge_id, data)
        return with_progress(conn, conn.execute("SELECT * FROM reading_challenges WHERE challenge_id = %s", (challenge_id,)).fetchone())


@router.delete("/reading/challenges/{challenge_id}", status_code=204)
def delete_challenge(challenge_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM reading_challenges WHERE challenge_id = %s RETURNING challenge_id", (challenge_id,)).fetchone(),
              "Challenge")
    return Response(status_code=204)


@router.put("/reading/challenges/{challenge_id}/books/{book_id}")
def tick_book(challenge_id: int, book_id: int):
    """Tick a book off a manual challenge (it counts once it's finished)."""
    with db() as conn:
        c = found(conn.execute("SELECT * FROM reading_challenges WHERE challenge_id = %s", (challenge_id,)).fetchone(), "Challenge")
        if c["rule"] != "manual":
            raise HTTPException(409, "Only a challenge you tick by hand takes ticked books.")
        found(conn.execute("SELECT 1 FROM books WHERE book_id = %s", (book_id,)).fetchone(), "Book")
        conn.execute("INSERT INTO reading_challenge_books (challenge_id, book_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                     (challenge_id, book_id))
        return with_progress(conn, c)


@router.delete("/reading/challenges/{challenge_id}/books/{book_id}")
def untick_book(challenge_id: int, book_id: int):
    with db() as conn:
        c = found(conn.execute("SELECT * FROM reading_challenges WHERE challenge_id = %s", (challenge_id,)).fetchone(), "Challenge")
        conn.execute("DELETE FROM reading_challenge_books WHERE challenge_id = %s AND book_id = %s", (challenge_id, book_id))
        return with_progress(conn, c)
