-- Video games backlog (2026-11-16): a status per game - Backlog / Playing / Finished / Dropped.
-- Only what you set is stored (NULL = not set: the API works out a starting value from playtime, 100% and
-- when you last played, in videogames.py). Same column on Steam games and on Epic / Ubisoft ones.
-- Must match STATUSES in api/app/videogames.py.
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS play_status TEXT;
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS play_status TEXT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vg_games_play_status_check') THEN
        ALTER TABLE vg_games ADD CONSTRAINT vg_games_play_status_check
            CHECK (play_status IN ('backlog', 'playing', 'finished', 'dropped'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vg_other_games_play_status_check') THEN
        ALTER TABLE vg_other_games ADD CONSTRAINT vg_other_games_play_status_check
            CHECK (play_status IN ('backlog', 'playing', 'finished', 'dropped'));
    END IF;
END $$;

COMMIT;
