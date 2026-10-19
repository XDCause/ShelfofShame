-- Precision shooting (2026-10-19): smallbore / rimfire and long-range rifle, factory ammunition. Idempotent.
--   shooting_settings  one row: licence expiry, how many club shoots a year you need, the default cleaning interval
--   shooting_ranges    where you shoot: club ranges count toward the yearly attendance
--   rifles             each rifle and its scope (MOA or MIL, click value), zero, rounds before you started logging,
--                      how often to clean - no serial or registration numbers (the app has no login)
--   ammo               factory ammunition: bullet, BC, box velocity, lot; rounds bought (left = bought - fired)
--   shooting_sessions  a day at the range: rifle, ammo, range, kind, conditions; rounds fired
--   shooting_groups    each group / string / card in a session: distance, shots, size, where it hit, what was
--                      dialled, score, chronograph velocities, and whether it confirms your DOPE at that distance
--   rifle_logs         cleaning, zeroing, scope changes, repairs - at the rifle's round count then
--   dope_rows          DOPE you enter yourself (e.g. from a ballistic app), beside what your groups confirmed
BEGIN;

CREATE TABLE IF NOT EXISTS shooting_settings (
    id                   integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    licence_expires      date,
    licence_note         text,                 -- e.g. the categories it covers (not its number)
    club_shoots_needed   integer CHECK (club_shoots_needed BETWEEN 0 AND 365),
    clean_every          integer NOT NULL DEFAULT 200 CHECK (clean_every BETWEEN 1 AND 100000),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
INSERT INTO shooting_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS shooting_ranges (
    range_id     serial PRIMARY KEY,
    name         text NOT NULL CHECK (btrim(name) <> ''),
    kind         text NOT NULL DEFAULT 'Club range' CHECK (kind IN ('Club range', 'Public range', 'Private property', 'Indoor')),
    distances    text,                          -- what it has: "25, 50, 100 m"
    counts_for_club boolean NOT NULL DEFAULT true,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rifles (
    rifle_id        serial PRIMARY KEY,
    name            text NOT NULL CHECK (btrim(name) <> ''),
    make            text,
    model           text,
    calibre         text,
    kind            text NOT NULL DEFAULT 'Centrefire' CHECK (kind IN ('Rimfire', 'Centrefire', 'Air')),
    action          text CHECK (action IN ('Bolt', 'Semi-auto', 'Lever', 'Single shot', 'Pump', 'Break', 'PCP / spring')),
    barrel_in       numeric(4, 1) CHECK (barrel_in > 0),
    twist           text,                       -- "1:8"
    scope           text,                       -- make / model / magnification
    scope_unit      text NOT NULL DEFAULT 'MOA' CHECK (scope_unit IN ('MOA', 'MIL')),
    click           numeric(5, 3) CHECK (click > 0),   -- 0.25 MOA, 0.1 MIL
    zero_m          integer CHECK (zero_m BETWEEN 1 AND 3000),
    sight_height_mm numeric(5, 1),
    rounds_before   integer NOT NULL DEFAULT 0 CHECK (rounds_before >= 0),   -- fired before you started logging here
    clean_every     integer CHECK (clean_every BETWEEN 1 AND 100000),      -- else the setting's
    status          text NOT NULL DEFAULT 'In use' CHECK (status IN ('In use', 'Wanted', 'Sold')),
    purchase_date   date,
    price_paid      numeric(10, 2) CHECK (price_paid >= 0),
    pta_applied     date,                      -- Queensland: a Permit to Acquire for each firearm you buy
    pta_approved    date,
    pta_expires     date,
    notes           text,
    photo           bytea,
    photo_type      text,
    photo_updated   timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ammo (
    ammo_id         serial PRIMARY KEY,
    name            text NOT NULL CHECK (btrim(name) <> ''),   -- "Lapua Center-X"
    brand           text,
    calibre         text,
    bullet_gr       numeric(6, 1) CHECK (bullet_gr > 0),
    bullet_type     text,                       -- "LRN", "ELD Match", "HPBT"
    bc              numeric(5, 3) CHECK (bc > 0 AND bc < 2),
    bc_model        text CHECK (bc_model IN ('G1', 'G7')),
    velocity_ms     numeric(6, 1) CHECK (velocity_ms > 0),    -- the box's muzzle velocity
    lot             text,
    box_size        integer CHECK (box_size > 0),
    box_price       numeric(10, 2) CHECK (box_price >= 0),
    rounds_bought   integer NOT NULL DEFAULT 0 CHECK (rounds_bought >= 0),
    bought_from     text,
    status          text NOT NULL DEFAULT 'Have' CHECK (status IN ('Have', 'Wanted', 'Used up')),
    notes           text,
    photo           bytea,
    photo_type      text,
    photo_updated   timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shooting_sessions (
    session_id   serial PRIMARY KEY,
    shot_on      date NOT NULL DEFAULT current_date,
    kind         text NOT NULL DEFAULT 'Practice' CHECK (kind IN ('Practice', 'Match', 'Zeroing', 'Ammo test', 'Load development', 'Fun')),
    range_id     integer REFERENCES shooting_ranges ON DELETE SET NULL,
    rifle_id     integer REFERENCES rifles ON DELETE SET NULL,
    ammo_id      integer REFERENCES ammo ON DELETE SET NULL,
    match_name   text,
    finish       text,                         -- where you placed: "3rd of 24"
    rounds       integer CHECK (rounds >= 0),  -- fired, sighters included; blank = the groups' shots added up
    temp_c       numeric(4, 1),
    wind_kmh     numeric(5, 1) CHECK (wind_kmh >= 0),
    wind_from    text,                         -- "3 o'clock", "NW"
    light        text,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS shooting_sessions_on_idx ON shooting_sessions (shot_on DESC);

CREATE TABLE IF NOT EXISTS shooting_groups (
    group_id      serial PRIMARY KEY,
    session_id    integer NOT NULL REFERENCES shooting_sessions ON DELETE CASCADE,
    distance      integer NOT NULL CHECK (distance BETWEEN 1 AND 5000),
    unit          text NOT NULL DEFAULT 'm' CHECK (unit IN ('m', 'yd')),
    shots         integer CHECK (shots BETWEEN 1 AND 1000),
    size_mm       numeric(7, 1) CHECK (size_mm >= 0),     -- centre to centre of the two widest shots
    up_mm         numeric(7, 1),                          -- where the group's centre was from the aim point
    right_mm      numeric(7, 1),
    elevation     numeric(6, 2),                          -- dialled (in the rifle's scope unit)
    windage       numeric(6, 2),
    position      text CHECK (position IN ('Bench', 'Prone', 'Sitting', 'Kneeling', 'Standing', 'Barricade')),
    score         numeric(6, 1),
    x_count       integer CHECK (x_count >= 0),
    velocities    numeric(6, 1)[] NOT NULL DEFAULT '{}',  -- chronograph, m/s
    confirms_dope boolean NOT NULL DEFAULT false,
    notes         text,
    photo         bytea,
    photo_type    text,
    photo_updated timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS shooting_groups_session_idx ON shooting_groups (session_id);

CREATE TABLE IF NOT EXISTS rifle_logs (
    log_id      serial PRIMARY KEY,
    rifle_id    integer NOT NULL REFERENCES rifles ON DELETE CASCADE,
    kind        text NOT NULL DEFAULT 'Cleaned' CHECK (kind IN ('Cleaned', 'Zeroed', 'Scope change', 'Repair', 'Part', 'Note')),
    done_on     date NOT NULL DEFAULT current_date,
    at_rounds   integer,                       -- the rifle's round count then
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS rifle_logs_rifle_idx ON rifle_logs (rifle_id, done_on DESC);

CREATE TABLE IF NOT EXISTS dope_rows (
    dope_id     serial PRIMARY KEY,
    rifle_id    integer NOT NULL REFERENCES rifles ON DELETE CASCADE,
    ammo_id     integer REFERENCES ammo ON DELETE CASCADE,
    distance    integer NOT NULL CHECK (distance BETWEEN 1 AND 5000),
    unit        text NOT NULL DEFAULT 'm' CHECK (unit IN ('m', 'yd')),
    elevation   numeric(6, 2) NOT NULL,
    wind10      numeric(6, 2),                 -- windage for a 10 km/h full-value wind
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Shooting gear on the shared gear pages (bipod, rear bag, spotting scope, chronograph, wind meter...)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'gear'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%shooting%') THEN
        ALTER TABLE gear DROP CONSTRAINT IF EXISTS gear_hobby_check;
        ALTER TABLE gear ADD CONSTRAINT gear_hobby_check CHECK (hobby IN ('volleyball', 'hiking', 'shooting'));
    END IF;
END $$;

COMMIT;
