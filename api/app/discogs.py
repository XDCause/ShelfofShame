"""Discogs' official API (https://www.discogs.com/developers): your collection, your wantlist, every pressing's facts,
and what a copy sells for.

Needs your personal access token (Discogs > Settings > Developers > Generate new token) as DISCOGS_TOKEN in .env,
passed in by docker-compose. With a token Discogs allows 60 requests a minute: the app waits PAUSE between calls in
a row (a sync, the weekly value check). The token never appears in logs or error messages. Only the API is used -
never Discogs' web pages.

    identity()                 whose token it is: the username
    collection(user)           every copy in your collection (folder 0 = all), 100 a page
    wants(user)                your wantlist
    release(id)                one pressing: tracklist, label, catalogue number, country, barcode, cover, have / want,
                               the lowest price for sale (in AUD)
    master_year(id)            the year the album first came out
    search(q, barcode)         vinyl releases matching words or a barcode
    price_suggestion(id)       what a copy sells for, by grade (Discogs' suggestion; in your seller currency)
    add_to_collection(user, id)  put a release in your collection (folder 1, Uncategorized)
    cover(url)                 the cover picture, checked like any download
    record_from(...)           Discogs' shapes -> vinyl_records columns
"""
import os
import re
import time

import httpx

from .images import fetched_photo

API = "https://api.discogs.com"
TIMEOUT = 20
PAUSE = 1.1          # between calls in a row: 60 a minute is Discogs' limit with a token
HEADERS = {"User-Agent": "OffTheClock/1.0 +https://github.com/XDCause/ShelfofShame", "Accept": "application/json"}

# Discogs' long grade names <-> the short ones the app keeps (the Goldmine scale).
GRADES = {"Mint (M)": "M", "Near Mint (NM or M-)": "NM", "Very Good Plus (VG+)": "VG+", "Very Good (VG)": "VG",
          "Good Plus (G+)": "G+", "Good (G)": "G", "Fair (F)": "F", "Poor (P)": "P", "Generic": "Generic", "No Cover": "No cover"}
GRADE_NAMES = {v: k for k, v in GRADES.items()}


class DiscogsError(Exception):
    """Something the user can act on: no token, the token refused, Discogs unreachable or limiting requests."""


def token() -> str:
    t = os.environ.get("DISCOGS_TOKEN", "").strip()
    if not t:
        raise DiscogsError("No Discogs token yet: add DISCOGS_TOKEN to the .env file, then restart.")
    return t


def has_token() -> bool:
    return bool(os.environ.get("DISCOGS_TOKEN", "").strip())


def pause():
    time.sleep(PAUSE)


def _call(method: str, path: str, params: dict | None = None):
    """Call the API and return its JSON (None for 404). Errors never include the token."""
    headers = {**HEADERS, "Authorization": f"Discogs token={token()}"}
    try:
        r = httpx.request(method, API + path, params=params, headers=headers, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise DiscogsError(f"Couldn't reach Discogs ({e.__class__.__name__}).") from None
    if r.status_code == 404:
        return None
    if r.status_code == 401:
        raise DiscogsError("Discogs refused the token. Check DISCOGS_TOKEN in .env (Discogs > Settings > Developers).")
    if r.status_code == 429:
        raise DiscogsError("Discogs is limiting requests right now (HTTP 429) - try again in a minute.")
    if r.status_code >= 400:
        raise DiscogsError(f"Discogs didn't answer (HTTP {r.status_code}).")
    if r.status_code == 204 or not r.content:
        return {}
    try:
        return r.json()
    except ValueError:
        raise DiscogsError(f"Discogs sent something unexpected (HTTP {r.status_code}).") from None


def _get(path: str, params: dict | None = None):
    return _call("GET", path, params)


def identity() -> str:
    me = _get("/oauth/identity") or {}
    if not me.get("username"):
        raise DiscogsError("Discogs didn't say whose token this is.")
    return me["username"]


def _pages(path: str, key: str):
    """Every item of a paged list, a page at a time (PAUSE between pages)."""
    page = 1
    while True:
        data = _get(path, {"per_page": 100, "page": page}) or {}
        yield from data.get(key) or []
        if page >= ((data.get("pagination") or {}).get("pages") or 1):
            return
        page += 1
        pause()


def collection(user: str):
    return _pages(f"/users/{user}/collection/folders/0/releases", "releases")


def wants(user: str):
    return _pages(f"/users/{user}/wants", "wants")


def release(release_id: int) -> dict | None:
    return _get(f"/releases/{int(release_id)}", {"curr_abbr": "AUD"})


def master_year(master_id: int) -> int | None:
    m = _get(f"/masters/{int(master_id)}") or {}
    return _year(m.get("year"))


def search(q: str | None = None, barcode: str | None = None) -> list[dict]:
    params = {"type": "release", "per_page": 25}
    if barcode:
        params["barcode"] = barcode
    if q:
        params["q"] = q
    data = _get("/database/search", params) or {}
    return [found_release(r) for r in data.get("results") or [] if r.get("id")]


def price_suggestion(release_id: int) -> dict:
    """{grade: (value, currency)} - empty when Discogs has none (no sales yet, or your seller settings aren't filled in)."""
    try:
        data = _get(f"/marketplace/price_suggestions/{int(release_id)}") or {}
    except DiscogsError as e:
        if "HTTP 4" in str(e):            # 422 / 403: no seller settings - Discogs can't suggest a price
            return {}
        raise
    out = {}
    for name, p in data.items():
        if isinstance(p, dict) and GRADES.get(name) and p.get("value") is not None:
            out[GRADES[name]] = (float(p["value"]), (p.get("currency") or "USD").upper())
    return out


def add_to_collection(user: str, release_id: int) -> int | None:
    data = _call("POST", f"/users/{user}/collection/folders/1/releases/{int(release_id)}") or {}
    return data.get("instance_id")


def cover(url: str | None) -> tuple[bytes | None, str | None]:
    if not url or not url.startswith("https://"):
        return None, None
    try:
        r = httpx.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError:
        return None, None
    return fetched_photo(r)


# ---------------------------------------------------------------- Discogs' shapes -> ours
def _year(v) -> int | None:
    try:
        y = int(str(v)[:4])
    except (TypeError, ValueError):
        return None
    return y if 1880 <= y <= 2200 else None


def artist_name(artists: list | None) -> str | None:
    """[{name: "Nirvana (2)", anv, join}] -> "Nirvana" (Discogs numbers artists who share a name)."""
    named = [(re.sub(r"\s\(\d+\)$", "", (a.get("anv") or a.get("name") or "").strip()), (a.get("join") or "").strip())
             for a in artists or []]
    named = [(n, j) for n, j in named if n]
    text = ""
    for i, (name, join) in enumerate(named):
        text += name
        if i < len(named) - 1:
            text += ", " if join in ("", ",") else f" {join} "      # "A & B", "A Feat. B", "A, B"
    return text or None


NOTABLE = ("Limited Edition", "Numbered", "Reissue", "Remastered", "Repress", "Picture Disc", "Club Edition", "Promo",
           "Test Pressing", "Deluxe Edition", "Special Edition", "Gatefold", "Mispress")


def format_facts(formats: list | None) -> dict:
    """Discogs' formats -> medium, format, size, discs and variant (colour, weight, notable descriptions)."""
    fmts = formats or []
    main = next((f for f in fmts if f.get("name") == "Vinyl"), None) or (fmts[0] if fmts else {})
    name = main.get("name") or ""
    medium = {"Vinyl": "Vinyl", "CD": "CD", "Cassette": "Cassette"}.get(name, "Other" if name else "Vinyl")
    desc = [d for f in fmts for d in (f.get("descriptions") or [])]
    if "Box Set" in [f.get("name") for f in fmts] or "Box Set" in desc:
        kind = "Box set"
    elif "LP" in desc or "Album" in desc and medium == "Vinyl" and not {'7"', "Single"} & set(desc):
        kind = "LP"
    elif "EP" in desc or "Mini-Album" in desc:
        kind = "EP"
    elif "Single" in desc or "Maxi-Single" in desc or '7"' in desc:
        kind = "Single"
    else:
        kind = "LP" if medium == "Vinyl" else "Other"
    size = next((s for s in ('12"', '10"', '7"') if s in desc), None)
    if not size and medium == "Vinyl":
        size = '7"' if kind == "Single" else '12"'
    try:
        discs = max(1, min(100, sum(int(f.get("qty") or 1) for f in fmts if f.get("name") == name)))
    except ValueError:
        discs = 1
    extra = [t.strip() for f in fmts for t in [f.get("text") or ""] if t.strip()]
    extra += [d for d in desc if d in NOTABLE or re.search(r"\d+ ?(g|Gram)\b", d)]
    variant = ", ".join(dict.fromkeys(extra)) or None
    return {"medium": medium, "format": kind, "size": size if medium == "Vinyl" else None, "discs": discs, "variant": variant}


def found_release(r: dict) -> dict:
    """A search result: Discogs' "Artist - Title" split, its facts as the add panel shows them."""
    artist, _, title = (r.get("title") or "").partition(" - ")
    if not title:
        artist, title = "", artist
    fmt = format_facts([{"name": (r.get("format") or [""])[0], "descriptions": (r.get("format") or [])[1:],
                         "qty": r.get("format_quantity") or 1}])
    return {"discogs_release_id": r["id"], "discogs_master_id": r.get("master_id") or None,
            "title": title.strip(), "artist": re.sub(r"\s\(\d+\)$", "", artist.strip()) or None,
            "year": _year(r.get("year")), "country": r.get("country") or None,
            "label": (r.get("label") or [None])[0], "catno": r.get("catno") or None,
            "formats": r.get("format") or [], **{k: fmt[k] for k in ("medium", "format", "size")},
            "thumb": r.get("thumb") or r.get("cover_image") or None, "genres": r.get("genre") or [], "styles": r.get("style") or []}


def record_from(basic: dict | None = None, full: dict | None = None) -> dict:
    """vinyl_records columns from a collection / wantlist item's basic_information, or from a full release (richer)."""
    src = full or basic or {}
    labels = src.get("labels") or []
    label = labels[0] if labels else {}
    out = {"title": (src.get("title") or "").strip() or "Untitled", "artist": artist_name(src.get("artists")),
           "year": _year(src.get("year") or src.get("released")), "label": (label.get("name") or "").strip() or None,
           "catno": (label.get("catno") or "").strip() or None if (label.get("catno") or "").lower() != "none" else None,
           "genres": src.get("genres") or [], "styles": src.get("styles") or [],
           "discogs_release_id": src.get("id"), "discogs_master_id": src.get("master_id") or None,
           **format_facts(src.get("formats"))}
    if basic and not full:
        out["cover_url"] = basic.get("cover_image") or basic.get("thumb") or None
    if full:
        images = full.get("images") or []
        primary = next((i for i in images if i.get("type") == "primary"), images[0] if images else {})
        community = full.get("community") or {}
        out.update(
            country=full.get("country") or None,
            barcode=next((re.sub(r"\D", "", i.get("value") or "") or None for i in full.get("identifiers") or []
                          if i.get("type") == "Barcode" and re.sub(r"\D", "", i.get("value") or "")), None),
            tracklist=[{"position": t.get("position") or "", "title": t.get("title") or "", "duration": t.get("duration") or ""}
                       for t in full.get("tracklist") or [] if (t.get("type_") or "track") == "track"],
            cover_url=primary.get("uri") or primary.get("uri150") or None,
            have_count=community.get("have"), want_count=community.get("want"),
            community_rating=(community.get("rating") or {}).get("average") or None,
            lowest_price=full.get("lowest_price"), for_sale=full.get("num_for_sale"))
    return out
