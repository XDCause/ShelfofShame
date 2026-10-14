-- Chess (a hobby module, 2026-10-14): your chess.com games through its official public API
-- (api/app/chesscom.py, no login - just the username), and games over the board, logged by hand.
--
--   chess_account   the one chess.com account followed: username, profile, the latest stats
--                   (rating / best / record per time control, puzzles), how the last sync went
--   chess_archives  each month chess.com keeps your games in, and whether it's been read in full
--                   (past months never change; the current and previous month are read each sync)
--   chess_games     every game: online (source 'chesscom', uuid = chess.com's) or over the board
--                   (source 'otb'); your colour, both ratings, the result from your side, the
--                   opening, the moves (PGN), accuracy (when the game was reviewed)
-- journal_links gains 'chess' (a game), so pages can mention games and a game shows its pages.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

CREATE TABLE IF NOT EXISTS chess_account (
    id            INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    username      TEXT,
    profile       JSONB,                    -- name, avatar, title, url, joined, ...
    stats         JSONB,                    -- chess.com's stats reply, as it was last read
    last_sync_at  TIMESTAMPTZ,
    last_error    TEXT
);
INSERT INTO chess_account (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS chess_archives (
    month     TEXT PRIMARY KEY,             -- 'YYYY-MM'
    games     INT NOT NULL DEFAULT 0,
    read_at   TIMESTAMPTZ,
    complete  BOOLEAN NOT NULL DEFAULT false   -- the month was over when it was read
);

CREATE TABLE IF NOT EXISTS chess_games (
    game_id       SERIAL PRIMARY KEY,
    source        TEXT NOT NULL DEFAULT 'chesscom' CHECK (source IN ('chesscom', 'otb')),
    uuid          TEXT UNIQUE,              -- chess.com's id (NULL for over the board)
    url           TEXT,
    played_at     TIMESTAMPTZ NOT NULL,
    time_class    TEXT NOT NULL CHECK (time_class IN ('bullet', 'blitz', 'rapid', 'daily', 'classical')),
    time_control  TEXT,                     -- chess.com's "180+2" / "1/86400"
    rated         BOOLEAN NOT NULL DEFAULT true,
    rules         TEXT NOT NULL DEFAULT 'chess',   -- chess, chess960, bughouse...
    colour        TEXT NOT NULL CHECK (colour IN ('white', 'black')),
    my_rating     INT,
    opp_name      TEXT NOT NULL,
    opp_rating    INT,
    result        TEXT NOT NULL CHECK (result IN ('win', 'loss', 'draw')),
    how           TEXT,                     -- checkmated, resigned, timeout, agreed, repetition...
    eco           TEXT,                     -- B90
    opening       TEXT,                     -- "Sicilian Defense Najdorf Variation"
    opening_family TEXT,                    -- "Sicilian Defense"
    pgn           TEXT,
    moves         INT,                      -- full moves
    accuracy      NUMERIC(5, 2),            -- yours, when reviewed
    opp_accuracy  NUMERIC(5, 2),
    event         TEXT,                     -- over the board: club night, tournament...
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chess_games_played_idx ON chess_games (played_at DESC);
CREATE INDEX IF NOT EXISTS chess_games_class_idx ON chess_games (time_class, played_at DESC);

ALTER TABLE journal_links DROP CONSTRAINT IF EXISTS journal_links_target_kind_check;
ALTER TABLE journal_links ADD CONSTRAINT journal_links_target_kind_check
    CHECK (target_kind IN ('model', 'supply', 'page', 'game', 'gear', 'videogame', 'chess'));
