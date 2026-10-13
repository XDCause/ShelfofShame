-- Colour matches and mixes (2026-10-13).
--
--   colour_groups / colour_group_members  your own "these are the same colour" lists, any brand
--       e.g. "Olive Drab (US WWII)": Tamiya XF-62, Mr. Color C38, ... with a note of the source.
--       (Same Tamiya code and same Tamiya colour name are worked out automatically - no rows.)
--   mixes / mix_parts                     recipes, e.g. "XF-62 + XF-2 (3:1)"
--   model_paints.mix_id                   a model's checklist line can be a mix: you "have" it
--                                         when you own every part
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\14_colours.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

CREATE TABLE IF NOT EXISTS colour_groups (
    group_id   SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    note       TEXT,                                -- where the match comes from
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS colour_group_members (
    member_id    SERIAL PRIMARY KEY,
    group_id     INT NOT NULL REFERENCES colour_groups (group_id) ON DELETE CASCADE,
    brand_id     INT REFERENCES brands (brand_id),
    product_code TEXT,
    paint_name   TEXT NOT NULL,
    sort_order   INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS colour_group_members_paint_idx ON colour_group_members (brand_id, product_code);

CREATE TABLE IF NOT EXISTS mixes (
    mix_id     SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    notes      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mix_parts (
    part_id      SERIAL PRIMARY KEY,
    mix_id       INT NOT NULL REFERENCES mixes (mix_id) ON DELETE CASCADE,
    brand_id     INT REFERENCES brands (brand_id),
    product_code TEXT,
    paint_name   TEXT NOT NULL,
    parts        NUMERIC(6, 2) NOT NULL DEFAULT 1 CHECK (parts > 0),
    sort_order   INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS mix_parts_mix_idx ON mix_parts (mix_id, sort_order);

ALTER TABLE model_paints ADD COLUMN IF NOT EXISTS mix_id INT REFERENCES mixes (mix_id) ON DELETE SET NULL;

COMMIT;
