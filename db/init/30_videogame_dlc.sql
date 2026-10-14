-- Video games: which achievements come with a DLC, from Exophase's game pages (2026-10-14).
--
-- Steam lists a game's DLC achievements in the same list as the main game's, with nothing to say
-- which is which. Exophase's achievement pages put each DLC in its own section, so for started
-- games with DLC (api/app/exophase.py, read gently during a sync):
--   vg_achievements.dlc    the DLC's name (e.g. "Captain Scarlett and her Pirate's Booty"),
--                          NULL = the main game (also when Exophase doesn't know the achievement)
--   vg_games.sh_has_dlc    SteamHunters says the game has paid DLC (only those are looked up)
--   vg_games.exo_url       the Exophase page that was used ('' = none found for this game)
--   vg_games.exo_synced_at when it was read (NULL = not yet, or the achievements changed since)
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE vg_achievements ADD COLUMN IF NOT EXISTS dlc TEXT;
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS sh_has_dlc BOOLEAN;
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS exo_url TEXT;
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS exo_synced_at TIMESTAMPTZ;
