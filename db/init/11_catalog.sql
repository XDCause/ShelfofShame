-- Tamiya product catalogue for searching and "Shop Tamiya" (2026-10-13).
-- Filled by the one-off importer (category list pages only, 2 s apart):
--   docker exec hobby-inventory-api python -m app.tamiya_catalog
-- Full details + photo for a product are fetched (once) only when you add it.
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\11_catalog.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

CREATE TABLE IF NOT EXISTS catalog_products (
    brand_id     INT NOT NULL REFERENCES brands (brand_id) ON DELETE CASCADE,
    product_code TEXT NOT NULL,          -- your convention, e.g. T87131
    item         TEXT NOT NULL,          -- Tamiya's own number, e.g. 87131 (used for lookups)
    title        TEXT NOT NULL,          -- e.g. PANEL LINE ACCENT COLOR (BLACK)
    genre        TEXT,                   -- Tamiya's category: Paints, Finishing Materials, ...
    thumb_url    TEXT,                   -- Tamiya's small photo, shown from their site in search
    source_url   TEXT,
    imported_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_id, product_code)
);

COMMIT;
