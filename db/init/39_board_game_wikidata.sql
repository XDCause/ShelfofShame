-- Board games found on Wikidata (2026-10-15).
--
-- Wikidata (the free, open database behind Wikipedia; no key or account) has the publisher's facts
-- for most well-known games: players, play time, age, year, designer, publisher, a photo on
-- Wikimedia Commons, and the game's BoardGameGeek id. A game found there keeps its Wikidata item
-- (to look it up again) and its BGG id (the "BoardGameGeek" link). BGG's own ratings, ranks and
-- complexity are NOT on Wikidata: they need BGG's registered API.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE board_games ADD COLUMN IF NOT EXISTS wikidata_id TEXT CHECK (wikidata_id ~ '^Q[0-9]+$');
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS bgg_id INT CHECK (bgg_id > 0);
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS designer TEXT;
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS min_age INT CHECK (min_age BETWEEN 1 AND 99);
