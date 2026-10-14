-- Video games: achievements that can't be earned any more (2026-10-14).
--
-- SteamHunters' moderators flag achievements that are unobtainable (a shut-down server, a removed
-- mode): their public API gives each game's count (unobtainableAchievementCount) and, per
-- achievement, obtainability = 3. Read during a sync for started games (api/app/steamhunters.py):
--   vg_games.sh_unobtainable      how many SteamHunters says the game has (0 = none)
--   vg_achievements.unobtainable  this one can't be earned any more
-- A game's achievements_total leaves out unobtainable ones you don't have (one you got before it
-- became unobtainable still counts), so a game can be 100% without them, as on SteamHunters.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS sh_unobtainable INT;
ALTER TABLE vg_achievements ADD COLUMN IF NOT EXISTS unobtainable BOOLEAN NOT NULL DEFAULT false;
