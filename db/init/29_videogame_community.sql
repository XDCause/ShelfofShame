-- Video games: how other players did, from SteamHunters' public JSON API (2026-10-14).
--
-- For the games you've started (api/app/steamhunters.py, read gently during a sync):
--   sh_median_minutes      the median time SteamHunters' players took to 100% the game
--   sh_fastest_minutes     the fastest 100%
--   sh_players_perfected   how many of their players have 100%'d it...
--   sh_players_started     ...out of how many started it (so: how rare a 100% is)
--   sh_points              SteamHunters' points for the game (rarer = more)
--   sh_synced_at           when it was last read (also set when SteamHunters doesn't know the game)
-- Steam's own cross-check (the rarest achievement's global %) is worked out from vg_achievements.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS sh_median_minutes INT;
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS sh_fastest_minutes INT;
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS sh_players_perfected INT;
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS sh_players_started INT;
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS sh_points INT;
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS sh_synced_at TIMESTAMPTZ;
