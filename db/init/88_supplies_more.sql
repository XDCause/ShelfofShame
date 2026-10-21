-- Supplies grow (2026-10-21, user: "do 1 to 12" from a look at paintRack, Sortly, Grocy and Homebox):
--   places        storage_locations nest (rack > drawer > box): parent_id; a name is unique beside its siblings only;
--                 location_path(id) = 'Paint rack > Drawer 2' (with a single angle quote)
--   shelf life    supplies.opened_on (set when it's first opened) and shelf_months (else its category's)
--   stocktake     supplies.counted_at
--   colour        supplies.swatch ('#5a6b3c': picked, or guessed from the bottle photo)
--   set aside     supplies.reserved_model_id: kept for that build
--   warranty      warranty_until on supplies and gear; attachments (receipts, manuals) on either
--   maintenance   todos.supply_id / todos.gear_id: a (repeating) to-do for that tool or gear
-- Idempotent.

ALTER TABLE storage_locations ADD COLUMN IF NOT EXISTS parent_id INT REFERENCES storage_locations (location_id);
ALTER TABLE storage_locations DROP CONSTRAINT IF EXISTS storage_locations_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS storage_locations_sibling_name ON storage_locations (COALESCE(parent_id, 0), lower(name));
DO $$ BEGIN
    ALTER TABLE storage_locations ADD CONSTRAINT storage_locations_not_own_parent CHECK (parent_id IS NULL OR parent_id <> location_id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE OR REPLACE FUNCTION location_path(id INT) RETURNS TEXT LANGUAGE sql STABLE AS $$
    WITH RECURSIVE up AS (
        SELECT location_id, parent_id, name, 0 AS depth FROM storage_locations WHERE location_id = id
        UNION ALL
        SELECT l.location_id, l.parent_id, l.name, up.depth + 1 FROM storage_locations l JOIN up ON l.location_id = up.parent_id
        WHERE up.depth < 10
    )
    SELECT string_agg(name, ' ' || chr(8250) || ' ' ORDER BY depth DESC) FROM up      -- (chr(8250) = the path's arrow: ASCII here)
$$;

ALTER TABLE categories ADD COLUMN IF NOT EXISTS shelf_months INT CHECK (shelf_months BETWEEN 1 AND 240);
-- A rough "check it after" once opened (you can change any of these, or set one per item).
UPDATE categories SET shelf_months = v.m FROM (VALUES ('Paint', 36), ('Glue / Cement', 24), ('Primer / Surfacer', 36),
    ('Clear / Varnish', 36), ('Putty / Filler', 24), ('Masking Fluid / Putty', 24), ('Decal Solution', 36), ('Thinner', 60),
    ('Weathering', 60)) AS v(n, m) WHERE categories.name = v.n AND categories.shelf_months IS NULL;

ALTER TABLE supplies ADD COLUMN IF NOT EXISTS opened_on DATE;
ALTER TABLE supplies ADD COLUMN IF NOT EXISTS shelf_months INT CHECK (shelf_months BETWEEN 1 AND 240);
ALTER TABLE supplies ADD COLUMN IF NOT EXISTS counted_at TIMESTAMPTZ;
ALTER TABLE supplies ADD COLUMN IF NOT EXISTS swatch TEXT CHECK (swatch ~ '^#[0-9a-f]{6}$');
ALTER TABLE supplies ADD COLUMN IF NOT EXISTS reserved_model_id INT REFERENCES models (model_id) ON DELETE SET NULL;
ALTER TABLE supplies ADD COLUMN IF NOT EXISTS warranty_until DATE;
ALTER TABLE gear ADD COLUMN IF NOT EXISTS warranty_until DATE;

CREATE TABLE IF NOT EXISTS attachments (
    attachment_id SERIAL PRIMARY KEY,
    thing_kind    TEXT NOT NULL CHECK (thing_kind IN ('supply', 'gear')),
    thing_id      INT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'Receipt' CHECK (kind IN ('Receipt', 'Manual', 'Warranty', 'Other')),
    name          TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    content_type  TEXT NOT NULL,
    data          BYTEA NOT NULL,
    size          INT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS attachments_thing ON attachments (thing_kind, thing_id);

ALTER TABLE todos ADD COLUMN IF NOT EXISTS supply_id INT REFERENCES supplies (supply_id) ON DELETE CASCADE;
ALTER TABLE todos ADD COLUMN IF NOT EXISTS gear_id INT REFERENCES gear (gear_id) ON DELETE CASCADE;

-- An item's receipts and manuals go when it does.
CREATE OR REPLACE FUNCTION drop_supply_attachments() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM attachments WHERE thing_kind = 'supply' AND thing_id = OLD.supply_id;
    RETURN OLD;
END $$;
CREATE OR REPLACE FUNCTION drop_gear_attachments() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM attachments WHERE thing_kind = 'gear' AND thing_id = OLD.gear_id;
    RETURN OLD;
END $$;
DROP TRIGGER IF EXISTS supplies_drop_attachments ON supplies;
CREATE TRIGGER supplies_drop_attachments AFTER DELETE ON supplies FOR EACH ROW EXECUTE FUNCTION drop_supply_attachments();
DROP TRIGGER IF EXISTS gear_drop_attachments ON gear;
CREATE TRIGGER gear_drop_attachments AFTER DELETE ON gear FOR EACH ROW EXECUTE FUNCTION drop_gear_attachments();
