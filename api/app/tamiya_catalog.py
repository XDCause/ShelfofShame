"""Import Tamiya's product catalogue (paints, finishing materials, tools, airbrush) for search.

Run it from Settings ("Refresh the Tamiya catalogue"), or from the project folder:
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
import time

import httpx
from bs4 import BeautifulSoup

from .db import brand_id, db
from .tamiya import HEADERS, TIMEOUT, product_code

LIST_URL = "https://www.tamiya.com/english/products/list.html?genre_item={genre}&absolutepage={page}"
GENRES = {
    "e_5040": "Paints",
    "e_5010": "Finishing Materials",
    "e_5020": "Craft Tools",
    "e_5030": "Airbrush System",
}
DELAY_SECONDS = 2
PER_PAGE = 20


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


def fetch_list(client, genre: str, page: int) -> str:
    return client.get(LIST_URL.format(genre=genre, page=page)).raise_for_status() \
        .content.decode("cp932", errors="replace")


def run(progress=print, delay: float = DELAY_SECONDS) -> int:
    """Read every list page and save the products. `progress(message)` is told about each page.
    Returns how many products the catalogue has afterwards."""
    with db() as conn:
        tamiya_id = brand_id(conn, "Tamiya")
    if tamiya_id is None:
        raise RuntimeError("Add 'Tamiya' to your brands first.")

    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        for genre, name in GENRES.items():
            page, pages = 1, 1
            while page <= pages:
                time.sleep(delay)
                products, total = parse_list(fetch_list(client, genre, page))
                pages = max(1, -(-total // PER_PAGE))  # ceiling division
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
                            (tamiya_id, product_code(p["item"]), p["item"], p["title"],
                             p["genre"] or name, p["thumb_url"], p["source_url"]))
                progress(f"{name}: page {page} of {pages}")
                page += 1

    with db() as conn:
        return conn.execute("SELECT count(*) AS n FROM catalog_products").fetchone()["n"]


if __name__ == "__main__":
    print(f"\nDone: the catalogue now has {run()} products.")
