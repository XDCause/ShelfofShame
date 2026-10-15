"""Open Library (https://openlibrary.org/developers/api): a free, open book database run by the
Internet Archive - no key. Used to find a book by title / author / ISBN when you add it, and to
fill in covers and details for books imported from Goodreads (in the background, spaced).

    search(q)            GET /search.json?q=      title, author, first year, typical page count,
                                                  cover id, the work's key, ISBNs, subjects
    by_isbn(isbn)        GET /search.json?isbn=   the same, for one ISBN
    find(title, author)  GET /search.json?title=&author=   the best match, for imports
    series_books(s, a)   GET /search.json?q=series:"..."   a series' books (bookseries.py)
    by_author(name)      GET /search.json?q=author:"..."   an author's books, best rated first  } for
    popular_in(genre)    GET /search.json?q=subject:"..."  well-rated books in a genre           } suggestions
    cover_url(id)        covers.openlibrary.org/b/id/<id>-M.jpg (shown straight from Open Library)

Open Library asks apps to say who they are (User-Agent) and to keep to about one request a second;
robots.txt keeps crawlers off its HTML search pages, not this API.
"""
import re
import time

import httpx

SEARCH = "https://openlibrary.org/search.json"
COVER = "https://covers.openlibrary.org/b/id/{id}-{size}.jpg"
HEADERS = {"User-Agent": "Off the Clock (personal hobby tracker; https://github.com/XDCause/ShelfofShame)",
           "Accept": "application/json"}
FIELDS = "key,title,author_name,first_publish_year,number_of_pages_median,cover_i,isbn,subject,series_name,series_position"
REC_FIELDS = FIELDS + ",ratings_average,ratings_count"
TIMEOUT = 20
PAUSE = 1.0

# Open Library's subjects are long and messy ("Fiction, science fiction, general", "nyt:..."): each
# book gets up to three plain genres, the first listed here that any subject mentions.
GENRES = [
    ("Fantasy", ("fantasy", "magic", "dragons", "wizards")),
    ("Science fiction", ("science fiction", "science-fiction", "sci-fi", "space opera", "dystopia")),
    ("Mystery", ("mystery", "detective", "crime fiction")),
    ("Thriller", ("thriller", "suspense", "espionage")),
    ("Horror", ("horror", "ghost stories", "vampires", "zombies")),
    ("Romance", ("romance", "love stories")),
    ("Historical fiction", ("historical fiction", "fiction, historical")),
    ("Young adult", ("young adult", "juvenile fiction", "teen")),
    ("Children's", ("children's", "juvenile literature", "picture books")),
    ("Graphic novel", ("graphic novel", "comic", "manga")),
    ("Classics", ("classics", "classic literature")),
    ("Poetry", ("poetry", "poems")),
    ("Biography", ("biography", "autobiography", "memoir")),
    ("History", ("history",)),
    ("Science", ("science", "physics", "biology", "astronomy", "mathematics")),
    ("Business", ("business", "economics", "management", "finance")),
    ("Self-help", ("self-help", "self-actualization", "personal development", "success")),
    ("Philosophy", ("philosophy",)),
    ("Psychology", ("psychology",)),
    ("Sport", ("sports", "football", "volleyball")),
]


class BookError(Exception):
    """A message for the user: Open Library unreachable..."""


def _get(params: dict) -> list[dict]:
    try:
        r = httpx.get(SEARCH, params={"fields": FIELDS, **params}, headers=HEADERS, timeout=TIMEOUT,
                      follow_redirects=True)
    except httpx.HTTPError as e:
        raise BookError(f"Couldn't reach Open Library ({e.__class__.__name__}).") from None
    if r.status_code != 200:
        raise BookError(f"Open Library didn't answer (HTTP {r.status_code}).")
    return r.json().get("docs") or []


def pause():
    time.sleep(PAUSE)


def cover_url(cover_id: int | None, size: str = "M") -> str | None:
    return COVER.format(id=cover_id, size=size) if cover_id else None


def isbn13(text: str | None) -> str | None:
    """'0-593-13520-2', '="9780593135204"' -> '9780593135204' (ISBN-10s become ISBN-13s); None if
    it isn't a valid ISBN (the check digit is checked)."""
    s = re.sub(r"[^0-9Xx]", "", text or "").upper()
    if len(s) == 10 and s[:9].isdigit():
        if sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s)) % 11:
            return None
        s = "978" + s[:9]
        return s + str((10 - sum((3 if i % 2 else 1) * int(c) for i, c in enumerate(s)) % 10) % 10)
    if len(s) == 13 and s.isdigit() and s[:3] in ("978", "979"):
        return s if sum((3 if i % 2 else 1) * int(c) for i, c in enumerate(s)) % 10 == 0 else None
    return None


def genres_of(subjects: list[str] | None) -> list[str]:
    """Each genre's words are taken out once matched, so "science fiction" isn't also Science."""
    text, out = " | ".join(subjects or []).lower(), []
    for name, words in GENRES:
        if any(w in text for w in words):
            out.append(name)
            for w in words:
                text = text.replace(w, " ")
    return out[:3]


def _book(doc: dict) -> dict:
    isbns = [i for i in doc.get("isbn") or [] if len(i) == 13 and i.startswith("978")]
    return {
        "title": doc.get("title"),
        "author": ", ".join((doc.get("author_name") or [])[:2]) or None,
        "year": doc.get("first_publish_year"),
        "pages": doc.get("number_of_pages_median"),
        "cover_id": doc.get("cover_i"),
        "cover_url": cover_url(doc.get("cover_i")),
        "ol_work": (doc.get("key") or "").rsplit("/", 1)[-1] or None,
        "isbn": isbns[0] if isbns else None,
        "genres": genres_of(doc.get("subject")),
        "series": (doc.get("series_name") or [None])[0],
        "series_number": _position(doc.get("series_position")),
    }


def _position(values: list | None) -> float | None:
    """Open Library's series_position: ["1"] -> 1.0 (anything not a plain number -> None)."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", str((values or [None])[0] or ""))
    return float(m.group(1)) if m and float(m.group(1)) < 10000 else None


def search(q: str, limit: int = 10) -> list[dict]:
    """Books matching a title / author search, best match first."""
    return [_book(d) for d in _get({"q": q, "limit": limit}) if d.get("title")]


def by_isbn(isbn: str) -> dict | None:
    docs = _get({"isbn": isbn, "limit": 1})
    if not docs:
        return None
    book = _book(docs[0])
    book["isbn"] = isbn                       # this edition's ISBN, not another edition's
    return book


def _key(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def find(title: str, author: str | None) -> dict | None:
    """The best match for a title (and author): the first result whose title starts the same way
    (Goodreads adds series to titles: "Dune (Dune, #1)")."""
    plain = re.sub(r"\s*\([^)]*#\d+[^)]*\)\s*$", "", title).split(":")[0]
    docs = _get({"title": plain, **({"author": author} if author else {}), "limit": 5})
    for d in docs:
        if d.get("title") and _key(d.get("title")).startswith(_key(plain)[:20]) or _key(plain).startswith(_key(d.get("title"))[:20]):
            return _book(d)
    return None


# ---- suggestions ------------------------------------------------------------------------------

# What to search Open Library's subjects for, per genre (default: the genre's first word list entry).
SUBJECTS = {name: words[0] for name, words in GENRES}
# Searches by subject leave out children's / young-adult books unless that's the genre asked for
# (they top every "fantasy" list otherwise), and manga (single volumes, "Naruto 33").
NOT_YA = ' -subject:"juvenile fiction" -subject:"young adult fiction" -subject:"children\'s fiction" -subject:manga'


def _rec(doc: dict) -> dict:
    book = _book(doc)
    book["authors"] = doc.get("author_name") or []
    book["ol_rating"] = round(doc["ratings_average"], 2) if doc.get("ratings_average") else None
    book["ol_ratings"] = doc.get("ratings_count") or 0
    return book


def by_author(name: str, limit: int = 40) -> list[dict]:
    """An author's books that have an English edition, best rated first."""
    name = name.replace('"', "")
    docs = _get({"q": f'author:"{name}" language:eng', "sort": "rating", "limit": limit, "fields": REC_FIELDS})
    return [_rec(d) for d in docs if d.get("title")]


def series_books(series: str, author: str | None, limit: int = 40) -> list[dict]:
    """Books Open Library lists in a series (by that author, when known), English editions."""
    q = f'series:"{series.replace(chr(34), "")}"' + (f' author:"{author.replace(chr(34), "")}"' if author else "") + " language:eng"
    return [_rec(d) for d in _get({"q": q, "limit": limit, "fields": REC_FIELDS}) if d.get("title")]


def popular_in(genre: str, limit: int = 60) -> list[dict]:
    """Well-rated books in a genre (English editions), best rated first."""
    subject = SUBJECTS.get(genre, genre.lower()).replace('"', "")
    q = f'subject:"{subject}" language:eng' + ("" if genre in ("Young adult", "Children's") else NOT_YA)
    return [_rec(d) for d in _get({"q": q, "sort": "rating", "limit": limit, "fields": REC_FIELDS}) if d.get("title")]
