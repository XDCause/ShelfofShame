-- Video games: games added by hand (2026-10-14).
--
-- Steam's owned-games list leaves out some games you have achievements in - free games such as
-- Counter-Strike 2, and games you no longer own (refunds, free weekends) - so SteamHunters counts
-- games the sync can't find. You add those by their store link or app id.
--   vg_games.extra   added by hand: kept, and re-read on every sync (there's no "last played" for them)
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS extra BOOLEAN NOT NULL DEFAULT false;
