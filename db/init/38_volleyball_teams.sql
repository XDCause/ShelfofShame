-- Volleyball teams (2026-10-14).
--
--   volleyball_teams   the teams you play in: name, where they play (their location), whether it's
--                      your default (one at most: a new game starts with it and its location), and
--                      retired (kept for old games, no longer offered).
--   volleyball_games.team_id   the team a game was for. It replaces the typed-in team name: names
--                      already typed become teams (their most used venue as the location).
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

CREATE TABLE IF NOT EXISTS volleyball_teams (
    team_id     SERIAL PRIMARY KEY,
    name        TEXT NOT NULL CHECK (btrim(name) <> ''),
    location    TEXT,
    is_default  BOOLEAN NOT NULL DEFAULT false,
    retired     BOOLEAN NOT NULL DEFAULT false,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS volleyball_teams_name_uq ON volleyball_teams (lower(name));
CREATE UNIQUE INDEX IF NOT EXISTS volleyball_teams_default_uq ON volleyball_teams (is_default) WHERE is_default;

ALTER TABLE volleyball_games ADD COLUMN IF NOT EXISTS team_id INT REFERENCES volleyball_teams (team_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS volleyball_games_team_idx ON volleyball_games (team_id);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'volleyball_games' AND column_name = 'team') THEN
        INSERT INTO volleyball_teams (name, location)
        SELECT DISTINCT ON (lower(btrim(team))) btrim(team),
               (SELECT v2.venue FROM volleyball_games v2 WHERE lower(btrim(v2.team)) = lower(btrim(v.team))
                  AND v2.venue IS NOT NULL GROUP BY v2.venue ORDER BY count(*) DESC, max(v2.played_on) DESC LIMIT 1)
        FROM volleyball_games v WHERE btrim(COALESCE(team, '')) <> ''
        ON CONFLICT DO NOTHING;
        UPDATE volleyball_games v SET team_id = t.team_id
        FROM volleyball_teams t WHERE lower(t.name) = lower(btrim(v.team)) AND v.team_id IS NULL;
        ALTER TABLE volleyball_games DROP COLUMN team;
    END IF;
END $$;
