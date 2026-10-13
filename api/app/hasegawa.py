"""Look up a Hasegawa kit on hasegawa-model.co.jp (English pages).

Checked 2026-10-11: robots.txt only disallows /hsite/wp-admin/. One page + one photo per lookup,
only when you ask, cached in product_info. Plain http:// because their HTTPS certificate
doesn't validate.

Pages are addressed by SERIES code: /product_g/jt86/. Boxes also show a 5-digit ITEM number:
    Item no … JT86（09086）      Scale … 1:48      div#a_item_title: P-40E WARHAWK
Some series map item numbers simply (PT29 = 07229, JT86 = 09086), so an item number can be
turned into a series code to try - and the page's own "Item no" must then match it.
"""
import re

import httpx
from bs4 import BeautifulSoup

from .tamiya import HEADERS, TIMEOUT, LookupFailed, NotFound
from .images import fetched_photo

PAGE_URL = "http://www.hasegawa-model.co.jp/product_g/{series}/"

# Item number prefix -> series letters, and the number to subtract (checked against real pages).
ITEM_SERIES = [
    ("072", "PT", 7200),   # 1/48 aircraft: PT29 = 07229
    ("090", "JT", 9000),   # 1/48 aircraft: JT86 = 09086
    ("091", "JT", 9000),
]


def normalise(code: str):
    """('series', 'JT86') or ('item', '09086'), or None.
    Accepts 'JT86', 'jt 86', '09086', 'HSG09086', 'HSG-09086'."""
    c = re.sub(r"[\s\-_]", "", code.upper())
    if c.startswith("HSG"):
        c = c[3:]
    if re.fullmatch(r"\d{5}", c):
        return "item", c
    if re.fullmatch(r"[A-Z]{1,3}\d{1,3}", c):
        return "series", c
    return None


def series_for_item(item: str) -> list[str]:
    """Series codes to try for an item number, e.g. '09086' -> ['JT86']."""
    return [f"{letters}{int(item) - offset}" for prefix, letters, offset in ITEM_SERIES
            if item.startswith(prefix) and int(item) - offset > 0]


def fetch(series: str) -> dict:
    url = PAGE_URL.format(series=series.lower())
    try:
        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            page = client.get(url)
            if page.status_code == 404:
                raise NotFound(f"Hasegawa has no page for {series.upper()}.")
            page.raise_for_status()
            info = parse(page.content.decode("utf-8", errors="replace"))
            info["source_url"] = url
            info["image"] = info["image_type"] = None
            image_url = info.pop("image_url")
            if image_url:
                info["image"], info["image_type"] = fetched_photo(client.get(image_url))
            return info
    except httpx.HTTPError as e:
        raise LookupFailed(f"Couldn't reach hasegawa-model.co.jp ({e.__class__.__name__}).") from e


def parse(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("#a_item_title")
    if title is None or not title.get_text(strip=True):
        raise NotFound("That page doesn't look like a Hasegawa kit page.")

    specs = {}
    box = soup.select_one(".a_itemdate_r")
    if box:
        # "<b>Scale</b> … 1:48<br><b>Item no</b> … JT86（09086）<br>..."
        for b in box.find_all("b"):
            value = b.next_sibling
            if isinstance(value, str):
                specs[b.get_text(strip=True)] = value.replace("…", "").strip()

    item_no = specs.get("Item no", "")
    m = re.match(r"([A-Z]{1,3}\d{1,3})\s*[（(]\s*(\d{5})\s*[）)]", item_no)
    scale = specs.get("Scale", "").replace(":", "/") or None

    return {
        "title": re.sub(r"\s+", " ", title.get_text(" ")).strip(),
        "series": m.group(1) if m else None,
        "item": m.group(2) if m else None,
        "scale": scale,
        "category": specs.get("Category") or None,
        "image_url": _box_photo(soup),
    }


def _box_photo(soup):
    """The box art: a ~768px version from srcset when offered (the full size is bigger than we
    need), else the linked full-size image."""
    pac = soup.select_one(".pacimg")
    if pac is None:
        return None
    img = pac.find("img")
    if img and img.get("srcset"):
        sizes = [part.strip().split() for part in img["srcset"].split(",")]
        sized = [(int(w[:-1]), u) for u, w in (s for s in sizes if len(s) == 2) if w.endswith("w")]
        best = [u for w, u in sorted(sized) if w >= 600]
        if best:
            return best[0]
    link = pac.find("a")
    return link["href"] if link and link.get("href") else (img.get("src") if img else None)
