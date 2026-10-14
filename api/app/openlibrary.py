"""Open Library (https://openlibrary.org/developers/api): a free, open book database run by the
Internet Archive - no key. Used to find a book by title / author / ISBN when you add it, and to
fill in covers and details for books imported from Goodreads (in the background, spaced).

    search(q)            GET /search.json?q=      title, author, first year, typical page count,
                                                  cover id, the work's key, ISBNs, subjects
    by_isbn(isbn)        GET /search.json?isbn=   the same, for one ISBN
    find(title, author)  GET /search.json?title=&author=   the best match, for imports
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
FIELDS = "key,title,author_name,first_publish_year,number_of_pages_median,cover_i,isbn,subject"
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
        r = httpx.get(SEARCH, params={**params, "fields": FIELDS}, headers=HEADERS, timeout=TIMEOUT,
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
    }


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
