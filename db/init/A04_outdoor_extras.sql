-- Outdoor extras (shooting + gardening). Idempotent.
--   shooting_sessions.pressure_hpa / humidity_pct   the day's air, beside temp_c: the ballistic solver turns the three into air
--                                                   density and density altitude
--   garden_spaces.sun_morning / sun_midday / sun_afternoon   hours of direct sun you measured in each part of the day
--                                                   (morning 6-10, midday 10-14, afternoon 14-18: up to 4 each); when any is
--                                                   set, the API keeps sun_hours (what the guide's "too little sun" checks read)
--                                                   equal to their sum
BEGIN;

ALTER TABLE shooting_sessions ADD COLUMN IF NOT EXISTS pressure_hpa numeric(5, 1);
ALTER TABLE shooting_sessions ADD COLUMN IF NOT EXISTS humidity_pct smallint;

ALTER TABLE garden_spaces ADD COLUMN IF NOT EXISTS sun_morning numeric(2, 1);
ALTER TABLE garden_spaces ADD COLUMN IF NOT EXISTS sun_midday numeric(2, 1);
ALTER TABLE garden_spaces ADD COLUMN IF NOT EXISTS sun_afternoon numeric(2, 1);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'shooting_sessions_air_check') THEN
        ALTER TABLE shooting_sessions ADD CONSTRAINT shooting_sessions_air_check
            CHECK ((pressure_hpa IS NULL OR pressure_hpa BETWEEN 300 AND 1100) AND (humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'garden_spaces_sun_parts_check') THEN
        ALTER TABLE garden_spaces ADD CONSTRAINT garden_spaces_sun_parts_check
            CHECK ((sun_morning IS NULL OR sun_morning BETWEEN 0 AND 4) AND (sun_midday IS NULL OR sun_midday BETWEEN 0 AND 4)
                   AND (sun_afternoon IS NULL OR sun_afternoon BETWEEN 0 AND 4));
    END IF;
END $$;

COMMIT;
