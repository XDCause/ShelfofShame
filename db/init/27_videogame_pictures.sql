-- Video games: each game's real picture address (2026-10-14).
--
-- Steam serves newer games' pictures from per-game hashed paths, so the old fixed address
-- (cdn.../steam/apps/<id>/header.jpg) is "not found" for them (17 of the user's 208 games). The
-- sync now asks Steam's store API (IStoreBrowseService/GetItems) for each game's header picture.
--   vg_games.header_url   NULL = not looked up yet; '' = Steam has none (the app shows a placeholder)
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS header_url TEXT;
