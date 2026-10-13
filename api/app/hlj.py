"""Look up a Bandai kit (Gunpla) on HobbyLink Japan, hlj.com.

Why HLJ: Bandai's own site is a JavaScript app fed by a private API, so there's nothing to read.
Checked 2026-10-13: hlj.com's robots.txt only disallows account / related-product pages. Their
copyright page reserves the text and images: fine for this personal tool, but see
BEFORE_GOING_PUBLIC.md before this is ever shared or sold. One lookup = one search page, one kit
page and one photo, only when you ask, then cached in product_info.

Kit pages carry schema.org Product data for search engines (name, HLJ code, barcode, photo),
which is far steadier to read than the page layout. Their details list adds the series
("Gundam 0079") and item type ("High Grade Kits").

Bandai's current item numbers sit inside the box barcode: 5057403 -> 4573102 57403 9. So a code
can be turned into the barcode to search for - and the kit page's own barcode must then match.
"""
import json
import re
import time
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from .tamiya import HEADERS, TIMEOUT, LookupFailed, NotFound, gtin_check_digit, normalise_barcode

SITE = "https://www.hlj.com"
SEARCH_URL = SITE + "/search/?q={q}"
BANDAI_SPIRITS = "4573102"  # barcode prefix for Bandai Spirits (Gunpla since 2018)
PAUSE = 1.0                 # seconds between the search, the page and the photo


def normalise(typed: str):
    """What was typed, as (kind, value):
    ('barcode', '4573102574039')   a box barcode, or a Bandai item number turned into one
                                   (G5057403 / 5057403 / 57403 -> 4573102574039)
    ('hlj', 'BANH574039-UP')       an HLJ product code
    ('name', 'rx-78-2 revive')     anything else: search by name
    None for an empty string."""
    text = typed.strip()
    if not text:
        return None
    compact = re.sub(r"[\s\-]", "", text.upper())
    if re.fullmatch(r"BAN[A-Z0-9]+(-[A-Z]+)?", text.upper().replace(" ", "")):
        return "hlj", text.upper().replace(" ", "")
    barcode = normalise_barcode(compact) if compact.isdigit() and len(compact) >= 12 else None
    if barcode:
        return "barcode", barcode
    m = re.fullmatch(r"G?(?:50)?(\d{5})", compact)
    if m:
        return "barcode", bandai_barcode(m.group(1))
    return "name", text


def bandai_barcode(item5: str) -> str:
    """'57403' -> '4573102574039' (prefix + item + check digit)."""
    body = BANDAI_SPIRITS + item5
    return body + gtin_check_digit(body)


def product_code_for(barcode: str | None, hlj_code: str) -> str:
    """Your code for the kit, like the box: G5057403 for a Bandai Spirits barcode, else HLJ's code."""
    if barcode and barcode.startswith(BANDAI_SPIRITS):
        return f"G50{barcode[7:12]}"
    return hlj_code


# HG, RG, MG... from the kit's name ("1/144 HGUC Revive RX-78-2 Gundam" -> HG).
GRADES = [
    (r"\bRE/100\b", "RE/100"), (r"\bFULL MECHANICS\b|\bFM\b", "FM"), (r"\bENTRY GRADE\b|\bEG\b", "EG"),
    (r"\bPG\w*\b|\bPERFECT GRADE\b", "PG"), (r"\bMG\w*\b|\bMASTER GRADE\b", "MG"),
    (r"\bRG\b|\bREAL GRADE\b", "RG"), (r"\bHG\w*\b|\bHIGH GRADE\b", "HG"), (r"\bSD\w*\b|\bBB\b", "SD"),
]


def grade_of(title: str) -> str | None:
    upper = title.upper()
    return next((grade for pattern, grade in GRADES if re.search(pattern, upper)), None)


def scale_of(title: str) -> str | None:
    m = re.search(r"\b1/\d+\b", title)
    return m.group(0) if m else None


def name_of(title: str) -> str:
    """'1/144 HGUC Revive RX-78-2 Gundam' -> 'HGUC Revive RX-78-2 Gundam' (the scale has its own field)."""
    return re.sub(r"^\s*1/\d+\s*(scale\s+)?", "", title, flags=re.I).strip()


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def _client():
    return httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)


def search(query: str) -> list[dict]:
    """Bandai kits on HLJ's search page for `query`: [{hlj_code, title, path, thumb_url}]."""
    try:
        with _client() as client:
            page = client.get(SEARCH_URL.format(q=quote(query)))
            page.raise_for_status()
            return parse_search(page.text)
    except httpx.HTTPError as e:
        raise LookupFailed(f"Couldn't reach hlj.com ({e.__class__.__name__}).") from e


def parse_search(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results, seen = [], set()
    for block in soup.select(".search-widget-block"):
        link = block.select_one(".product-item-name a")
        stock = block.select_one("[id$='_stock']")
        if not link or not stock:
            continue
        code = stock["id"].removesuffix("_stock")
        if not code.startswith("BAN") or code in seen:   # Bandai only
            continue
        seen.add(code)
        img = block.select_one("img")
        thumb = img.get("src") if img else None
        results.append({"hlj_code": code, "title": re.sub(r"\s+", " ", link.get_text()).strip(),
                        "path": link["href"],
                        "thumb_url": ("https:" + thumb) if thumb and thumb.startswith("//") else thumb})
    return results


def fetch(path: str) -> dict:
    """One kit page (and its photo)."""
    url = SITE + path
    try:
        with _client() as client:
            page = client.get(url)
            if page.status_code == 404:
                raise NotFound("HLJ has no page for that kit.")
            page.raise_for_status()
            info = parse(page.text)
            info["source_url"] = url
            info["image"] = info["image_type"] = None
            if info["image_url"]:
                time.sleep(PAUSE)
                photo = client.get(info["image_url"])
                if photo.status_code == 200 and photo.headers.get("content-type", "").startswith("image/"):
                    info["image"] = photo.content
                    info["image_type"] = photo.headers["content-type"].split(";")[0]
            return info
    except httpx.HTTPError as e:
        raise LookupFailed(f"Couldn't reach hlj.com ({e.__class__.__name__}).") from e


def parse(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    product = None
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            product = data
            break
    if not product or not product.get("name"):
        raise NotFound("That page doesn't look like an HLJ product page.")

    details = {}
    for li in soup.select(".product-details li"):
        key, _, value = li.get_text(" ", strip=True).partition(":")
        if value:
            details[key.strip()] = value.strip()

    image = product.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    title = re.sub(r"\s+", " ", product["name"]).strip()
    return {
        "title": title,
        "hlj_code": product.get("sku") or details.get("Code"),
        "barcode": product.get("gtin13") or details.get("JAN Code"),
        "maker": details.get("Manufacturer"),
        "series": details.get("Series"),
        "item_type": details.get("Item Type"),
        "released": details.get("Release Date"),
        "grade": grade_of(title),
        "scale": scale_of(title),
        "image_url": image,
    }
