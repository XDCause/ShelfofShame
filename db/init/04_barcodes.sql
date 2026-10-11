-- Barcodes (EAN-13 / UPC / EAN-8) for products, so a photo of a barcode can identify an item.
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\04_barcodes.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

-- Stored on product_info (one row per brand + product code), next to the photo.
ALTER TABLE product_info ADD COLUMN IF NOT EXISTS barcode TEXT;

-- A barcode identifies exactly one product. Partial index: many products have no barcode yet.
CREATE UNIQUE INDEX IF NOT EXISTS product_info_barcode_uq
    ON product_info (barcode) WHERE barcode IS NOT NULL;

-- Barcodes are LEARNED (saved when you add a scanned item), never calculated. An earlier
-- version of this file calculated Tamiya barcodes as 4950344 + item number + check digit; that
-- is right for some products (87038 cement) but wrong for others (the Mini paints), so those
-- calculated values were removed from the live database on 2026-10-11.

COMMIT;
