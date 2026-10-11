-- Wishlist + cached manufacturer product info (photos, titles, descriptions).
--
-- Idempotent (IF NOT EXISTS / DROP ... IF EXISTS), so the same file can:
--   * run automatically on a brand-new database (docker init), and
--   * be applied by hand to the existing database:
--       Get-Content db\init\03_wishlist.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

-- One row per manufacturer product we've looked up. A cache: each item is fetched from the
-- manufacturer's website once, then served from here. Keyed by brand + product code, the same
-- way supplies are, so inventory items can share the photos too.
CREATE TABLE IF NOT EXISTS product_info (
    product_info_id SERIAL PRIMARY KEY,
    brand_id        INT NOT NULL REFERENCES brands (brand_id) ON DELETE CASCADE,
    product_code    TEXT NOT NULL,
    title           TEXT,           -- manufacturer's product name
    series          TEXT,           -- e.g. "Tamiya Color Acrylic Paint Mini"
    description     TEXT,
    source_url      TEXT,
    image           BYTEA,          -- the photo itself (~80 KB), so it's in backups and works offline
    image_type      TEXT,           -- e.g. image/jpeg
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT product_info_brand_code_uq UNIQUE (brand_id, product_code)
);

-- Things you want to buy. Separate from supplies, so nothing here shows up as inventory.
CREATE TABLE IF NOT EXISTS wishlist (
    wish_id      SERIAL PRIMARY KEY,
    brand_id     INT REFERENCES brands (brand_id),
    product_code TEXT,
    name         TEXT NOT NULL,
    category_id  INT NOT NULL REFERENCES categories (category_id),
    paint_type   TEXT CHECK (paint_type IN
                     ('Acrylic', 'Lacquer', 'Enamel', 'Water-based', 'Oil', 'Alcohol-based', 'N/A')),
    finish       TEXT CHECK (finish IN
                     ('Flat / Matt', 'Satin', 'Semi-gloss', 'Gloss', 'Metallic', 'Clear',
                      'Pearl', 'Fluorescent', 'N/A')),
    size         TEXT,
    qty_wanted   INT NOT NULL DEFAULT 1 CHECK (qty_wanted >= 1),
    est_price    NUMERIC(10, 2) CHECK (est_price >= 0),
    priority     TEXT NOT NULL DEFAULT 'Normal' CHECK (priority IN ('High', 'Normal', 'Low')),
    for_project  TEXT,
    notes        TEXT,
    got_it       BOOLEAN NOT NULL DEFAULT false,  -- ticked off while shopping
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wishlist_brand_code_uq UNIQUE (brand_id, product_code)
);

-- Reuse the updated_at trigger function from 01_schema.sql.
DROP TRIGGER IF EXISTS wishlist_set_updated_at ON wishlist;
CREATE TRIGGER wishlist_set_updated_at
    BEFORE UPDATE ON wishlist
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
