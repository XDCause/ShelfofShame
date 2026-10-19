-- Kits (2026-10-20): a supply can be part of another - the nipper, knife and sanding sticks that came in a tool kit.
-- Each part is its own supply (searchable, its own stock and condition); the kit keeps the price and the link.
-- One level only (a part can't have parts) - checked by the API. Idempotent.
ALTER TABLE supplies ADD COLUMN IF NOT EXISTS part_of integer REFERENCES supplies (supply_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS supplies_part_of_idx ON supplies (part_of) WHERE part_of IS NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'supplies_not_own_kit') THEN
        ALTER TABLE supplies ADD CONSTRAINT supplies_not_own_kit CHECK (part_of IS NULL OR part_of <> supply_id);
    END IF;
END $$;
