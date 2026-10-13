-- Settings and the price guide (2026-10-13).
--
--   settings     simple key -> value pairs, e.g. default_shop = Hobbyrama
--   price_guide  your usual prices, used as the expected price on the wishlist and pre-filled
--                when adding. First matching rule (lowest sort_order) wins; a rule matches when
--                every condition it has is true (title contains / paint type / size).
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\15_settings.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
INSERT INTO settings (key, value) VALUES ('default_shop', 'Hobbyrama') ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS price_guide (
    rule_id        SERIAL PRIMARY KEY,
    label          TEXT NOT NULL,                  -- e.g. "Panel Line Accent"
    title_contains TEXT,                           -- matched against the product name, any case
    paint_type     TEXT,
    size           TEXT,
    price          NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    sort_order     INT NOT NULL DEFAULT 0,
    CONSTRAINT price_guide_condition_check
        CHECK (title_contains IS NOT NULL OR paint_type IS NOT NULL OR size IS NOT NULL)
);

-- The user's prices (2026-10-13), only on the first run.
INSERT INTO price_guide (label, title_contains, paint_type, size, price, sort_order)
SELECT * FROM (VALUES
    ('Panel Line Accent', 'PANEL LINE ACCENT', NULL, NULL, 10.95, 1),
    ('Acrylic paint, 10ml', NULL, 'Acrylic', '10ml', 3.95, 2)
) AS seed (label, title_contains, paint_type, size, price, sort_order)
WHERE NOT EXISTS (SELECT 1 FROM price_guide);

COMMIT;
