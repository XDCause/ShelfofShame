"""Everything we know about Tamiya: their website, item numbers, barcodes and colour codes.

Polite by design: one page + one photo per lookup, only when you ask, identified by a clear
User-Agent. The caller caches the result in product_info so an item is never fetched twice.

Page layout this relies on (checked 2026-10-11, e.g. /english/products/81701/index.html):
    div.item_title_block_  > div.title1_ > span "Item No:81701"  + p (series)
                           > h1 (product name)
    div.img_ img           -> main photo (protocol-relative URL)
    div.wysiwyg_area_      -> description ("Contents: 10ml" etc.)
    div.item_colors_used_  -> kits only: "Tamiya Colors required", h3 groups of li > a
                              (span.ttl_ = name, "ITEM No.82103" = item number)
The pages are Shift_JIS encoded, not UTF-8.
"""
import re
import unicodedata

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


# ---------------------------------------------------------------------------
# Item numbers and colour codes
# ---------------------------------------------------------------------------
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


def product_code(item: str) -> str:
    """Your convention: Tamiya's number with a T in front (87131 -> T87131, 00XF1 -> T00XF1)."""
    return "T" + item if item[:1].isdigit() else item


def title_mentions(title: str | None, paint: str) -> bool:
    """Does Tamiya's title really contain this colour code? 'XF-76' must not match 'XF-7'."""
    prefix, number = paint.split("-")
    return bool(title and re.search(rf"\b{prefix}-?{re.escape(number)}(?![0-9])", title.upper()))


# Any Tamiya colour code in a name: X-7, XF-62, LP-28, TS-5, AS-12, PS-1 ("XF76" works too).
COLOUR_CODE = re.compile(r"\b(XF|X|LP|TS|AS|PS)-?(\d{1,3})([A-Z]?)\b")
# Words in front of the code that name the paint range, not the colour.
RANGE_WORDS = re.compile(r"^(TAMIYA\s+COLOR\s+|ACRYLIC\s+PAINT\s+MINI\s+|ACRYLIC\s+MINI\s+|"
                         r"ACRYLIC\s+PAINT\s+|ACRYLIC\s+|ENAMEL\s+|TAMIYA\s+)+")


def colour_of(name: str | None) -> tuple[str, str] | None:
    """The colour a Tamiya paint is: (code, colour name).
    'ACRYLIC PAINT MINI XF-62 OLIVE DRAB' -> ('XF-62', 'OLIVE DRAB'); 'Acrylic XF76 Grey Green'
    -> ('XF-76', 'GRAY GREEN'). None for things that aren't a colour (no code, or a thinner)."""
    text = tidy(name or "").upper()
    m = COLOUR_CODE.search(RANGE_WORDS.sub("", text))
    if m is None:
        return None
    code = f"{m.group(1)}-{int(m.group(2))}{m.group(3)}"
    colour = RANGE_WORDS.sub("", text)[m.end():]
    colour = re.sub(r"\(\s*\d+\s*ML\s*\)", "", colour)          # "(10ml)"
    colour = re.sub(r"[^A-Z0-9() ]+", " ", colour).replace("GREY", "GRAY")
    colour = re.sub(r"\s+", " ", colour).strip()
    if not colour or "THINNER" in colour or "RETARDER" in colour:
        return None
    return code, colour


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


# ---------------------------------------------------------------------------
# Product pages
# ---------------------------------------------------------------------------
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
        "kit_paints": parse_kit_paints(soup),
    }


def parse_kit_paints(soup) -> list[dict]:
    """A kit page's "Tamiya Colors required": [{section, group, item, title}], in page order.
    `section` numbers the page's lists: Tamiya can give two lists the same heading.
    Empty for pages without the list (paints, tools)."""
    box = soup.select_one("div.item_colors_used_")
    if box is None:
        return []
    paints = []
    for section, h3 in enumerate(box.select("h3")):
        group = _text(h3)
        ul = h3.find_next_sibling("ul")
        for li in ul.select("li") if ul else []:
            title = li.select_one(".ttl_")
            number = re.search(r"ITEM No\.\s*(\w+)", li.get_text(" "))
            if title and number:
                paints.append({"section": section, "group": group, "item": number.group(1),
                               "title": tidy(_text(title))})
    return paints


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
# Suggestions: best guesses for the form, always editable by you. (Your usual prices are a
# separate, editable list: see settings.price_for.)
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

# What a Tamiya item number says about the product: Tamiya numbers its paints in ranges.
# (prefixes, paint type, size). Used when the page itself doesn't say (panel line pages have no
# description at all) and when adding straight from the catalogue before the page is fetched.
ITEM_RANGES = [
    (("815", "817"), "Acrylic", "10ml"),    # Acrylic Paint Mini X-/XF-
    (("810", "813"), "Acrylic", "23ml"),    # Acrylic Paint X-/XF- (big jar)
    (("800", "803"), "Enamel", "10ml"),     # Tamiya Color enamel X-/XF-
    (("821",), "Lacquer", "10ml"),          # LP lacquer
    (("850", "851", "865"), "Lacquer", "100ml"),  # TS / AS spray cans
    (("860",), None, "100ml"),              # PS polycarbonate sprays
]


def tidy(text: str | None) -> str | None:
    """Tamiya sometimes uses full-width characters: 'COLOR（DARK BROWN）' -> 'COLOR (DARK BROWN)'."""
    if text is None:
        return None
    return re.sub(r"(\S)\(", r"\1 (", unicodedata.normalize("NFKC", text))  # "COLOR(" -> "COLOR ("


def suggest(title: str, series: str | None, description: str | None, item: str | None = None) -> dict:
    """Best guesses for a new supply / wishlist item: name, category, paint type, finish, size.
    `item` = Tamiya item number or our product code (81776 or T81776): its number range fills
    in paint type and size the page lacks."""
    title, series, description = tidy(title), tidy(series), tidy(description)
    words = " ".join(filter(None, [title, series])).lower()
    category = next((c for keys, c in CATEGORY_KEYWORDS if any(k in words for k in keys)), None)

    paint_type = next((t for t in ("Acrylic", "Enamel", "Lacquer") if t.lower() in words), None)
    finish = None
    if category in ("Paint", "Clear / Varnish", "Primer / Surfacer"):
        finish = next((f for keys, f in FINISH_KEYWORDS if any(k in title.lower() for k in keys)), None)
        code = re.search(r"\b(XF|X)-\d", title.upper())
        if finish is None and code:  # Tamiya's own rule: XF = flat, X = gloss
            finish = "Flat / Matt" if code.group(1) == "XF" else "Gloss"
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

    range_type, range_size = _item_range(item, title)
    if "PANEL LINE ACCENT" in title.upper():  # enamel-based, 40ml (pages don't say)
        range_type, range_size = "Enamel", "40ml"
    if range_type and paint_type in (None, "N/A"):
        paint_type = range_type

    return {
        "name": your_style_name(title),
        "category": category,
        "paint_type": paint_type,
        "finish": finish,
        "size": size or range_size,
    }


def _item_range(item: str | None, title: str) -> tuple[str | None, str | None]:
    if "MINI" in title.upper().split() and "ACRYLIC" in title.upper():
        return "Acrylic", "10ml"  # some minis sit in the 813xx range
    number = re.sub(r"^T(?=\d)", "", item or "")
    if not number.isdigit():
        return None, None
    return next(((kind, size) for prefixes, kind, size in ITEM_RANGES if number[:3] in prefixes),
                (None, None))


# Abbreviations that must stay in capitals, e.g. "GRAY GREEN (IJN)" -> "Gray Green (IJN)".
ACRONYMS = {"IJN", "IJA", "RAF", "RLM", "USN", "USAF", "USMC", "JGSDF", "JASDF", "JMSDF", "NATO",
            "IDF", "DAK", "WWII", "US", "UK", "LP", "TS", "PS", "AS", "RC", "LED", "PE", "UV", "HG"}

# "ACRYLIC PAINT MINI XF-2 FLAT WHITE", "ACRYLIC MINI X-35 SEMI GLOSS CLEAR", "... X-20A THINNER (10ml)"
ACRYLIC_MINI = re.compile(r"ACRYLIC\s+(?:PAINT\s+)?MINI\s+(XF|X)-(\d+[A-Z]?)\s+(.*?)\s*(?:\(\d+\s*ml\))?\s*$", re.I)


def your_style_name(title: str) -> str:
    """Names the way the user writes them: 'ACRYLIC PAINT MINI XF-2 FLAT WHITE' ->
    'Acrylic XF2 Flat White' (like their 'Acrylic XF1 Flat Black'). Anything else is just
    tidied: 'TAMIYA EXTRA-THIN CEMENT (40ml)' -> 'Tamiya Extra-Thin Cement (40ml)'."""
    title = tidy(title)
    m = ACRYLIC_MINI.match(title)
    if m:
        return f"Acrylic {m.group(1).upper()}{m.group(2).upper()} {nice_name(m.group(3))}".strip()
    return nice_name(title)


def nice_name(title: str) -> str:
    """'ACRYLIC PAINT MINI XF-1 FLAT BLACK' -> 'Acrylic Paint Mini XF-1 Flat Black'.
    Words with digits (XF-1, X-20A, (40ml)) are left exactly as Tamiya wrote them."""
    def fix(word):
        if any(ch.isdigit() for ch in word):
            return word
        # capitalise each run of letters, so "EXTRA-THIN" -> "Extra-Thin", "(GRAY)" -> "(Gray)"
        # acronyms (IJN) and Roman numerals (FIGURES II) stay in capitals
        keep = lambda w: w.upper() in ACRONYMS or re.fullmatch(r"I{2,3}|IV|VI{0,3}", w.upper())  # noqa: E731
        return re.sub(r"[A-Za-z]+", lambda m: m.group(0) if keep(m.group(0)) else m.group(0).capitalize(), word)
    return " ".join(fix(w) for w in title.split())
