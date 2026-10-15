-- Board games (2026-10-16): which shop a game was filled in from - Gameology (the main search: BGG's facts)
-- or Good Games (fills the holes, through its official UCP interface). Games filled in before came from
-- Gameology.
BEGIN;

ALTER TABLE board_games ADD COLUMN IF NOT EXISTS shop_name TEXT CHECK (shop_name IN ('Gameology', 'Good Games'));
UPDATE board_games SET shop_name = 'Gameology' WHERE shop_handle IS NOT NULL AND shop_name IS NULL;

COMMIT;
