-- Calendar events can belong to any hobby (the first list only had the first three). The old
-- CHECK is found by its definition and replaced (idempotent). Keep in step with db.MODULE_IDS.
DO $$
DECLARE c TEXT;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'calendar_events'::regclass AND contype = 'c'
               AND pg_get_constraintdef(oid) LIKE '%boardgames%' AND pg_get_constraintdef(oid) NOT LIKE '%reading%'
    LOOP
        EXECUTE format('ALTER TABLE calendar_events DROP CONSTRAINT %I', c);
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND conname = 'calendar_events_hobby_check') THEN
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_hobby_check
            CHECK (hobby IN ('models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'car'));
    END IF;
END $$;
