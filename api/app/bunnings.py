"""Bunnings (https://www.bunnings.com.au): one product page, read when you paste or share its link.

Bunnings has no public product API and no official app catalogue. Its robots.txt keeps tools off its
search (/search) and internal APIs (/api/), and allows product pages (/..._p1234567) for everyone - so
this only ever reads a product page you chose, one at a time (PAUSE apart), with an honest User-Agent:
never its search, never in bulk, never a cart. "Search Bunnings" in the app just opens their own search
in your browser. A page that answers with a check (a bot challenge) instead of the product is an error -
it's never worked around.

    product_url(text)   a Bunnings product link (or text containing one) -> its clean address, or None
    fetch(url)          the product: name, item number, price, brand, rating, reviews, weight, category,
                        description, how to use, photo URL
    parse(html)         the same from a page's HTML (the page's own __NEXT_DATA__ JSON)

The price is the one the page shows for Bunnings' default store (prices can differ a little by store).
"""
import html as htmllib
import json
import re
import threading
import time

import httpx

from .images import fetched_photo
from .openlibrary import HEADERS as _HEADERS

HEADERS = {**_HEADERS, "Accept": "text/html,application/xhtml+xml"}
SITE = "https://www.bunnings.com.au/"
LINK = re.compile(r"https://(?:www\.)?bunnings\.com\.au/([a-z0-9-]{3,200})_p(\d{4,10})", re.I)
TIMEOUT = 30
PAUSE = 2.0
_lock = threading.Lock()
_last = [0.0]


class BunningsError(Exception):
    """A message for the user: the link isn't a Bunnings product, or the page couldn't be read."""


def product_url(text: str | None) -> str | None:
    m = LINK.search(text or "")
    return f"{SITE}{m.group(1).lower()}_p{m.group(2)}" if m else None


def _plain(text: str | None, limit: int = 2000) -> str | None:
    if not text:
        return None
    t = re.sub(r"<br\s*/?>|</p>|</li>", "\n", text, flags=re.I)
    t = htmllib.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", t)).strip()
    return t[:limit] or None


def _number(v) -> float | None:
    try:
        n = float(re.sub(r"[^\d.]", "", str(v))) if v not in (None, "") else None
    except ValueError:
        return None
    return n


def parse(page: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        raise BunningsError("That Bunnings page didn't have the product details (it may have asked for a check this app doesn't do).")
    try:
        queries = json.loads(m.group(1))["props"]["pageProps"]["dehydratedState"]["queries"]
    except (ValueError, KeyError, TypeError):
        raise BunningsError("Bunnings' page has changed - the app can't read its product details any more.") from None
    found = {q.get("queryKey", [None])[0]: (q.get("state") or {}).get("data") or {} for q in queries if q.get("queryKey")}
    p, price = found.get("retail-product") or {}, found.get("product-retail-price") or {}
    if not p.get("name") or not p.get("itemNumber"):
        raise BunningsError("Bunnings' page has no product on it.")
    images = p.get("images") or []
    primary = next((i for i in images if i.get("imageType") == "PRIMARY"), images[0] if images else {})
    cats = [c.get("displayName") for c in p.get("allCategories") or [] if c.get("displayName")]
    weight = _number(p.get("weight"))
    feature = p.get("feature") or {}
    return {
        "name": p["name"].strip()[:200], "bunnings_item": str(p["itemNumber"]),
        "price": round(float(price["value"]), 2) if price.get("priceAvailable") and price.get("value") is not None else None,
        "brand": (p.get("manufacturer") or "").strip() or None,
        "rating": round(float(p["averageRating"]), 2) if p.get("averageRating") else None,
        "reviews": int(p["numberOfReviews"]) if p.get("numberOfReviews") else None,
        "weight_kg": weight if weight and weight < 10000 else None,
        "category": " › ".join(cats[-2:]) or None,
        "description": _plain(feature.get("description"), 1500),
        "how_to": _plain(p.get("installationInformation")),
        "image": (primary.get("url") or primary.get("thumbnailUrl") or None),
    }


def _wait():
    with _lock:
        gap = PAUSE - (time.monotonic() - _last[0])
        if gap > 0:
            time.sleep(gap)
        _last[0] = time.monotonic()


def _get(url: str) -> str:
    _wait()
    try:
        r = httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError as e:
        raise BunningsError(f"Couldn't reach Bunnings ({e.__class__.__name__}).") from None
    if not str(r.url).startswith(SITE):
        raise BunningsError("Bunnings sent that link somewhere else.")
    if r.status_code == 404:
        raise BunningsError("Bunnings doesn't have that product any more.")
    if r.status_code != 200:
        raise BunningsError(f"Bunnings didn't answer (HTTP {r.status_code}).")
    return r.text


def fetch(url: str) -> dict:
    clean = product_url(url)
    if not clean:
        raise BunningsError("That isn't a Bunnings product link (they look like bunnings.com.au/..._p1234567).")
    return {**parse(_get(clean)), "url": clean}


def photo_url(image: str | None, width: int = 1200) -> str | None:
    """Bunnings' image service resizes with &t=w<width> - only to the sizes its own pages use (w600 is a 404;
    w1200, the product page's own, works: a PNG of about 1 MB)."""
    if not image or not image.startswith("https://media.bunnings.com.au/"):
        return None
    return image + ("&" if "?" in image else "?") + f"t=w{width}"


def photo(image: str | None) -> tuple[bytes | None, str | None]:
    """The product's picture, 1200 px wide - only from Bunnings' own image server."""
    url = photo_url(image)
    if not url:
        return None, None
    _wait()
    try:
        r = httpx.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError:
        return None, None
    if r.url.host != "media.bunnings.com.au":       # a redirect somewhere else: not taken
        return None, None
    return fetched_photo(r)
