"""Read a product page you pasted: its name, price and picture (for "add from a link" on the wishlist).

One page, once, when you ask - never a crawl. Only public web addresses (webphoto.check_address: never this PC or the
home network; each redirect checked), at most 2 MB of page, the site's robots.txt respected (no answer from it = allowed,
a Disallow = not read), and sites whose pages the app must not read are refused outright (BoardGameGeek and
SteamHunters: the user's rule). Anything the page says is only ever data: its words are never followed.

What's read, best first: the page's JSON-LD Product (name, offers.price, image), then its Open Graph tags
(og:title, product:price:amount / og:price:amount, og:image), then <title>.
"""
import json
import re
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .webphoto import check_address

HEADERS = {"User-Agent": "OffTheClock/1.0 (personal hobby tracker; one product page you pasted)",
           "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"}
AGENT = "OffTheClock"
TIMEOUT = 15
MAX_BYTES = 2 * 1024 * 1024
REDIRECTS = 4
REFUSED = ("boardgamegeek.com", "steamhunters.com")


class LinkError(Exception):
    """Why the page couldn't be read (said to the user)."""


def _get(url: str, limit: int = MAX_BYTES) -> tuple[str, str]:
    """(final url, text) - following redirects, each address checked."""
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=False) as client:
        for _ in range(REDIRECTS + 1):
            try:
                check_address(url)
            except Exception as e:  # its HTTPException: the same words for the user
                raise LinkError(getattr(e, "detail", str(e))) from None
            try:
                with client.stream("GET", url) as r:
                    if r.is_redirect and r.headers.get("location"):
                        url = urljoin(url, r.headers["location"])
                        continue
                    if r.status_code != 200:
                        raise LinkError(f"The site said no (HTTP {r.status_code}).")
                    body = bytearray()
                    for chunk in r.iter_bytes():
                        body += chunk
                        if len(body) > limit:
                            raise LinkError("That page is too big to read.")
                    return url, body.decode(r.encoding or "utf-8", errors="replace")
            except httpx.HTTPError as e:
                raise LinkError(f"Couldn't reach the site ({e.__class__.__name__}).") from None
    raise LinkError("Too many redirects.")


def allowed(url: str) -> bool:
    """robots.txt: can this app read that page? (No robots.txt, or it can't be read: yes.)"""
    parts = urlsplit(url)
    try:
        _, text = _get(f"{parts.scheme}://{parts.netloc}/robots.txt", 256 * 1024)
    except LinkError:
        return True
    rp = RobotFileParser()
    rp.parse(text.splitlines())
    return rp.can_fetch(AGENT, url)


def _price(v) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"\d+(?:[.,]\d{1,2})?", str(v or "").replace(",", ""))
    return float(m.group(0)) if m else None


def _product(data) -> dict | None:
    """The first schema.org Product in JSON-LD (it can be a list, or under @graph)."""
    items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("@type")
        if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
            return item
    return None


def parse(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out = {"title": None, "price": None, "currency": None, "image": None}
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            product = _product(json.loads(tag.string or ""))
        except (ValueError, TypeError):
            continue
        if product:
            out["title"] = str(product.get("name") or "").strip() or None
            offers = product.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else offers if isinstance(offers, dict) else {}
            out["price"] = _price(offer.get("price") or offer.get("lowPrice"))
            out["currency"] = offer.get("priceCurrency")
            image = product.get("image")
            out["image"] = image[0] if isinstance(image, list) and image else image if isinstance(image, str) else None
            break

    def meta(*names):
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None
    out["title"] = out["title"] or meta("og:title") or (soup.title.string.strip() if soup.title and soup.title.string else None)
    out["price"] = out["price"] if out["price"] is not None else _price(meta("product:price:amount", "og:price:amount"))
    out["currency"] = out["currency"] or meta("product:price:currency", "og:price:currency")
    out["image"] = out["image"] or meta("og:image")
    if out["image"]:
        out["image"] = urljoin(url, out["image"])
        if not out["image"].startswith(("http://", "https://")):
            out["image"] = None
    if out["title"]:
        out["title"] = re.sub(r"\s+", " ", out["title"])[:200]
    return out


def peek(url: str) -> dict:
    """{title, price, currency, image, site, url} from one product page."""
    host = (urlsplit(url).hostname or "").lower()
    if any(host == d or host.endswith("." + d) for d in REFUSED):
        raise LinkError("The app doesn't read that site's pages.")
    if not allowed(url):
        raise LinkError("That site asks apps not to read this page (its robots.txt) - type it in instead.")
    final, html = _get(url)
    found = parse(html, final)
    if not found["title"]:
        raise LinkError("Couldn't find a product on that page - type it in instead.")
    return {**found, "site": urlsplit(final).hostname, "url": final}
