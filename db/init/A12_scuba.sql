-- Scuba diving (2026-11-18), a hobby module (api/app/scuba*.py, divemath.py, diveimport.py; web/src/modules/scuba). Idempotent.
--   scuba_settings      one row: your planning defaults (gas, tank, breathing rate, gradient factors, ppO2 limit), the
--                       dives you logged before the app (so numbering carries on), medical / insurance dates
--   scuba_sites         dive sites: by hand, or from OpenStreetMap (sport=scuba_diving) - reef, wreck, wall...
--   scuba_trips         a dive trip / liveaboard / dive weekend that groups dives
--   scuba_dives         the logbook: one row per dive (depth, time, gas, tank pressures, conditions, buddy, rating) and
--                       the dive computer's profile (samples, from a UDDF / Subsurface file)
--   scuba_sightings     what you saw on a dive (the life list)
--   scuba_certs         certification cards (agency, level, number, date, instructor)
--   scuba_gear_service  servicing of scuba gear (the shared gear table, hobby 'scuba'): regulator service, tank
--                       visual inspection / hydro test, and when the next one is due
BEGIN;

CREATE TABLE IF NOT EXISTS scuba_settings (
    id               integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    gas_o2           smallint NOT NULL DEFAULT 21 CHECK (gas_o2 BETWEEN 21 AND 100),
    tank_l           numeric(4, 1) NOT NULL DEFAULT 12 CHECK (tank_l BETWEEN 1 AND 30),
    start_bar        smallint NOT NULL DEFAULT 200 CHECK (start_bar BETWEEN 50 AND 300),
    sac_l_min        numeric(4, 1) NOT NULL DEFAULT 20 CHECK (sac_l_min BETWEEN 5 AND 60),
    gf_low           smallint NOT NULL DEFAULT 40 CHECK (gf_low BETWEEN 10 AND 100),
    gf_high          smallint NOT NULL DEFAULT 85 CHECK (gf_high BETWEEN 10 AND 100),
    ppo2_max         numeric(3, 2) NOT NULL DEFAULT 1.40 CHECK (ppo2_max BETWEEN 1.0 AND 1.6),
    dives_before     integer NOT NULL DEFAULT 0 CHECK (dives_before >= 0),
    minutes_before   integer NOT NULL DEFAULT 0 CHECK (minutes_before >= 0),
    medical_due      date,
    insurance_until  date,
    home_lat         double precision CHECK (home_lat BETWEEN -90 AND 90),
    home_lon         double precision CHECK (home_lon BETWEEN -180 AND 180),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT scuba_settings_gf_order CHECK (gf_low <= gf_high)
);
INSERT INTO scuba_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS scuba_sites (
    site_id     serial PRIMARY KEY,
    name        text NOT NULL CHECK (btrim(name) <> ''),
    place       text,                                   -- area / region ("Moreton Island", "Great Barrier Reef")
    country     text,
    lat         double precision CHECK (lat BETWEEN -90 AND 90),
    lon         double precision CHECK (lon BETWEEN -180 AND 180),
    kind        text,                                   -- Reef / Wreck / Wall / Drift / Pinnacle / Cave / Muck / Lake...
    entry       text CHECK (entry IN ('shore', 'boat')),
    depth_min   numeric(5, 1) CHECK (depth_min BETWEEN 0 AND 350),
    depth_max   numeric(5, 1) CHECK (depth_max BETWEEN 0 AND 350),
    osm         text UNIQUE CHECK (osm ~ '^(node|way|relation)/[0-9]+$'),
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scuba_trips (
    trip_id     serial PRIMARY KEY,
    name        text NOT NULL CHECK (btrim(name) <> ''),
    place       text,
    operator    text,                                   -- the dive centre / boat / liveaboard
    start_on    date NOT NULL,
    end_on      date,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT scuba_trips_dates_fit CHECK (end_on IS NULL OR end_on >= start_on)
);

CREATE TABLE IF NOT EXISTS scuba_dives (
    dive_id      serial PRIMARY KEY,
    dive_no      integer UNIQUE CHECK (dive_no > 0),    -- your logbook number (dives_before + its place, unless typed)
    dived_on     date NOT NULL,
    time_in      time,
    site_id      integer REFERENCES scuba_sites ON DELETE SET NULL,
    trip_id      integer REFERENCES scuba_trips ON DELETE SET NULL,
    max_depth    numeric(5, 1) CHECK (max_depth BETWEEN 0 AND 350),
    avg_depth    numeric(5, 1) CHECK (avg_depth BETWEEN 0 AND 350),
    minutes      smallint CHECK (minutes BETWEEN 1 AND 1440),   -- the dive's length (in to out)
    water_temp   numeric(4, 1) CHECK (water_temp BETWEEN -3 AND 40),
    air_temp     numeric(4, 1) CHECK (air_temp BETWEEN -30 AND 55),
    visibility_m smallint CHECK (visibility_m BETWEEN 0 AND 100),
    current      text CHECK (current IN ('none', 'light', 'moderate', 'strong')),
    entry        text CHECK (entry IN ('shore', 'boat')),
    tags         text[] NOT NULL DEFAULT '{}',          -- night, drift, deep, wreck, training, photo...
    gas_o2       smallint NOT NULL DEFAULT 21 CHECK (gas_o2 BETWEEN 21 AND 100),
    tank_l       numeric(4, 1) CHECK (tank_l BETWEEN 1 AND 30),
    start_bar    smallint CHECK (start_bar BETWEEN 0 AND 350),
    end_bar      smallint CHECK (end_bar BETWEEN 0 AND 350),
    weight_kg    numeric(4, 1) CHECK (weight_kg BETWEEN 0 AND 40),
    suit         text,                                  -- "5 mm wetsuit", "3 mm shorty", "drysuit"
    buddy        text,
    guide        text,
    operator     text,
    rating       smallint CHECK (rating BETWEEN 1 AND 5),
    notes        text,
    computer     text,                                  -- the dive computer it came from
    import_key   text UNIQUE,                           -- computer + start time: the same dive imported twice is skipped
    samples      jsonb,                                 -- the profile: [[seconds, depth_m, temp_c or null], ...]
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT scuba_dives_avg_fit CHECK (avg_depth IS NULL OR max_depth IS NULL OR avg_depth <= max_depth),
    CONSTRAINT scuba_dives_bar_fit CHECK (end_bar IS NULL OR start_bar IS NULL OR end_bar <= start_bar)
);
CREATE INDEX IF NOT EXISTS scuba_dives_on_idx ON scuba_dives (dived_on, time_in);
CREATE INDEX IF NOT EXISTS scuba_dives_site_idx ON scuba_dives (site_id);

CREATE TABLE IF NOT EXISTS scuba_sightings (
    dive_id     integer NOT NULL REFERENCES scuba_dives ON DELETE CASCADE,
    species     text NOT NULL CHECK (btrim(species) <> ''),
    how_many    smallint CHECK (how_many > 0),
    notes       text,
    PRIMARY KEY (dive_id, species)
);

CREATE TABLE IF NOT EXISTS scuba_certs (
    cert_id       serial PRIMARY KEY,
    agency        text NOT NULL CHECK (btrim(agency) <> ''),   -- PADI, SSI, NAUI, SDI, RAID...
    name          text NOT NULL CHECK (btrim(name) <> ''),     -- Open Water Diver, Advanced, Nitrox, Rescue...
    cert_no       text,
    certified_on  date,
    instructor    text,
    expires_on    date,                                        -- first aid / O2 provider cards expire
    notes         text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scuba_gear_service (
    service_id  serial PRIMARY KEY,
    gear_id     integer NOT NULL REFERENCES gear ON DELETE CASCADE,
    done_on     date NOT NULL,
    what        text NOT NULL CHECK (btrim(what) <> ''),       -- Annual service, Visual inspection, Hydro test...
    done_by     text,
    cost        numeric(8, 2) CHECK (cost >= 0),
    next_due    date,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT scuba_gear_service_due_fit CHECK (next_due IS NULL OR next_due >= done_on)
);
CREATE INDEX IF NOT EXISTS scuba_gear_service_gear_idx ON scuba_gear_service (gear_id, done_on);

-- Scuba gear on the shared gear pages (keep in step with db.GEAR_HOBBIES)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'gear'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%scuba%') THEN
        ALTER TABLE gear DROP CONSTRAINT IF EXISTS gear_hobby_check;
        ALTER TABLE gear ADD CONSTRAINT gear_hobby_check CHECK (hobby IN ('volleyball', 'hiking', 'shooting', 'scuba'));
    END IF;
END $$;

-- Calendar events for the Scuba hobby too (keep in step with db.MODULE_IDS): booked dives and trips.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%scuba%') THEN
        ALTER TABLE calendar_events DROP CONSTRAINT IF EXISTS calendar_events_hobby_check;
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_hobby_check
            CHECK (hobby IN ('models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'car', 'travel', 'shooting',
                             'hiking', 'gardening', 'vinyl', 'sudoku', 'golf', 'language', 'scuba'));
    END IF;
END $$;

COMMIT;
