"""One-off import of Tamiya Acrylic Mini barcodes into barcode_catalog.

Run it (from the project folder) whenever you want to pick up new colours:
    docker exec hobby-inventory-api python -m app.catalog_import            # new pages only
    docker exec hobby-inventory-api python -m app.catalog_import --refresh  # re-check every page

Source: rchobbyland.com.au product pages, whose "Specifications" table lists
    SKU        81776-A00       (Tamiya item number + the shop's suffix)
    Barcode #  4950344070053
Checked 2026-10-11: robots.txt allows product pages and asks for a 1 s crawl delay; the terms of
use don't mention automated access. We go slower than asked (2 s), identify ourselves, visit only
the ~100 Acrylic Mini pages listed in their sitemap, and store only the factual barcode -> item
pair (none of their text, images or design).
"""
import gzip
import re
import sys
import time

import httpx
from bs4 import BeautifulSoup

from . import tamiya
from .db import db

SOURCE = "rchobbyland.com.au"
SITEMAP_INDEX = "https://www.rchobbyland.com.au/sitemap_index.xml.gz"
PAGE_PATTERN = re.compile(r"/tamiya-acrylic-mini-[^/?#]+$")
DELAY_SECONDS = 2
HEADERS = {"User-Agent": "ShelfOfShame/1.0 (personal hobby inventory; one-off barcode import; "
                         "+https://github.com/XDCause/ShelfofShame)"}


def get_xml(client, url):
    body = client.get(url).raise_for_status().content
    return gzip.decompress(body).decode() if body[:2] == b"\x1f\x8b" else body.decode()


def product_urls(client):
    index = get_xml(client, SITEMAP_INDEX)
    urls = []
    for sitemap in re.findall(r"<loc>([^<]+)</loc>", index):
        time.sleep(DELAY_SECONDS)
        urls += [u for u in re.findall(r"<loc>([^<]+)</loc>", get_xml(client, sitemap))
                 if PAGE_PATTERN.search(u)]
    return sorted(set(urls))


def parse_specs(html):
    """{'SKU': '81776-A00', 'Barcode #': '4950344070053', 'Brand': 'TAMIYA', ...}"""
    soup = BeautifulSoup(html, "html.parser")
    specs = {}
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) == 2:
            specs[cells[0].get_text(" ", strip=True)] = cells[1].get_text(" ", strip=True)
    return specs


def main(refresh=False):
    with db() as conn:
        tamiya_id = conn.execute("SELECT brand_id FROM brands WHERE name = 'Tamiya'").fetchone()["brand_id"]
        done = {r["source_url"] for r in conn.execute(
            "SELECT source_url FROM barcode_catalog WHERE source = %s", (SOURCE,)).fetchall()}

    added, skipped, problems = 0, 0, []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        urls = product_urls(client)
        todo = urls if refresh else [u for u in urls if u not in done]
        print(f"{len(urls)} Acrylic Mini pages in the sitemap; {len(todo)} to fetch "
              f"(~{len(todo) * (DELAY_SECONDS + 1) // 60 + 1} min)", flush=True)

        for i, url in enumerate(todo, 1):
            time.sleep(DELAY_SECONDS)
            try:
                specs = parse_specs(client.get(url).raise_for_status().text)
            except httpx.HTTPError as e:
                problems.append(f"{url}: {e.__class__.__name__}")
                continue

            sku = re.match(r"(\d{5})", specs.get("SKU", ""))
            barcode = tamiya.normalise_barcode(specs.get("Barcode #", ""))
            if not sku or not barcode or not tamiya.is_tamiya_barcode(barcode) \
                    or specs.get("Brand", "").upper() != "TAMIYA":
                skipped += 1
                problems.append(f"{url}: unusable specs SKU={specs.get('SKU')!r} "
                                f"barcode={specs.get('Barcode #')!r}")
                continue

            with db() as conn:
                conn.execute("""
                    INSERT INTO barcode_catalog (barcode, brand_id, product_code, source, source_url)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (barcode) DO UPDATE SET product_code = EXCLUDED.product_code,
                        source_url = EXCLUDED.source_url, imported_at = now()""",
                    (barcode, tamiya_id, "T" + sku.group(1), SOURCE, url))
            added += 1
            print(f"  [{i}/{len(todo)}] {barcode} -> T{sku.group(1)}", flush=True)

    print(f"\nDone: {added} barcodes saved, {skipped} pages skipped.")
    for p in problems:
        print("  !", p)


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
