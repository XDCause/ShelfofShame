-- Video games: Steam achievement hunting, the fourth hobby module (2026-10-14).
--
-- Everything here comes from the official Steam Web API (api/app/steam.py) and is refreshed by a
-- sync (api/app/videogames.py); nothing is scraped from other sites.
--
--   vg_games         every game you own: name, playtime, when you last played it, how many of its
--                    achievements you have, and when you got the last one (completed_at, once 100%)
--   vg_achievements  each game's achievements: name, description, icons, how rare (the % of all
--                    players who have it), and whether / when you unlocked it
--   vg_sync          the one Steam account being tracked and how the last sync went
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE TABLE IF NOT EXISTS vg_games (
    app_id             INT PRIMARY KEY,                 -- Steam's id for the game
    name               TEXT NOT NULL,
    icon_hash          TEXT,                            -- Steam's small icon (img_icon_url)
    playtime_minutes   INT NOT NULL DEFAULT 0,
    playtime_2weeks    INT NOT NULL DEFAULT 0,
    last_played        TIMESTAMPTZ,
    has_achievements   BOOLEAN,                         -- NULL = not checked yet
    achievements_total INT NOT NULL DEFAULT 0,
    achievements_done  INT NOT NULL DEFAULT 0,
    completed_at       TIMESTAMPTZ,                     -- the last unlock, once every one is done
    hidden             BOOLEAN NOT NULL DEFAULT false,  -- you've hidden it from the dashboard
    synced_at          TIMESTAMPTZ,                     -- achievements last read from Steam
    rarity_synced_at   TIMESTAMPTZ                      -- global percentages last read
);
CREATE INDEX IF NOT EXISTS vg_games_completed_idx ON vg_games (completed_at) WHERE completed_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS vg_achievements (
    app_id         INT NOT NULL REFERENCES vg_games (app_id) ON DELETE CASCADE,
    api_name       TEXT NOT NULL,                       -- Steam's id for the achievement
    name           TEXT NOT NULL,
    description    TEXT,                                -- Steam leaves hidden ones' empty
    icon           TEXT,                                -- unlocked icon (Steam's CDN)
    icon_gray      TEXT,                                -- locked icon
    hidden         BOOLEAN NOT NULL DEFAULT false,
    global_percent NUMERIC(6, 3),                       -- % of all players who have it
    achieved       BOOLEAN NOT NULL DEFAULT false,
    unlocked_at    TIMESTAMPTZ,
    PRIMARY KEY (app_id, api_name)
);
CREATE INDEX IF NOT EXISTS vg_achievements_unlocked_idx ON vg_achievements (unlocked_at DESC) WHERE achieved;

CREATE TABLE IF NOT EXISTS vg_sync (
    id             INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),   -- one row: the account being tracked
    profile        TEXT,                                -- what was typed: a profile name or id
    steam_id       TEXT,                                -- the 17-digit SteamID64
    persona_name   TEXT,
    last_sync_at   TIMESTAMPTZ,
    last_full_at   TIMESTAMPTZ,
    last_error     TEXT
);
INSERT INTO vg_sync (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- Journal pages can @mention a video game.
ALTER TABLE journal_links DROP CONSTRAINT IF EXISTS journal_links_target_kind_check;
ALTER TABLE journal_links ADD CONSTRAINT journal_links_target_kind_check
    CHECK (target_kind IN ('model', 'supply', 'page', 'game', 'gear', 'videogame'));

COMMIT;
