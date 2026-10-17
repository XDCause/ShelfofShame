-- Calendar events for the Gardening hobby too (keep in step with db.MODULE_IDS). Idempotent.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%gardening%') THEN
        ALTER TABLE calendar_events DROP CONSTRAINT IF EXISTS calendar_events_hobby_check;
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_hobby_check
            CHECK (hobby IN ('models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'car', 'travel', 'shooting',
                             'hiking', 'gardening'));
    END IF;
END $$;
