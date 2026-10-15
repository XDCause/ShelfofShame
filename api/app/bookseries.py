"""Every book in a series, for a book's panel ("In this series").

    Wikidata    (query.wikidata.org, CC0, no key) knows which books are in a series and their
                number in it ("part of the series" + "series ordinal"), with publication dates -
                the order comes from here when it has the series
    Open Library the author's books (openlibrary.by_author) give covers and work ids for those; when
                Wikidata doesn't have the series, Open Library's own series search is used instead
                (no numbers there - ordered by first published)

One series = about 2 requests (Wikidata, then Open Library a second later), kept a week in
book_series_cache. The list is merged with your own books each time it's shown: yours show
your shelf and stars, the rest can go on your want-to-read shelf. A book of yours found in the
list without a series (or number) gets it filled in.
"""
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter

from . import openlibrary
from .db import db, found
from .reading_recs import JUNK, OTHER_SCRIPT, _first_author, _key

router = APIRouter(prefix="/api", tags=["reading"])
log = logging.getLogger("reading")

WIKIDATA = "https://query.wikidata.org/sparql"
KEEP_FOR = timedelta(days=7)
TIMEOUT = 25

# The series is found by name (Wikidata's own search), then every work "part of the series" it -
# not ones that are series themselves (a trilogy inside a saga) - with its number, date and author.
QUERY = """
SELECT ?series ?seriesLabel ?book ?bookLabel ?ord ?date ?authorLabel WHERE {
  SERVICE wikibase:mwapi { bd:serviceParam wikibase:api "EntitySearch"; wikibase:endpoint "www.wikidata.org";
    mwapi:search %s; mwapi:language "en". ?series wikibase:apiOutputItem mwapi:item. }
  ?book wdt:P179 ?series .
  FILTER NOT EXISTS { ?part wdt:P179 ?book }
  OPTIONAL { ?book p:P179 ?st . ?st ps:P179 ?series . ?st pq:P1545 ?ord }
  OPTIONAL { ?book wdt:P577 ?date }
  OPTIONAL { ?book wdt:P50 ?author }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 300"""


class SeriesError(Exception):
    pass


def _wikidata(query: str) -> list[dict]:
    try:
        r = httpx.get(WIKIDATA, params={"query": query, "format": "json"}, headers=openlibrary.HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise SeriesError(f"Couldn't reach Wikidata ({e.__class__.__name__}).") from None
    if r.status_code != 200:
        raise SeriesError(f"Wikidata didn't answer (HTTP {r.status_code}).")
    return r.json()["results"]["bindings"]


def _number(text) -> float | None:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", str(text or ""))
    return float(m.group(1)) if m and float(m.group(1)) < 10000 else None


def _same_series(a: str, b: str) -> bool:
    """"Red Rising Saga" ~ "Red Rising Saga"; "Gentleman Bastard" ~ "Gentleman Bastard Sequence"."""
    a, b = _key(re.sub(r"^the\s+", "", a, flags=re.I)), _key(re.sub(r"^the\s+", "", b, flags=re.I))
    return bool(a and b) and (a == b or a in b or b in a)


def from_wikidata(series: str, author: str | None) -> list[dict]:
    """The series' books (title, number, year), or [] if Wikidata doesn't have it. Of the series
    its search finds, the one named like ours with the most books by this author."""
    groups: dict[str, dict] = {}
    for r in _wikidata(QUERY % json.dumps(series)):
        if not _same_series(r["seriesLabel"]["value"], series):
            continue
        who = r.get("authorLabel", {}).get("value")
        if author and who and _key(who) != _key(author):
            continue
        g = groups.setdefault(r["series"]["value"], {})
        b = g.setdefault(r["book"]["value"], {"title": r["bookLabel"]["value"], "number": None, "year": None})
        n = _number(r.get("ord", {}).get("value"))
        if n is not None and (b["number"] is None or n < b["number"]):
            b["number"] = n
        y = r.get("date", {}).get("value", "")[:4]
        if y.isdigit() and (b["year"] is None or int(y) < b["year"]):
            b["year"] = int(y)
    if not groups:
        return []
    books = max(groups.values(), key=len).values()
    return [b for b in books if not re.fullmatch(r"Q\d+", b["title"])]      # no English name: skip


def _usable(b: dict, author: str | None) -> bool:
    return bool(b["title"]) and not JUNK.search(b["title"]) and not OTHER_SCRIPT.search(b["title"]) \
        and (not author or (b["authors"] and _key(b["authors"][0]) == _key(author)))


def look_up(series: str, author: str | None) -> tuple[str | None, list[dict]]:
    """(source, books): each book {title, number, year, ol_work, cover_id, pages}."""
    wd = []
    try:
        wd = from_wikidata(series, author)
    except SeriesError as e:
        log.warning("Series %r: %s", series, e)
    if wd:
        theirs = {}
        if author:
            for b in openlibrary.by_author(author):
                if _usable(b, author):
                    theirs.setdefault(_key(b["title"]), b)
        out = []
        for w in wd:
            ol = theirs.get(_key(w["title"]), {})
            out.append({"title": w["title"], "number": w["number"], "year": w["year"] or ol.get("year"),
                        "ol_work": ol.get("ol_work"), "cover_id": ol.get("cover_id"), "pages": ol.get("pages")})
        return "wikidata", out
    best: dict[str, dict] = {}
    for b in openlibrary.series_books(series, author):
        if _usable(b, author):
            k = _key(b["title"])
            if k not in best or b["ol_ratings"] > best[k]["ol_ratings"]:
                best[k] = b
    if not best:
        return None, []
    return "openlibrary", [{"title": b["title"], "number": b.get("series_number"), "year": b["year"], "ol_work": b["ol_work"],
                            "cover_id": b["cover_id"], "pages": b["pages"]} for b in best.values()]


def _cached(conn, series: str, author: str | None) -> tuple[str | None, list[dict], str | None]:
    key = f"{series.lower().strip()}|{(author or '').lower().strip()}"
    row = conn.execute("SELECT source, books, fetched_at FROM book_series_cache WHERE key = %s", (key,)).fetchone()
    if row and datetime.now(timezone.utc) - row["fetched_at"] < KEEP_FOR:
        return row["source"], row["books"], None
    try:
        source, books = look_up(series, author)
    except openlibrary.BookError as e:
        return (row["source"], row["books"], None) if row else (None, [], str(e))
    conn.execute("""INSERT INTO book_series_cache (key, source, books, fetched_at) VALUES (%s, %s, %s, now())
                    ON CONFLICT (key) DO UPDATE SET source = EXCLUDED.source, books = EXCLUDED.books, fetched_at = now()""",
                 (key, source, json.dumps(books)))
    return source, books, None


def order(books: list[dict]) -> list[dict]:
    """Numbered books by number, then the rest by year (in the order found)."""
    numbered = sorted((b for b in books if b["number"] is not None), key=lambda b: b["number"])
    rest = sorted((b for b in books if b["number"] is None), key=lambda b: b["year"] or 9999)
    return numbered + rest


@router.get("/reading/books/{book_id}/series")
def series_of(book_id: int):
    """The book's series in order. Each: title, number, year, cover_url and - for your books -
    book_id, status, rating (`this` = the book asked about); others carry what "+ Want to read" needs."""
    with db() as conn:
        book = found(conn.execute("SELECT * FROM books WHERE book_id = %s", (book_id,)).fetchone(), "Book")
        if not book["series"]:
            return {"series": None, "books": []}
        author = _first_author(book["author"]) or None
        source, listed, error = _cached(conn, book["series"], author)
        mine = conn.execute("SELECT book_id, title, author, status, rating, cover_id, ol_work, year, series, series_number "
                            "FROM books WHERE lower(series) = lower(%s) OR (%s::text IS NOT NULL AND lower(author) LIKE lower(%s) || '%%')",
                            (book["series"], author, author)).fetchall()
        by_work = {b["ol_work"]: b for b in mine if b["ol_work"]}
        by_title = {_key(b["title"]): b for b in mine}
        out, used = [], set()
        for item in listed:
            own = by_work.get(item.get("ol_work")) or by_title.get(_key(item["title"]))
            if own and own["book_id"] not in used:
                used.add(own["book_id"])
                number = float(own["series_number"]) if own["series_number"] is not None else item["number"]
                learn = {}
                if not own["series"]:
                    learn["series"] = book["series"]
                if own["series_number"] is None and item["number"] is not None:
                    learn["series_number"] = item["number"]
                if learn:                                    # it's in this series: remember that
                    conn.execute("UPDATE books SET series = COALESCE(series, %(series)s), "
                                 "series_number = COALESCE(series_number, %(series_number)s) WHERE book_id = %(id)s",
                                 {"series": learn.get("series"), "series_number": learn.get("series_number"), "id": own["book_id"]})
                out.append(_mine(own, number, item))
            elif not own:
                out.append({**item, "book_id": None, "author": book["author"], "series": book["series"],
                            "cover_url": openlibrary.cover_url(item.get("cover_id"))})
        for own in mine:                                    # yours in the series that the sources don't list
            if own["book_id"] not in used and own["series"] and own["series"].lower() == book["series"].lower():
                out.append(_mine(own, float(own["series_number"]) if own["series_number"] is not None else None, {}))
        today = date.today().year
        for b in out:
            b["this"] = b.get("book_id") == book_id
            b["upcoming"] = not b.get("book_id") and (b["year"] is None or b["year"] > today)    # not out yet
    return {"series": book["series"], "source": source, "error": error, "books": order(out)}


def _mine(own: dict, number, item: dict) -> dict:
    cover = own["cover_id"] or item.get("cover_id")
    return {"book_id": own["book_id"], "title": own["title"], "status": own["status"], "rating": own["rating"],
            "number": number, "year": own["year"] or item.get("year"), "ol_work": own["ol_work"] or item.get("ol_work"),
            "cover_url": openlibrary.cover_url(cover)}
