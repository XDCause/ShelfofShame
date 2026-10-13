-- Volleyball, the third hobby module (2026-10-13).
--
--   gear              equipment you own, for any hobby that has some (volleyball now; scuba,
--                     woodworking... later): shoes, knee pads, balls, with condition and a photo
--   volleyball_games  each game or training: the day, kind, team, opponent, sets won and lost,
--                     where, notes; `event_id` = the calendar event it was logged from
--   volleyball_videos links to videos: game footage or a drill to learn from (YouTube, Google
--                     Drive...). Only the link is stored, never the video itself.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE TABLE IF NOT EXISTS gear (
    gear_id       SERIAL PRIMARY KEY,
    hobby         TEXT NOT NULL DEFAULT 'volleyball' CHECK (hobby IN ('volleyball')),
    name          TEXT NOT NULL CHECK (btrim(name) <> ''),
    kind          TEXT,                    -- Shoes, Knee pads, Ball...
    brand         TEXT,
    size          TEXT,
    condition     TEXT NOT NULL DEFAULT 'Good'
                  CHECK (condition IN ('New', 'Good', 'Worn', 'Needs replacing', 'Retired')),
    purchase_date DATE,
    price_paid    NUMERIC(10, 2) CHECK (price_paid >= 0),
    notes         TEXT,
    photo         BYTEA,
    photo_type    TEXT,
    photo_updated TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS gear_set_updated_at ON gear;
CREATE TRIGGER gear_set_updated_at
    BEFORE UPDATE ON gear
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS volleyball_games (
    game_id    SERIAL PRIMARY KEY,
    played_on  DATE NOT NULL DEFAULT current_date,
    kind       TEXT NOT NULL DEFAULT 'Game' CHECK (kind IN ('Game', 'Training', 'Social', 'Tournament')),
    team       TEXT,
    opponent   TEXT,
    venue      TEXT,
    sets_won   INT CHECK (sets_won >= 0),
    sets_lost  INT CHECK (sets_lost >= 0),
    notes      TEXT,
    event_id   INT REFERENCES calendar_events (event_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS volleyball_games_day_idx ON volleyball_games (played_on DESC);

CREATE TABLE IF NOT EXISTS volleyball_videos (
    video_id   SERIAL PRIMARY KEY,
    title      TEXT NOT NULL CHECK (btrim(title) <> ''),
    url        TEXT NOT NULL CHECK (url ~* '^https?://'),
    topic      TEXT,                       -- Highlights, Serving, Passing...
    game_id    INT REFERENCES volleyball_games (game_id) ON DELETE SET NULL,
    notes      TEXT,
    watched    BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Journal pages can @mention gear too.
ALTER TABLE journal_links DROP CONSTRAINT IF EXISTS journal_links_target_kind_check;
ALTER TABLE journal_links ADD CONSTRAINT journal_links_target_kind_check
    CHECK (target_kind IN ('model', 'supply', 'page', 'game', 'gear'));

COMMIT;
