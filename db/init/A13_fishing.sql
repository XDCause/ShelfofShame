-- Fishing (2026-11-18), a hobby module (api/app/fishing*.py, solunar.py; web/src/modules/fishing). Idempotent.
--   fishing_settings  one row: home position, the Stocked Impoundment Permit and boat registration expiry dates
--   fishing_spots     your spots (kept private - this is the user's own database): beach, jetty, river, dam, reef...
--                     typed, or a boat ramp / fishing spot from OpenStreetMap
--   fishing_species   the species list with the rules YOU typed (min / max size, possession limit, closed season):
--                     seeded with names only - the rules change (Queensland changed them in 2026), so no numbers are
--                     shipped; the app links to the official page instead
--   fishing_lures     your lures / baits / flies (the tackle box), so catches can say what worked
--   fishing_trips     a session on the water: when, where, from shore / boat / kayak, with whom, the conditions then
--   fishing_catches   each fish: species, length, weight, kept / released, lure or bait, time and place, photo(s)
--   fishing_photos    catch photos (shrunk in the browser, like hike photos)
-- Rods and reels go on the shared gear pages (gear.hobby 'fishing').
BEGIN;

CREATE TABLE IF NOT EXISTS fishing_settings (
    id               integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    home_lat         double precision CHECK (home_lat BETWEEN -90 AND 90),
    home_lon         double precision CHECK (home_lon BETWEEN -180 AND 180),
    sip_until        date,                                  -- Stocked Impoundment Permit (fishing stocked dams, Qld)
    boat_rego_until  date,
    rules_url        text NOT NULL DEFAULT 'https://www.qld.gov.au/recreation/activities/boating-fishing/rec-fishing/rules',
    updated_at       timestamptz NOT NULL DEFAULT now()
);
INSERT INTO fishing_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS fishing_spots (
    spot_id     serial PRIMARY KEY,
    name        text NOT NULL CHECK (btrim(name) <> ''),
    place       text,                                   -- area ("Moreton Bay", "Lake Somerset")
    water       text CHECK (water IN ('salt', 'estuary', 'fresh')),
    kind        text,                                   -- Beach / Rocks / Jetty / Boat ramp / River / Creek / Dam / Reef / Offshore...
    lat         double precision CHECK (lat BETWEEN -90 AND 90),
    lon         double precision CHECK (lon BETWEEN -180 AND 180),
    sip_needed  boolean NOT NULL DEFAULT false,         -- a stocked impoundment: the permit is needed
    osm         text UNIQUE CHECK (osm ~ '^(node|way|relation)/[0-9]+$'),
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fishing_species (
    species_id   serial PRIMARY KEY,
    name         text NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    sci_name     text,
    water        text CHECK (water IN ('salt', 'estuary', 'fresh', 'any')),
    min_cm       numeric(5, 1) CHECK (min_cm > 0),        -- the rules you typed (null = none known / not set)
    max_cm       numeric(5, 1) CHECK (max_cm > 0),
    bag          smallint CHECK (bag >= 0),               -- possession limit per person (0 = no take)
    closed_from  text CHECK (closed_from ~ '^[01][0-9]-[0-3][0-9]$'),   -- 'MM-DD', a yearly closed season
    closed_to    text CHECK (closed_to ~ '^[01][0-9]-[0-3][0-9]$'),
    no_take      boolean NOT NULL DEFAULT false,
    rules_checked_on date,                                -- when you last checked them against the official page
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fishing_species_size_fit CHECK (min_cm IS NULL OR max_cm IS NULL OR min_cm <= max_cm),
    CONSTRAINT fishing_species_closed_fit CHECK ((closed_from IS NULL) = (closed_to IS NULL))
);
-- Common South-East Queensland catches, names only (no rules - type them from the official page).
INSERT INTO fishing_species (name, sci_name, water) VALUES
    ('Dusky flathead', 'Platycephalus fuscus', 'estuary'), ('Yellowfin bream', 'Acanthopagrus australis', 'estuary'),
    ('Summer whiting', 'Sillago ciliata', 'estuary'), ('Snapper', 'Chrysophrys auratus', 'salt'),
    ('Tailor', 'Pomatomus saltatrix', 'salt'), ('Mangrove jack', 'Lutjanus argentimaculatus', 'estuary'),
    ('Grass emperor', 'Lethrinus laticaudis', 'salt'), ('Moses perch', 'Lutjanus russellii', 'salt'),
    ('Spanish mackerel', 'Scomberomorus commerson', 'salt'), ('Spotted mackerel', 'Scomberomorus munroi', 'salt'),
    ('Mulloway', 'Argyrosomus japonicus', 'salt'), ('Trevally', NULL, 'salt'), ('Luderick', 'Girella tricuspidata', 'estuary'),
    ('Barramundi', 'Lates calcarifer', 'any'), ('Australian bass', 'Percalates novemaculeata', 'fresh'),
    ('Golden perch', 'Macquaria ambigua', 'fresh'), ('Murray cod', 'Maccullochella peelii', 'fresh'),
    ('Saratoga', 'Scleropages leichardti', 'fresh'), ('Silver perch', 'Bidyanus bidyanus', 'fresh'),
    ('Mud crab', 'Scylla serrata', 'estuary'), ('Sand crab', 'Portunus armatus', 'salt'),
    ('Squid', NULL, 'salt'), ('Tilapia (noxious - do not release)', 'Oreochromis mossambicus', 'fresh')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS fishing_lures (
    lure_id     serial PRIMARY KEY,
    name        text NOT NULL CHECK (btrim(name) <> ''),   -- "Zerek Prawn Shrimp 3.5\"", "Live yabby", "Pilchard"
    kind        text NOT NULL DEFAULT 'lure' CHECK (kind IN ('lure', 'soft plastic', 'bait', 'live bait', 'fly', 'jig', 'other')),
    brand       text,
    colour      text,
    size        text,
    qty         smallint CHECK (qty >= 0),
    retired     boolean NOT NULL DEFAULT false,            -- lost to a snag / used up: kept for the stats
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fishing_trips (
    trip_id     serial PRIMARY KEY,
    started_at  timestamptz NOT NULL,
    ended_at    timestamptz,
    spot_id     integer REFERENCES fishing_spots ON DELETE SET NULL,
    platform    text CHECK (platform IN ('shore', 'jetty', 'boat', 'kayak', 'wading')),
    target      text,                                    -- what you were after
    companions  text,
    conditions  jsonb,                                   -- a snapshot at save: {moon_phase, moon_pct, tide [...], wind_kmh, pressure_hpa, sst...}
    rating      smallint CHECK (rating BETWEEN 1 AND 5),
    notes       text,
    client_key  text UNIQUE,                             -- made by the phone for a trip started on the water: resending is safe
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fishing_trips_end_fit CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX IF NOT EXISTS fishing_trips_start_idx ON fishing_trips (started_at);
CREATE INDEX IF NOT EXISTS fishing_trips_spot_idx ON fishing_trips (spot_id);

CREATE TABLE IF NOT EXISTS fishing_catches (
    catch_id    serial PRIMARY KEY,
    trip_id     integer NOT NULL REFERENCES fishing_trips ON DELETE CASCADE,
    species_id  integer REFERENCES fishing_species ON DELETE SET NULL,
    species     text,                                    -- typed when it isn't on the list (or not sure)
    caught_at   timestamptz,
    length_cm   numeric(5, 1) CHECK (length_cm > 0 AND length_cm < 1000),
    weight_kg   numeric(6, 2) CHECK (weight_kg > 0 AND weight_kg < 1000),
    fate        text NOT NULL DEFAULT 'released' CHECK (fate IN ('released', 'kept', 'tagged', 'died')),
    lure_id     integer REFERENCES fishing_lures ON DELETE SET NULL,
    bait        text,                                    -- typed when it isn't in the tackle box
    method      text,                                    -- Casting / Trolling / Bottom bashing / Drifting / Fly / Jigging...
    depth_m     numeric(5, 1) CHECK (depth_m BETWEEN 0 AND 2000),
    lat         double precision CHECK (lat BETWEEN -90 AND 90),
    lon         double precision CHECK (lon BETWEEN -180 AND 180),
    client_key  text UNIQUE,                             -- made by the phone for a catch logged on the water: resending is safe
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fishing_catches_what_fit CHECK (species_id IS NOT NULL OR btrim(coalesce(species, '')) <> '')
);
CREATE INDEX IF NOT EXISTS fishing_catches_trip_idx ON fishing_catches (trip_id);
CREATE INDEX IF NOT EXISTS fishing_catches_species_idx ON fishing_catches (species_id);

CREATE TABLE IF NOT EXISTS fishing_photos (
    photo_id    serial PRIMARY KEY,
    catch_id    integer NOT NULL REFERENCES fishing_catches ON DELETE CASCADE,
    image       bytea NOT NULL,
    image_type  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fishing_photos_catch_idx ON fishing_photos (catch_id);

-- Rods and reels on the shared gear pages (keep in step with db.GEAR_HOBBIES)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'gear'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%fishing%') THEN
        ALTER TABLE gear DROP CONSTRAINT IF EXISTS gear_hobby_check;
        ALTER TABLE gear ADD CONSTRAINT gear_hobby_check CHECK (hobby IN ('volleyball', 'hiking', 'shooting', 'scuba', 'fishing'));
    END IF;
END $$;

-- Calendar events for the Fishing hobby too (keep in step with db.MODULE_IDS)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%fishing%') THEN
        ALTER TABLE calendar_events DROP CONSTRAINT IF EXISTS calendar_events_hobby_check;
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_hobby_check
            CHECK (hobby IN ('models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'car', 'travel', 'shooting',
                             'hiking', 'gardening', 'vinyl', 'sudoku', 'golf', 'language', 'scuba', 'fishing'));
    END IF;
END $$;

COMMIT;
