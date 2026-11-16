-- Reading, Vinyl and Volleyball extras (2026-11-16, from the market review). Safe to run twice.
--   Reading     private tags on books; your own reading challenges (a name, a target, a rule) and the books ticked by hand
--   Vinyl       who a record is loaned to, a cleaning log, and the stylus (when it was fitted, when to replace it)
--   Volleyball  serve / pass ratings (0-3), points with the rotation, clips tagged by skill and outcome, drill results
BEGIN;

-- ---- Reading ----
ALTER TABLE books ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';      -- yours alone: "slow start", "dark themes"

CREATE TABLE IF NOT EXISTS reading_challenges (
    challenge_id SERIAL PRIMARY KEY,
    name         TEXT NOT NULL CHECK (btrim(name) <> ''),
    target       INT NOT NULL CHECK (target BETWEEN 1 AND 1000),
    rule         TEXT NOT NULL CHECK (rule IN ('tag', 'genre', 'pages_over', 'manual')),
    rule_value   TEXT,                                   -- the tag, the genre or the page count; none for a manual one
    year         INT CHECK (year BETWEEN 2000 AND 2100), -- only books finished that year (NULL = any time)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reading_challenge_books (     -- the books you ticked off a manual challenge
    challenge_id INT NOT NULL REFERENCES reading_challenges (challenge_id) ON DELETE CASCADE,
    book_id      INT NOT NULL REFERENCES books (book_id) ON DELETE CASCADE,
    PRIMARY KEY (challenge_id, book_id)
);
CREATE INDEX IF NOT EXISTS reading_challenge_books_book_idx ON reading_challenge_books (book_id);

-- ---- Vinyl ----
ALTER TABLE vinyl_records ADD COLUMN IF NOT EXISTS loaned_to TEXT;
ALTER TABLE vinyl_records ADD COLUMN IF NOT EXISTS loaned_on DATE;

CREATE TABLE IF NOT EXISTS vinyl_care (
    care_id   SERIAL PRIMARY KEY,
    record_id INT NOT NULL REFERENCES vinyl_records (record_id) ON DELETE CASCADE,
    kind      TEXT NOT NULL DEFAULT 'clean' CHECK (kind IN ('clean')),
    done_on   DATE NOT NULL DEFAULT current_date,
    note      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS vinyl_care_record_idx ON vinyl_care (record_id, done_on DESC);

ALTER TABLE vinyl_settings ADD COLUMN IF NOT EXISTS stylus_limit_hours NUMERIC(6, 1) NOT NULL DEFAULT 800;   -- replace at
ALTER TABLE vinyl_settings ADD COLUMN IF NOT EXISTS stylus_since DATE;                                       -- fitted on (NULL = from the first play)

-- ---- Volleyball ----
CREATE TABLE IF NOT EXISTS volleyball_ratings (          -- one tap = one serve or pass, scored 0-3
    rating_id  SERIAL PRIMARY KEY,
    game_id    INT NOT NULL REFERENCES volleyball_games (game_id) ON DELETE CASCADE,
    skill      TEXT NOT NULL CHECK (skill IN ('serve', 'pass')),
    score      SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS volleyball_ratings_game_idx ON volleyball_ratings (game_id);

CREATE TABLE IF NOT EXISTS volleyball_points (           -- optional: a rally, with the rotation you were in
    point_id   SERIAL PRIMARY KEY,
    game_id    INT NOT NULL REFERENCES volleyball_games (game_id) ON DELETE CASCADE,
    rotation   SMALLINT NOT NULL CHECK (rotation BETWEEN 1 AND 6),
    serving    BOOLEAN NOT NULL,                         -- your team served this rally
    won        BOOLEAN NOT NULL,                         -- your team won it
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS volleyball_points_game_idx ON volleyball_points (game_id);

ALTER TABLE volleyball_clips ADD COLUMN IF NOT EXISTS skill TEXT;
ALTER TABLE volleyball_clips ADD COLUMN IF NOT EXISTS outcome TEXT;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'volleyball_clips_skill_check') THEN
        ALTER TABLE volleyball_clips ADD CONSTRAINT volleyball_clips_skill_check
            CHECK (skill IN ('serve', 'pass', 'set', 'attack', 'block', 'dig'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'volleyball_clips_outcome_check') THEN
        ALTER TABLE volleyball_clips ADD CONSTRAINT volleyball_clips_outcome_check CHECK (outcome IN ('good', 'error'));
    END IF;
END $$;

ALTER TABLE volleyball_coach ADD COLUMN IF NOT EXISTS result_label TEXT;                       -- "in a row", "out of 20"
ALTER TABLE volleyball_coach ADD COLUMN IF NOT EXISTS lower_is_better BOOLEAN NOT NULL DEFAULT false;   -- a time: lowest wins

CREATE TABLE IF NOT EXISTS volleyball_drill_logs (
    log_id   SERIAL PRIMARY KEY,
    note_id  INT NOT NULL REFERENCES volleyball_coach (note_id) ON DELETE CASCADE,
    game_id  INT REFERENCES volleyball_games (game_id) ON DELETE SET NULL,     -- the training it was part of
    done_on  DATE NOT NULL DEFAULT current_date,
    result   NUMERIC(10, 2),                             -- your score for the drill, if it has one
    reps     INT CHECK (reps > 0),                       -- how many you did (the weekly volume)
    minutes  INT CHECK (minutes > 0),
    note     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS volleyball_drill_logs_note_idx ON volleyball_drill_logs (note_id, done_on DESC);
CREATE INDEX IF NOT EXISTS volleyball_drill_logs_game_idx ON volleyball_drill_logs (game_id);

COMMIT;
