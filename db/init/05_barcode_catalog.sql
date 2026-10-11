-- Barcode catalogue: barcode -> manufacturer product code, imported in bulk from a public source
-- (so a product you've never scanned can still be identified). Only factual pairs are stored.
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\05_barcode_catalog.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory
-- Filled by: docker exec hobby-inventory-api python -m app.catalog_import

BEGIN;

CREATE TABLE IF NOT EXISTS barcode_catalog (
    barcode      TEXT PRIMARY KEY,           -- EAN-13, checksum verified
    brand_id     INT NOT NULL REFERENCES brands (brand_id) ON DELETE CASCADE,
    product_code TEXT NOT NULL,              -- your convention, e.g. T81776
    source       TEXT NOT NULL,              -- e.g. rchobbyland.com.au
    source_url   TEXT,
    imported_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS barcode_catalog_product_idx ON barcode_catalog (brand_id, product_code);

COMMIT;
