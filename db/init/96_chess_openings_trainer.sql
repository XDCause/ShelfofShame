-- Chess opening trainer (2026-11-15, the user: "teach me the lines - instead of going there, when you want to play this
-- opening do this instead"). Must match api/app/lichess.py and api/app/chess_trainer.py. Idempotent.
--
--   chess_explorer_cache  every answer the Lichess opening explorer gave, kept 30 days so a position is asked once
--   chess_repertoire      an opening you chose to learn (a colour and the moves that start it) and how its build went
--   chess_drill_cards     one per position where YOU must move: the move to play, why, and the spaced-repetition
--                         numbers (due_at, interval_days, ease, reps, lapses - Anki's SM-2 way)

BEGIN;

CREATE TABLE IF NOT EXISTS chess_explorer_cache (
    key        TEXT PRIMARY KEY,            -- source | position | ratings | speeds
    answer     JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chess_repertoire (
    repertoire_id SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    colour        TEXT NOT NULL CHECK (colour IN ('white', 'black')),
    start_moves   TEXT NOT NULL DEFAULT '',     -- the opening's moves in SAN: "e4 c5 Nf3"
    eco           TEXT,
    status        TEXT NOT NULL DEFAULT 'building' CHECK (status IN ('building', 'ready', 'failed')),
    error         TEXT,
    replies       JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {epd: [{san, uci, share, epd}]}: what the opponent plays, by how often
    notes         TEXT,                                  -- how the build went ("from the explorer" / "from theory only")
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    built_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chess_drill_cards (
    card_id       SERIAL PRIMARY KEY,
    repertoire_id INT NOT NULL REFERENCES chess_repertoire (repertoire_id) ON DELETE CASCADE,
    epd           TEXT NOT NULL,
    fen           TEXT NOT NULL,
    ply           INT NOT NULL DEFAULT 0,
    line          TEXT NOT NULL DEFAULT '',     -- the moves that led here, in SAN
    move_san      TEXT NOT NULL,
    move_uci      TEXT NOT NULL,
    why           TEXT NOT NULL DEFAULT 'opening' CHECK (why IN ('opening', 'masters', 'engine', 'theory', 'lichess')),
    note          TEXT,
    due_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    interval_days NUMERIC(8, 2) NOT NULL DEFAULT 0,
    ease          NUMERIC(4, 2) NOT NULL DEFAULT 2.5,
    reps          INT NOT NULL DEFAULT 0,
    lapses        INT NOT NULL DEFAULT 0,
    last_result   TEXT CHECK (last_result IN ('right', 'wrong')),
    last_at       TIMESTAMPTZ,
    UNIQUE (repertoire_id, epd)
);
CREATE INDEX IF NOT EXISTS chess_drill_due_idx ON chess_drill_cards (repertoire_id, due_at);

COMMIT;
