-- Board games (2026-10-16): what each one is - a game ('game'), an expansion for one ('expansion', with
-- the base game it belongs to) or something else ('other': metal coins, sleeves, organisers...) - so the
-- Games page can show base games on their own. Gameology's "Board Game BEA" tag says which (set when a
-- game is added or filled in from the shop); shop_expansions = the handles a base game's product lists
-- as its expansions, used to link them.
BEGIN;

ALTER TABLE board_games ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'game'
    CHECK (kind IN ('game', 'expansion', 'other'));
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS base_game_id INT REFERENCES board_games (game_id) ON DELETE SET NULL
    CHECK (base_game_id IS DISTINCT FROM game_id);
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS shop_expansions TEXT[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS board_games_base_idx ON board_games (base_game_id);

-- A first guess from the names (the shop's tags correct it on the next fill-in / shop check).
UPDATE board_games SET kind = 'expansion'
WHERE kind = 'game' AND name ~* '\m(expansion|extension|exp\.?)\M';
UPDATE board_games SET kind = 'other'
WHERE kind = 'game' AND name ~* '\m(metal coins|coins|sleeves|insert|organi[sz]er|playmat|dice set|token|upgrade pack)\M';

-- An expansion's base game: the game whose name starts it ("Scythe the Wind Gambit" -> Scythe), longest first.
UPDATE board_games e SET base_game_id = (
    SELECT b.game_id FROM board_games b
    WHERE b.kind = 'game' AND b.game_id <> e.game_id AND lower(e.name) LIKE lower(b.name) || ' %'
    ORDER BY length(b.name) DESC LIMIT 1)
WHERE e.kind IN ('expansion', 'other') AND e.base_game_id IS NULL;

COMMIT;
