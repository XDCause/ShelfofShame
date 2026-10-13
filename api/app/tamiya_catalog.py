"""Import Tamiya's product catalogue (paints, finishing materials, tools, airbrush) for search.

Run it (from the project folder) whenever you want new releases:
    docker exec hobby-inventory-api python -m app.tamiya_catalog

Reads only the category LIST pages - 20 products per page, ~54 pages, 2 s apart (~3 min):
    /english/products/list.html?genre_item=e_5040&absolutepage=2
Each listing gives the item number, name, category and a small photo:
    <li><a href=".../products/87131/index.html" data-article="87131">
        <div class="img_"><img src="//.../87131_s.jpg"></div>
        <div class="txt_"><span class="category_e_5010">Finishing Materials</span>
        <h3><span>ITEM 87131 </span>PANEL LINE ACCENT COLOR (BLACK) </h3>
Full details + photo for one product are fetched (once) only when you add it.
"""
import re
import sys
import time

import httpx
from bs4 import BeautifulSoup

from .db import db
from .tamiya import HEADERS, TIMEOUT

LIST_URL = "https://www.tamiya.com/english/products/list.html?genre_item={genre}&absolutepage={page}"
GENRES = {
    "e_5040": "Paints",
    "e_5010": "Finishing Materials",
    "e_5020": "Craft Tools",
    "e_5030": "Airbrush System",
}
DELAY_SECONDS = 2


def parse_list(html: str) -> tuple[list[dict], int]:
    """(products on this page, total number of products in the category)."""
    soup = BeautifulSoup(html, "html.parser")
    total = re.search(r"([0-9,]+)\s*results", soup.get_text(" "))
    products = []
    for a in soup.select("ul.item_list_ li > a[data-article]"):
        item = a["data-article"].strip()
        h3 = a.find("h3")
        if not item or h3 is None:
            continue
        label = h3.find("span")
        if label:
            label.extract()  # drop the "ITEM 87131" prefix, keep the name
        img = a.select_one(".img_ img")
        genre = a.select_one(".txt_ span")
        thumb = (img.get("src") or "").strip() if img else ""
        products.append({
            "item": item,
            "title": re.sub(r"\s+", " ", h3.get_text(" ")).strip(),
            "genre": genre.get_text(strip=True) if genre else None,
            "thumb_url": ("https:" + thumb) if thumb.startswith("//") else (thumb or None),
            "source_url": a.get("href"),
        })
    return products, int(total.group(1).replace(",", "")) if total else len(products)


def product_code(item: str) -> str:
    """Your convention: Tamiya's number with a T in front (87131 -> T87131, 00XF1 -> T00XF1)."""
    return "T" + item if item[:1].isdigit() else item


def main():
    with db() as conn:
        tamiya = conn.execute("SELECT brand_id FROM brands WHERE name = 'Tamiya'").fetchone()
    if tamiya is None:
        sys.exit("Add 'Tamiya' to your brands first.")

    saved = 0
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        for genre, name in GENRES.items():
            page, pages = 1, 1
            while page <= pages:
                time.sleep(DELAY_SECONDS)
                html = client.get(LIST_URL.format(genre=genre, page=page)).raise_for_status() \
                    .content.decode("cp932", errors="replace")
                products, total = parse_list(html)
                pages = max(1, -(-total // 20))  # ceiling division
                with db() as conn:
                    for p in products:
                        conn.execute("""
                            INSERT INTO catalog_products
                                (brand_id, product_code, item, title, genre, thumb_url, source_url)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (brand_id, product_code) DO UPDATE SET
                                title = EXCLUDED.title, genre = EXCLUDED.genre,
                                thumb_url = EXCLUDED.thumb_url, source_url = EXCLUDED.source_url,
                                imported_at = now()""",
                            (tamiya["brand_id"], product_code(p["item"]), p["item"], p["title"],
                             p["genre"] or name, p["thumb_url"], p["source_url"]))
                saved += len(products)
                print(f"  {name}: page {page}/{pages} ({len(products)} products)", flush=True)
                page += 1

    with db() as conn:
        n = conn.execute("SELECT count(*) AS n FROM catalog_products").fetchone()["n"]
    print(f"\nDone: {saved} listings read; the catalogue now has {n} products.")


if __name__ == "__main__":
    main()
