-- The calendar (2026-10-13).
--
--   calendar_events   things planned for a day: a volleyball game, a games night, a model show.
--                     A time is optional (no start_time = all day). An event can repeat weekly or
--                     fortnightly until a date (or for ever); `skipped` holds the days a repeating
--                     event isn't on (e.g. a public holiday). `hobby` is the module it belongs to
--                     (models / boardgames / volleyball), or NULL for anything else.
--
-- What already HAPPENED (stock, kits, plays, games, journal pages) isn't stored here: the
-- calendar reads it from the activity feed (api/app/activity.py), so nothing is kept twice.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE TABLE IF NOT EXISTS calendar_events (
    event_id     SERIAL PRIMARY KEY,
    title        TEXT NOT NULL CHECK (btrim(title) <> ''),
    hobby        TEXT CHECK (hobby IN ('models', 'boardgames', 'volleyball')),
    starts_on    DATE NOT NULL,
    start_time   TIME,
    end_time     TIME,
    location     TEXT,
    notes        TEXT,
    repeats      TEXT NOT NULL DEFAULT 'never' CHECK (repeats IN ('never', 'weekly', 'fortnightly')),
    repeat_until DATE,
    skipped      DATE[] NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT calendar_events_until_check CHECK (repeat_until IS NULL OR repeat_until >= starts_on),
    CONSTRAINT calendar_events_time_check CHECK (end_time IS NULL OR (start_time IS NOT NULL AND end_time > start_time))
);
CREATE INDEX IF NOT EXISTS calendar_events_starts_idx ON calendar_events (starts_on);

DROP TRIGGER IF EXISTS calendar_events_set_updated_at ON calendar_events;
CREATE TRIGGER calendar_events_set_updated_at
    BEFORE UPDATE ON calendar_events
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
