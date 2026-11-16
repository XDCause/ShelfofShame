-- Board games and video games extras (2026-11-16). Idempotent: safe on a fresh database and on an existing one.
--
-- Board games
--   turn timer     board_game_live.turns keeps the chess-clock state (whose turn, since when, each player's time so far);
--                  finishing saves each seat's time on board_game_play_players (turn_seconds / turn_count / turn_over)
--                  and the limit on the play (turn_limit_s).
--   round scores   a grid, one row per round: [{"<player_id>": 5, ...}, ...] (live, then kept on the play).
--   tags           free text tags on a play ("close game"), live or logged.
-- Video games
--   beat_hours     your own time-to-beat estimate for a game (hours); empty = the API suggests one.
--   price_paid     what you paid, for cost per hour.
BEGIN;

ALTER TABLE board_game_live ADD COLUMN IF NOT EXISTS turns JSONB;                                  -- NULL = no turn timer
ALTER TABLE board_game_live ADD COLUMN IF NOT EXISTS round_scores JSONB NOT NULL DEFAULT '[]';
ALTER TABLE board_game_live ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS round_scores JSONB NOT NULL DEFAULT '[]';
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS turn_limit_s INT;

ALTER TABLE board_game_play_players ADD COLUMN IF NOT EXISTS turn_seconds INT;       -- thinking time, all turns added up
ALTER TABLE board_game_play_players ADD COLUMN IF NOT EXISTS turn_count INT;         -- turns taken
ALTER TABLE board_game_play_players ADD COLUMN IF NOT EXISTS turn_over INT;          -- turns that ran past the limit

ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS beat_hours NUMERIC(6, 1);
ALTER TABLE vg_games ADD COLUMN IF NOT EXISTS price_paid NUMERIC(10, 2);
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS beat_hours NUMERIC(6, 1);
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS price_paid NUMERIC(10, 2);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vg_games_beat_price_check') THEN
        ALTER TABLE vg_games ADD CONSTRAINT vg_games_beat_price_check CHECK (beat_hours >= 0 AND price_paid >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vg_other_games_beat_price_check') THEN
        ALTER TABLE vg_other_games ADD CONSTRAINT vg_other_games_beat_price_check CHECK (beat_hours >= 0 AND price_paid >= 0);
    END IF;
END $$;

COMMIT;
