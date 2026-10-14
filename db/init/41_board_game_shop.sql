-- Board games found at Gameology instead of Wikidata (2026-10-15; Wikidata's board game facts were
-- too thin). Gameology, an Australian board game shop, tags its products with BoardGameGeek's facts.
--
--   board_games.weight      BGG's weight - how complex the game is, 1 (light) to 5 (heavy)
--   board_games.categories  BGG's categories and types (Economic, Negotiation, Family...)
--   board_games.mechanisms  BGG's mechanisms (Dice Rolling, Hand Management...)
--   board_games.shop_handle the product at Gameology (to look it up again), shop_url its page,
--                           shop_price what it sells for (when you looked it up)
-- Wikidata's item id goes (never used outside dev); bgg_id / designer / min_age stay.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE board_games ADD COLUMN IF NOT EXISTS weight NUMERIC(3, 2) CHECK (weight BETWEEN 1 AND 5);
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS categories TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS mechanisms TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS shop_handle TEXT;
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS shop_url TEXT CHECK (shop_url ~ '^https://');
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS shop_price NUMERIC(10, 2) CHECK (shop_price >= 0);
ALTER TABLE board_games DROP COLUMN IF EXISTS wikidata_id;
