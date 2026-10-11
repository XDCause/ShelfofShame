"""Look up a product on Tamiya's English website.

Polite by design: one page + one photo per lookup, only when you ask, identified by a clear
User-Agent. The caller caches the result in product_info so an item is never fetched twice.

Page layout this relies on (checked 2026-10-11, e.g. /english/products/81701/index.html):
    div.item_title_block_  > div.title1_ > span "Item No:81701"  + p (series)
                           > h1 (product name)
    div.img_ img           -> main photo (protocol-relative URL)
    div.wysiwyg_area_      -> description ("Contents: 10ml" etc.)
The pages are Shift_JIS encoded, not UTF-8.
"""
import re

import httpx
from bs4 import BeautifulSoup

PAGE_URL = "https://www.tamiya.com/english/products/{item}/index.html"
HEADERS = {"User-Agent": "ShelfOfShame/1.0 (personal hobby inventory; one request per lookup; "
                         "+https://github.com/XDCause/ShelfofShame)"}
TIMEOUT = 30  # tamiya.com can be slow, especially for kit pages with big photos


class NotFound(Exception):
    pass


class LookupFailed(Exception):
    pass


# Tamiya Color Acrylic Mini (10 ml) item numbers follow the colour code exactly:
#   X-n -> 815nn (X-10 = 81510, X-22 = 81522, X-20A thinner = 81520)
#   XF-n -> 817nn (XF-1 = 81701, XF-76 = 81776)
# The colour code is printed big on every bottle, so it's the easiest thing to type.
PAINT_CODE = re.compile(r"(XF|X)\s*-?\s*(\d{1,2})(A?)")
PAINT_SERIES = {"X": "815", "XF": "817"}


def paint_code(code: str) -> str | None:
    """'xf76', 'XF 76', 'XF-76' -> 'XF-76'. None if it isn't an X/XF colour code."""
    m = PAINT_CODE.fullmatch(code.strip().upper())
    return f"{m.group(1)}-{int(m.group(2))}{m.group(3)}" if m else None


def item_number(code: str) -> str | None:
    """'T81701', '81701', ' t81701 ' -> '81701'; 'XF-76' -> '81776' (Acrylic Mini).
    Your codes are Tamiya's number with a T prefix."""
    code = code.strip().upper()
    m = PAINT_CODE.fullmatch(code)
    if m:
        return PAINT_SERIES[m.group(1)] + f"{int(m.group(2)):02d}"
    if re.fullmatch(r"T\d\w*", code):
        code = code[1:]
    return code if re.fullmatch(r"[0-9A-Z]{3,12}", code) else None


def title_mentions(title: str | None, paint: str) -> bool:
    """Does Tamiya's title really contain this colour code? 'XF-76' must not match 'XF-7'."""
    prefix, number = paint.split("-")
    return bool(title and re.search(rf"\b{prefix}-?{re.escape(number)}(?![0-9])", title.upper()))


# ---------------------------------------------------------------------------
# Barcodes. Tamiya's are EAN-13 starting 4950344 (their company prefix). SOME also contain the
# item number (87038 Extra Thin Cement = 4950344 87038 7) but many don't: the Mini paints use a
# different numbering (81510 X-10 = 4950344 06900 2). So the item number taken from a barcode is
# only a guess to try; barcodes are learned when you save an item, never calculated.
# ---------------------------------------------------------------------------
TAMIYA_PREFIX = "4950344"


def gtin_check_digit(digits: str) -> str:
    """Check digit for any EAN/UPC: weights 3,1,3,1... starting from the right-most data digit."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return str((10 - total % 10) % 10)


def normalise_barcode(raw: str) -> str | None:
    """Digits only, checksum verified. UPC-A (12 digits) becomes EAN-13 with a leading 0,
    which is how the same product reads on EAN scanners. None if it isn't a valid barcode."""
    code = "".join(ch for ch in raw if ch.isdigit())
    if len(code) == 12:
        code = "0" + code
    if len(code) not in (8, 13) or gtin_check_digit(code[:-1]) != code[-1]:
        return None
    return code


def is_tamiya_barcode(barcode: str) -> bool:
    return len(barcode) == 13 and barcode.startswith(TAMIYA_PREFIX)


def guess_item_from_barcode(barcode: str) -> str | None:
    """'4950344870387' -> '87038'. Only a guess: right for some products, not for others."""
    return barcode[7:12] if is_tamiya_barcode(barcode) else None


def fetch(item: str) -> dict:
    """Download and parse one product page plus its photo."""
    url = PAGE_URL.format(item=item)
    try:
        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            page = client.get(url)
            if page.status_code == 404:
                raise NotFound(f"Tamiya has no product page for item {item}.")
            page.raise_for_status()
            # cp932 = Microsoft's Shift_JIS, a superset of what the page declares
            info = parse(page.content.decode("cp932", errors="replace"))
            info["source_url"] = url

            info["image"] = info["image_type"] = None
            image_url = info.pop("image_url")
            if image_url:
                photo = client.get(_absolute(image_url))
                if photo.status_code == 200 and photo.headers.get("content-type", "").startswith("image/"):
                    info["image"] = photo.content
                    info["image_type"] = photo.headers["content-type"].split(";")[0]
            return info
    except httpx.HTTPError as e:
        raise LookupFailed(f"Couldn't reach tamiya.com ({e.__class__.__name__}).") from e


def parse(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one("div.item_title_block_")
    if block is None or block.h1 is None:
        raise NotFound("That page doesn't look like a Tamiya product page.")

    series = block.select_one("div.title1_ p")
    img = soup.select_one("div.img_ img") or soup.select_one('meta[property="og:image"]')
    desc = soup.select_one("div.wysiwyg_area_")
    return {
        "title": _text(block.h1),
        "series": _text(series) if series else None,
        "description": _clean_description(desc.get_text("\n")) if desc else None,
        "image_url": (img.get("src") or img.get("content")) if img else None,
    }


def _absolute(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.tamiya.com" + url
    return url


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip()


def _clean_description(text: str) -> str | None:
    # Tamiya uses ★ as bullet points; put each on its own line.
    text = text.replace("★", "\n").replace("　", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:2000] or None


# ---------------------------------------------------------------------------
# Suggestions: best guesses for the form, always editable by you.
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = [  # first match wins, so specific words come before general ones
    (("thinner", "retarder"), "Thinner"),
    (("primer", "surface"), "Primer / Surfacer"),
    (("cement", "glue", "bond", "craft bind"), "Glue / Cement"),
    (("putty", "filler"), "Putty / Filler"),
    (("masking tape",), "Masking Tape"),
    (("masking sol", "masking liquid"), "Masking Fluid / Putty"),
    (("panel line", "weathering"), "Weathering"),
    (("pigment",), "Pigments"),
    (("decal",), "Decal Solution"),
    (("sanding", "sandpaper", "abrasive", "polishing", "compound"), "Sanding / Abrasives"),
    (("airbrush", "spray-work", "spray work"), "Airbrush & Parts"),
    (("brush",), "Brushes"),
    (("clear", "top coat", "varnish"), "Clear / Varnish"),
    (("paint", "color", "colour"), "Paint"),
    (("tool", "cutter", "knife", "tweezer", "file", "scriber"), "Tools"),
]

FINISH_KEYWORDS = [  # semi-gloss before gloss, metallic words before plain colours
    (("semi-gloss", "semi gloss"), "Semi-gloss"),
    (("flat", "matt", "matte"), "Flat / Matt"),
    (("metallic", "metal", "chrome", "silver", "gold", "aluminum", "aluminium", "titanium"), "Metallic"),
    (("pearl",), "Pearl"),
    (("fluorescent",), "Fluorescent"),
    (("clear",), "Clear"),
    (("gloss",), "Gloss"),
]


def suggest(title: str, series: str | None, description: str | None) -> dict:
    words = " ".join(filter(None, [title, series])).lower()
    category = next((c for keys, c in CATEGORY_KEYWORDS if any(k in words for k in keys)), None)

    paint_type = next((t for t in ("Acrylic", "Enamel", "Lacquer") if t.lower() in words), None)
    finish = None
    if category in ("Paint", "Clear / Varnish", "Primer / Surfacer"):
        finish = next((f for keys, f in FINISH_KEYWORDS if any(k in title.lower() for k in keys)), None)
    elif category:
        paint_type = paint_type if category == "Thinner" else "N/A"
        finish = "N/A"

    # Prefer the description's "Contents: 18m" (tape length, bottle size) over sizes in the
    # title, which can be a width ("MASKING TAPE 10mm").
    size = None
    amount = r"(\d+(?:\.\d+)?)\s*(ml|g|m|mm|cm)\b"
    for pattern, text in ((r"contents:\s*" + amount, description or ""),
                          (amount, title), (amount, description or "")):
        m = re.search(pattern, text, re.I)
        if m:
            size = m.group(1) + m.group(2).lower()
            break

    return {
        "name": your_style_name(title),
        "category": category,
        "paint_type": paint_type,
        "finish": finish,
        "size": size,
    }


# Abbreviations that must stay in capitals, e.g. "GRAY GREEN (IJN)" -> "Gray Green (IJN)".
ACRONYMS = {"IJN", "IJA", "RAF", "RLM", "USN", "USAF", "USMC", "JGSDF", "JASDF", "JMSDF", "NATO",
            "IDF", "DAK", "WWII", "US", "UK", "LP", "TS", "PS", "AS", "RC", "LED", "PE", "UV", "HG"}


# "ACRYLIC PAINT MINI XF-2 FLAT WHITE", "ACRYLIC MINI X-35 SEMI GLOSS CLEAR", "... X-20A THINNER (10ml)"
ACRYLIC_MINI = re.compile(r"ACRYLIC\s+(?:PAINT\s+)?MINI\s+(XF|X)-(\d+[A-Z]?)\s+(.*?)\s*(?:\(\d+\s*ml\))?\s*$", re.I)


def your_style_name(title: str) -> str:
    """Names the way the user writes them: 'ACRYLIC PAINT MINI XF-2 FLAT WHITE' ->
    'Acrylic XF2 Flat White' (like their 'Acrylic XF1 Flat Black'). Anything else is just
    tidied: 'TAMIYA EXTRA-THIN CEMENT (40ml)' -> 'Tamiya Extra-Thin Cement (40ml)'."""
    m = ACRYLIC_MINI.match(title.strip())
    if m:
        return f"Acrylic {m.group(1).upper()}{m.group(2).upper()} {_nice_name(m.group(3))}".strip()
    return _nice_name(title)


def _nice_name(title: str) -> str:
    """'ACRYLIC PAINT MINI XF-1 FLAT BLACK' -> 'Acrylic Paint Mini XF-1 Flat Black'.
    Words with digits (XF-1, X-20A, (40ml)) are left exactly as Tamiya wrote them."""
    def fix(word):
        if any(ch.isdigit() for ch in word):
            return word
        # capitalise each run of letters, so "EXTRA-THIN" -> "Extra-Thin", "(GRAY)" -> "(Gray)"
        return re.sub(r"[A-Za-z]+",
                      lambda m: m.group(0) if m.group(0).upper() in ACRONYMS else m.group(0).capitalize(),
                      word)
    return " ".join(fix(w) for w in title.split())
