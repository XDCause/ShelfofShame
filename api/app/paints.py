"""Turning typed or pasted paints into products. Used by model checklists, mixes and colour
matches, so "XF-76", "xf76 Grey Green" and "81776" all mean Tamiya T81776 everywhere.
"""
import re
from decimal import Decimal, InvalidOperation

from . import tamiya

# Between the paint and what it's for: a tab, or " - " / " – " / " — " / ": ".
SPLIT = re.compile(r"\t+|\s+[-–—]\s+|:\s+")
# Notes about buying aren't part of the name: the checklist works that out from your inventory.
BUY_NOTE = re.compile(r"\s*\((?:still\s+)?(?:to|need to)\s+buy\)", re.I)
LEADING_PAINT_CODE = re.compile(r"(XF|X)\s*-?\s*(\d{1,2})(A?)(?![\dA-Z])", re.I)
# "XF-62 + XF-2 (3:1)", "XF-62 3 + XF-2 1", "XF-62 + XF-2"
MIX_RATIO = re.compile(r"\(?\s*(\d+(?:\.\d+)?(?:\s*:\s*\d+(?:\.\d+)?)+)\s*\)?\s*$")


def parse_line(line: str) -> tuple[str, str | None]:
    """'XF-76 Grey Green (IJN)<tab>The whole exterior' -> ('XF-76 Grey Green (IJN)', 'The whole exterior')"""
    parts = SPLIT.split(line.strip(), maxsplit=1)
    paint = re.sub(r"\s+", " ", BUY_NOTE.sub("", parts[0])).strip()
    purpose = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return paint, purpose


def is_mix(paint: str) -> bool:
    return " + " in paint or re.search(r"\w\s*\+\s*\w", paint) is not None


def parse_mix(text: str) -> list[tuple[str, Decimal]]:
    """'XF-62 + XF-2 (3:1)' -> [('XF-62', 3), ('XF-2', 1)]. Without a ratio every part is 1."""
    text = text.strip()
    ratio = MIX_RATIO.search(text)
    amounts = []
    if ratio and ":" in ratio.group(1):
        amounts = [Decimal(x.strip()) for x in ratio.group(1).split(":")]
        text = text[:ratio.start()].strip()
    names = [p.strip() for p in text.split("+") if p.strip()]
    parts = []
    for i, name in enumerate(names):
        amount = amounts[i] if i < len(amounts) else None
        trailing = re.search(r"\s(\d+(?:\.\d+)?)\s*(?:parts?)?$", name)  # "XF-62 3"
        if amount is None and trailing and not LEADING_PAINT_CODE.fullmatch(name):
            try:
                amount = Decimal(trailing.group(1))
                name = name[:trailing.start()].strip()
            except InvalidOperation:
                pass
        parts.append((name, amount or Decimal(1)))
    return parts


def resolve(conn, paint: str, tamiya_id: int | None):
    """Which product a typed paint is: (brand_id, product_code, display name or None).
    None for the name means only a code was typed - use default_name() for it."""
    first = paint.split()[0] if paint.split() else ""
    m = LEADING_PAINT_CODE.match(paint)
    if m and tamiya_id:                                    # XF-76 -> Tamiya T81776
        code = "T" + tamiya.item_number(m.group(0))
        return tamiya_id, code, None if tamiya.paint_code(paint) else paint
    owned = conn.execute("SELECT brand_id, product_code FROM supplies WHERE upper(product_code) = upper(%s) "
                         "LIMIT 1", (first,)).fetchone()
    if owned:                                              # a code you own, e.g. MIL3
        return owned["brand_id"], owned["product_code"], paint if paint != first else None
    if re.fullmatch(r"T?\d{5}", first, re.I) and tamiya_id:  # a Tamiya item number
        return tamiya_id, "T" + first.upper().lstrip("T"), paint if paint != first else None
    return None, None, paint                               # not linked: tick it by hand


def default_name(conn, brand_id, code, typed: str) -> str:
    """Just a code was typed (e.g. 'XF-76'): use your own name for it, else Tamiya's."""
    row = conn.execute("SELECT name FROM supplies WHERE brand_id = %s AND product_code = %s",
                       (brand_id, code)).fetchone()
    if row:
        return row["name"]
    row = conn.execute("""
        SELECT COALESCE(p.title, c.title) AS title
        FROM (SELECT %(b)s::int AS brand_id, %(c)s::text AS product_code) x
        LEFT JOIN product_info p ON p.brand_id = x.brand_id AND p.product_code = x.product_code
        LEFT JOIN catalog_products c ON c.brand_id = x.brand_id AND c.product_code = x.product_code""",
        {"b": brand_id, "c": code}).fetchone()
    return tamiya.your_style_name(row["title"]) if row and row["title"] else typed


def to_product(conn, typed: str, tamiya_id: int | None) -> dict:
    """A typed paint as {brand_id, product_code, paint_name}."""
    brand_id, code, name = resolve(conn, typed, tamiya_id)
    return {"brand_id": brand_id, "product_code": code,
            "paint_name": name if name is not None else default_name(conn, brand_id, code, typed)}
