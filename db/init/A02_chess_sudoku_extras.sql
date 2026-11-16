-- Chess puzzles from your own mistakes (2026-11-16, market review: "your blunders as a puzzle set with spaced
-- repetition"). Must match api/app/chess_insights.py. Idempotent.
--
--   chess_puzzles   one per move of yours that a game review called a mistake, miss or blunder: the position BEFORE it,
--                   the engine's move, and the spaced-repetition numbers (the opening trainer's: due_at, interval_days,
--                   ease, reps, lapses - Anki's SM-2 way). Deleting a game deletes its puzzles.
-- (Sudoku's colour marks live in the saved game's JSON; per-technique stats read the finished games: no table.)

BEGIN;

CREATE TABLE IF NOT EXISTS chess_puzzles (
    puzzle_id     SERIAL PRIMARY KEY,
    game_id       INT NOT NULL REFERENCES chess_games (game_id) ON DELETE CASCADE,
    ply           INT NOT NULL,
    fen           TEXT NOT NULL,
    colour        TEXT NOT NULL CHECK (colour IN ('white', 'black')),
    played_san    TEXT NOT NULL,
    best_san      TEXT,
    best_uci      TEXT NOT NULL,
    best_line     JSONB NOT NULL DEFAULT '[]'::jsonb,
    loss          NUMERIC(5, 3) NOT NULL DEFAULT 0,
    kind          TEXT NOT NULL CHECK (kind IN ('mistake', 'miss', 'blunder')),
    due_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    interval_days NUMERIC(8, 2) NOT NULL DEFAULT 0,
    ease          NUMERIC(4, 2) NOT NULL DEFAULT 2.5,
    reps          INT NOT NULL DEFAULT 0,
    lapses        INT NOT NULL DEFAULT 0,
    last_result   TEXT CHECK (last_result IN ('right', 'wrong')),
    last_at       TIMESTAMPTZ,
    UNIQUE (game_id, ply)
);
CREATE INDEX IF NOT EXISTS chess_puzzles_due_idx ON chess_puzzles (due_at);

COMMIT;
