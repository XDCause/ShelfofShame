"""Look up a Trumpeter kit or tool on trumpeter-china.com (their official site, English pages).

Checked 2026-10-18: there's no robots.txt (a 404), so nothing is off limits - we still ask only when you look
something up: their search for the item number, that one product page, and its box photo, PAUSE apart, with an
honest User-Agent. Cached in product_info, so a second look-up never asks again.

Every product - kits (00968 Leopard 2A6), and tools (08005 Masking Tape Cutter) - has a 5-digit item number on
the box. Pages are addressed by the site's own id, not the item number:
    /index.php?l=en&m=Search&keyword=00968            -> a link "German Leopard2A6 MBT 00968" to a=show&id=4217
    /index.php?g=home&m=product&a=show&id=4217&l=en   -> <h3>German Leopard2A6 MBT 00968</h3>, the box photo
                                                         (img#bigpicimg), and a two-column table:
       Item No 00968 · Item Name · Bar Code 9580208009681 · Scale 1:16 · Item Type Plastic Model Armor Kit ·
       Model Brief Length: 705.8mm ... · Total Parts 1700+ · Photo Etched Parts · Released Date 2026-09 · More Features
The search also lists the site's "hot products" beside the results, so a link counts only if its name ends in
the item number - and the page's own Item No must then match it.
"""
import re
import threading
import time

import httpx
from bs4 import BeautifulSoup

from .images import fetched_photo
from .tamiya import HEADERS, TIMEOUT, LookupFailed, NotFound

SITE = "https://www.trumpeter-china.com"
SEARCH_URL = SITE + "/index.php"
PAGE_URL = SITE + "/index.php?g=home&m=product&a=show&id={page_id}&l=en"
PAUSE = 2.0
_lock = threading.Lock()
_last = [0.0]
TOOL_TYPES = ("tool", "display", "case", "rigging", "track")    # Item Type words for equipment, not a kit


def normalise(code: str) -> str | None:
    """The 5-digit item number: '00968', '968', 'TRU00968', 'tr-00968' -> '00968'."""
    c = re.sub(r"[\s\-_]", "", (code or "").upper())
    c = re.sub(r"^(TRU|TR|TRUMPETER)", "", c)
    return c.zfill(5) if re.fullmatch(r"\d{3,5}", c) else None


def _get(client: httpx.Client, url: str, **kw) -> httpx.Response:
    """One request, at least PAUSE after the last one (whatever asked)."""
    with _lock:
        gap = PAUSE - (time.monotonic() - _last[0])
        if gap > 0:
            time.sleep(gap)
        try:
            return client.get(url, **kw)
        finally:
            _last[0] = time.monotonic()


def find(client: httpx.Client, item: str) -> int:
    """The site's page id for an item number, from their search."""
    r = _get(client, SEARCH_URL, params={"l": "en", "m": "Search", "keyword": item})
    r.raise_for_status()
    return page_id_in(r.text, item)


def page_id_in(html: str, item: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        m = re.search(r"m=product&(?:amp;)?a=show&(?:amp;)?id=(\d+)", a["href"], re.I)
        if m and re.search(rf"\b{item}\s*$", a.get_text(" ", strip=True)):
            return int(m.group(1))
    raise NotFound(f"Trumpeter's site has nothing for item {item}.")


def fetch(item: str, photo: bool = True) -> dict:
    """A product's details (and box photo) by item number."""
    try:
        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            page_id = find(client, item)
            url = PAGE_URL.format(page_id=page_id)
            page = _get(client, url)
            page.raise_for_status()
            info = parse(page.content.decode("utf-8", errors="replace"))
            if info["item"] != item:
                raise NotFound(f"Trumpeter's search led to item {info['item']}, not {item}.")
            info["source_url"] = url
            info["image"] = info["image_type"] = None
            image_url = info.pop("image_url")
            if photo and image_url:
                info["image"], info["image_type"] = fetched_photo(_get(client, image_url))
            return info
    except httpx.HTTPError as e:
        raise LookupFailed(f"Couldn't reach trumpeter-china.com ({e.__class__.__name__}).") from e


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def parse(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".con_right") or soup
    heading = body.find("h3")
    specs = {}
    for tr in body.find_all("tr"):                    # the details table: label | value (older pages lack its class)
        cells = tr.find_all("td", recursive=False)
        if len(cells) == 2:
            specs.setdefault(_clean(cells[0].get_text(" ")).lower(), _clean(cells[1].get_text(" ")))
    item = specs.get("item no", "")
    if heading is None or not re.fullmatch(r"\d{5}", item):
        raise NotFound("That page doesn't look like a Trumpeter product page.")
    title = specs.get("item name") or re.sub(rf"\s*{item}\s*$", "", _clean(heading.get_text(" ")))
    barcode = re.sub(r"\D", "", specs.get("bar code", ""))
    scale = re.fullmatch(r"1\s*[:/]\s*(\d+)", specs.get("scale", ""))
    kind = specs.get("item type") or None
    # "Length: 705.8mm Width: 235.2mm" - tools often have the labels with no numbers
    size = " · ".join(f"{k} {v}" for k, v in re.findall(r"(Length|Width|Height):\s*([\d.]+\s*mm)", specs.get("model brief", "")))
    intro = next((_clean(p.get_text(" ")) for p in body.find_all("p")
                  if _clean(p.get_text(" ")) and not _clean(p.get_text(" ")).startswith("Item No")), None)
    img = body.select_one("#bigpicimg")
    image_url = img.get("src") if img is not None else None
    if image_url and image_url.startswith("/"):
        image_url = SITE + image_url
    return {
        "title": title, "item": item, "barcode": barcode if 8 <= len(barcode) <= 14 else None,
        "scale": f"1/{scale.group(1)}" if scale else None, "item_type": kind,
        "is_tool": bool(kind) and any(w in kind.lower() for w in TOOL_TYPES),
        "size": size or None, "parts": _real(specs.get("total parts")), "etched": _real(specs.get("photo etched parts")),
        "released": _real(specs.get("released date")), "features": _real(specs.get("more features")),
        "intro": intro[:2000] if intro else None, "image_url": image_url,
    }


def _real(v: str | None) -> str | None:
    """A table value, or None for the blanks ('', 'n/a', '-')."""
    return None if not v or v.lower() in ("n/a", "na", "-", "none", "/") else v


def describe(info: dict) -> str:
    """The details as one line (kept in product_info.description), then the introduction."""
    line = " · ".join(filter(None, [
        f"Item no {info['item']}", info.get("scale") and f"Scale {info['scale']}", info.get("item_type"), info.get("size"),
        info.get("parts") and f"{info['parts']} parts", info.get("etched") and f"photo-etched: {info['etched']}",
        info.get("released") and f"released {info['released']}"]))
    more = "\n\n".join(filter(None, [info.get("features"), info.get("intro")]))
    return line + (f"\n\n{more}" if more else "")
