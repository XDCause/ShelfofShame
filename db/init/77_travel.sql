-- Travel (2026-10-20): trips - planned, happening and remembered - with their bookings, a day-by-day plan, money
-- (budget vs spent, other currencies in AUD), packing, places (a map and a bucket list), a journal and photos.
--   travel_settings   passport expiry (warned about before overseas trips)
--   trips             a trip: dates, kind, hobby it's for, countries, budget, rating, what you'll remember
--   trip_places       places: a trip's stops (in order - a road trip's route) and the bucket list (no trip);
--                     Want / Planned / Been, with where they are on the map
--   travel_countries  countries you've been to (before the app, too) or want to go to
--   trip_bookings     flights, stays, cars, tours...: when, from / to, reference, cost (in its currency + the rate)
--   trip_plan         the day-by-day plan; no day = "before you go" (visa, insurance...)
--   trip_expenses     money spent there (in its currency + the rate to AUD at the time)
--   trip_packing      the trip's packing list (from packing_lists, your gear, or typed)
--   packing_lists     reusable packing lists (a few to start with; yours too)
--   trip_entries      the journal: a note per day; trip_photos: photos (on the map when they carry GPS)
-- Rates are AUD for one unit of the currency (JPY 0.0090), so AUD = amount * rate. Idempotent.
BEGIN;

CREATE TABLE IF NOT EXISTS travel_settings (
    id               integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    passport_expires date,
    updated_at       timestamptz NOT NULL DEFAULT now()
);
INSERT INTO travel_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS trips (
    trip_id       serial PRIMARY KEY,
    name          text NOT NULL CHECK (btrim(name) <> ''),
    kind          text NOT NULL DEFAULT 'Domestic' CHECK (kind IN ('Overseas', 'Domestic', 'Road trip', 'Camping')),
    status        text NOT NULL DEFAULT 'Planned' CHECK (status IN ('Idea', 'Planned', 'Cancelled')),
    hobby         text,                                   -- a hobby trip: hiking, shooting, volleyball...
    start_date    date,
    end_date      date CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
    destination   text,
    countries     text[] NOT NULL DEFAULT '{}',           -- ISO codes: JP, NZ
    budget        numeric(12, 2) CHECK (budget >= 0),     -- AUD
    rates         jsonb NOT NULL DEFAULT '{}',            -- rates you set: {"JPY": 0.0091}
    rating        smallint CHECK (rating BETWEEN 1 AND 5),
    highlights    text,                                   -- what you'll remember
    notes         text,
    photo         bytea,
    photo_type    text,
    photo_updated timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trips_start_idx ON trips (start_date);

CREATE TABLE IF NOT EXISTS trip_places (
    place_id     serial PRIMARY KEY,
    trip_id      integer REFERENCES trips ON DELETE CASCADE,  -- none = the bucket list / places from before
    name         text NOT NULL CHECK (btrim(name) <> ''),
    kind         text NOT NULL DEFAULT 'City' CHECK (kind IN ('City', 'Sight', 'Food', 'Stay', 'Nature', 'Beach',
                                                               'Campsite', 'Activity', 'Other')),
    status       text NOT NULL DEFAULT 'Want' CHECK (status IN ('Want', 'Planned', 'Been')),
    country      text CHECK (country ~ '^[A-Z]{2}$'),
    region       text,
    lat          numeric(9, 6) CHECK (lat BETWEEN -90 AND 90),
    lon          numeric(9, 6) CHECK (lon BETWEEN -180 AND 180),
    stop_order   integer,                                  -- a trip's stops in order (the route)
    visit_on     date,
    rating       smallint CHECK (rating BETWEEN 1 AND 5),
    link         text,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_places_trip_idx ON trip_places (trip_id);

CREATE TABLE IF NOT EXISTS travel_countries (
    code        text PRIMARY KEY CHECK (code ~ '^[A-Z]{2}$'),
    status      text NOT NULL DEFAULT 'Been' CHECK (status IN ('Been', 'Want')),
    first_year  integer CHECK (first_year BETWEEN 1900 AND 2100),
    notes       text
);

CREATE TABLE IF NOT EXISTS trip_bookings (
    booking_id  serial PRIMARY KEY,
    trip_id     integer NOT NULL REFERENCES trips ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('Flight', 'Stay', 'Car hire', 'Train', 'Bus', 'Ferry', 'Tour', 'Event',
                                              'Campsite', 'Insurance', 'Other')),
    title       text NOT NULL CHECK (btrim(title) <> ''),
    provider    text,
    reference   text,                                       -- booking / confirmation number
    starts_at   timestamp,                                  -- local time where it happens
    ends_at     timestamp CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at),
    from_place  text,
    to_place    text,
    address     text,
    cost        numeric(12, 2) CHECK (cost >= 0),
    currency    text NOT NULL DEFAULT 'AUD' CHECK (currency ~ '^[A-Z]{3}$'),
    rate        numeric(14, 8) NOT NULL DEFAULT 1 CHECK (rate > 0),
    paid        boolean NOT NULL DEFAULT false,
    link        text,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_bookings_trip_idx ON trip_bookings (trip_id);

CREATE TABLE IF NOT EXISTS trip_plan (
    item_id    serial PRIMARY KEY,
    trip_id    integer NOT NULL REFERENCES trips ON DELETE CASCADE,
    day        date,                                        -- none = before you go
    at         time,
    title      text NOT NULL CHECK (btrim(title) <> ''),
    place_id   integer REFERENCES trip_places ON DELETE SET NULL,
    notes      text,
    done       boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_plan_trip_idx ON trip_plan (trip_id);

CREATE TABLE IF NOT EXISTS trip_expenses (
    expense_id serial PRIMARY KEY,
    trip_id    integer NOT NULL REFERENCES trips ON DELETE CASCADE,
    spent_on   date NOT NULL DEFAULT current_date,
    category   text NOT NULL DEFAULT 'Food' CHECK (category IN ('Stay', 'Transport', 'Food', 'Activities', 'Shopping', 'Other')),
    what       text,
    amount     numeric(12, 2) NOT NULL CHECK (amount >= 0),
    currency   text NOT NULL DEFAULT 'AUD' CHECK (currency ~ '^[A-Z]{3}$'),
    rate       numeric(14, 8) NOT NULL DEFAULT 1 CHECK (rate > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_expenses_trip_idx ON trip_expenses (trip_id);

CREATE TABLE IF NOT EXISTS packing_lists (
    list_id    serial PRIMARY KEY,
    name       text NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    items      jsonb NOT NULL DEFAULT '[]',                 -- [{"name": "Passport", "grp": "Documents"}]
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trip_packing (
    item_id  serial PRIMARY KEY,
    trip_id  integer NOT NULL REFERENCES trips ON DELETE CASCADE,
    name     text NOT NULL CHECK (btrim(name) <> ''),
    grp      text NOT NULL DEFAULT 'Other' CHECK (grp IN ('Documents', 'Clothes', 'Toiletries', 'Health', 'Tech', 'Gear', 'Other')),
    qty      integer NOT NULL DEFAULT 1 CHECK (qty BETWEEN 1 AND 999),
    packed   boolean NOT NULL DEFAULT false,
    gear_id  integer REFERENCES gear ON DELETE SET NULL,
    UNIQUE (trip_id, name)
);

CREATE TABLE IF NOT EXISTS trip_entries (
    entry_id   serial PRIMARY KEY,
    trip_id    integer NOT NULL REFERENCES trips ON DELETE CASCADE,
    day        date NOT NULL,
    text       text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (trip_id, day)
);

CREATE TABLE IF NOT EXISTS trip_photos (
    photo_id   serial PRIMARY KEY,
    trip_id    integer NOT NULL REFERENCES trips ON DELETE CASCADE,
    day        date,
    taken_at   timestamptz,
    lat        numeric(9, 6),
    lon        numeric(9, 6),
    caption    text,
    image      bytea NOT NULL,
    image_type text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_photos_trip_idx ON trip_photos (trip_id);

-- A few packing lists to start from (edit or delete them; add your own from a trip's list).
INSERT INTO packing_lists (name, items) VALUES
  ('Essentials', '[{"name":"Phone","grp":"Tech"},{"name":"Phone charger","grp":"Tech"},{"name":"Power bank","grp":"Tech"},
    {"name":"Earphones","grp":"Tech"},{"name":"Wallet and cards","grp":"Documents"},{"name":"Keys","grp":"Documents"},
    {"name":"Driver licence","grp":"Documents"},{"name":"Toothbrush and toothpaste","grp":"Toiletries"},
    {"name":"Deodorant","grp":"Toiletries"},{"name":"Sunscreen","grp":"Toiletries"},{"name":"Medications","grp":"Health"},
    {"name":"Underwear","grp":"Clothes"},{"name":"Socks","grp":"Clothes"},{"name":"T-shirts","grp":"Clothes"},
    {"name":"Shorts / pants","grp":"Clothes"},{"name":"Sleepwear","grp":"Clothes"},{"name":"Jacket","grp":"Clothes"}]'),
  ('Overseas', '[{"name":"Passport","grp":"Documents"},{"name":"Visa / travel authority","grp":"Documents"},
    {"name":"Travel insurance details","grp":"Documents"},{"name":"Bookings saved offline","grp":"Documents"},
    {"name":"Card with no foreign fees","grp":"Documents"},{"name":"Some local cash","grp":"Documents"},
    {"name":"Power adapter","grp":"Tech"},{"name":"eSIM / SIM card","grp":"Tech"},
    {"name":"Prescriptions and doctor''s letter","grp":"Health"},{"name":"Pen for arrival forms","grp":"Other"}]'),
  ('Beach', '[{"name":"Swimmers","grp":"Clothes"},{"name":"Rashie","grp":"Clothes"},{"name":"Hat","grp":"Clothes"},
    {"name":"Thongs","grp":"Clothes"},{"name":"Beach towel","grp":"Other"},{"name":"Sunglasses","grp":"Other"},
    {"name":"After-sun","grp":"Toiletries"}]'),
  ('Cold weather', '[{"name":"Thermals","grp":"Clothes"},{"name":"Beanie","grp":"Clothes"},{"name":"Gloves","grp":"Clothes"},
    {"name":"Warm jacket","grp":"Clothes"},{"name":"Scarf","grp":"Clothes"},{"name":"Lip balm","grp":"Toiletries"}]'),
  ('Camping', '[{"name":"Tent","grp":"Gear"},{"name":"Sleeping bag","grp":"Gear"},{"name":"Sleeping mat","grp":"Gear"},
    {"name":"Pillow","grp":"Gear"},{"name":"Head torch","grp":"Gear"},{"name":"Camp chairs","grp":"Gear"},
    {"name":"Stove and gas","grp":"Gear"},{"name":"Cookware and utensils","grp":"Gear"},{"name":"Esky","grp":"Gear"},
    {"name":"Water containers","grp":"Gear"},{"name":"Rubbish bags","grp":"Other"},{"name":"Toilet paper","grp":"Toiletries"},
    {"name":"Insect repellent","grp":"Health"},{"name":"First aid kit","grp":"Health"}]'),
  ('Road trip', '[{"name":"Driver licence","grp":"Documents"},{"name":"Roadside assistance details","grp":"Documents"},
    {"name":"Phone mount","grp":"Tech"},{"name":"Car charger","grp":"Tech"},{"name":"Offline maps","grp":"Tech"},
    {"name":"Snacks","grp":"Other"},{"name":"Water","grp":"Other"},{"name":"Tyres and spare checked","grp":"Other"}]'),
  ('Hiking trip', '[{"name":"Daypack","grp":"Gear"},{"name":"Hiking boots","grp":"Gear"},{"name":"Water bottles / bladder","grp":"Gear"},
    {"name":"Rain jacket","grp":"Clothes"},{"name":"Head torch","grp":"Gear"},{"name":"Trail snacks","grp":"Other"},
    {"name":"Offline map of the track","grp":"Tech"},{"name":"First aid kit","grp":"Health"}]'),
  ('Shooting trip', '[{"name":"Firearms licence","grp":"Documents"},{"name":"Rifle, cased and locked","grp":"Gear"},
    {"name":"Ammunition, stored apart","grp":"Gear"},{"name":"Eye protection","grp":"Gear"},{"name":"Ear protection","grp":"Gear"},
    {"name":"Spotting scope","grp":"Gear"},{"name":"Targets","grp":"Gear"},{"name":"Range bag","grp":"Gear"},
    {"name":"Cleaning kit","grp":"Gear"}]'),
  ('Volleyball tournament', '[{"name":"Court shoes","grp":"Gear"},{"name":"Knee pads","grp":"Gear"},{"name":"Team uniform","grp":"Clothes"},
    {"name":"Ball","grp":"Gear"},{"name":"Water bottle","grp":"Gear"},{"name":"Strapping tape","grp":"Health"},
    {"name":"Snacks","grp":"Other"}]')
ON CONFLICT (name) DO NOTHING;

COMMIT;
