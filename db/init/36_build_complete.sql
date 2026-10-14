-- Build steps end with "Complete", and steps can be skipped (2026-10-14).
--
-- Some kits have no detailing to do (a snap-fit High Grade Gunpla: no panel lining, decals or top
-- coat), so a build can go straight from Built to Complete. models.stage is still the last step
-- reached; models.skipped_steps lists the steps passed over on the way (shown as skipped, not done).
-- The first step (Built) can't be skipped. Reaching Complete finishes the kit, and a Finished kit
-- is always at Complete.
--
-- Finished kits from before get Complete, with the steps after their last ticked one (but never
-- Built) marked skipped - tap one in the kit to say it was done.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE models ADD COLUMN IF NOT EXISTS skipped_steps TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE models DROP CONSTRAINT IF EXISTS models_stage_check;
ALTER TABLE models ADD CONSTRAINT models_stage_check CHECK (stage IS NULL
    OR (hobby = 'Scale model' AND stage IN ('Built', 'Primed', 'Painted', 'Decals', 'Weathered', 'Complete'))
    OR (hobby = 'Warhammer'   AND stage IN ('Built', 'Primed', 'Painted', 'Based', 'Complete'))
    OR (hobby = 'Gundam'      AND stage IN ('Built', 'Panel lined', 'Decals', 'Top coat', 'Complete')));

WITH steps(hobby, list) AS (VALUES
    ('Scale model', ARRAY['Built', 'Primed', 'Painted', 'Decals', 'Weathered']),
    ('Warhammer',   ARRAY['Built', 'Primed', 'Painted', 'Based']),
    ('Gundam',      ARRAY['Built', 'Panel lined', 'Decals', 'Top coat']))
UPDATE models m
SET stage = 'Complete',
    skipped_steps = m.skipped_steps || s.list[GREATEST(COALESCE(array_position(s.list, m.stage), 0) + 1, 2):]
FROM steps s
WHERE s.hobby = m.hobby AND m.status = 'Finished' AND m.stage IS DISTINCT FROM 'Complete';
