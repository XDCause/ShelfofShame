-- Gear you'd like to buy: the condition 'Wanted' (not counted as in use). Idempotent: the old
-- condition CHECK is found by its definition and replaced.
DO $$
DECLARE c TEXT;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'gear'::regclass AND contype = 'c'
               AND pg_get_constraintdef(oid) LIKE '%Needs replacing%' AND pg_get_constraintdef(oid) NOT LIKE '%Wanted%'
    LOOP
        EXECUTE format('ALTER TABLE gear DROP CONSTRAINT %I', c);
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'gear'::regclass AND conname = 'gear_condition_check') THEN
        ALTER TABLE gear ADD CONSTRAINT gear_condition_check
            CHECK (condition IN ('Wanted', 'New', 'Good', 'Worn', 'Needs replacing', 'Retired'));
    END IF;
END $$;
