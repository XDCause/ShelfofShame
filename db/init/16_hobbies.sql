-- More than scale models: Warhammer and Gundam (2026-10-13).
--
--   models.hobby         Scale model / Warhammer / Gundam (everything so far is a Scale model)
--   models.stage         how far the build has got; each hobby has its own steps (below)
--   models.grade         Gundam: HG, RG, MG, PG, SD...
--   models.faction       Warhammer: the army it's for
--   models.figures       Warhammer: minis in the box (a box of 10 is one model, not ten)
--   models.figures_done  ...and how many of them are painted
--
-- Must match HOBBIES / STAGES in api/app/db.py.
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\16_hobbies.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

ALTER TABLE models ADD COLUMN IF NOT EXISTS hobby        TEXT NOT NULL DEFAULT 'Scale model';
ALTER TABLE models ADD COLUMN IF NOT EXISTS stage        TEXT;
ALTER TABLE models ADD COLUMN IF NOT EXISTS grade        TEXT;
ALTER TABLE models ADD COLUMN IF NOT EXISTS faction      TEXT;
ALTER TABLE models ADD COLUMN IF NOT EXISTS figures      INT NOT NULL DEFAULT 1;
ALTER TABLE models ADD COLUMN IF NOT EXISTS figures_done INT NOT NULL DEFAULT 0;

ALTER TABLE models DROP CONSTRAINT IF EXISTS models_hobby_check;
ALTER TABLE models ADD CONSTRAINT models_hobby_check
    CHECK (hobby IN ('Scale model', 'Warhammer', 'Gundam'));

-- Each hobby's build steps, in order. The stage is the last step done (NULL = none yet).
ALTER TABLE models DROP CONSTRAINT IF EXISTS models_stage_check;
ALTER TABLE models ADD CONSTRAINT models_stage_check CHECK (stage IS NULL
    OR (hobby = 'Scale model' AND stage IN ('Built', 'Primed', 'Painted', 'Decals', 'Weathered'))
    OR (hobby = 'Warhammer'   AND stage IN ('Built', 'Primed', 'Painted', 'Based'))
    OR (hobby = 'Gundam'      AND stage IN ('Built', 'Panel lined', 'Decals', 'Top coat')));

ALTER TABLE models DROP CONSTRAINT IF EXISTS models_figures_check;
ALTER TABLE models ADD CONSTRAINT models_figures_check
    CHECK (figures >= 1 AND figures_done >= 0 AND figures_done <= figures);

COMMIT;
