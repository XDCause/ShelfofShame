-- Which db/init files a database has had (2026-10-13).
--
-- Until now each new file was applied by hand. With a dev and a prod copy, migrate.ps1 does it:
-- it applies every file not listed here, in order, and records it. Files must stay idempotent
-- (safe to run twice), as they always have been.
--
-- This file records itself and everything before it: an existing database already has them,
-- and on a brand-new database Docker has just run them all.
-- Idempotent: safe on a fresh database (docker init) and on the existing one.

CREATE TABLE IF NOT EXISTS schema_migrations (
    name       TEXT PRIMARY KEY,                 -- the file name, e.g. '17_schema_migrations.sql'
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (name)
SELECT unnest(ARRAY[
    '01_schema.sql', '02_seed.sql', '03_wishlist.sql', '04_barcodes.sql', '05_barcode_catalog.sql',
    '06_stock_history.sql', '07_remove_used_for.sql', '08_condition_low.sql', '09_models.sql',
    '10_model_links.sql', '11_catalog.sql', '12_spend.sql', '13_kit_stash.sql', '14_colours.sql',
    '15_settings.sql', '16_hobbies.sql', '17_schema_migrations.sql'])
ON CONFLICT (name) DO NOTHING;
