-- Video games on other platforms: Epic and Ubisoft (2026-10-14).
--
-- Kept apart from vg_games (Steam), so profile completion, the goal, streaks and the 7-day changes
-- stay Steam-only and keep matching SteamHunters.
--   Epic     achievements read from the user's Exophase profile on each sync (api/app/othergames.py)
--   Ubisoft  Exophase only sees Ubisoft *challenges*, never the achievements, so names, pictures and
--            playtime come from Exophase and the achievements are typed in by the user (my_done /
--            my_total). Games Exophase doesn't list can be added by hand (source_id NULL).
--
-- vg_sync gets the Exophase profile: its name and the player id for each linked platform
-- ({"epic": 123, "uplay": 456}).
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE vg_sync ADD COLUMN IF NOT EXISTS exo_profile TEXT;
ALTER TABLE vg_sync ADD COLUMN IF NOT EXISTS exo_players JSONB;
ALTER TABLE vg_sync ADD COLUMN IF NOT EXISTS exo_synced_at TIMESTAMPTZ;
ALTER TABLE vg_sync ADD COLUMN IF NOT EXISTS exo_error TEXT;

CREATE TABLE IF NOT EXISTS vg_other_games (
    game_id       SERIAL PRIMARY KEY,
    platform      TEXT NOT NULL CHECK (platform IN ('epic', 'ubisoft')),
    source_id     TEXT,                    -- Exophase's game id; NULL = added by hand
    name          TEXT NOT NULL,
    picture_url   TEXT,                    -- Exophase's game tile
    page_url      TEXT,                    -- the game's page on Exophase
    exo_done      INT,                     -- from Exophase: Epic achievements / Ubisoft challenges
    exo_total     INT,
    exo_minutes   INT,                     -- playtime Exophase knows (often none)
    last_played   TIMESTAMPTZ,
    exo_completed_at TIMESTAMPTZ,
    my_done       INT CHECK (my_done >= 0),  -- typed in (Ubisoft achievements)
    my_total      INT CHECK (my_total >= 0),
    my_minutes    INT CHECK (my_minutes >= 0),
    hidden        BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (my_done IS NULL OR my_total IS NULL OR my_done <= my_total)
);
CREATE UNIQUE INDEX IF NOT EXISTS vg_other_games_source_uq ON vg_other_games (platform, source_id)
    WHERE source_id IS NOT NULL;
