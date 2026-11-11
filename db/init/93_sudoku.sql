-- Sudoku (2026-11-11), a hobby module: every puzzle you play - made by the app (web/src/modules/sudoku/engine.js),
-- the daily one, a technique to practise, or one you typed in from a book or a paper - where you're up to, and how it
-- went (time, mistakes, hints).
--
--   sudoku_games   the puzzle and its answer (size * size characters: 1-9, then A-G on a 16 x 16; 0 = empty), its size
--                  (9 or 16), where it came from, its grade (difficulty, the
--                  techniques it needs, the hardest), your board (state: {"v": 81 digits, "n": 81 note masks}), status,
--                  time played (seconds, paused time not counted), mistakes, hints, when it was finished
--
-- Solved games show on the calendar and in Recent activity; goals can count them. Must match api/app/sudoku.py.
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE TABLE IF NOT EXISTS sudoku_games (
    game_id     SERIAL PRIMARY KEY,
    size        INT NOT NULL DEFAULT 9,
    puzzle      TEXT NOT NULL,
    solution    TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'new',            -- new / daily / weekly / practice / typed / set (sudoku_games_source_check)
    daily_on    DATE,                                   -- the daily puzzle's day
    week_of     DATE,                                   -- the weekly puzzle's Monday
    set_key     TEXT,                                   -- a puzzle from a set: 'hardest' (the Hardest 100) or an event's path
    set_stop    INT,                                    -- ...its number in the set (1 = the first)
    paper       TEXT,                                   -- typed in from this newspaper / book
    difficulty  TEXT NOT NULL CHECK (difficulty IN ('Easy', 'Medium', 'Hard', 'Expert', 'Extreme')),
    techniques  JSONB NOT NULL DEFAULT '{}',            -- {technique: steps} the app's solver used
    hardest     TEXT,                                   -- its hardest technique (NULL: beyond the app's)
    practice    TEXT,                                   -- the technique it was made to practise
    clues       INT NOT NULL,
    state       JSONB,                                  -- your board: {"v": "81 digits", "n": [81 note masks]}
    status      TEXT NOT NULL DEFAULT 'playing' CHECK (status IN ('playing', 'solved', 'gave_up')),
    seconds     INT NOT NULL DEFAULT 0 CHECK (seconds >= 0),
    mistakes    INT NOT NULL DEFAULT 0 CHECK (mistakes >= 0),
    hints       INT NOT NULL DEFAULT 0 CHECK (hints >= 0),
    hint_kinds  JSONB NOT NULL DEFAULT '{}',            -- {technique: times a hint showed it}
    finished_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sudoku_games_daily_check CHECK ((source = 'daily') = (daily_on IS NOT NULL))
);
-- (Re-runnable: dev had the first 9 x 9-only version of this file.)
ALTER TABLE sudoku_games ADD COLUMN IF NOT EXISTS size INT NOT NULL DEFAULT 9;
ALTER TABLE sudoku_games DROP CONSTRAINT IF EXISTS sudoku_games_puzzle_check;
ALTER TABLE sudoku_games DROP CONSTRAINT IF EXISTS sudoku_games_solution_check;
ALTER TABLE sudoku_games DROP CONSTRAINT IF EXISTS sudoku_games_clues_check;
ALTER TABLE sudoku_games DROP CONSTRAINT IF EXISTS sudoku_games_size_check;
ALTER TABLE sudoku_games ADD CONSTRAINT sudoku_games_size_check CHECK (size IN (9, 16));
ALTER TABLE sudoku_games ADD CONSTRAINT sudoku_games_puzzle_check CHECK (length(puzzle) = size * size AND puzzle ~ '^[0-9A-G]+$');
ALTER TABLE sudoku_games ADD CONSTRAINT sudoku_games_solution_check CHECK (length(solution) = size * size AND solution ~ '^[1-9A-G]+$');
ALTER TABLE sudoku_games ADD CONSTRAINT sudoku_games_clues_check CHECK (clues BETWEEN 17 AND size * size);
ALTER TABLE sudoku_games ADD COLUMN IF NOT EXISTS week_of DATE;
ALTER TABLE sudoku_games ADD COLUMN IF NOT EXISTS set_key TEXT;
ALTER TABLE sudoku_games ADD COLUMN IF NOT EXISTS set_stop INT;
ALTER TABLE sudoku_games ADD COLUMN IF NOT EXISTS paper TEXT;
ALTER TABLE sudoku_games DROP CONSTRAINT IF EXISTS sudoku_games_source_check;
ALTER TABLE sudoku_games ADD CONSTRAINT sudoku_games_source_check CHECK (source IN ('new', 'daily', 'weekly', 'practice', 'typed', 'set'));
ALTER TABLE sudoku_games DROP CONSTRAINT IF EXISTS sudoku_games_weekly_check;
ALTER TABLE sudoku_games ADD CONSTRAINT sudoku_games_weekly_check CHECK ((source = 'weekly') = (week_of IS NOT NULL)
    AND (week_of IS NULL OR extract(isodow FROM week_of) = 1));
ALTER TABLE sudoku_games DROP CONSTRAINT IF EXISTS sudoku_games_set_check;
ALTER TABLE sudoku_games ADD CONSTRAINT sudoku_games_set_check CHECK ((source = 'set') = (set_key IS NOT NULL AND set_stop >= 1));
ALTER TABLE sudoku_games ADD COLUMN IF NOT EXISTS variant TEXT NOT NULL DEFAULT 'classic';   -- or 'x': the diagonals hold 1-9 too
ALTER TABLE sudoku_games DROP CONSTRAINT IF EXISTS sudoku_games_variant_check;
ALTER TABLE sudoku_games ADD CONSTRAINT sudoku_games_variant_check CHECK (variant IN ('classic', 'x') AND (variant = 'classic' OR size = 9));
CREATE UNIQUE INDEX IF NOT EXISTS sudoku_games_weekly_uq ON sudoku_games (week_of) WHERE week_of IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS sudoku_games_set_uq ON sudoku_games (set_key, set_stop) WHERE set_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS sudoku_games_daily_uq ON sudoku_games (daily_on) WHERE daily_on IS NOT NULL;
CREATE INDEX IF NOT EXISTS sudoku_games_status_idx ON sudoku_games (status, updated_at DESC);

DROP TRIGGER IF EXISTS sudoku_games_set_updated_at ON sudoku_games;
CREATE TRIGGER sudoku_games_set_updated_at
    BEFORE UPDATE ON sudoku_games
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- The library: puzzles in ranked lists, loaded by load-sudoku-library.ps1 from a file kept out of the public repo
-- (data\sudoku\hardest-published.tsv: the sudoku community's hardest, not ours to publish). 'hardest': ranks 1-100 are
-- the Hardest 100 (101-1000 kept for later); 'weekly': the weekly's puzzles if loaded. Empty = the app's own lists.
CREATE TABLE IF NOT EXISTS sudoku_library (
    list_key TEXT NOT NULL,
    rank     INT  NOT NULL CHECK (rank >= 1),
    puzzle   TEXT NOT NULL CHECK (puzzle ~ '^[0-9]{81}$'),
    measure  INT,                                   -- how hard (the list's own measure: nested-search branches)
    PRIMARY KEY (list_key, rank)
);

-- Calendar events for the Sudoku hobby too (keep in step with db.MODULE_IDS).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%sudoku%') THEN
        ALTER TABLE calendar_events DROP CONSTRAINT IF EXISTS calendar_events_hobby_check;
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_hobby_check
            CHECK (hobby IN ('models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'car', 'travel', 'shooting',
                             'hiking', 'gardening', 'vinyl', 'sudoku'));
    END IF;
END $$;

COMMIT;
