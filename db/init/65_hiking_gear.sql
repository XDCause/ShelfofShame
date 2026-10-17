-- Gear for Hiking too (gear was volleyball's only; gear.hobby was there for this), and which gear went
-- on which hike - so boots, packs and poles show their hikes and kilometres. Idempotent.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'gear'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%hiking%') THEN
        ALTER TABLE gear DROP CONSTRAINT IF EXISTS gear_hobby_check;
        ALTER TABLE gear ADD CONSTRAINT gear_hobby_check CHECK (hobby IN ('volleyball', 'hiking'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS hike_gear (
    hike_id integer NOT NULL REFERENCES hikes ON DELETE CASCADE,
    gear_id integer NOT NULL REFERENCES gear ON DELETE CASCADE,
    PRIMARY KEY (hike_id, gear_id)
);
CREATE INDEX IF NOT EXISTS hike_gear_gear_idx ON hike_gear (gear_id);
