-- Chess game review (2026-11-15, the user: "a chess review tool to see blunders and brilliants, much like chess.com's
-- game review"): one game at a time, when you ask (a button on the game - not every game in the background: "it will
-- take a lot of time and grow too far"). Stockfish (in the API's image) looks at every position; the review is kept,
-- so opening it again is instant.
--
--   chess_reviews   a game's review: running (how far it got) / done / failed; the engine and depth used; summary
--                   (each side's accuracy, game rating estimate, counts of each kind of move, accuracy by phase, the
--                   opening and where theory was left, the key moments) and moves (per move: the eval before and
--                   after, win chances, its class - brilliant / great / best / excellent / good / book / inaccuracy /
--                   mistake / miss / blunder / forced - the best move and the line the engine expected)
--
-- Must match api/app/chess_review.py. Idempotent: safe on a fresh database (docker init) and on an existing one.

BEGIN;

CREATE TABLE IF NOT EXISTS chess_reviews (
    game_id     INT PRIMARY KEY REFERENCES chess_games (game_id) ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'failed')),
    done_plies  INT NOT NULL DEFAULT 0,
    total_plies INT NOT NULL DEFAULT 0,
    engine      TEXT,
    depth       INT,
    summary     JSONB,
    moves       JSONB,
    error       TEXT,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

COMMIT;
