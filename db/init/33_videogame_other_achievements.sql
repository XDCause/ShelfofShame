-- Video games on other platforms: every achievement, and the game's Steam version (2026-10-14).
--
-- Epic and Ubisoft games get the same detail as Steam ones:
--   vg_other_achievements  each achievement (name, description, icon, how rare, have it):
--                          Epic - from the game's Exophase page, with your unlock dates;
--                          Ubisoft - from the game's Steam version (same list), ticked off by you.
--   vg_other_games.steam_app_id   the game's Steam version (found by name, or set by you): its
--                          picture and SteamHunters' numbers (median time to 100%, 100% rate).
-- Once a game has its list, its done / total come from the list (the typed-in totals are a
-- fallback for games with no list).
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS steam_app_id INT;
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS steam_checked_at TIMESTAMPTZ;   -- looked for it (NULL app = none)
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS header_url TEXT;                 -- the Steam version's picture
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS list_synced_at TIMESTAMPTZ;      -- achievement list read
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS list_done INT;                   -- Epic: earned count it was read at
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS sh_median_minutes INT;
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS sh_fastest_minutes INT;
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS sh_players_perfected INT;
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS sh_players_started INT;
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS sh_synced_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS vg_other_achievements (
    game_id        INT NOT NULL REFERENCES vg_other_games (game_id) ON DELETE CASCADE,
    api_name       TEXT NOT NULL,              -- Steam's id (Ubisoft) or Exophase's award id (Epic)
    name           TEXT NOT NULL,
    description    TEXT,
    icon           TEXT,
    icon_gray      TEXT,
    hidden         BOOLEAN NOT NULL DEFAULT false,
    global_percent NUMERIC(6, 3),              -- Steam's players (Ubisoft) / Exophase's players (Epic)
    achieved       BOOLEAN NOT NULL DEFAULT false,
    unlocked_at    TIMESTAMPTZ,                -- Epic: when; Ubisoft: unknown (ticked by hand)
    sort_order     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, api_name)
);
