-- The calendar grows (2026-10-21, user: "do them all" from a scan of Google / Apple Calendar, Fantastical, Notion
-- Calendar, Sunsama...):
--   repeats       also monthly (the same date), monthly_nth (the 2nd Saturday...), yearly (birthdays), weekdays
--                 (chosen days: repeat_days, 0 = Monday); weekly / weekdays every repeat_every weeks
--   countdown     "Regional comp in 12 days" on Home and the event
--   lat / lon     where it is (weather on the day; the place's name stays in location)
--   checklist     what to bring: [{"text": "Knee pads", "done": false}]
--   to-dos        plan_on / plan_time / plan_minutes: when you'll do it (time-blocking on the calendar)
-- Idempotent. The repeats CHECK is found by its definition and replaced (like 53_calendar_hobbies.sql).

DO $$
DECLARE c TEXT;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'calendar_events'::regclass AND contype = 'c'
               AND pg_get_constraintdef(oid) LIKE '%fortnightly%' AND pg_get_constraintdef(oid) NOT LIKE '%yearly%'
    LOOP
        EXECUTE format('ALTER TABLE calendar_events DROP CONSTRAINT %I', c);
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND conname = 'calendar_events_repeats_check2') THEN
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_repeats_check2
            CHECK (repeats IN ('never', 'weekly', 'fortnightly', 'monthly', 'monthly_nth', 'yearly', 'weekdays'));
    END IF;
END $$;

ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS repeat_every INT NOT NULL DEFAULT 1;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS repeat_days INT[];
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS countdown BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS lat NUMERIC(8, 5);
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS lon NUMERIC(8, 5);
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS checklist JSONB NOT NULL DEFAULT '[]';

DO $$ BEGIN
    ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_every_check CHECK (repeat_every BETWEEN 1 AND 12);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_days_check
        CHECK (repeat_days IS NULL OR (repeat_days <@ ARRAY[0, 1, 2, 3, 4, 5, 6] AND cardinality(repeat_days) BETWEEN 1 AND 7));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_place_check
        CHECK ((lat IS NULL) = (lon IS NULL) AND (lat IS NULL OR (lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180)));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

ALTER TABLE todos ADD COLUMN IF NOT EXISTS plan_on DATE;
ALTER TABLE todos ADD COLUMN IF NOT EXISTS plan_time TIME;
ALTER TABLE todos ADD COLUMN IF NOT EXISTS plan_minutes INT;
DO $$ BEGIN
    ALTER TABLE todos ADD CONSTRAINT todos_plan_check
        CHECK ((plan_time IS NULL OR plan_on IS NOT NULL) AND (plan_minutes IS NULL OR plan_minutes BETWEEN 5 AND 720));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
